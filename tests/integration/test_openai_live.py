"""Live OpenAI LLM baseline gate. Not part of the default test run or CI.

Needs OPENAI_API_KEY in the git-ignored .env, a funded account and the llm-openai group:

    uv sync --group llm-openai
    uv run --no-sync --env-file .env pytest tests/integration -m openai_live

Network: only api.openai.com is expected; the test asserts it from audit hooks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback

import pytest

from voiceos.benchmark.dataset import load_llm_gate_cases
from voiceos.benchmark.llm_gate import INSTRUCTIONS, LlmGateStatus, run_llm_gate
from voiceos.benchmark.ports import Message
from voiceos.benchmark.providers import ConfiguredTextLLM, ProviderError
from voiceos.benchmark.stt_gate import HostAudit

pytestmark = pytest.mark.openai_live
GATE = {
    "VOICEOS_BENCH_LLM_PROVIDER": "openai",
    "VOICEOS_BENCH_LLM_MODEL": "gpt-6-luna",
    "VOICEOS_BENCH_LLM_REASONING_EFFORT": "low",
}
AUDIT = HostAudit()


@pytest.fixture(scope="module")
def key() -> str:
    value = os.environ.get("OPENAI_API_KEY", "")
    if not value:
        pytest.fail("OPENAI_API_KEY not set (run with --env-file .env)")
    if ConfiguredTextLLM({**GATE, "OPENAI_API_KEY": value}).info.version is None:
        pytest.fail("openai SDK not installed (uv sync --group llm-openai)")
    return value


def test_live_gate_all_cases(key: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    llm = ConfiguredTextLLM(
        {**GATE, "OPENAI_API_KEY": key}, allow_live=True, instructions=INSTRUCTIONS
    )
    result = asyncio.run(
        run_llm_gate(
            load_llm_gate_cases(), llm,
            run_id="test", timestamp="t", git_commit=None, git_dirty=None, audit=AUDIT,
        )
    )  # fmt: skip
    assert key not in result.model_dump_json() and key not in caplog.text
    assert result.network_hosts == ["api.openai.com"]
    if result.status is LlmGateStatus.NOT_TESTED:
        errors = sorted({c.provider_error for c in result.cases})
        pytest.fail(f"gate blocked by provider account: {errors}")
    assert len(result.cases) >= 15
    assert all(not c.hard_failures for c in result.cases)
    assert result.status is LlmGateStatus.VERIFIED


def test_invalid_key_fails_cleanly_without_leaking_it(
    key: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    canary = "sk-invalid-canary-" + "0" * 32
    llm = ConfiguredTextLLM({**GATE, "OPENAI_API_KEY": canary}, allow_live=True)
    result = asyncio.run(llm.respond([Message("user", "Hallo")]))
    assert not result.ok and result.error is not None and ":401" in result.error
    assert canary not in repr(result) and canary not in caplog.text
    with pytest.raises(ProviderError) as exc:
        list(llm.stream([Message("user", "Hallo")]))
    assert canary not in "".join(traceback.format_exception(exc.value))
