"""Live Cartesia TTS challenger gate. Not part of the default test run or CI.

Needs CARTESIA_API_KEY in the git-ignored .env and the tts-cartesia group:

    uv sync --group tts-cartesia
    uv run --no-sync --env-file .env pytest tests/integration -m cartesia_live

Model and voices: chosen from the live listing on 2026-10-26 (see BENCHMARK_METHOD.md).
Network: only api.cartesia.ai is expected; the test asserts it from audit hooks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from pathlib import Path

import pytest

from voiceos.benchmark.dataset import load_tts_gate_cases
from voiceos.benchmark.providers import CartesiaTTS, ProviderError
from voiceos.benchmark.stt_gate import HostAudit
from voiceos.benchmark.tts_gate import TtsGateStatus, run_tts_gate

pytestmark = pytest.mark.cartesia_live
MODEL = "sonic-3.5-2026-05-04"
VOICES = {
    "Alina": "38aabb6a-f52b-4fb0-a3d1-988518f4dc06",
    "Lukas": "e00dd3df-19e7-4cd4-827a-7ff6687b6954",
    "Nico": "afa425cf-5489-4a09-8a3f-d3cb1f82150d",
}
AUDIT = HostAudit()


def env(key: str, voice_id: str) -> dict[str, str]:
    return {
        "CARTESIA_API_KEY": key,
        CartesiaTTS.model_env: MODEL,
        CartesiaTTS.voice_env: voice_id,
        CartesiaTTS.language_env: "de",
    }


@pytest.fixture(scope="module")
def key() -> str:
    value = os.environ.get("CARTESIA_API_KEY", "")
    if not value:
        pytest.fail("CARTESIA_API_KEY not set (run with --env-file .env)")
    if CartesiaTTS(env(value, "x")).info.version is None:
        pytest.fail("cartesia SDK not installed (uv sync --group tts-cartesia)")
    return value


@pytest.mark.parametrize("name", sorted(VOICES))
def test_live_challenger_all_cases(
    key: str, name: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    tts = CartesiaTTS(env(key, VOICES[name]), allow_live=True)
    result = asyncio.run(
        run_tts_gate(
            load_tts_gate_cases(), tts, tmp_path, voice_name=name, challenger=True,
            run_id="test", timestamp="t", git_commit=None, git_dirty=None, audit=AUDIT,
        )
    )  # fmt: skip
    assert result.status is TtsGateStatus.CHALLENGER_VERIFIED, [
        c.provider_error for c in result.cases
    ]
    assert len(result.cases) == 10 and all(c.audio.valid for c in result.cases)
    assert result.network_hosts == ["api.cartesia.ai"]
    assert key not in result.model_dump_json() and key not in caplog.text
    for wav in tmp_path.glob("*.wav"):
        assert key.encode() not in wav.read_bytes()


def test_invalid_key_fails_cleanly_without_leaking_it(
    key: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    canary = "sk_car_invalid_canary_" + "0" * 24
    tts = CartesiaTTS(env(canary, VOICES["Alina"]), allow_live=True)
    result = asyncio.run(tts.synthesize("Hallo."))
    assert not result.ok and result.error is not None and ":401" in result.error
    assert result.pcm == b"" and canary not in repr(result) and canary not in caplog.text
    with pytest.raises(ProviderError) as exc:
        list(tts.stream("Hallo."))
    assert canary not in "".join(traceback.format_exception(exc.value))
