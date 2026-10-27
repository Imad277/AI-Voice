"""Live Deepgram STT baseline gate. Not part of the default test run or CI.

Needs DEEPGRAM_API_KEY in the git-ignored .env, the stt-deepgram group and macOS speech:

    uv sync --group stt-deepgram
    uv run --no-sync --env-file .env pytest tests/integration -m deepgram_live

Network: only api.deepgram.com is expected; the test asserts it from audit hooks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from pathlib import Path

import pytest

from voiceos.benchmark.dataset import load_stt_gate_cases
from voiceos.benchmark.ports import AudioSegment
from voiceos.benchmark.providers import DeepgramSTT, ProviderError
from voiceos.benchmark.stt_gate import HostAudit, SttGateStatus, run_stt_gate
from voiceos.benchmark.synthetic_audio import ensure_available

pytestmark = pytest.mark.deepgram_live
GATE = {"VOICEOS_BENCH_STT_MODEL": "nova-3", "VOICEOS_BENCH_STT_LANGUAGE": "de"}
AUDIT = HostAudit()


@pytest.fixture(scope="module")
def key() -> str:
    value = os.environ.get("DEEPGRAM_API_KEY", "")
    if not value:
        pytest.fail("DEEPGRAM_API_KEY not set (run with --env-file .env)")
    if DeepgramSTT({**GATE, "DEEPGRAM_API_KEY": value}).info.version is None:
        pytest.fail("deepgram-sdk not installed (uv sync --group stt-deepgram)")
    ensure_available()
    return value


def test_live_streaming_baseline_for_all_cases(
    key: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)  # includes websockets handshake debug logging
    stt = DeepgramSTT({**GATE, "DEEPGRAM_API_KEY": key}, allow_live=True)
    result, events = asyncio.run(
        run_stt_gate(
            load_stt_gate_cases(), stt, tmp_path / "audio",
            run_id="test", timestamp="t", git_commit=None, git_dirty=None, audit=AUDIT,
        )
    )  # fmt: skip
    assert result.status is SttGateStatus.VERIFIED
    assert len(result.cases) == 10
    for case in result.cases:
        assert case.connected and case.final_present and case.error is None, case.case_id
        assert case.first_transcript_ms is not None and case.close_ms is not None
    assert (result.model, result.language, result.sdk_version) == ("nova-3", "de", "7.12.0")
    assert result.network_hosts == ["api.deepgram.com"]
    serialized = result.model_dump_json() + repr(events)
    assert key not in serialized
    assert key not in caplog.text


def test_invalid_key_fails_cleanly_without_leaking_it(
    key: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    canary = "invalid-canary-" + "0" * 24
    stt = DeepgramSTT({**GATE, "DEEPGRAM_API_KEY": canary}, allow_live=True)
    pcm = b"\0\0" * 3200
    result = asyncio.run(stt.stream(AudioSegment("invalid", pcm, 16_000), realtime=False))
    assert result.connected is False
    assert result.error is not None and result.final_transcript == ""
    assert canary not in repr(result) and canary not in caplog.text
    with pytest.raises(ProviderError) as exc:
        stt.transcribe(AudioSegment("invalid", pcm, 16_000))
    assert canary not in "".join(traceback.format_exception(exc.value))
