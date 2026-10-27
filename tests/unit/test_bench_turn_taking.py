"""Turn-taking gate: offline tests (fakes only, no network, no key, no runtime SDK)."""

from __future__ import annotations

import array
import ast
import asyncio
import math
import sys
import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, ClassVar

import pytest
from e2e_fakes import FakeLLM, FakeTTS, reply, server_state

from voiceos.benchmark import turn_taking
from voiceos.benchmark.binding import GatewayBinding
from voiceos.benchmark.ports import Probe
from voiceos.benchmark.providers import DeepgramSTT, SttLiveEvent, TtsSynthesisResult
from voiceos.benchmark.turn_taking import (
    ProviderFailure,
    RunValidity,
    Segment,
    TurnRunMetrics,
    TurnRunResult,
    TurnTakingAgent,
    TurnTakingStatus,
    classify_run,
    evaluate_run,
    gate_evidence,
    gate_status,
    load_turn_taking_cases,
    render_segments,
    summarize_runs,
    tools_only_after_final_transcript,
    voiced_intervals,
)
from voiceos.benchmark.voice_loop import TimedEvent, VoiceAgentLoop

ROOT = Path(__file__).resolve().parents[2]


# -- dataset and audio -----------------------------------------------------------------------


def test_cases_cover_the_required_turn_taking_set() -> None:
    cases = load_turn_taking_cases()
    assert len(cases) >= 12
    categories = {c.category for c in cases}
    for required in (
        "NORMAL_SHORT", "NORMAL_LONG", "THINK_PAUSE_SHORT", "THINK_PAUSE_LONG",
        "FALSE_ENDPOINT_200", "FALSE_ENDPOINT_400", "FALSE_ENDPOINT_700",
        "LATE_ENDPOINT_SHORT", "LATE_ENDPOINT_PHONE", "LATE_ENDPOINT_DATETIME",
        "BARGE_IN_200", "BARGE_IN_500", "BARGE_IN_1000", "SELF_CORRECTION",
    ):  # fmt: skip
        assert required in categories
    offsets = sorted(c.barge_in.offset_ms for c in cases if c.barge_in)
    assert offsets == [200, 500, 1000]
    critical = {c.category for c in cases if c.critical}
    assert critical == {
        "FALSE_ENDPOINT_400", "FALSE_ENDPOINT_700", "LATE_ENDPOINT_PHONE",
        "BARGE_IN_200", "BARGE_IN_500", "BARGE_IN_1000",
    }  # fmt: skip
    pauses = {c.category: [s.pause_ms for s in c.segments if s.pause_ms] for c in cases}
    assert pauses["FALSE_ENDPOINT_200"] == [200] and pauses["FALSE_ENDPOINT_700"] == [700]


def tone(seconds: float, rate: int = 16_000) -> bytes:
    n = int(seconds * rate)
    samples = (int(4000 * math.sin(2 * math.pi * 220 * i / rate)) for i in range(n))
    return array.array("h", samples).tobytes()


def test_rendered_audio_has_exact_pauses_and_trimmed_speech(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    silence = b"\x00\x00" * 1600  # 100 ms around each fake utterance
    spoken = {"eins": tone(0.5), "zwei": tone(0.3)}

    def fake_render(text: str, out_wav: Path) -> str:
        out_wav.write_bytes(silence + spoken[text] + silence)
        return "sha"

    monkeypatch.setattr(turn_taking.synthetic_audio, "render", fake_render)
    monkeypatch.setattr(turn_taking.synthetic_audio, "read_pcm", lambda p: p.read_bytes())
    audio = render_segments(
        [Segment(text="eins"), Segment(pause_ms=400), Segment(text="zwei")], tmp_path / "a.wav"
    )
    assert audio.voiced_end_s == pytest.approx(0.5 + 0.4 + 0.3, abs=0.011)
    samples = array.array("h", audio.pcm)
    gap = samples[int(0.5 * 16000) + 160 : int(0.9 * 16000) - 160]
    assert max(abs(s) for s in gap) == 0  # the pause is exact digital silence
    assert audio.sha256 and (tmp_path / "a.wav").read_bytes()[:4] == b"RIFF"


# -- shared agent: commit only from final STT results -----------------------------------------


def make_agent(replies: list[Any] | None = None) -> tuple[TurnTakingAgent, list[TimedEvent], Any]:
    gateway, context, calendar, _ = server_state()
    events: list[TimedEvent] = []
    loop = VoiceAgentLoop(
        object(), FakeLLM(replies or [reply("Gerne.")]), FakeTTS(),  # type: ignore[arg-type]
        GatewayBinding(gateway, context),
        input_sample_rate_hz=16_000, endpointing_ms=500, emit=events.append,
    )  # fmt: skip
    agent = TurnTakingAgent(loop, object(), FakeTTS(), emit=events.append)  # type: ignore[arg-type]
    return agent, events, calendar


def ev(kind: str, text: str = "", from_finalize: bool = False) -> SttLiveEvent:
    return SttLiveEvent(kind, text, 0.0, from_finalize)


def test_interim_text_never_becomes_a_turn() -> None:
    agent, events, calendar = make_agent()
    agent.on_stt(ev("interim", "Buchen Sie bitte"))
    agent.on_stt(ev("interim", "Buchen Sie bitte sofort"))
    assert asyncio.run(agent.commit()) is None  # no final result -> nothing to answer
    assert [e.name for e in events][-1] == "EMPTY_TURN"
    assert not [e for e in events if e.name.startswith("LLM")] and calendar.create_calls == 0


def test_commit_waits_for_the_finalize_result_after_vad_end() -> None:
    agent, events, _ = make_agent()

    async def scenario() -> Any:
        agent.on_stt(ev("final", "Meine Nummer ist"))
        agent.on_vad("end")
        task = asyncio.ensure_future(agent.commit())
        await asyncio.sleep(0.05)
        assert not task.done()  # waits for Deepgram's Finalize result
        agent.on_stt(ev("final", "null drei null.", from_finalize=True))
        return await task

    assert asyncio.run(scenario()) == (0, "Meine Nummer ist null drei null.")
    ready = next(e for e in events if e.name == "TRANSCRIPT_READY")
    assert ready.attrs["waited_ms"] >= 40


def test_cancelled_reply_is_rolled_back_and_carried_into_the_next_turn() -> None:
    gate = asyncio.Event()

    class SlowLLM(FakeLLM):
        async def respond(self, messages: Any, *, timeout_s: float = 60.0) -> Any:
            await gate.wait()
            return await super().respond(messages)

    agent, events, _ = make_agent()
    agent.loop._llm = SlowLLM([reply("Gerne.")])  # type: ignore[attr-defined]

    async def scenario() -> Any:
        agent.on_stt(ev("final", "Ich hätte gerne einen Termin"))
        first = await agent.commit()
        assert first is not None
        task = asyncio.ensure_future(agent.reply(*first))
        await asyncio.sleep(0.01)
        task.cancel()  # runtime interrupted the premature reply
        with pytest.raises(asyncio.CancelledError):
            await task
        assert agent.loop.history == []  # rolled back, nothing half-done remains
        agent.on_stt(ev("final", "am Freitag um zehn Uhr."))
        return await agent.commit()

    assert asyncio.run(scenario()) == (1, "Ich hätte gerne einen Termin am Freitag um zehn Uhr.")
    assert any(e.name == "REPLY_CANCELLED" and not e.attrs["tools_ran"] for e in events)


def test_gateway_execution_requires_a_final_transcript_event() -> None:
    def e(t: float, name: str, turn: int, **attrs: Any) -> TimedEvent:
        return TimedEvent(t, "agent", name, turn, attrs)

    ok = [e(1, "TRANSCRIPT_READY", 0, chars=12), e(2, "TOOL_EXEC_START", 0)]
    assert tools_only_after_final_transcript(ok)
    assert not tools_only_after_final_transcript([e(2, "TOOL_EXEC_START", 0)])
    assert not tools_only_after_final_transcript(
        [e(1, "TRANSCRIPT_READY", 0, chars=0), e(2, "TOOL_EXEC_START", 0)]
    )


# -- evaluation -------------------------------------------------------------------------------


def frames(*voiced: tuple[float, float], until: float = 20.0) -> list[tuple[float, int]]:
    out = []
    t = 0.02
    while t <= until:
        out.append((round(t, 2), 3000 if any(s < t <= e for s, e in voiced) else 0))
        t += 0.02
    return out


def at(t: float, name: str, **attrs: Any) -> TimedEvent:
    return TimedEvent(t, "agent", name, 0, attrs)


def test_single_turn_metrics_and_endpoint_classification() -> None:
    # user speaks 1.0 -> 3.0 s; VAD end 3.4; finalize 3.4 -> result 3.6; commit 3.7
    events = [
        at(3.4, "VAD_END"), at(3.4, "FINALIZE_SENT"), at(3.6, "STT_FINAL", from_finalize=True),
        at(3.7, "TURN_COMMITTED"), at(3.7, "TRANSCRIPT_READY", waited_ms=0.0, chars=10),
        at(3.7, "LLM_REQUEST_START"), at(5.0, "FIRST_ASSISTANT_AUDIO_PUBLISHED"),
    ]  # fmt: skip
    m = evaluate_run(
        events, frames((5.1, 7.0)), user_start=1.0, user_voiced_end_s=2.0,
        barge_start=None, barge_voiced_end_s=None, barge_transcript_in_history=None,
    )  # fmt: skip
    assert m.user_end_to_vad_end_ms == 400.0 and m.endpoint_latency_ms == 700.0
    assert m.deepgram_finalize_delay_ms == 200.0 and m.stt_final_latency_ms == 600.0
    assert m.user_end_to_first_heard_ms == pytest.approx(2100.0)
    assert not m.false_endpoint and not m.late_endpoint and m.barge_valid is None
    early = [at(2.0, "TURN_COMMITTED"), *events]  # committed inside the utterance
    m2 = evaluate_run(
        early, frames(), user_start=1.0, user_voiced_end_s=2.0, barge_start=None,
        barge_voiced_end_s=None, barge_transcript_in_history=None,
    )  # fmt: skip
    assert m2.false_endpoint and m2.commits_during_utterance == 1
    late = [at(5.0, "TURN_COMMITTED")]
    m3 = evaluate_run(
        late, frames(), user_start=1.0, user_voiced_end_s=2.0, barge_start=None,
        barge_voiced_end_s=None, barge_transcript_in_history=None,
    )  # fmt: skip
    assert m3.late_endpoint is True


def test_barge_in_metrics_success_missed_and_context_loss() -> None:
    # assistant audible 5.0 -> 6.4; caller barges in at 5.5; answer to the barge-in at 9.0
    events = [
        at(5.9, "AUDIO_STOP_REQUESTED", kind="pause"), at(6.2, "INTERRUPTION_DETECTED"),
        at(8.5, "TRANSCRIPT_READY", waited_ms=0.0, chars=30),
    ]  # fmt: skip
    m = evaluate_run(
        events, frames((5.0, 6.4), (9.0, 10.0)), user_start=1.0, user_voiced_end_s=2.0,
        barge_start=5.5, barge_voiced_end_s=2.0, barge_transcript_in_history=True,
    )  # fmt: skip
    assert m.barge_valid and m.interruption_detection_ms == pytest.approx(400.0)
    assert m.tts_stop_request_ms == pytest.approx(400.0)
    assert m.tts_stop_latency_ms == pytest.approx(900.0, abs=21)
    assert m.barge_end_to_accepted_ms == pytest.approx(1000.0)
    assert m.missed_interruption is False and m.context_loss is False and m.barge_success
    missed = evaluate_run(
        [], frames((5.0, 9.5)), user_start=1.0, user_voiced_end_s=2.0,
        barge_start=5.5, barge_voiced_end_s=2.0, barge_transcript_in_history=False,
    )  # fmt: skip
    assert missed.missed_interruption and missed.context_loss and not missed.barge_success
    not_audible = evaluate_run(
        [], frames((3.0, 4.0)), user_start=1.0, user_voiced_end_s=2.0,
        barge_start=6.0, barge_voiced_end_s=2.0, barge_transcript_in_history=True,
    )  # fmt: skip
    assert not_audible.barge_valid is False and not_audible.barge_success is None


def test_voiced_intervals_merge_short_pauses() -> None:
    assert voiced_intervals(frames((1.0, 2.0), (2.3, 3.0))) == [pytest.approx((1.0, 3.0), abs=0.03)]
    assert len(voiced_intervals(frames((1.0, 2.0), (3.0, 4.0)))) == 2


def run_result(**overrides: Any) -> TurnRunResult:
    metrics = TurnRunMetrics(**dict.fromkeys(TurnRunMetrics.model_fields) | {
        "commits_during_utterance": 0, "false_endpoint": False,
    } | overrides.pop("metrics", {}))  # fmt: skip
    values: dict[str, Any] = {
        "runtime": "x", "case_id": "TT11", "category": "BARGE_IN_200", "repetition": 0,
        "room": "r", "completed": True, "runtime_error": None, "harness_error": None,
        "provider_errors": [], "provider_failures": [], "transcripts": {}, "spoken": [],
        "tools": [], "hard_failures": [], "tools_only_after_final": True,
        "room_cleaned_up": True, "metrics": metrics, "entity_ok": None,
        "validity": RunValidity.VALID,
    }  # fmt: skip
    return TurnRunResult(**(values | overrides))


OK_BARGE = {"barge_valid": True, "missed_interruption": False, "context_loss": False}
QUOTA = ProviderFailure(
    component="tts", provider="cartesia", error_class="APIStatusError", http_status=402,
    provider_code="quota_exceeded",
)  # fmt: skip


def complete_series(runtime: str = "x", barge: dict[str, Any] | None = None) -> list[Any]:
    """Every evidence group exactly at its pre-registered minimum, all usable."""
    groups = [
        ("TT01", "NORMAL_SHORT", 3, {}), ("TT07", "FALSE_ENDPOINT_700", 9, {}),
        ("TT09", "LATE_ENDPOINT_PHONE", 3, {}),
        ("TT11", "BARGE_IN_200", 9, OK_BARGE if barge is None else barge),
    ]  # fmt: skip
    return [
        run_result(runtime=runtime, case_id=case_id, category=category, repetition=i,
                   metrics=dict(metrics))
        for case_id, category, n, metrics in groups
        for i in range(n)
    ]  # fmt: skip


def provider_failed(**overrides: Any) -> TurnRunResult:
    return run_result(
        provider_errors=[str(QUOTA)], provider_failures=[QUOTA],
        validity=RunValidity.INVALID_PROVIDER_FAILURE, **overrides,
    )  # fmt: skip


def test_gate_status_rule() -> None:
    ok = OK_BARGE
    assert gate_status(complete_series()) is TurnTakingStatus.VERIFIED
    # barge-in evidence alone is not enough any more: the other groups are missing
    assert gate_status([run_result(metrics=ok)] * 10) is TurnTakingStatus.INCONCLUSIVE
    assert gate_status([]) is TurnTakingStatus.INCONCLUSIVE
    invalid = run_result(validity=RunValidity.INVALID_RUNTIME_FAILURE)
    assert gate_status([invalid] * 2) is TurnTakingStatus.INCONCLUSIVE
    failing = run_result(hard_failures=["FOREIGN_TENANT"], metrics=ok)
    assert gate_status([failing]) is TurnTakingStatus.FAILED
    partial = run_result(tools_only_after_final=False, metrics=ok)
    assert gate_status([partial]) is TurnTakingStatus.FAILED
    lost = run_result(metrics=ok | {"context_loss": True})
    assert gate_status([lost]) is TurnTakingStatus.FAILED
    missed = run_result(metrics=ok | {"missed_interruption": True})
    assert gate_status([missed] + [run_result(metrics=ok)] * 4) is TurnTakingStatus.FAILED
    false_endpoints = [
        r.model_copy(update={"metrics": r.metrics.model_copy(update={"false_endpoint": True})})
        if r.category == "FALSE_ENDPOINT_700" else r
        for r in complete_series()
    ]  # fmt: skip
    assert gate_status(false_endpoints) is TurnTakingStatus.VERIFIED  # measured, not gating


# -- fail-closed: provider failures and missing evidence ------------------------------------

CANARY = "sk_car_canary_0123456789abcdef"


class ScriptedTTS:
    """TTS fake that returns a given result or raises (provider name as on CartesiaTTS)."""

    provider = "cartesia"

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome

    async def synthesize(self, text: str, *, timeout_s: float = 60.0, on_audio: Any = None) -> Any:
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if on_audio is not None and self.outcome.pcm:
            on_audio(self.outcome.pcm)
        return self.outcome


def tts_result(ok: bool, pcm: bytes, error: str | None) -> TtsSynthesisResult:
    return TtsSynthesisResult(ok, pcm, 24_000, 1, None, None, "", None, None, None, error)


def speak_with(outcome: Any) -> tuple[TurnTakingAgent, list[TimedEvent]]:
    agent, events, _ = make_agent()
    agent._tts = ScriptedTTS(outcome)  # type: ignore[assignment]
    asyncio.run(agent.speak(0, "Gerne.", lambda pcm: None))
    return agent, events


def test_failed_tts_synthesis_is_recorded_as_a_provider_failure() -> None:
    agent, events = speak_with(tts_result(False, b"", "APIStatusError:402:quota_exceeded"))
    assert agent.provider_failures == [QUOTA]
    done = next(e for e in events if e.name == "TTS_DONE")
    assert done.attrs == {"ok": False, "error": "tts:cartesia:APIStatusError:402:quota_exceeded"}

    no_done, _ = speak_with(tts_result(False, b"", None))  # stream ended without "done"
    assert [str(f) for f in no_done.provider_failures] == ["tts:cartesia:NoAudio"]
    empty, _ = speak_with(tts_result(True, b"", None))  # "ok" but no audio at all
    assert [str(f) for f in empty.provider_failures] == ["tts:cartesia:EmptyAudio"]

    class APIStatusError(Exception):
        status_code = 402
        body: ClassVar[dict[str, str]] = {
            "error_code": "quota_exceeded",
            "message": f"upgrade {CANARY}",
        }

    agent, events = make_agent()[:2]
    agent._tts = ScriptedTTS(APIStatusError(f"refused {CANARY}"))  # type: ignore[assignment]
    with pytest.raises(APIStatusError):
        asyncio.run(agent.speak(0, "Gerne.", lambda pcm: None))
    assert agent.provider_failures == [QUOTA]

    fine, events = speak_with(tts_result(True, b"\x10\x00" * 240, None))
    assert fine.provider_failures == []
    assert next(e for e in events if e.name == "TTS_DONE").attrs == {"ok": True}


def test_tts_cancelled_by_an_interruption_is_not_a_provider_failure() -> None:
    gate = asyncio.Event()

    class BlockingTTS:
        provider = "cartesia"

        async def synthesize(self, text: str, **_: Any) -> Any:
            await gate.wait()

    agent, events, _ = make_agent()
    agent._tts = BlockingTTS()  # type: ignore[assignment]

    async def scenario() -> None:
        task = asyncio.ensure_future(agent.speak(0, "Gerne.", lambda pcm: None))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert agent.provider_failures == [] and not [e for e in events if e.name == "TTS_DONE"]


def test_provider_failure_invalidates_the_session_and_its_audio_metrics() -> None:
    validity = classify_run(
        completed=True, runtime_error=None, harness_error=None, provider_failures=[QUOTA],
        room_cleaned_up=True,
    )  # fmt: skip
    assert validity is RunValidity.INVALID_PROVIDER_FAILURE
    heard = OK_BARGE | {"user_end_to_first_heard_ms": 900.0, "tts_stop_latency_ms": 400.0}
    failed = provider_failed(metrics=heard)
    assert not failed.valid
    summary = summarize_runs([failed])
    assert summary["user_end_to_first_heard_ms"]["n"] == 0
    assert summary["tts_stop_latency_ms"]["n"] == 0
    assert summary["barge_valid"] == [0, 0] and summary["missed_interruptions"] == [0, 0]
    assert summary["provider_failures"] == {"tts:cartesia:APIStatusError:402:quota_exceeded": 1}
    assert gate_evidence([failed])["barge_in"]["usable"] == 0


def test_provider_failure_is_not_counted_as_a_runtime_failure() -> None:
    def classify(**kw: Any) -> RunValidity:
        args: dict[str, Any] = {"completed": True, "runtime_error": None, "harness_error": None,
                                "provider_failures": [], "room_cleaned_up": True}  # fmt: skip
        return classify_run(**(args | kw))

    assert classify() is RunValidity.VALID
    assert classify(provider_failures=[QUOTA]) is RunValidity.INVALID_PROVIDER_FAILURE
    # even if the session also ended badly, the root cause stays the provider
    assert classify(provider_failures=[QUOTA], completed=False) is (
        RunValidity.INVALID_PROVIDER_FAILURE
    )  # fmt: skip
    assert classify(runtime_error="ConnectionError") is RunValidity.INVALID_RUNTIME_FAILURE
    assert classify(completed=False) is RunValidity.INVALID_RUNTIME_FAILURE
    assert classify(room_cleaned_up=False) is RunValidity.INVALID_RUNTIME_FAILURE
    assert classify(harness_error="ServerError", provider_failures=[QUOTA]) is (
        RunValidity.INVALID_HARNESS_FAILURE
    )  # fmt: skip
    counts = summarize_runs([provider_failed()] * 3 + [run_result()])["validity"]
    assert counts == {"VALID": 1, "INVALID_PROVIDER_FAILURE": 3,
                      "INVALID_RUNTIME_FAILURE": 0, "INVALID_HARNESS_FAILURE": 0}  # fmt: skip


def test_no_usable_barge_in_run_is_inconclusive() -> None:
    not_audible = {"barge_valid": False}  # caller never heard the assistant before barging
    runs = complete_series(barge=not_audible)
    assert gate_evidence(runs)["barge_in"] == {
        "usable": 0, "runs": 9, "minimum": 9, "sufficient": False,
    }  # fmt: skip
    assert gate_status(runs) is TurnTakingStatus.INCONCLUSIVE


def test_zero_missed_of_zero_valid_barge_runs_is_never_verified() -> None:
    no_barge = [r for r in complete_series() if not r.category.startswith("BARGE_IN")]
    assert summarize_runs(no_barge)["missed_interruptions"] == [0, 0]
    assert gate_status(no_barge) is TurnTakingStatus.INCONCLUSIVE
    # the 2026-10-27 pattern: every barge-in session lost its TTS to the provider
    quota = [provider_failed(repetition=i, metrics=OK_BARGE) for i in range(9)]
    usable = [r for r in complete_series() if not r.category.startswith("BARGE_IN")]
    assert summarize_runs(usable + quota)["missed_interruptions"] == [0, 0]
    assert gate_status(usable + quota) is TurnTakingStatus.INCONCLUSIVE


def test_barge_in_evidence_below_the_minimum_is_inconclusive() -> None:
    runs = complete_series()
    assert gate_status(runs[:-1]) is TurnTakingStatus.INCONCLUSIVE  # 8 usable < 9
    # 9 usable but only 9 of 11 barge-in runs (< 90 %): still not enough evidence
    extra = [run_result(repetition=9 + i, metrics={"barge_valid": False}) for i in range(2)]
    assert gate_evidence(runs + extra)["barge_in"]["sufficient"] is False
    assert gate_status(runs + extra) is TurnTakingStatus.INCONCLUSIVE
    for group in ("NORMAL_SHORT", "FALSE_ENDPOINT_700", "LATE_ENDPOINT_PHONE"):
        missing = [r for r in runs if r.category != group]
        assert gate_status(missing) is TurnTakingStatus.INCONCLUSIVE


def test_complete_valid_fixture_is_verified_and_security_still_fails() -> None:
    runs = complete_series()
    assert all(g["sufficient"] for g in gate_evidence(runs).values())
    assert gate_status(runs) is TurnTakingStatus.VERIFIED
    # a security violation is never hidden behind missing evidence or invalid runs
    leak = run_result(
        hard_failures=["FOREIGN_TENANT"], validity=RunValidity.INVALID_RUNTIME_FAILURE
    )
    assert gate_status([leak]) is TurnTakingStatus.FAILED
    assert gate_status([*runs, leak]) is TurnTakingStatus.FAILED


def test_provider_failure_keeps_no_message_text_or_credentials() -> None:
    parsed = ProviderFailure.parse("tts", "cartesia", f"Bad Thing {CANARY}:402:{CANARY}!")
    assert parsed.error_class == "UnparsedError" and parsed.http_status == 402
    assert parsed.provider_code is None
    assert CANARY not in str(parsed) and CANARY not in parsed.model_dump_json()
    with pytest.raises(ValueError):
        ProviderFailure(component="tts", provider="cartesia", error_class="X",
                        provider_code=f"code {CANARY}")  # fmt: skip
    with pytest.raises(ValueError):
        ProviderFailure(component="tts", provider="cartesia", error_class=f"X {CANARY}")
    assert ProviderFailure.parse("tts", f"evil {CANARY}", "X").provider == "unknown"
    failed = provider_failed()
    assert CANARY not in failed.model_dump_json()


def test_both_runtimes_share_one_gate_rule(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from voiceos.benchmark import turn_gate

    for scenario in (
        complete_series,
        lambda runtime: complete_series(runtime, {"barge_valid": False}),
    ):
        livekit, pipecat = scenario("livekit"), scenario("pipecat")
        assert gate_status(livekit) is gate_status(pipecat)

    cases = load_turn_taking_cases()
    audio = types.SimpleNamespace(utterance=types.SimpleNamespace(sha256="0" * 64), barge=None)
    monkeypatch.setattr(turn_gate, "render_case", lambda case, directory: audio)

    async def fake_run_case(case: Any, rep: int, runtime: str, *_: Any) -> TurnRunResult:
        if case.case_id == "TT01" and rep == 0:
            raise ConnectionError("infrastructure")  # one harness failure per runtime
        if case.category.startswith("BARGE_IN"):  # TTS refused: no audible assistant
            return provider_failed(runtime=runtime, case_id=case.case_id,
                                   category=case.category, repetition=rep)  # fmt: skip
        return run_result(runtime=runtime, case_id=case.case_id, category=case.category,
                          repetition=rep)  # fmt: skip

    monkeypatch.setattr(turn_gate, "run_case", fake_run_case)
    result = asyncio.run(
        turn_gate.run_turn_gate(
            types.SimpleNamespace(url="ws://127.0.0.1:7880"),  # type: ignore[arg-type]
            {}, cases, tmp_path, runtimes=("livekit", "pipecat"), repetitions_critical=5,
            repetitions_other=3, run_id="offline", timestamp="t", git_commit=None,
            git_dirty=None,
        )
    )  # fmt: skip
    assert result.status == {"livekit": TurnTakingStatus.INCONCLUSIVE,
                             "pipecat": TurnTakingStatus.INCONCLUSIVE}  # fmt: skip
    for runtime in ("livekit", "pipecat"):
        summary = result.summary[runtime]
        assert summary["validity"]["INVALID_HARNESS_FAILURE"] == 1
        assert summary["validity"]["INVALID_PROVIDER_FAILURE"] == 15
        assert summary["validity"]["INVALID_RUNTIME_FAILURE"] == 0
        assert summary["evidence"]["barge_in"]["usable"] == 0
    harness = next(r for r in result.runs if r.validity is RunValidity.INVALID_HARNESS_FAILURE)
    assert harness.harness_error == "ConnectionError" and harness.runtime_error is None


# -- Deepgram live session against a fake SDK -----------------------------------------------


def _result(text: str, final: bool, speech_final: bool = False, finalize: bool = False) -> Any:
    return types.SimpleNamespace(
        type="Results", is_final=final, speech_final=speech_final, from_finalize=finalize,
        channel=types.SimpleNamespace(alternatives=[types.SimpleNamespace(transcript=text)]),
    )  # fmt: skip


class LiveSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.finalized = 0
        self.closed = asyncio.Event()
        self.incoming: asyncio.Queue[Any] = asyncio.Queue()

    async def send_media(self, chunk: bytes) -> None:
        self.sent.append(chunk)

    async def send_finalize(self) -> None:
        self.finalized += 1
        await self.incoming.put(_result("null drei null.", True, finalize=True))

    async def send_close_stream(self) -> None:
        self.closed.set()
        await self.incoming.put(None)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[Any]:
        while (item := await self.incoming.get()) is not None:
            yield item


def test_live_session_streams_finalizes_and_maps_events(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = LiveSocket()
    seen: list[dict[str, Any]] = []

    class Client:
        def __init__(self, *, api_key: str) -> None:
            self.listen = types.SimpleNamespace(v1=types.SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, **options: Any) -> AsyncIterator[LiveSocket]:
            seen.append(options)
            yield socket

    module = types.ModuleType("deepgram")
    module.AsyncDeepgramClient = Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", module)

    class Probed(DeepgramSTT):
        def probe(self) -> Probe:
            return Probe(True)

    env = {"DEEPGRAM_API_KEY": "k", DeepgramSTT.model_env: "nova-3",
           DeepgramSTT.language_env: "de"}  # fmt: skip

    async def scenario() -> list[SttLiveEvent]:
        out: list[SttLiveEvent] = []
        async with Probed(env).open_live(16_000, endpointing_ms=500) as dg:
            await dg.send(b"\x00\x00" * 320)
            await socket.incoming.put(_result("Meine Nummer", False))
            await socket.incoming.put(_result("Meine Nummer ist", True))
            await dg.finalize()
            async for event in dg.events():
                out.append(event)
                if event.from_finalize:
                    break
        return out

    events = asyncio.run(scenario())
    assert [(e.kind, e.text, e.from_finalize) for e in events] == [
        ("interim", "Meine Nummer", False),
        ("final", "Meine Nummer ist", False),
        ("final", "null drei null.", True),
    ]
    assert socket.finalized == 1 and socket.sent and socket.closed.is_set()
    assert seen[0]["endpointing"] == "500" and seen[0]["interim_results"] == "true"


# -- runtime arms: explicit native settings (structure) --------------------------------------


def _source(name: str) -> str:
    return (ROOT / "src/voiceos/benchmark" / name).read_text()


def test_livekit_arm_pins_local_and_non_preemptive_settings() -> None:
    src = _source("turn_runtimes.py")
    assert '"preemptive_generation": {"enabled": False}' in src  # no replies on partial text
    assert 'TurnDetector(version="v1-mini")' in src  # local model, never LiveKit Cloud
    assert '"interruption": {"mode": "vad"}' in src  # adaptive mode would call the cloud
    assert "record=False" in src and "aec_warmup_duration=None" in src


def test_runtime_arms_use_no_provider_plugins_or_services() -> None:
    tree = ast.parse(_source("turn_runtimes.py"))
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not {m for m in modules if m.startswith(("livekit.plugins", "pipecat.services"))}
    assert not {m for m in modules if m.startswith(("voiceos.gateway", "voiceos.mocks"))}
