"""Shared offline fakes for the end-to-end gate tests (no SDK, no network, no key)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

from voiceos.benchmark.binding import GatewayBinding
from voiceos.benchmark.e2e_gate import AuditedGateway
from voiceos.benchmark.ports import Message
from voiceos.benchmark.providers import (
    LlmProposal,
    LlmTurnResult,
    SttStreamResult,
    TtsSynthesisResult,
)
from voiceos.benchmark.runner import bench_calendar, bench_context
from voiceos.benchmark.voice_loop import TimedEvent, VoiceAgentLoop
from voiceos.booking.ledger import InMemoryBookingLedger
from voiceos.mocks.calendar import CalendarMock
from voiceos.mocks.crm import CrmMock

# -- fakes for the agent loop --------------------------------------------------------------


class FakeSTT:
    def __init__(self, transcripts: Sequence[str]) -> None:
        self.transcripts = list(transcripts)
        self.frames_read = 0
        self.chunks: list[bytes] = []

    async def stream_live(
        self,
        frames: AsyncIterator[bytes],
        sample_rate_hz: int,
        *,
        endpointing_ms: int,
        on_event: Callable[[str], None] | None = None,
        timeout_s: float = 60.0,
    ) -> SttStreamResult:
        assert endpointing_ms == 500 and sample_rate_hz == 16_000
        emit = on_event or (lambda _: None)
        emit("open")
        async for chunk in frames:
            self.frames_read += 1
            self.chunks.append(chunk)
            if self.transcripts:
                break
        # like DeepgramSTT.stream_live, whose sender is cancelled: the iterator closes now
        await frames.aclose()  # type: ignore[attr-defined]
        text = self.transcripts.pop(0) if self.transcripts else ""
        if text:
            for kind in ("interim", "interim", "final", "speech_final"):
                emit(kind)
        return SttStreamResult(
            True, text, 2, 1, (), 1.0, 2.0, 3.0, None, 4.0, 5.0, None, None
        )  # fmt: skip


def reply(text: str = "", *proposals: tuple[str, dict[str, Any]]) -> LlmTurnResult:
    calls = tuple(LlmProposal(name, args, True) for name, args in proposals)
    return LlmTurnResult(True, text, calls, 10.0, 20.0, 1, 1, 0, "m", None)


class FakeLLM:
    def __init__(self, replies: Sequence[LlmTurnResult]) -> None:
        self.replies = list(replies)
        self.seen: list[list[Message]] = []

    async def respond(self, messages: Sequence[Message], *, timeout_s: float = 60.0) -> Any:
        self.seen.append(list(messages))
        return self.replies.pop(0) if self.replies else reply("Gerne.")


class FakeTTS:
    sample_rate_hz = 24_000

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def synthesize(
        self,
        text: str,
        *,
        timeout_s: float = 60.0,
        on_audio: Callable[[bytes], None] | None = None,
    ) -> TtsSynthesisResult:
        self.texts.append(text)
        pcm = b"\x10\x00" * 2400
        if on_audio is not None:
            on_audio(pcm[:2000])
            on_audio(pcm[2000:])
        return TtsSynthesisResult(True, pcm, 24_000, 2, 1.0, 2.0, text, 0.1, None, None, None)


class FakeSink:
    def __init__(self) -> None:
        self.audio = bytearray()

    def write(self, pcm: bytes) -> None:
        self.audio += pcm

    async def drain(self) -> float | None:
        return time.monotonic() if self.audio else None


def frames_for(turns: int) -> Callable[[], Any]:
    left = [turns]

    async def next_frames() -> AsyncIterator[bytes] | None:
        if left[0] == 0:
            return None
        left[0] -= 1

        async def gen() -> AsyncIterator[bytes]:
            for _ in range(5):
                yield b"\x00\x00" * 320

        return gen()

    return next_frames


def server_state() -> tuple[AuditedGateway, Any, CalendarMock, CrmMock]:
    context = bench_context("e2e-unit")
    calendar, crm = bench_calendar(), CrmMock()
    gateway = AuditedGateway(InMemoryBookingLedger(), calendar, crm, context)
    gateway.open_session(context)
    return gateway, context, calendar, crm


def run_loop(
    transcripts: Sequence[str], replies: Sequence[LlmTurnResult]
) -> tuple[VoiceAgentLoop, AuditedGateway, CalendarMock, CrmMock, list[TimedEvent], FakeTTS]:
    gateway, context, calendar, crm = server_state()
    events: list[TimedEvent] = []
    tts = FakeTTS()
    loop = VoiceAgentLoop(
        FakeSTT(transcripts), FakeLLM(replies), tts, GatewayBinding(gateway, context),
        input_sample_rate_hz=16_000, endpointing_ms=500, emit=events.append,
    )  # fmt: skip
    asyncio.run(loop.run(frames_for(len(transcripts) + 1), FakeSink(), max_turns=10))
    return loop, gateway, calendar, crm, events, tts


HAPPY_REPLIES = [
    reply("", ("contact.collect_candidate", {"name": "Erika Musterfrau", "phone": "030 1234567"})),
    reply("", ("calendar.list_slots", {"date": "2026-10-23"})),
    reply("Um 9, 10 oder 11 Uhr."),
    reply("", ("calendar.book_slot", {"slot_id": "slot_a_1000"})),
    reply("", ("calendar.book_slot", {"slot_id": "slot_a_1000"})),
    reply("Auf Wiederhören."),
]
HAPPY_TRANSCRIPTS = [
    "Erika Musterfrau, 030 1234567.",
    "Ja, genau.",
    "Zehn Uhr, bitte buchen.",
    "Ja, genau.",
    "Auf Wiederhören.",
]
