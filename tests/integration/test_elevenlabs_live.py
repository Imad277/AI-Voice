"""Live ElevenLabs TTS baseline gate. Not part of the default test run or CI.

Needs ELEVENLABS_API_KEY in the git-ignored .env and the tts-elevenlabs group:

    uv sync --group tts-elevenlabs
    uv run --no-sync --env-file .env pytest tests/integration -m elevenlabs_live

Model and voice: chosen from the live listing on 2026-10-23 (see BENCHMARK_METHOD.md).
Network: only api.elevenlabs.io is expected; the test asserts it from audit hooks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from pathlib import Path

import pytest

from voiceos.benchmark.dataset import load_tts_gate_cases
from voiceos.benchmark.providers import ElevenLabsTTS, ProviderError
from voiceos.benchmark.stt_gate import HostAudit
from voiceos.benchmark.tts_gate import TtsGateStatus, run_tts_gate

pytestmark = pytest.mark.elevenlabs_live
GATE = {
    "VOICEOS_BENCH_TTS_MODEL": "eleven_flash_v2_5",
    "VOICEOS_BENCH_TTS_VOICE_ID": "CwhRBWXzGAHq8TQ4Fs17",
    "VOICEOS_BENCH_TTS_LANGUAGE": "de",
}
AUDIT = HostAudit()


@pytest.fixture(scope="module")
def key() -> str:
    value = os.environ.get("ELEVENLABS_API_KEY", "")
    if not value:
        pytest.fail("ELEVENLABS_API_KEY not set (run with --env-file .env)")
    if ElevenLabsTTS({**GATE, "ELEVENLABS_API_KEY": value}).info.version is None:
        pytest.fail("elevenlabs SDK not installed (uv sync --group tts-elevenlabs)")
    return value


def test_live_tts_baseline_for_all_cases(
    key: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    tts = ElevenLabsTTS({**GATE, "ELEVENLABS_API_KEY": key}, allow_live=True)
    result = asyncio.run(
        run_tts_gate(
            load_tts_gate_cases(), tts, tmp_path, voice_name="Roger",
            run_id="test", timestamp="t", git_commit=None, git_dirty=None, audit=AUDIT,
        )
    )  # fmt: skip
    assert result.status is TtsGateStatus.VERIFIED, [c.provider_error for c in result.cases]
    assert len(result.cases) == 10 and all(c.audio.valid for c in result.cases)
    assert result.network_hosts == ["api.elevenlabs.io"]
    assert key not in result.model_dump_json() and key not in caplog.text
    for wav in tmp_path.glob("*.wav"):
        assert key.encode() not in wav.read_bytes()


def test_invalid_key_fails_cleanly_without_leaking_it(
    key: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    canary = "sk_invalid_canary_" + "0" * 32
    tts = ElevenLabsTTS({**GATE, "ELEVENLABS_API_KEY": canary}, allow_live=True)
    result = asyncio.run(tts.synthesize("Hallo."))
    assert not result.ok and result.error is not None and ":401" in result.error
    assert result.pcm == b"" and canary not in repr(result) and canary not in caplog.text
    with pytest.raises(ProviderError) as exc:
        list(tts.stream("Hallo."))
    assert canary not in "".join(traceback.format_exception(exc.value))
