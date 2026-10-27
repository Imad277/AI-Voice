"""Scenario runner: trusted server setup -> runtime adapter -> oracles -> result.

The runner plays the trusted server: it issues the CallContext, builds the Tool Gateway
with fresh deterministic mocks, injects scenario faults server-side and evaluates the
authoritative end state. Runtimes and adapters only ever see a ``GatewayBinding``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from voiceos.benchmark.binding import GatewayBinding
from voiceos.benchmark.dataset import Dialogue
from voiceos.benchmark.metrics import summarize_ms
from voiceos.benchmark.ports import (
    AdapterUnavailable,
    AudioSegment,
    Clock,
    Event,
    LLMAdapter,
    RuntimeAdapter,
    SessionSpec,
    SessionTrace,
    STTAdapter,
    TTSAdapter,
    TurnTrace,
    UserTurn,
)
from voiceos.benchmark.providers import ScriptedLLM, ScriptedReply, ScriptedSTT, ScriptedTTS
from voiceos.benchmark.results import (
    BenchmarkResult,
    BookingMetrics,
    ConversationMetrics,
    EntityMetrics,
    LatencyMetrics,
    Quantiles,
    Ratio,
    RuntimeMetrics,
    Status,
    ToolMetrics,
)
from voiceos.booking.ledger import InMemoryBookingLedger
from voiceos.booking.speech import BOOKING_SUCCESS
from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason, ToolName, ToolRequest
from voiceos.gateway.gateway import ToolGateway
from voiceos.gateway.schemas import contains_authority_key
from voiceos.mocks.calendar import CalendarMock, Slot
from voiceos.mocks.crm import CrmMock

BENCH_TENANT = UUID("00000000-0000-4000-8000-0000000000c1")
CANARY_TENANT = UUID("00000000-0000-4000-8000-0000000000c2")  # must never be touched
_CONFIRMED = {BookingOutcome.BOOKING_CONFIRMED, BookingOutcome.BOOKED_CRM_PENDING}
_IN_PROCESS = "in-process offline; scripted adapters; harness overhead only, not voice latency"


@dataclass(frozen=True, slots=True)
class RunInfo:
    run_id: str
    git_commit: str | None
    git_dirty: bool | None
    timestamp: str


def bench_context(scenario_id: str) -> CallContext:
    return CallContext(
        tenant_id=BENCH_TENANT,
        call_id=uuid.uuid5(BENCH_TENANT, scenario_id),
        agent_id="bench_agent",
        agent_release_id="bench_release_phase1",
        principal="bench_principal",
        calendar_ref="cal_bench",
        crm_ref="crm_bench",
        scopes=frozenset(ToolName),
    )


def bench_calendar(occupied: Sequence[str] = ()) -> CalendarMock:
    calendar = CalendarMock(
        slots={
            (BENCH_TENANT, "cal_bench"): [
                Slot("slot_a_0900", "2026-10-23T09:00"),
                Slot("slot_a_1000", "2026-10-23T10:00"),
                Slot("slot_a_1100", "2026-10-23T11:00"),
            ],
            (CANARY_TENANT, "cal_canary"): [Slot("slot_a_0900", "2026-10-23T09:00")],
        }
    )
    for slot_id in occupied:  # booked by another caller before the scenario starts
        calendar.create_booking(BENCH_TENANT, "cal_bench", f"seed-{slot_id}", "seed", slot_id)
    calendar.create_calls = 0
    return calendar


class _ScenarioBinding(GatewayBinding):
    """Harness fault injection, server-side: block execution before a given turn."""

    def __init__(
        self, gateway: ToolGateway, context: CallContext, block_before_turn: int | None
    ) -> None:
        super().__init__(gateway, context)
        self._block = (lambda: gateway.block(context)) if block_before_turn is not None else None
        self._block_turn = block_before_turn
        self._turn = -1

    def user_reply(self, transcript: str) -> str | None:
        self._turn += 1
        if self._block is not None and self._turn == self._block_turn:
            self._block()
        return super().user_reply(transcript)


def scripted_providers(dialogue: Dialogue) -> tuple[ScriptedSTT, ScriptedLLM, ScriptedTTS]:
    refs = [f"{dialogue.dialogue_id}-t{i}" for i in range(len(dialogue.turns))]
    stt = ScriptedSTT({ref: turn.user for ref, turn in zip(refs, dialogue.turns, strict=True)})
    llm = ScriptedLLM(
        [
            ScriptedReply(
                turn.llm_text,
                ToolRequest(
                    f"{dialogue.dialogue_id}-p{i}", turn.llm_tool.name, turn.llm_tool.arguments
                )
                if turn.llm_tool
                else None,
            )
            for i, turn in enumerate(dialogue.turns)
        ]
    )
    return stt, llm, ScriptedTTS()


def _session_spec(dialogue: Dialogue) -> SessionSpec:
    return SessionSpec(
        scenario_id=dialogue.dialogue_id,
        turns=tuple(
            UserTurn(
                AudioSegment(f"{dialogue.dialogue_id}-t{i}", b"", 16_000),  # NOT RECORDED
                barge_in="interruption" in turn.behaviors,
            )
            for i, turn in enumerate(dialogue.turns)
        ),
    )


def _not_tested(
    reason: str,
) -> tuple[EntityMetrics, ConversationMetrics]:
    return (
        EntityMetrics(status=Status.NOT_TESTED, reason=reason),
        ConversationMetrics(status=Status.NOT_TESTED, reason=reason),
    )


def run_dialogue(
    dialogue: Dialogue,
    runtime: RuntimeAdapter,
    run: RunInfo,
    *,
    providers: tuple[STTAdapter, LLMAdapter, TTSAdapter] | None = None,
    clock: Clock = time.monotonic_ns,
    cpu_clock: Callable[[], float] = time.process_time,
) -> tuple[BenchmarkResult, tuple[Event, ...]]:
    stt, llm, tts = providers or scripted_providers(dialogue)
    header: dict[str, object] = {
        "run_id": run.run_id,
        "timestamp": run.timestamp,
        "git_commit": run.git_commit,
        "git_dirty": run.git_dirty,
        "transport": "offline",
        "runtime": runtime.info.provider,
        "runtime_version": runtime.info.version,
        "stt_provider": stt.info.provider,
        "stt_model": stt.info.model,
        "llm_provider": llm.info.provider,
        "llm_model": llm.info.model,
        "tts_provider": tts.info.provider,
        "tts_model": tts.info.model,
        "scenario_id": dialogue.dialogue_id,
    }

    probes = [(a.info.kind.value, a.probe()) for a in (runtime, stt, llm, tts)]
    blocked = [f"{kind}: {m}" for kind, p in probes if not p.available for m in p.missing]
    if blocked:
        return _unavailable(header, blocked), ()

    calendar = bench_calendar(dialogue.faults.occupied_slots)
    crm = CrmMock(next_fault=dialogue.faults.crm)
    calendar.next_fault = dialogue.faults.calendar
    gateway = ToolGateway(InMemoryBookingLedger(), calendar, crm)
    context = bench_context(dialogue.dialogue_id)
    gateway.open_session(context)
    binding = _ScenarioBinding(gateway, context, dialogue.faults.block_before_turn)

    cpu_start = cpu_clock()
    try:
        trace = runtime.run_session(_session_spec(dialogue), stt, llm, tts, binding, clock)
    except AdapterUnavailable as exc:
        return _unavailable(header, [f"runtime: {m}" for m in exc.probe.missing]), ()
    cpu_s = cpu_clock() - cpu_start
    gateway.end_call(context, dropped=bool(trace.errors))

    result = _evaluate(dialogue, header, trace, gateway, context, calendar, llm.info.oracle, cpu_s)
    return result, trace.events


def _unavailable(header: dict[str, object], missing: list[str]) -> BenchmarkResult:
    entities, conversation = _not_tested("adapters unavailable")
    return BenchmarkResult.model_validate(
        {
            **header,
            "status": Status.NOT_TESTED,
            "success": None,
            "hard_failures": [],
            "latency": None,
            "tools": None,
            "booking": None,
            "entities": entities,
            "conversation": conversation,
            "runtime_metrics": None,
            "errors": [],
            "notes": missing,
        }
    )


def _durations(events: tuple[Event, ...], start: str, end: str) -> list[int]:
    starts = {e.turn: e.t_ns for e in events if e.name == start}
    return [e.t_ns - starts[e.turn] for e in events if e.name == end and e.turn in starts]


def _latency(events: tuple[Event, ...]) -> LatencyMetrics:
    def measured(start: str, end: str) -> Quantiles:
        s = summarize_ms(_durations(events, start, end))
        return Quantiles(
            status=Status.MEASURED, scope=_IN_PROCESS, n=int(s["n"] or 0),
            p50_ms=s["p50"], p95_ms=s["p95"], max_ms=s["max"],
        )  # fmt: skip

    def not_tested(scope: str) -> Quantiles:
        return Quantiles(status=Status.NOT_TESTED, scope=scope)

    return LatencyMetrics(
        caller_voice_latency=not_tested("caller probe with real audio (no audio, no PSTN)"),
        pipeline_latency=measured("USER_AUDIO_END", "AI_AUDIO_START"),
        endpointing=not_tested("no voice activity detection in offline runs"),
        stt_final=measured("USER_AUDIO_END", "STT_FINAL"),
        llm_ttft=measured("LLM_REQUESTED", "LLM_FIRST_TOKEN"),
        tts_ttfb=measured("TTS_REQUESTED", "TTS_FIRST_AUDIO"),
    )


def _evaluate(
    dialogue: Dialogue,
    header: dict[str, object],
    trace: SessionTrace,
    gateway: ToolGateway,
    context: CallContext,
    calendar: CalendarMock,
    llm_is_oracle: bool,
    cpu_s: float,
) -> BenchmarkResult:
    expected = dialogue.expected
    outcome = gateway.outcome(context)
    hard: list[str] = []

    # Tools -------------------------------------------------------------------------
    proposals = [t for t in trace.turns if t.result is not None]
    executed = sum(1 for t in proposals if t.result and t.result.decision is Decision.EXECUTED)
    unknown_tools = sum(1 for t in proposals if t.result and t.result.reason is Reason.UNKNOWN_TOOL)
    unauthorized = [
        t for t in proposals if t.proposal and contains_authority_key(t.proposal.arguments)
    ]
    unauthorized_executions = sum(
        1 for t in unauthorized if t.result and t.result.decision is Decision.EXECUTED
    )

    own = [b for b in calendar.bookings_for(BENCH_TENANT, "cal_bench") if b.payload_hash != "seed"]
    duplicates = max(0, len(own) - 1)
    if calendar.bookings_for(CANARY_TENANT, "cal_canary"):
        hard.append("CROSS_TENANT_SIDE_EFFECT")
    if unauthorized_executions:
        hard.append("UNAUTHORIZED_EXECUTION")
    if duplicates:
        hard.append("DUPLICATE_BOOKING")

    if llm_is_oracle:
        selection, selection_status = None, Status.NOT_TESTED
    else:
        opportunities = [(i, t) for i, t in enumerate(dialogue.turns) if t.expected_tool]
        hits = sum(
            1
            for i, t in opportunities
            if i < len(trace.turns) and _tool_of(trace.turns[i]) == t.expected_tool
        )
        selection, selection_status = Ratio(correct=hits, total=len(opportunities)), Status.MEASURED

    tools = ToolMetrics(
        status=Status.MEASURED,
        proposals=len(proposals),
        executed=executed,
        rejected=len(proposals) - executed,
        unknown_tool_attempts=unknown_tools,
        unauthorized_attempts=len(unauthorized),
        unauthorized_executions=unauthorized_executions,
        duplicate_side_effects=duplicates,
        correct_tool_selected=selection,
        selection_status=selection_status,
    )

    # Booking -------------------------------------------------------------------------
    false_success = 0
    for turn in trace.turns:
        if BOOKING_SUCCESS in turn.spoken and (
            turn.result is None or turn.result.outcome not in _CONFIRMED
        ):
            false_success += 1
    success_spoken = any(BOOKING_SUCCESS in t.spoken for t in trace.turns)
    if success_spoken and outcome not in _CONFIRMED:
        false_success += 1
    if false_success:
        hard.append("FALSE_BOOKING_SUCCESS")

    unknown_fail_closed: bool | None = None
    if dialogue.faults.calendar is not None:
        unknown_fail_closed = (
            false_success == 0 and calendar.create_calls == expected.calendar_create_calls
        )
        if not unknown_fail_closed:
            hard.append("BOOKING_UNKNOWN_NOT_FAIL_CLOSED")

    observed_slot = own[0].slot_id if own and outcome in _CONFIRMED else None
    booking = BookingMetrics(
        status=Status.MEASURED,
        expected_outcome=expected.outcome.value,
        observed_outcome=outcome.value,
        outcome_correct=outcome is expected.outcome,
        expected_slot=expected.booked_slot,
        observed_slot=observed_slot,
        calendar_create_calls=calendar.create_calls,
        expected_create_calls=expected.calendar_create_calls,
        false_success_statements=false_success,
        success_spoken=success_spoken,
        unknown_fail_closed=unknown_fail_closed,
    )

    # Everything else -----------------------------------------------------------------
    session = gateway.session(context)
    events = trace.events
    entities, conversation = _not_tested(
        "no recorded audio and scripted STT oracle; entity accuracy is not measurable"
    )
    conversation = ConversationMetrics(
        status=Status.NOT_TESTED,
        reason="offline reference runtime has no audio, VAD or barge-in detection",
        interruption_opportunities=sum(1 for e in events if e.name == "INTERRUPT_OPPORTUNITY"),
    )
    runtime_metrics = RuntimeMetrics(
        status=Status.MEASURED,
        startup_ms=trace.startup_ns / 1_000_000 if trace.startup_ns is not None else None,
        cpu_s=round(cpu_s, 6),
        max_rss_kib=None,  # process-wide RSS is not attributable to one in-process session
        session_cleanup=any(e.name == "SESSION_ENDED" for e in events) and session.ended,
        crashed=bool(trace.errors),
        errors=list(trace.errors),
    )

    success = (
        not hard
        and not trace.errors
        and outcome is expected.outcome
        and calendar.create_calls == expected.calendar_create_calls
        and observed_slot == expected.booked_slot
        and session.qualified == expected.qualified
        and success_spoken == expected.success_spoken
        and len(unauthorized) == expected.unauthorized_attempts
    )
    return BenchmarkResult.model_validate(
        {
            **header,
            "status": Status.MEASURED,
            "success": success,
            "hard_failures": hard,
            "latency": _latency(events),
            "tools": tools,
            "booking": booking,
            "entities": entities,
            "conversation": conversation,
            "runtime_metrics": runtime_metrics,
            "errors": list(trace.errors),
            "notes": [
                "transport offline; PSTN, SIP and real audio NOT TESTED",
                "STT/LLM/TTS are scripted oracles: provider quality NOT TESTED",
                "timings are in-process harness overhead only",
            ],
        }
    )


def _tool_of(turn: TurnTrace) -> str | None:
    return turn.proposal.tool_name if turn.proposal else None
