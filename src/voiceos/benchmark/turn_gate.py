"""Turn-taking gate harness (Phase 1, local only).

Plays the fixed synthetic turn-taking cases (exact pauses and barge-in offsets) into a
throwaway room on the loopback LiveKit dev server, alternating runtime arms per case and
repetition, records what the caller hears (receive time + peak per 20 ms frame) and
evaluates every run with the shared, pre-registered definitions in ``turn_taking``.

Security invariants are the E2E gate's (trusted CallContext, gateway-only business
actions, server-side tenant, no secrets in artifacts) plus: no gateway execution without
a committed *final* transcript.
"""

from __future__ import annotations

import array
import asyncio
import contextlib
import dataclasses
import json
import re
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from voiceos.benchmark import synthetic_audio
from voiceos.benchmark.binding import GatewayBinding
from voiceos.benchmark.e2e_gate import (
    AuditedGateway,
    SyntheticCaller,
    _room_empty,
    hard_failures,
    scan_for_secrets,
    secret_values,
)
from voiceos.benchmark.livekit_local import LocalServer
from voiceos.benchmark.llm_gate import INSTRUCTIONS, PROMPT_SHA256
from voiceos.benchmark.providers import CartesiaTTS, ConfiguredTextLLM, DeepgramSTT
from voiceos.benchmark.runner import BENCH_TENANT, bench_calendar, bench_context
from voiceos.benchmark.runtimes import LiveKitRuntimeAdapter, PipecatRuntimeAdapter
from voiceos.benchmark.stt_gate import HostAudit
from voiceos.benchmark.tts_gate import write_wav
from voiceos.benchmark.turn_runtimes import (
    LIVEKIT_SETTINGS,
    PIPECAT_SETTINGS,
    TurnSessionSpec,
    run_livekit_turn_session,
    run_pipecat_turn_session,
)
from voiceos.benchmark.turn_taking import (
    ENDPOINTING_MS,
    VOICED_PEAK,
    ProviderFailure,
    RenderedAudio,
    RunValidity,
    TurnCase,
    TurnRunMetrics,
    TurnRunResult,
    TurnTakingAgent,
    TurnTakingStatus,
    classify_run,
    evaluate_run,
    gate_status,
    render_segments,
    summarize_runs,
    tools_only_after_final_transcript,
)
from voiceos.benchmark.voice_loop import TimedEvent, VoiceAgentLoop
from voiceos.booking.ledger import InMemoryBookingLedger
from voiceos.mocks.crm import CrmMock

RuntimeName = Literal["livekit", "pipecat"]
REPLY_TIMEOUT_S = 30.0
REPLY_SILENCE_S = 2.0
OUTPUT_RATE_HZ = 24_000
COMPONENTS: tuple[Literal["stt", "llm", "tts"], ...] = ("stt", "llm", "tts")


class TurnCaller(SyntheticCaller):
    """Synthetic caller that also keeps (receive time, peak) for every 20 ms frame."""

    def __init__(self, rtc: Any, emit: Any) -> None:
        super().__init__(rtc, emit)
        self.frames: list[tuple[float, int]] = []

    async def _listen(self, track: Any) -> None:
        stream = self._rtc.AudioStream(
            track, sample_rate=OUTPUT_RATE_HZ, num_channels=1, frame_size_ms=20
        )
        async for event in stream:
            pcm = bytes(event.frame.data)
            self.recording += pcm
            samples = array.array("h", pcm[: len(pcm) - len(pcm) % 2])
            self.frames.append((time.monotonic(), max((abs(s) for s in samples), default=0)))

    async def first_voiced_after(self, after: float, timeout_s: float) -> float | None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            hit = next((t for t, p in self.frames if t >= after and p >= VOICED_PEAK), None)
            if hit is not None:
                return hit
            await asyncio.sleep(0.01)
        return None

    async def silence_after(self, after: float, silence_s: float, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            voiced = [t for t, p in self.frames if t >= after and p >= VOICED_PEAK]
            last = voiced[-1] if voiced else after
            if time.monotonic() - last >= silence_s:
                return
            await asyncio.sleep(0.05)


@dataclasses.dataclass(frozen=True, slots=True)
class CaseAudio:
    utterance: RenderedAudio
    barge: RenderedAudio | None


def render_case(case: TurnCase, directory: Path) -> CaseAudio:
    main = render_segments(case.segments, directory / f"{case.case_id}-utterance.wav")
    barge = (
        render_segments(case.barge_in.segments, directory / f"{case.case_id}-barge.wav")
        if case.barge_in
        else None
    )
    return CaseAudio(main, barge)


async def run_case(
    case: TurnCase,
    repetition: int,
    runtime: RuntimeName,
    audio: CaseAudio,
    server: LocalServer,
    providers: tuple[DeepgramSTT, ConfiguredTextLLM, CartesiaTTS],
    out_dir: Path,
) -> TurnRunResult:
    from livekit import api, rtc

    stt, llm, tts = providers
    events: list[TimedEvent] = []
    context = bench_context(f"turn-taking-{case.case_id}")  # identical for both arms
    original = dataclasses.replace(context)
    calendar, crm = bench_calendar(), CrmMock()
    gateway = AuditedGateway(InMemoryBookingLedger(), calendar, crm, context)
    gateway.open_session(context)
    loop = VoiceAgentLoop(
        stt, llm, tts, GatewayBinding(gateway, context),
        input_sample_rate_hz=16_000, endpointing_ms=ENDPOINTING_MS, emit=events.append,
    )  # fmt: skip
    agent = TurnTakingAgent(loop, stt, tts, emit=events.append)

    room = f"voiceos-turn-{runtime}-{case.case_id.lower()}-{uuid.uuid4().hex[:8]}"
    caller_identity, runtime_identity = "synthetic-caller", f"{runtime}-runtime"

    def token(who: str) -> str:
        grants = api.VideoGrants(room_join=True, room=room)
        return str(
            api.AccessToken(server.api_key, server.api_secret)
            .with_identity(who)
            .with_grants(grants)
            .to_jwt()
        )

    lk = api.LiveKitAPI(server.http_url, server.api_key, server.api_secret)

    async def dispatch(agent_name: str) -> None:
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
        )

    worker = runtime == "livekit"  # only LiveKit Agents' worker needs the server secret
    spec = TurnSessionSpec(
        url=server.url, room=room, caller_identity=caller_identity, identity=runtime_identity,
        join_token=None if worker else token(runtime_identity),
        worker_api_key=server.api_key if worker else None,
        worker_api_secret=server.api_secret if worker else None,
        dispatch=dispatch if worker else None,
    )  # fmt: skip
    caller = TurnCaller(rtc, events.append)

    def mark(name: str) -> float:
        now = time.monotonic()
        events.append(TimedEvent(now, "harness", name, None))
        return now

    async def play() -> None:
        await asyncio.wait_for(caller.agent_track.wait(), 30)
        await asyncio.sleep(0.6)
        start = time.monotonic()
        await caller.say(0, audio.utterance.pcm)
        if case.barge_in is None or audio.barge is None:
            await caller.first_voiced_after(start, REPLY_TIMEOUT_S)
            await caller.silence_after(start, REPLY_SILENCE_S, REPLY_TIMEOUT_S)
            return
        heard = await caller.first_voiced_after(start, REPLY_TIMEOUT_S)
        if heard is None:
            return
        await asyncio.sleep(max(0.0, heard + case.barge_in.offset_ms / 1000 - time.monotonic()))
        await caller.say(1, audio.barge.pcm)
        barge_end = time.monotonic()
        await caller.first_voiced_after(barge_end, REPLY_TIMEOUT_S)
        await caller.silence_after(barge_end, REPLY_SILENCE_S, REPLY_TIMEOUT_S)

    if runtime == "livekit":
        serve_coro = run_livekit_turn_session(LiveKitRuntimeAdapter(), spec, agent)
    else:
        serve_coro = run_pipecat_turn_session(PipecatRuntimeAdapter(), spec, agent)
    observation = None
    empty = None
    deleted = False
    try:
        await lk.room.create_room(api.CreateRoomRequest(name=room, empty_timeout=30))
        await caller.join(server.url, token(caller_identity))
        mark("RUNTIME_START")
        serve = asyncio.ensure_future(serve_coro)
        try:
            await play()
        finally:
            await caller.leave()
            mark("CALLER_LEFT")
        observation = await serve
        empty = await _room_empty(lk, api, room, 10.0)
    finally:
        with contextlib.suppress(Exception):
            await lk.room.delete_room(api.DeleteRoomRequest(room=room))
            rooms = await lk.room.list_rooms(api.ListRoomsRequest(names=[room]))
            deleted = not rooms.rooms
        await lk.aclose()

    run_dir = out_dir / runtime / f"{case.case_id}-r{repetition}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_wav(run_dir / "assistant_output.wav", bytes(caller.recording), OUTPUT_RATE_HZ)
    events.sort(key=lambda e: e.t)
    t0 = events[0].t if events else 0.0
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as f:
        for e in events:
            row = {"t_ms": round((e.t - t0) * 1000, 1), "source": e.source, "name": e.name}
            f.write(json.dumps(row | {"turn": e.turn, "attrs": dict(e.attrs)}) + "\n")
    (run_dir / "caller_frames.json").write_text(
        json.dumps([[round((t - t0) * 1000, 1), p] for t, p in caller.frames])
    )

    starts = {e.turn: e.t for e in events if e.name == "USER_AUDIO_START"}
    barge_start = starts.get(1)
    after_barge = {
        e.turn for e in events
        if barge_start is not None and e.name == "TRANSCRIPT_READY" and e.t >= barge_start
        and e.attrs.get("chars")
    }  # fmt: skip
    user_messages = {m.content for m in loop.history if m.role == "user"}
    in_history = (
        any(agent.transcripts.get(i, "") in user_messages for i in after_barge if i is not None)
        if barge_start is not None
        else None
    )
    metrics = evaluate_run(
        events, caller.frames,
        user_start=starts.get(0, t0), user_voiced_end_s=audio.utterance.voiced_end_s,
        barge_start=barge_start,
        barge_voiced_end_s=audio.barge.voiced_end_s if audio.barge else None,
        barge_transcript_in_history=in_history,
    )  # fmt: skip
    names = {"stt": stt.provider, "llm": llm.provider, "tts": tts.provider}
    provider_failures = list(agent.provider_failures) + [
        ProviderFailure.parse(component, names[component], e.removeprefix(f"{component}:"))
        for t in loop.turns
        for e in t.errors
        for component in COMPONENTS
        if e.startswith(f"{component}:")
    ]
    context_unchanged = context == original and context.tenant_id == BENCH_TENANT
    failures = hard_failures(
        gateway.calls, loop.turns, calendar, crm, context_unchanged=context_unchanged
    )
    entity_ok = None
    if case.expect_digits:
        first_turn = agent.transcripts.get(0, "") + " " + agent.transcripts.get(1, "")
        entity_ok = case.expect_digits in re.sub(r"\D", "", first_turn)
    transcript_doc = {
        "case": case.case_id, "runtime": runtime, "repetition": repetition,
        "transcripts": agent.transcripts, "spoken": [t.spoken for t in loop.turns],
        "interrupted_turns": agent.interrupted_turns,
    }  # fmt: skip
    (run_dir / "transcript.json").write_text(
        json.dumps(transcript_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    completed = bool(observation and observation.completed and observation.error is None)
    runtime_error = observation.error if observation else "NoObservation"
    cleaned = empty is not None and deleted
    return TurnRunResult(
        runtime=runtime,
        case_id=case.case_id,
        category=case.category,
        repetition=repetition,
        room=room,
        completed=completed,
        runtime_error=runtime_error,
        harness_error=None,
        provider_errors=[str(f) for f in provider_failures],
        provider_failures=provider_failures,
        transcripts={int(k): v for k, v in agent.transcripts.items()},
        spoken=[t.spoken for t in loop.turns],
        tools=[dataclasses.asdict(s) for t in loop.turns for s in t.tools],
        hard_failures=failures if cleaned else sorted({*failures, "ROOM_NOT_CLEANED_UP"}),
        tools_only_after_final=tools_only_after_final_transcript(events),
        room_cleaned_up=cleaned,
        metrics=metrics,
        entity_ok=entity_ok,
        validity=classify_run(
            completed=completed,
            runtime_error=runtime_error,
            harness_error=None,
            provider_failures=provider_failures,
            room_cleaned_up=cleaned,
        ),
    )


def _failed_run(case: TurnCase, repetition: int, runtime: str, error: str) -> TurnRunResult:
    metrics = TurnRunMetrics.model_validate(
        dict.fromkeys(TurnRunMetrics.model_fields)
        | {"commits_during_utterance": 0, "false_endpoint": False}
    )
    return TurnRunResult(
        runtime=runtime, case_id=case.case_id, category=case.category, repetition=repetition,
        room="", completed=False, runtime_error=None, harness_error=error,
        provider_errors=[], provider_failures=[], transcripts={}, spoken=[], tools=[],
        hard_failures=[], tools_only_after_final=True, room_cleaned_up=False,
        metrics=metrics, entity_ok=None, validity=RunValidity.INVALID_HARNESS_FAILURE,
    )  # fmt: skip


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TurnGateResult(_Strict):
    schema_version: Literal["voiceos.benchmark.turn_gate/1"] = "voiceos.benchmark.turn_gate/1"
    run_id: str
    timestamp: str
    git_commit: str | None
    git_dirty: bool | None
    header: dict[str, Any]
    settings: dict[str, dict[str, Any]]
    input_audio_sha256: dict[str, str]
    status: dict[str, TurnTakingStatus]
    summary: dict[str, dict[str, Any]]
    runs: list[TurnRunResult]
    secret_scan_clean: bool
    network_hosts: list[str]
    network_peers: list[str]
    notes: list[str]


async def run_turn_gate(
    server: LocalServer,
    env: Mapping[str, str],
    cases: Sequence[TurnCase],
    out_dir: Path,
    *,
    runtimes: Sequence[RuntimeName],
    repetitions_critical: int,
    repetitions_other: int,
    run_id: str,
    timestamp: str,
    git_commit: str | None,
    git_dirty: bool | None,
    audit: HostAudit | None = None,
) -> TurnGateResult:
    stt = DeepgramSTT(env, allow_live=True)
    llm = ConfiguredTextLLM(env, allow_live=True, instructions=INSTRUCTIONS)
    tts = CartesiaTTS(env, allow_live=True)
    header: dict[str, Any] = {
        "livekit_server_url": server.url,
        "runtimes": {"livekit": LiveKitRuntimeAdapter().info.version,
                     "pipecat": PipecatRuntimeAdapter().info.version},
        "stt": {"provider": "deepgram", "model": stt.info.model, "language": stt.language,
                "endpointing_ms": ENDPOINTING_MS, "finalize_on_vad_end": True},
        "llm": {"model": llm.info.model, "reasoning_effort": llm.reasoning_effort},
        "tts": {"model": tts.info.model, "voice_id": tts.voice_id},
        "prompt_sha256": PROMPT_SHA256,
        "input_source": synthetic_audio.source_description(),
        "repetitions": {"critical": repetitions_critical, "other": repetitions_other},
    }  # fmt: skip
    audio_dir = out_dir / "audio"
    audios = {case.case_id: render_case(case, audio_dir) for case in cases}
    shas = {
        f"{cid}-{kind}": a.sha256
        for cid, ca in audios.items()
        for kind, a in (("utterance", ca.utterance), ("barge", ca.barge))
        if a is not None
    }
    plan = [
        (rep, case, runtime)
        for rep in range(max(repetitions_critical, repetitions_other))
        for case in cases
        if rep < (repetitions_critical if case.critical else repetitions_other)
        for runtime in runtimes
    ]
    runs: list[TurnRunResult] = []
    if audit is not None:
        audit.active = True
    try:
        for rep, case, runtime in plan:
            try:
                result = await run_case(
                    case, rep, runtime, audios[case.case_id], server, (stt, llm, tts), out_dir
                )
            except Exception as exc:  # harness/infrastructure failure: an invalid run, not a stop
                result = _failed_run(case, rep, runtime, type(exc).__name__)
            runs.append(result)
            print(
                runtime, case.case_id, rep, result.validity.value, result.runtime_error,
                result.harness_error, result.provider_errors, result.hard_failures, flush=True,
            )  # fmt: skip
    finally:
        if audit is not None:
            audit.active = False
    clean = scan_for_secrets(out_dir, secret_values(env))
    statuses: dict[str, TurnTakingStatus] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for runtime in runtimes:
        mine = [r for r in runs if r.runtime == runtime]
        statuses[runtime] = gate_status(mine) if clean else TurnTakingStatus.FAILED
        summaries[runtime] = summarize_runs(mine)
    return TurnGateResult(
        run_id=run_id, timestamp=timestamp, git_commit=git_commit, git_dirty=git_dirty,
        header=header, settings={"livekit": LIVEKIT_SETTINGS, "pipecat": PIPECAT_SETTINGS},
        input_audio_sha256=shas, status=statuses, summary=summaries, runs=runs,
        secret_scan_clean=clean,
        network_hosts=sorted(audit.hosts) if audit is not None else [],
        network_peers=sorted(audit.peers) if audit is not None else [],
        notes=[
            "local synthetic Phase-1 values over loopback WebRTC; not PSTN, not production",
            "native VAD/turn/interruption per runtime; settings differ where the frameworks "
            "differ and are listed under 'settings'",
            "Deepgram Finalize is sent on each runtime's VAD end (shared policy)",
            "false/late endpoint thresholds and the gate rule were fixed before the runs",
            "fail-closed: provider failures (e.g. TTS refused) invalidate the session as "
            "INVALID_PROVIDER_FAILURE; missing evidence per group is INCONCLUSIVE",
        ],
    )  # fmt: skip
