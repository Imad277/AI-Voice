"""Turn-taking gate, shared runtime-neutral part (Phase 1, no SDK imports).

Both runtime arms (LiveKit Agents, Pipecat) use their *native* VAD, end-of-turn and
interruption mechanics. Everything else is shared and identical:

- the synthetic test audio (fixed utterances, exact pauses, exact barge-in offsets),
- ``TurnTakingAgent``: one Deepgram live stream per session (``Finalize`` on the runtime's
  VAD end), the commit rule (a turn is answered only from *final* STT results, never from
  interim/partial text), the business reply through ``VoiceAgentLoop.respond`` (gateway,
  speech guard), Cartesia synthesis,
- the measurement definitions and the evaluation below (pre-registered thresholds).

Times are absolute ``time.monotonic()`` seconds; caller and runtime share one process.
"""

from __future__ import annotations

import array
import asyncio
import hashlib
import math
import re
import tempfile
import time
import wave
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field

from voiceos.benchmark import synthetic_audio
from voiceos.benchmark.dataset import DATASET_DIR
from voiceos.benchmark.providers import (
    DeepgramLiveSession,
    SttLiveEvent,
    TtsSynthesisResult,
    safe_provider_error,
)
from voiceos.benchmark.voice_loop import LiveTTS, TimedEvent, TurnReply, VoiceAgentLoop

# -- pre-registered harness definitions (fixed before any live run) -------------------------
ENDPOINTING_MS = 500  # Deepgram endpointing, unchanged from the E2E gates
COMMIT_WAIT_S = 1.5  # max wait for Deepgram's Finalize result after the last VAD end
LATE_ENDPOINT_S = 1.5  # turn committed later than this after the end of user speech
MISSED_INTERRUPTION_S = 2.0  # no detection or old audio still heard after this
EARLY_TOLERANCE_S = 0.05  # commit/VAD this close before the voiced end counts as "at end"
VOICED_PEAK = 500  # |sample| per 20 ms frame (of 32767) counted as voiced at the caller
VOICED_GAP_S = 0.5  # pauses shorter than this inside assistant speech are one interval
SEGMENT_PEAK = 300  # trimming threshold for rendered speech segments (10 ms windows)
# Minimum evidence per group before a runtime can be VERIFIED (fixed before the next series).
# A group needs at least this many usable runs AND at least MIN_USABLE_FRACTION of its runs
# usable; "usable" = valid session (barge-in: valid session with the assistant audible when
# the caller interrupted). Missing evidence is INCONCLUSIVE, never VERIFIED.
MIN_USABLE_RUNS = {"normal": 3, "endpointing": 9, "phone": 3, "barge_in": 9}
MIN_USABLE_FRACTION = 0.9
EVIDENCE_GROUPS = {
    "NORMAL_SHORT": "normal", "NORMAL_LONG": "normal",
    "THINK_PAUSE_SHORT": "endpointing", "THINK_PAUSE_LONG": "endpointing",
    "FALSE_ENDPOINT_200": "endpointing", "FALSE_ENDPOINT_400": "endpointing",
    "FALSE_ENDPOINT_700": "endpointing", "LATE_ENDPOINT_SHORT": "endpointing",
    "LATE_ENDPOINT_DATETIME": "endpointing", "SELF_CORRECTION": "endpointing",
    "LATE_ENDPOINT_PHONE": "phone",
    "BARGE_IN_200": "barge_in", "BARGE_IN_500": "barge_in", "BARGE_IN_1000": "barge_in",
}  # fmt: skip


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderFailure(_Strict):
    """A provider call that failed, in safe fields only (no message text, no credentials)."""

    component: Literal["stt", "llm", "tts"]
    provider: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    error_class: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    http_status: int | None = Field(default=None, ge=100, le=599)
    provider_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,64}$")

    @classmethod
    def parse(cls, component: Literal["stt", "llm", "tts"], provider: str, safe: str) -> Self:
        """From a ``safe_provider_error`` string ``Class[:status][:code]``. Anything that does not
        parse as such is dropped (never copied), but the failure itself is always kept."""
        parts = safe.split(":")
        error_class = parts[0] if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", parts[0]) else (
            "UnparsedError"
        )  # fmt: skip
        status = next((int(p) for p in parts[1:] if p.isdigit() and 100 <= int(p) <= 599), None)
        code = next((p for p in parts[1:] if re.fullmatch(r"[a-z0-9_]{1,64}", p)
                     and not p.isdigit()), None)  # fmt: skip
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", provider):
            provider = "unknown"
        return cls(component=component, provider=provider, error_class=error_class,
                   http_status=status, provider_code=code)  # fmt: skip

    def __str__(self) -> str:
        tail = [str(self.http_status)] if self.http_status is not None else []
        tail += [self.provider_code] if self.provider_code else []
        return ":".join([self.component, self.provider, self.error_class, *tail])


class RunValidity(StrEnum):
    """Why a session is (not) usable. A provider failure is never a runtime failure."""

    VALID = "VALID"
    INVALID_PROVIDER_FAILURE = "INVALID_PROVIDER_FAILURE"
    INVALID_RUNTIME_FAILURE = "INVALID_RUNTIME_FAILURE"
    INVALID_HARNESS_FAILURE = "INVALID_HARNESS_FAILURE"


def classify_run(
    *,
    completed: bool,
    runtime_error: str | None,
    harness_error: str | None,
    provider_failures: Sequence[ProviderFailure],
    room_cleaned_up: bool,
) -> RunValidity:
    """Precedence: harness > provider > runtime. A failed provider call (e.g. no assistant
    audio because TTS was refused) invalidates the whole session, including its audio and
    barge-in metrics, and is attributed to the provider, not to the runtime under test."""
    if harness_error is not None:
        return RunValidity.INVALID_HARNESS_FAILURE
    if provider_failures:
        return RunValidity.INVALID_PROVIDER_FAILURE
    if not completed or runtime_error is not None or not room_cleaned_up:
        return RunValidity.INVALID_RUNTIME_FAILURE
    return RunValidity.VALID


class Segment(_Strict):
    text: str | None = None
    pause_ms: int | None = None


class BargeIn(_Strict):
    offset_ms: int  # after the caller first hears the assistant
    segments: list[Segment]


class TurnCase(_Strict):
    case_id: str
    category: str
    critical: bool
    segments: list[Segment]
    barge_in: BargeIn | None = None
    expect_digits: str | None = None


def load_turn_taking_cases(directory: Path = DATASET_DIR) -> list[TurnCase]:
    path = directory / "turn_taking_cases.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [TurnCase.model_validate_json(line) for line in lines if line.strip()]


# -- synthetic audio with exact pauses -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class RenderedAudio:
    pcm: bytes = field(repr=False)  # 16 kHz mono PCM16
    sha256: str
    voiced_start_s: float
    voiced_end_s: float


def _trim(pcm: bytes, rate: int) -> bytes:
    """Cut leading/trailing silence so that pauses between segments are exact."""
    samples = array.array("h", pcm)
    window = rate // 100
    peaks = [
        max((abs(s) for s in samples[i : i + window]), default=0)
        for i in range(0, len(samples), window)
    ]
    voiced = [i for i, p in enumerate(peaks) if p >= SEGMENT_PEAK]
    if not voiced:
        return b""
    return samples[voiced[0] * window : (voiced[-1] + 1) * window].tobytes()


def render_segments(segments: Sequence[Segment], out_wav: Path) -> RenderedAudio:
    rate = synthetic_audio.SAMPLE_RATE_HZ
    parts: list[bytes] = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, segment in enumerate(segments):
            if segment.text:
                wav = Path(tmp) / f"seg{n}.wav"
                synthetic_audio.render(segment.text, wav)
                parts.append(_trim(synthetic_audio.read_pcm(wav), rate))
            elif segment.pause_ms:
                parts.append(b"\x00\x00" * (rate * segment.pause_ms // 1000))
    pcm = b"".join(parts)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(rate)
        wav_out.writeframes(pcm)
    return RenderedAudio(
        pcm=pcm,
        sha256=hashlib.sha256(out_wav.read_bytes()).hexdigest(),
        voiced_start_s=0.0,  # segments are trimmed; audio starts with speech
        voiced_end_s=len(pcm) / 2 / rate,
    )


# -- shared agent side ---------------------------------------------------------------------


class LiveSessionSTT(Protocol):
    def open_live(
        self, sample_rate_hz: int, *, endpointing_ms: int
    ) -> AbstractAsyncContextManager[DeepgramLiveSession]: ...


class TurnTakingAgent:
    """Runtime-neutral agent side: STT stream, commit rule, business reply, synthesis.

    Runtimes call ``on_vad`` from their native VAD, ``commit`` when their native turn
    detection ends the user turn, and ``interrupted``/``tts_stopped`` from their native
    interruption handling. The reply never sees interim text.
    """

    def __init__(
        self,
        loop: VoiceAgentLoop,
        stt: LiveSessionSTT,
        tts: LiveTTS,
        *,
        emit: Callable[[TimedEvent], None],
        input_sample_rate_hz: int = 16_000,
        endpointing_ms: int = ENDPOINTING_MS,
    ) -> None:
        self.loop = loop
        self._stt, self._tts, self._emit = stt, tts, emit
        self._rate, self._endpointing_ms = input_sample_rate_hz, endpointing_ms
        self._finals: list[str] = []
        self._turn = 0
        self._interim_seen = False
        self._last_vad_end: float | None = None
        self._finalized_since_vad_end = False
        self.stt_errors: list[str] = []
        self.provider_failures: list[ProviderFailure] = []
        self.interrupted_turns: list[int] = []
        self.transcripts: dict[int, str] = {}
        self._carry = ""  # final text of a reply the runtime cancelled before it acted

    def _event(self, name: str, turn: int | None, **attrs: Any) -> float:
        now = time.monotonic()
        self._emit(TimedEvent(now, "agent", name, turn, attrs))
        return now

    @property
    def current_turn(self) -> int:
        return self._turn

    def stt_session(self) -> AbstractAsyncContextManager[DeepgramLiveSession]:
        return self._stt.open_live(self._rate, endpointing_ms=self._endpointing_ms)

    # -- signals from the runtime's native mechanics -----------------------------------
    def on_vad(self, kind: Literal["start", "end"]) -> None:
        t = self._event("VAD_START" if kind == "start" else "VAD_END", self._turn)
        if kind == "end":
            self._last_vad_end = t
            self._finalized_since_vad_end = False

    def on_finalize_sent(self) -> None:
        self._event("FINALIZE_SENT", self._turn)

    def on_stt(self, ev: SttLiveEvent) -> None:
        if ev.kind == "interim":
            if not self._interim_seen:
                self._interim_seen = True
                self._emit(TimedEvent(ev.t, "agent", "STT_INTERIM", self._turn, {}))
        elif ev.kind == "final":
            if ev.text:
                self._finals.append(ev.text)
            self._emit(
                TimedEvent(
                    ev.t, "agent", "STT_FINAL", self._turn,
                    {"from_finalize": ev.from_finalize, "empty": not ev.text},
                )
            )  # fmt: skip
            if ev.from_finalize:
                self._finalized_since_vad_end = True
        elif ev.kind == "speech_final":
            self._emit(TimedEvent(ev.t, "agent", "STT_SPEECH_FINAL", self._turn, {}))
        elif ev.kind == "error":
            self.stt_errors.append(ev.text)
            self.provider_failures.append(
                ProviderFailure.parse("stt", getattr(self._stt, "provider", "unknown"), ev.text)
            )
            self._emit(TimedEvent(ev.t, "agent", "STT_ERROR", self._turn, {"error": ev.text}))

    async def commit(self) -> tuple[int, str] | None:
        """The runtime ended the user turn. Answer only from final STT results.

        Final text of an earlier reply that the runtime cancelled before any tool ran is
        carried into this turn, so a premature turn end does not lose the caller's words.
        """
        committed = self._event("TURN_COMMITTED", self._turn)
        deadline = committed + COMMIT_WAIT_S
        try:
            while (
                self._last_vad_end is not None
                and not self._finalized_since_vad_end
                and time.monotonic() < deadline
            ):
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            self._event("COMMIT_CANCELLED", self._turn)
            raise
        transcript = " ".join([self._carry, *self._finals]).strip()
        self._carry = ""
        self._finals.clear()
        self._interim_seen = False
        index = self._turn
        self._turn += 1
        self._event(
            "TRANSCRIPT_READY", index, waited_ms=round((time.monotonic() - committed) * 1000, 1),
            chars=len(transcript),
        )  # fmt: skip
        if not transcript:
            self._event("EMPTY_TURN", index)
            return None
        self.transcripts[index] = transcript
        return index, transcript

    async def reply(self, index: int, transcript: str) -> TurnReply:
        """Business reply. If the runtime cancels it before any tool ran, the history is
        rolled back and the transcript is carried into the next commit."""
        history = len(self.loop.history)
        try:
            return await self.loop.respond(index, transcript)
        except asyncio.CancelledError:
            tools_ran = any(m.role == "tool" for m in self.loop.history[history:])
            self._event("REPLY_CANCELLED", index, tools_ran=tools_ran)
            if not tools_ran:
                del self.loop.history[history:]
                self._carry = transcript
            raise

    async def speak(
        self, index: int, text: str, on_audio: Callable[[bytes], None]
    ) -> TtsSynthesisResult:
        """Fail-closed: a refused/failed synthesis or a stream without audio is recorded as
        a TTS provider failure (safe fields only), which invalidates the session. A
        cancellation by the runtime (interruption) is not a failure."""
        self._event("TTS_REQUEST_START", index, characters=len(text))
        first: list[float] = []
        provider = getattr(self._tts, "provider", "unknown")

        def forward(pcm: bytes) -> None:
            if not first:
                first.append(time.monotonic())
                self._emit(TimedEvent(first[0], "agent", "TTS_FIRST_AUDIO", index, {}))
            on_audio(pcm)

        try:
            result = await self._tts.synthesize(text, on_audio=forward)
        except Exception as exc:
            failure = ProviderFailure.parse("tts", provider, safe_provider_error(exc))
            self.provider_failures.append(failure)
            self._event("TTS_DONE", index, ok=False, error=str(failure))
            raise
        if not result.ok or not result.pcm:
            safe = result.error or ("EmptyAudio" if result.ok else "NoAudio")
            failure = ProviderFailure.parse("tts", provider, safe)
            self.provider_failures.append(failure)
            self._event("TTS_DONE", index, ok=False, error=str(failure))
        else:
            self._event("TTS_DONE", index, ok=True)
        return result

    def published(self, index: int) -> None:
        self._event("FIRST_ASSISTANT_AUDIO_PUBLISHED", index)

    def interrupted(self) -> None:
        self._event("INTERRUPTION_DETECTED", self._turn - 1)
        self.interrupted_turns.append(self._turn - 1)

    def tts_stopped(self, index: int) -> None:
        """Synthesis of the current reply was cancelled."""
        self._event("TTS_STOP_REQUESTED", index)

    def audio_stop_requested(self, kind: str) -> None:
        """The runtime paused/cleared its audio output (first action of an interruption)."""
        self._event("AUDIO_STOP_REQUESTED", self._turn - 1, kind=kind)

    def audio_resumed(self) -> None:
        self._event("AUDIO_RESUMED", self._turn - 1)


# -- evaluation (pure; offline-tested) -------------------------------------------------------


def voiced_intervals(
    frames: Sequence[tuple[float, int]], *, frame_s: float = 0.02
) -> list[tuple[float, float]]:
    """Caller-side assistant speech intervals from (receive time, peak) per 20 ms frame."""
    intervals: list[tuple[float, float]] = []
    for t, peak in frames:
        if peak < VOICED_PEAK:
            continue
        start, end = t - frame_s, t
        if intervals and start - intervals[-1][1] <= VOICED_GAP_S:
            intervals[-1] = (intervals[-1][0], end)
        else:
            intervals.append((start, end))
    return intervals


def _first(events: Sequence[TimedEvent], name: str, after: float) -> TimedEvent | None:
    return next((e for e in events if e.name == name and e.t >= after), None)


def _ms(start: float | None, end: float | None) -> float | None:
    return round((end - start) * 1000, 1) if start is not None and end is not None else None


class TurnRunMetrics(_Strict):
    user_end_to_vad_end_ms: float | None  # runtime VAD delay
    endpoint_latency_ms: float | None  # user speech end -> runtime commits the turn
    user_end_to_finalize_sent_ms: float | None
    deepgram_finalize_delay_ms: float | None  # Finalize sent -> Deepgram finalize result
    stt_final_latency_ms: float | None  # user speech end -> last final used for the turn
    commit_wait_ms: float | None  # commit -> transcript ready (waiting for Finalize result)
    response_start_ms: float | None  # user speech end -> first LLM request
    first_audio_published_ms: float | None  # user speech end -> first assistant frame out
    user_end_to_first_heard_ms: float | None  # user speech end -> caller hears the assistant
    commits_during_utterance: int
    false_endpoint: bool
    late_endpoint: bool | None
    # barge-in only
    barge_valid: bool | None  # assistant was audible when the caller started interrupting
    interruption_detection_ms: float | None
    tts_stop_request_ms: float | None
    tts_stop_latency_ms: float | None  # barge start -> last old assistant audio at caller
    missed_interruption: bool | None
    barge_utterance_accepted_ms: float | None  # barge start -> barge turn transcript ready
    barge_end_to_accepted_ms: float | None  # end of barge speech -> barge transcript ready
    barge_answered: bool | None
    context_loss: bool | None
    barge_success: bool | None


def evaluate_run(
    events: Sequence[TimedEvent],
    frames: Sequence[tuple[float, int]],
    *,
    user_start: float,
    user_voiced_end_s: float,
    barge_start: float | None,
    barge_voiced_end_s: float | None,
    barge_transcript_in_history: bool | None,
) -> TurnRunMetrics:
    events = sorted(events, key=lambda e: e.t)
    user_end = user_start + user_voiced_end_s
    edge = user_end - EARLY_TOLERANCE_S
    commits = [e.t for e in events if e.name == "TURN_COMMITTED"]
    during = sum(1 for c in commits if user_start < c < edge)
    commit = next((c for c in commits if c >= edge), None)
    vad_end = _first(events, "VAD_END", edge)
    finalize = _first(events, "FINALIZE_SENT", edge)
    finalized = (
        next((e for e in events if e.name == "STT_FINAL" and e.attrs.get("from_finalize")
              and e.t >= finalize.t), None)
        if finalize else None
    )  # fmt: skip
    ready = _first(events, "TRANSCRIPT_READY", commit) if commit is not None else None
    last_final = (
        max((e.t for e in events if e.name == "STT_FINAL" and not e.attrs.get("empty")
             and e.t <= ready.t), default=None)
        if ready else None
    )  # fmt: skip
    llm = _first(events, "LLM_REQUEST_START", edge)
    published = _first(events, "FIRST_ASSISTANT_AUDIO_PUBLISHED", edge)
    intervals = voiced_intervals(frames)
    heard = next((s for s, _ in intervals if s >= edge), None)
    endpoint = _ms(user_end, commit)

    barge: dict[str, Any] = dict.fromkeys(
        ("barge_valid", "interruption_detection_ms", "tts_stop_request_ms",
         "tts_stop_latency_ms", "missed_interruption", "barge_utterance_accepted_ms",
         "barge_end_to_accepted_ms", "barge_answered", "context_loss", "barge_success"),
    )  # fmt: skip
    if barge_start is not None and barge_voiced_end_s is not None:
        covering = next(((s, e) for s, e in intervals if s <= barge_start <= e), None)
        since = barge_start - EARLY_TOLERANCE_S
        detected = min(
            (e for e in (_first(events, "INTERRUPTION_DETECTED", since),
                         _first(events, "AUDIO_STOP_REQUESTED", since)) if e is not None),
            key=lambda e: e.t, default=None,
        )  # fmt: skip
        stop = min(
            (e for e in (_first(events, "AUDIO_STOP_REQUESTED", since),
                         _first(events, "TTS_STOP_REQUESTED", since)) if e is not None),
            key=lambda e: e.t, default=None,
        )  # fmt: skip
        barge_end = barge_start + barge_voiced_end_s
        accepted = next(
            (e for e in events if e.name == "TRANSCRIPT_READY" and e.t >= barge_start
             and e.attrs.get("chars")), None,
        )  # fmt: skip
        answered = any(s >= barge_end - EARLY_TOLERANCE_S for s, _ in intervals)
        stop_latency = _ms(barge_start, covering[1]) if covering else None
        detect_ms = _ms(barge_start, detected.t) if detected else None
        missed = covering is not None and (
            detect_ms is None
            or detect_ms > MISSED_INTERRUPTION_S * 1000
            or (stop_latency or 0) > MISSED_INTERRUPTION_S * 1000
        )
        context_loss = accepted is None or not answered or not barge_transcript_in_history
        barge = {
            "barge_valid": covering is not None,
            "interruption_detection_ms": detect_ms,
            "tts_stop_request_ms": _ms(barge_start, stop.t) if stop else None,
            "tts_stop_latency_ms": stop_latency,
            "missed_interruption": missed if covering else None,
            "barge_utterance_accepted_ms": _ms(barge_start, accepted.t) if accepted else None,
            "barge_end_to_accepted_ms": _ms(barge_end, accepted.t) if accepted else None,
            "barge_answered": answered,
            "context_loss": context_loss if covering else None,
            "barge_success": (covering is not None and not missed and not context_loss)
            if covering
            else None,
        }

    return TurnRunMetrics(
        user_end_to_vad_end_ms=_ms(user_end, vad_end.t) if vad_end else None,
        endpoint_latency_ms=endpoint,
        user_end_to_finalize_sent_ms=_ms(user_end, finalize.t) if finalize else None,
        deepgram_finalize_delay_ms=_ms(finalize.t, finalized.t) if finalize and finalized else None,
        stt_final_latency_ms=_ms(user_end, last_final),
        commit_wait_ms=ready.attrs.get("waited_ms") if ready else None,
        response_start_ms=_ms(user_end, llm.t) if llm else None,
        first_audio_published_ms=_ms(user_end, published.t) if published else None,
        user_end_to_first_heard_ms=_ms(user_end, heard),
        commits_during_utterance=during,
        false_endpoint=during > 0,
        late_endpoint=(endpoint > LATE_ENDPOINT_S * 1000) if endpoint is not None else None,
        **barge,
    )


def tools_only_after_final_transcript(events: Sequence[TimedEvent]) -> bool:
    """Every gateway execution belongs to a turn whose transcript came from final results."""
    ready = {e.turn: e.t for e in events if e.name == "TRANSCRIPT_READY" and e.attrs.get("chars")}
    return all(
        e.turn in ready and ready[e.turn] <= e.t for e in events if e.name == "TOOL_EXEC_START"
    )


class TurnTakingStatus(StrEnum):
    VERIFIED = "TURN_TAKING_VERIFIED"
    FAILED = "TURN_TAKING_FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class TurnRunResult(_Strict):
    runtime: str
    case_id: str
    category: str
    repetition: int
    room: str
    completed: bool
    runtime_error: str | None  # the runtime arm's own error; never a provider failure
    harness_error: str | None  # harness/infrastructure exception (class name only)
    provider_errors: list[str]  # str(ProviderFailure), for reading
    provider_failures: list[ProviderFailure]
    transcripts: dict[int, str]
    spoken: list[str]
    tools: list[dict[str, Any]]
    hard_failures: list[str]
    tools_only_after_final: bool
    room_cleaned_up: bool
    metrics: TurnRunMetrics
    entity_ok: bool | None
    validity: RunValidity

    @computed_field  # type: ignore[prop-decorator]
    @property
    def valid(self) -> bool:
        return self.validity is RunValidity.VALID


def gate_evidence(runs: Sequence[TurnRunResult]) -> dict[str, dict[str, int | bool]]:
    """Usable runs per evidence group against the pre-registered minimum."""
    out: dict[str, dict[str, int | bool]] = {}
    for group, minimum in MIN_USABLE_RUNS.items():
        mine = [r for r in runs if EVIDENCE_GROUPS.get(r.category) == group]
        usable = sum(
            r.valid and (group != "barge_in" or r.metrics.barge_valid is True) for r in mine
        )
        out[group] = {
            "usable": usable, "runs": len(mine), "minimum": minimum,
            "sufficient": usable >= minimum and usable >= MIN_USABLE_FRACTION * len(mine),
        }  # fmt: skip
    return out


def gate_status(runs: Sequence[TurnRunResult]) -> TurnTakingStatus:
    """Gate rule; identical for every runtime arm. Fail-closed: VERIFIED needs evidence.

    1. FAILED on any security violation in any run: hard failure, or a gateway execution
       not backed by a final transcript.
    2. INCONCLUSIVE if there are no runs or fewer than 90 % of all runs are valid (provider,
       runtime and harness failures all count as invalid; provider failures are never
       re-labelled as runtime failures).
    3. FAILED on observed interruption defects among usable barge-in runs: any context
       loss, or more than 10 % missed interruptions.
    4. INCONCLUSIVE if any evidence group (normal, endpointing, phone, barge-in) is below
       its pre-registered minimum. In particular 0 missed of 0 usable barge-in runs is
       missing evidence, never a pass.
    5. VERIFIED otherwise. False/late endpoints are measured and reported, not gating.
    """
    if any(r.hard_failures or not r.tools_only_after_final for r in runs):
        return TurnTakingStatus.FAILED
    if not runs or sum(r.valid for r in runs) < 0.9 * len(runs):
        return TurnTakingStatus.INCONCLUSIVE
    barge = [r for r in runs if r.valid and r.metrics.barge_valid is True]
    if any(r.metrics.context_loss for r in barge):
        return TurnTakingStatus.FAILED
    if barge and sum(bool(r.metrics.missed_interruption) for r in barge) > 0.1 * len(barge):
        return TurnTakingStatus.FAILED
    if not all(g["sufficient"] for g in gate_evidence(runs).values()):
        return TurnTakingStatus.INCONCLUSIVE
    return TurnTakingStatus.VERIFIED


def summarize_runs(runs: Sequence[TurnRunResult]) -> dict[str, Any]:
    def stats(values: Sequence[float]) -> dict[str, float | int | None]:
        v = sorted(values)

        def rank(q: float) -> float | None:
            return v[max(0, math.ceil(q * len(v)) - 1)] if v else None

        return {"n": len(v), "min": v[0] if v else None, "p50": rank(0.5), "p95": rank(0.95),
                "max": v[-1] if v else None}  # fmt: skip

    valid = [r for r in runs if r.valid]
    clean = [r for r in valid if not r.metrics.false_endpoint]  # turn latencies: clean turns
    turn_numeric = (
        "user_end_to_vad_end_ms", "endpoint_latency_ms", "user_end_to_finalize_sent_ms",
        "deepgram_finalize_delay_ms", "stt_final_latency_ms", "response_start_ms",
        "first_audio_published_ms", "user_end_to_first_heard_ms",
    )  # fmt: skip
    barge_numeric = (
        "interruption_detection_ms", "tts_stop_request_ms", "tts_stop_latency_ms",
        "barge_utterance_accepted_ms", "barge_end_to_accepted_ms",
    )  # fmt: skip
    out: dict[str, Any] = {
        name: stats([v for r in clean if (v := getattr(r.metrics, name)) is not None])
        for name in turn_numeric
    }
    out |= {
        name: stats([v for r in valid if (v := getattr(r.metrics, name)) is not None])
        for name in barge_numeric
    }
    single = [r for r in valid if r.metrics.barge_valid is None]
    barge = [r for r in valid if r.metrics.barge_valid]
    out["runs"] = len(runs)
    out["valid_runs"] = len(valid)
    out["false_endpoint"] = [sum(r.metrics.false_endpoint for r in valid), len(valid)]
    out["late_endpoint"] = [sum(bool(r.metrics.late_endpoint) for r in valid), len(valid)]
    out["barge_valid"] = [len(barge), sum(1 for r in valid if r.category.startswith("BARGE_IN"))]
    out["barge_success"] = [sum(bool(r.metrics.barge_success) for r in barge), len(barge)]
    out["missed_interruptions"] = [
        sum(bool(r.metrics.missed_interruption) for r in barge),
        len(barge),
    ]
    out["context_loss"] = [sum(bool(r.metrics.context_loss) for r in barge), len(barge)]
    out["single_turn_runs"] = len(single)
    out["validity"] = {v.value: sum(r.validity is v for r in runs) for v in RunValidity}
    out["provider_failures"] = dict(
        sorted(Counter(str(f) for r in runs for f in r.provider_failures).items())
    )
    out["evidence"] = gate_evidence(runs)
    return out


def by_category(runs: Sequence[TurnRunResult]) -> Mapping[str, list[TurnRunResult]]:
    out: dict[str, list[TurnRunResult]] = {}
    for r in runs:
        out.setdefault(r.category, []).append(r)
    return out
