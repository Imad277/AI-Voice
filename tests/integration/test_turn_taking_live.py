"""Live turn-taking gate smoke (both runtimes). Not part of the default test run or CI.

Needs the local LiveKit dev server, the provider keys in the git-ignored .env and the
voice-sdk, stt-deepgram, llm-openai and tts-cartesia groups:

    uv run --no-sync --env-file .env pytest tests/integration -m turn_taking_live

Runs one single-turn case and one barge-in case once per runtime and checks the safety
and lifecycle invariants; the measured series runs through the CLI (--turn-taking-gate).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from voiceos.benchmark.livekit_local import LocalServer
from voiceos.benchmark.providers import CartesiaTTS, ConfiguredTextLLM, DeepgramSTT
from voiceos.benchmark.stt_gate import HostAudit
from voiceos.benchmark.turn_gate import run_turn_gate
from voiceos.benchmark.turn_taking import load_turn_taking_cases

pytestmark = pytest.mark.turn_taking_live
PROVIDER_HOSTS = {"api.deepgram.com", "api.openai.com", "api.cartesia.ai"}


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
        CartesiaTTS.voice_env: "afa425cf-5489-4a09-8a3f-d3cb1f82150d",
        CartesiaTTS.language_env: "de",
    }


def test_both_runtimes_take_turns_and_stop_on_barge_in(env: dict[str, str], tmp_path: Path) -> None:
    cases = [c for c in load_turn_taking_cases() if c.case_id in ("TT01", "TT12")]
    result = asyncio.run(
        run_turn_gate(
            LocalServer.from_env(env), env, cases, tmp_path, runtimes=["livekit", "pipecat"],
            repetitions_critical=1, repetitions_other=1, run_id="test", timestamp="t",
            git_commit=None, git_dirty=None, audit=HostAudit(),
        )
    )  # fmt: skip
    assert len(result.runs) == 4
    for run in result.runs:
        assert run.valid and not run.hard_failures and run.tools_only_after_final, run
    for run in (r for r in result.runs if r.case_id == "TT12"):
        assert run.metrics.barge_valid and run.metrics.barge_success, run.metrics
    assert result.secret_scan_clean and set(result.network_hosts) <= PROVIDER_HOSTS
