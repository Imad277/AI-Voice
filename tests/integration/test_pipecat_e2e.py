"""Live Pipecat end-to-end voice pipeline gate. Not part of the default test run or CI.

Same harness, dialog, injection test, providers, gateway and measurements as the LiveKit
gate (``test_livekit_e2e.py``); only the runtime differs (Pipecat ``LiveKitTransport``).
Needs the local LiveKit dev server, the provider keys in the git-ignored .env and the
voice-sdk, stt-deepgram, llm-openai and tts-cartesia groups:

    docker compose -f docker-compose.livekit.yml up -d
    uv sync --group voice-sdk --group stt-deepgram --group llm-openai --group tts-cartesia
    uv run --no-sync --env-file .env pytest tests/integration -m pipecat_e2e

Network: loopback (LiveKit) plus api.deepgram.com, api.openai.com and api.cartesia.ai only;
the test asserts the resolved hosts from audit hooks.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import pytest

from voiceos.benchmark.e2e_gate import E2EStatus, run_e2e_gate
from voiceos.benchmark.livekit_local import LocalServer
from voiceos.benchmark.providers import CartesiaTTS, ConfiguredTextLLM, DeepgramSTT
from voiceos.benchmark.runtimes import PipecatRuntimeAdapter
from voiceos.benchmark.stt_gate import HostAudit

pytestmark = pytest.mark.pipecat_e2e
PROVIDER_HOSTS = {"api.deepgram.com", "api.openai.com", "api.cartesia.ai"}
NICO = "afa425cf-5489-4a09-8a3f-d3cb1f82150d"  # PHASE1_REFERENCE_VOICE (not a provider decision)


@pytest.fixture(scope="module")
def env() -> dict[str, str]:
    for key in ("DEEPGRAM_API_KEY", "OPENAI_API_KEY", "CARTESIA_API_KEY", "LIVEKIT_URL"):
        if not os.environ.get(key):
            pytest.fail(f"{key} not set (run with --env-file .env)")
    return {
        **os.environ,
        DeepgramSTT.model_env: "nova-3",
        DeepgramSTT.language_env: "de",
        "VOICEOS_BENCH_LLM_PROVIDER": "openai",
        ConfiguredTextLLM.model_env: "gpt-6-luna",
        ConfiguredTextLLM.reasoning_env: "low",
        CartesiaTTS.model_env: "sonic-3.5-2026-05-04",
        CartesiaTTS.voice_env: NICO,
        CartesiaTTS.language_env: "de",
    }


def test_live_end_to_end_pipeline(
    env: dict[str, str], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    result = asyncio.run(
        run_e2e_gate(
            LocalServer.from_env(env), env, tmp_path, run_id="test", timestamp="t",
            git_commit=None, git_dirty=None, audit=HostAudit(),
            runtime=PipecatRuntimeAdapter(env),
        )
    )  # fmt: skip
    happy, injection = result.sessions
    assert result.runtime == "pipecat"
    assert result.status is E2EStatus.PIPECAT_VERIFIED, [
        (s.name, s.checks) for s in result.sessions
    ]
    assert happy.bench_bookings == ["slot_a_1000"] and happy.calendar_creates == 1
    assert injection.calendar_creates == 0 and injection.canary_bookings == 0
    assert all(s.room_empty_after_session and s.room_deleted for s in result.sessions)
    assert set(result.network_hosts) <= PROVIDER_HOSTS
    for key in ("DEEPGRAM_API_KEY", "OPENAI_API_KEY", "CARTESIA_API_KEY"):
        assert env[key] not in result.model_dump_json() and env[key] not in caplog.text
