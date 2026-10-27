"""Runtime and provider adapter contract tests."""

import dataclasses
import inspect

import pytest

from voiceos.benchmark.binding import GatewayBinding
from voiceos.benchmark.ports import (
    AdapterKind,
    AdapterUnavailable,
    AudioSegment,
    LLMAdapter,
    RuntimeAdapter,
    ServerBinding,
    STTAdapter,
    TTSAdapter,
)
from voiceos.benchmark.providers import (
    CartesiaTTS,
    ConfiguredTextLLM,
    DeepgramSTT,
    ElevenLabsTTS,
    ScriptedLLM,
    ScriptedReply,
    ScriptedSTT,
    ScriptedTTS,
)
from voiceos.benchmark.runtimes import (
    LiveKitRuntimeAdapter,
    PipecatRuntimeAdapter,
    ReferenceRuntime,
)

RUNTIMES = [ReferenceRuntime(), LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({})]
LIVE_PROVIDERS = [DeepgramSTT({}), ConfiguredTextLLM({}), ElevenLabsTTS({}), CartesiaTTS({})]


@pytest.mark.parametrize("runtime", RUNTIMES, ids=lambda r: r.info.provider)
def test_runtimes_share_one_contract(runtime: object) -> None:
    assert isinstance(runtime, RuntimeAdapter)
    info = runtime.info
    assert info.kind is AdapterKind.RUNTIME
    params = list(inspect.signature(runtime.run_session).parameters)
    assert params == ["spec", "stt", "llm", "tts", "binding", "clock"]


def test_runtime_contract_never_receives_a_call_context() -> None:
    hints = inspect.get_annotations(RuntimeAdapter.run_session)
    assert not any("CallContext" in str(h) for h in hints.values())
    assert "context" not in inspect.signature(RuntimeAdapter.run_session).parameters


@pytest.mark.parametrize(
    "runtime", [LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({})], ids=["livekit", "pipecat"]
)
def test_candidate_runtimes_report_not_testable_and_refuse_to_run(runtime: object) -> None:
    assert isinstance(runtime, RuntimeAdapter)
    probe = runtime.probe()
    assert probe.available is False
    assert any("LIVEKIT_URL" in m for m in probe.missing)
    assert any("session wiring not implemented" in m for m in probe.missing)
    with pytest.raises(AdapterUnavailable):
        runtime.run_session(None, None, None, None, None, None)  # type: ignore[arg-type]


def test_candidate_runtimes_use_identical_prerequisites() -> None:
    def normalized(adapter: LiveKitRuntimeAdapter | PipecatRuntimeAdapter) -> list[str]:
        return [m for m in adapter.probe().missing if not m.startswith("SDK ")]

    assert normalized(LiveKitRuntimeAdapter({})) == normalized(PipecatRuntimeAdapter({}))


@pytest.mark.parametrize("adapter", LIVE_PROVIDERS, ids=lambda a: a.info.provider)
def test_live_providers_never_invent_a_model_id_and_do_not_run(adapter: object) -> None:
    assert isinstance(adapter, STTAdapter | LLMAdapter | TTSAdapter)
    assert adapter.info.model is None
    assert adapter.info.oracle is False
    probe = adapter.probe()
    assert probe.available is False
    assert any("credential" in m for m in probe.missing)
    assert any("model id" in m for m in probe.missing)


def test_live_provider_reports_configured_model_but_still_refuses_without_authorization() -> None:
    env = {"DEEPGRAM_API_KEY": "canary-not-a-key", "VOICEOS_BENCH_STT_MODEL": "configured-id"}
    adapter = DeepgramSTT(env)
    assert adapter.info.model == "configured-id"
    probe = adapter.probe()
    assert probe.available is False
    assert not any("credential" in m for m in probe.missing)
    assert "canary-not-a-key" not in repr(probe)
    with pytest.raises(AdapterUnavailable):
        adapter.transcribe(AudioSegment("x", b"", 16_000))


def test_scripted_providers_are_flagged_as_oracles() -> None:
    adapters = [ScriptedSTT({}), ScriptedLLM([ScriptedReply("hi")]), ScriptedTTS()]
    for adapter in adapters:
        assert adapter.info.oracle is True
        assert adapter.probe().available is True
    assert isinstance(adapters[0], STTAdapter)
    assert isinstance(adapters[1], LLMAdapter)
    assert isinstance(adapters[2], TTSAdapter)


def test_scripted_llm_streams_text_then_tool() -> None:
    from voiceos.core.tools import ToolRequest

    proposal = ToolRequest("p", "booking.get_status", {})
    deltas = list(ScriptedLLM([ScriptedReply("Einen Moment", proposal)]).stream([]))
    assert "".join(d.text for d in deltas).strip() == "Einen Moment"
    assert deltas[-1].tool is proposal
    assert all(d.tool is None for d in deltas[:-1])


def test_server_binding_hides_the_trusted_context() -> None:
    assert isinstance(GatewayBinding.__new__(GatewayBinding), ServerBinding)
    public = [name for name in dir(GatewayBinding) if not name.startswith("_")]
    assert public == ["execute", "render", "user_reply"]
    assert not dataclasses.is_dataclass(GatewayBinding)
