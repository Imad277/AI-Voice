"""Agent-side voice turn loop shared by the end-to-end gates (Phase 1).

Provider- and SDK-neutral: both runtime adapters (LiveKit Agents, Pipecat) feed it caller
audio frames and an audio sink; the existing adapters do the work. Per turn:

    caller frames -> STT (live stream, endpointing) -> ServerBinding.user_reply
    -> LLM (proposals only) -> ServerBinding.execute (Tool Gateway) -> speech guard
    -> TTS (streamed chunks) -> audio sink (LiveKit track)

The loop never sees a CallContext, tenant, scope or credential. Business actions exist
only as ``ServerBinding.execute``. A server status note returned by
``ServerBinding.user_reply`` (slot confirmation recorded) goes into the history as a
server message before the next LLM request; it is context, not an action. Spoken booking
statements come from the speech guard (``ServerBinding.render``), never from model text.
Half duplex: no barge-in.

Every step emits a timing event with an absolute ``time.monotonic()`` timestamp (same
process as the synthetic caller, so both sides share one clock).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from voiceos.benchmark.ports import Message, ServerBinding
from voiceos.benchmark.providers import LlmTurnResult, SttStreamResult, TtsSynthesisResult
from voiceos.benchmark.runtimes import safe_tool_name
from voiceos.core.booking import BookingOutcome
from voiceos.core.tools import ToolRequest, ToolResult

MAX_TOOL_ROUNDS = 2  # LLM calls after the first one that may follow an executed tool


class LiveSTT(Protocol):
    async def stream_live(
        self,
        frames: AsyncIterator[bytes],
        sample_rate_hz: int,
        *,
        endpointing_ms: int,
        on_event: Callable[[str], None] | None = ...,
        timeout_s: float = ...,
    ) -> SttStreamResult: ...


class LiveLLM(Protocol):
    async def respond(
        self, messages: Sequence[Message], *, timeout_s: float = ...
    ) -> LlmTurnResult: ...


class LiveTTS(Protocol):
    sample_rate_hz: int

    async def synthesize(
        self,
        text: str,
        *,
        timeout_s: float = ...,
        on_audio: Callable[[bytes], None] | None = ...,
    ) -> TtsSynthesisResult: ...


@dataclass(frozen=True, slots=True)
class TimedEvent:
    t: float  # absolute time.monotonic() seconds
    source: str  # "agent" | "caller"
    name: str
    turn: int | None
    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolStep:
    proposed: str  # allowlisted name or "<unknown>"
    arguments: Mapping[str, Any]  # model output; synthetic dialog data only
    decision: str
    outcome: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class AgentTurn:
    index: int
    transcript: str
    model_texts: tuple[str, ...]
    tools: tuple[ToolStep, ...]
    spoken: str
    audio_ms: float
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TurnReply:
    spoken: str
    model_texts: tuple[str, ...]
    steps: tuple[ToolStep, ...]
    errors: tuple[str, ...]


class AudioSink(Protocol):
    """Where assistant PCM goes (the LiveKit track). ``write`` must not block."""

    def write(self, pcm: bytes) -> None: ...
    async def drain(self) -> float | None:
        """Wait until everything written so far is played out; return first publish time."""
        ...


def tool_message(tool: str, result: ToolResult) -> str:
    """Server result for the model: identifiers and server-held data, never authority."""
    data = {k: v for k, v in result.data.items() if k != "readback_revision"}
    reason = result.reason.value if result.reason else "-"
    return (
        f"Server-Ergebnis {tool}: Entscheidung {result.decision.value}, "
        f"Ergebnis {result.outcome.value}, Grund {reason}, "
        f"Daten {json.dumps(data, ensure_ascii=False, sort_keys=True)}"
    )


def _needs_caller(result: ToolResult) -> bool:
    """Readback pending or a booking state to state: speak now and let the caller answer.

    Other results (slot list, schema rejection) go back to the model for one more round.
    """
    return "readback_revision" in result.data or result.outcome is not BookingOutcome.NO_BOOKING


class VoiceAgentLoop:
    def __init__(
        self,
        stt: LiveSTT,
        llm: LiveLLM,
        tts: LiveTTS,
        binding: ServerBinding,
        *,
        input_sample_rate_hz: int,
        endpointing_ms: int,
        stt_timeout_s: float = 60.0,
        emit: Callable[[TimedEvent], None],
    ) -> None:
        self._stt, self._llm, self._tts, self._binding = stt, llm, tts, binding
        self._rate = input_sample_rate_hz
        self._endpointing_ms = endpointing_ms
        self._stt_timeout_s = stt_timeout_s
        self._emit = emit
        self.history: list[Message] = []
        self.turns: list[AgentTurn] = []

    def _event(self, name: str, turn: int | None, **attrs: Any) -> None:
        self._emit(TimedEvent(time.monotonic(), "agent", name, turn, attrs))

    async def run(
        self,
        next_frames: Callable[[], Awaitable[AsyncIterator[bytes] | None]],
        sink: AudioSink,
        *,
        max_turns: int,
    ) -> None:
        """Turns until the caller leaves (``next_frames`` returns None) or ``max_turns``."""
        for index in range(max_turns):
            frames = await next_frames()
            if frames is None:
                return
            if not await self.turn(index, frames, sink):
                return

    async def turn(self, i: int, frames: AsyncIterator[bytes], sink: AudioSink) -> bool:
        """One caller turn. False if there was nothing to answer (caller gone / no speech)."""
        names = {
            "open": "STT_OPEN",
            "interim": "STT_INTERIM",
            "final": "STT_FINAL_SEGMENT",
            "speech_final": "STT_FINAL",
            "error": "STT_ERROR",
        }
        seen: set[str] = set()

        def on_stt(kind: str) -> None:
            name = names.get(kind, kind)
            if name == "STT_INTERIM" and "interim" in seen:
                return  # only the first interim of a turn is a timing point
            seen.add(kind)
            self._event(name, i)

        self._event("LISTEN_START", i)
        stt = await self._stt.stream_live(
            frames,
            self._rate,
            endpointing_ms=self._endpointing_ms,
            on_event=on_stt,
            timeout_s=self._stt_timeout_s,
        )
        transcript = stt.final_transcript
        errors: list[str] = [f"stt:{stt.error}"] if stt.error else []
        if not transcript:
            self._event("NO_USER_SPEECH", i)
            return False

        reply = await self.respond(i, transcript)
        spoken = reply.spoken
        errors.extend(reply.errors)

        self._event("TTS_REQUEST_START", i, characters=len(spoken))
        first_audio: list[float] = []

        def on_audio(pcm: bytes) -> None:
            if not first_audio:
                first_audio.append(time.monotonic())
                self._emit(TimedEvent(first_audio[0], "agent", "TTS_FIRST_AUDIO", i, {}))
            sink.write(pcm)

        tts = await self._tts.synthesize(spoken, on_audio=on_audio)
        self._event("TTS_DONE", i, ok=tts.ok, chunks=tts.chunk_count)
        if not tts.ok:
            errors.append(f"tts:{tts.error}")
        published = await sink.drain()
        if published is not None:
            self._emit(TimedEvent(published, "agent", "FIRST_ASSISTANT_AUDIO_PUBLISHED", i, {}))
        self._event("ASSISTANT_AUDIO_COMPLETE", i)
        self.turns.append(
            AgentTurn(
                i, transcript, reply.model_texts, reply.steps, spoken,
                round(len(tts.pcm) / 2 / self._tts.sample_rate_hz * 1000, 1), tuple(errors),
            )
        )  # fmt: skip
        return True

    async def respond(self, i: int, transcript: str) -> TurnReply:
        """Business part of a turn, on a *final* transcript only: server-side reply
        handling, LLM proposals, gateway execution, speech guard. No audio."""
        errors: list[str] = []
        note = self._binding.user_reply(transcript)
        self.history.append(Message("user", transcript))
        if note is not None:  # trusted server state, before the next LLM request
            self.history.append(Message("tool", note))
            self._event("SERVER_CONFIRMATION_NOTE", i)

        model_texts: list[str] = []
        steps: list[ToolStep] = []
        last: tuple[str, ToolResult] | None = None
        for round_ in range(1 + MAX_TOOL_ROUNDS):
            requested = time.monotonic()
            self._emit(TimedEvent(requested, "agent", "LLM_REQUEST_START", i, {"round": round_}))
            reply = await self._llm.respond(self.history)
            if reply.first_output_ms is not None:  # adapter-relative, anchored to the request
                self._emit(
                    TimedEvent(
                        requested + reply.first_output_ms / 1000, "agent", "LLM_FIRST_OUTPUT", i,
                        {"round": round_},
                    )
                )  # fmt: skip
            self._event(
                "LLM_DONE", i, round=round_, ok=reply.ok, proposals=len(reply.proposals),
                first_output_ms=reply.first_output_ms, total_ms=reply.total_ms,
            )  # fmt: skip
            if not reply.ok:
                errors.append(f"llm:{reply.error}")
                break
            if reply.text:
                model_texts.append(reply.text)
            if not reply.proposals:
                break
            stop = False
            for n, proposal in enumerate(reply.proposals):
                tool = safe_tool_name(proposal.tool_name)
                self._event("TOOL_PROPOSAL", i, tool=tool, round=round_)
                self._event("TOOL_EXEC_START", i, tool=tool)
                result = self._binding.execute(
                    ToolRequest(f"turn{i}-r{round_}-{n}", proposal.tool_name, proposal.arguments)
                )
                self._event(
                    "TOOL_EXEC_END", i, tool=tool, decision=result.decision.value,
                    outcome=result.outcome.value,
                    reason=result.reason.value if result.reason else None,
                )  # fmt: skip
                steps.append(
                    ToolStep(
                        tool, dict(proposal.arguments), result.decision.value,
                        result.outcome.value, result.reason.value if result.reason else None,
                    )
                )  # fmt: skip
                self.history.append(Message("tool", tool_message(tool, result)))
                last = (proposal.tool_name, result)
                if _needs_caller(result):
                    stop = True
                    break
            if stop:
                break

        spoken = self._binding.render(
            " ".join(model_texts), last[0] if last else None, last[1] if last else None
        )
        if not spoken:
            spoken = "Entschuldigung, können Sie das bitte wiederholen?"
            errors.append("empty_reply_fallback")
        self.history.append(Message("assistant", spoken))

        return TurnReply(spoken, tuple(model_texts), tuple(steps), tuple(errors))
