"""Deterministic fake voice pipeline: STT, LLM, TTS and a minimal runtime loop.

These exist only to exercise the security boundary offline. They are not a runtime
design; the production voice runtime is NOT DECIDED (see docs/architecture).

The runtime is server-side code: it holds the trusted CallContext and passes it to the
gateway. The fake LLM only ever produces text and untrusted ``ToolRequest`` proposals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from voiceos.booking.session import Reply, classify_reply
from voiceos.booking.speech import render_turn
from voiceos.core.context import CallContext
from voiceos.core.tools import Reason, ToolName, ToolRequest, ToolResult
from voiceos.gateway.gateway import ToolGateway


class FakeSTT:
    def __init__(self, transcripts: Mapping[bytes, str]) -> None:
        self._transcripts = dict(transcripts)

    def transcribe(self, audio: bytes) -> str:
        return self._transcripts[audio]


@dataclass(frozen=True, slots=True)
class LLMReply:
    text: str
    tool: ToolRequest | None = None


class FakeLLM:
    """Returns scripted replies in order, regardless of input."""

    def __init__(self, replies: Sequence[LLMReply]) -> None:
        self._replies = list(replies)

    def respond(self, transcript: str) -> LLMReply:
        return self._replies.pop(0)


class FakeTTS:
    def synthesize(self, text: str) -> bytes:
        return text.encode()


@dataclass
class FakeRuntime:
    gateway: ToolGateway
    context: CallContext
    stt: FakeSTT
    llm: FakeLLM
    tts: FakeTTS
    spoken: list[str] = field(default_factory=list)
    _pending: tuple[ToolName, int] | None = None

    def handle_user_audio(self, audio: bytes) -> bytes:
        transcript = self.stt.transcribe(audio)
        self._apply_reply_to_pending_readback(transcript)

        reply = self.llm.respond(transcript)
        result = self.gateway.execute(self.context, reply.tool) if reply.tool else None
        if result is not None:
            self._track_readback(result)

        text = render_turn(reply.text, reply.tool.tool_name if reply.tool else None, result)
        self.spoken.append(text)
        return self.tts.synthesize(text)

    def _track_readback(self, result: ToolResult) -> None:
        if "readback_revision" not in result.data:
            return
        revision = result.data["readback_revision"]
        if not isinstance(revision, int):
            return
        kind = (
            ToolName.CALENDAR_BOOK_SLOT
            if result.reason is Reason.SLOT_CONFIRMATION_REQUIRED
            else ToolName.CONTACT_COLLECT_CANDIDATE
        )
        self._pending = (kind, revision)

    def _apply_reply_to_pending_readback(self, transcript: str) -> None:
        if self._pending is None:
            return
        kind, revision = self._pending
        self._pending = None  # any reply consumes the readback; a new one is needed
        session = self.gateway.session(self.context)
        reply = classify_reply(transcript)
        if kind is ToolName.CONTACT_COLLECT_CANDIDATE:
            if reply is Reply.AFFIRM:
                session.affirm_contact(revision)
            elif reply is Reply.NEGATE:
                session.reject_contact()
        elif reply is Reply.AFFIRM:
            session.affirm_slot(revision)
        elif reply is Reply.NEGATE:
            session.clear_slot()
