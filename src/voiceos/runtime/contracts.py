"""Runtime, media session and session lifecycle contracts of the data plane.

Authority rules carried over from Phase 0/1:

- The runtime never receives a ``CallContext``, tenant id, credential or scope. It gets a
  ``CallSessionSpec`` (no authority fields), a ``MediaSessionPort``, the provider ports and
  a ``GatewayBinding`` bound by trusted server code to exactly one call.
- Business actions happen only through ``GatewayBinding.submit_proposal``; the model's
  ``ToolRequest`` is a proposal, the gateway's ``ToolResult`` is authoritative.
- Caller replies are passed on only from final transcripts, never from partial text.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from voiceos.core.tools import ToolRequest, ToolResult
from voiceos.runtime.audio import AudioFrame
from voiceos.runtime.providers import LanguageModelPort, SpeechToTextPort, TextToSpeechPort

EventValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """Timed data plane event (Phase 1 vocabulary). Never transcript text or contact data."""

    name: str
    t: float  # time.monotonic() seconds
    turn: int | None = None
    attrs: Mapping[str, EventValue] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None: ...


class CallSessionState(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    ENDING = "ENDING"
    ENDED = "ENDED"


_TRANSITIONS: Mapping[CallSessionState, frozenset[CallSessionState]] = {
    CallSessionState.CREATED: frozenset({CallSessionState.ACTIVE, CallSessionState.ENDED}),
    CallSessionState.ACTIVE: frozenset({CallSessionState.ENDING, CallSessionState.ENDED}),
    CallSessionState.ENDING: frozenset({CallSessionState.ENDED}),
    CallSessionState.ENDED: frozenset(),
}


class InvalidSessionTransition(Exception):
    pass


def transition(current: CallSessionState, target: CallSessionState) -> CallSessionState:
    """Fail closed: any transition not listed is rejected; ``ENDED`` is terminal."""
    if target not in _TRANSITIONS[current]:
        raise InvalidSessionTransition(f"{current} -> {target}")
    return target


class SessionEndReason(StrEnum):
    CALLER_HANGUP = "CALLER_HANGUP"
    AGENT_ENDED = "AGENT_ENDED"
    TIMEOUT = "TIMEOUT"
    MEDIA_FAILURE = "MEDIA_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    RUNTIME_FAILURE = "RUNTIME_FAILURE"


@dataclass(frozen=True, slots=True)
class CallSessionSpec:
    """What the runtime may know about a call. Deliberately no call id, tenant, principal,
    scope or integration reference: identity and authority stay with the gateway binding and
    the server-side event sink, which attributes events to the call."""

    agent_version_id: str
    language: str
    input_sample_rate_hz: int
    output_sample_rate_hz: int
    max_duration_s: float


@dataclass(frozen=True, slots=True)
class SessionResult:
    end_reason: SessionEndReason
    turns: int
    error_class: str | None = None  # exception class name only, never a message


class MediaSessionPort(Protocol):
    """One call's media transport (WebRTC room, SIP bridge, media stream) with call-scoped
    credentials only. No business logic."""

    def incoming(self) -> AsyncIterator[AudioFrame]: ...

    async def play(self, frame: AudioFrame) -> None: ...

    async def clear_output(self) -> None:
        """Stop and drop queued assistant audio (barge-in)."""
        ...

    async def close(self) -> None: ...


class GatewayBinding(Protocol):
    """The runtime's only path to business actions, bound by trusted server code to one call.
    It cannot change tenant, scopes or integration bindings."""

    async def submit_proposal(self, proposal: ToolRequest) -> ToolResult: ...

    async def record_caller_reply(self, final_transcript: str) -> None:
        """Pass a committed *final* caller transcript to server-side confirmation state."""
        ...

    def render_reply(
        self, model_text: str, tool_name: str | None, result: ToolResult | None
    ) -> str:
        """Speech guard: business statements come from authoritative results only."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeProviders:
    stt: SpeechToTextPort
    llm: LanguageModelPort
    tts: TextToSpeechPort


class RuntimePort(Protocol):
    """Runs one call session. Implementations (e.g. a LiveKit Agents or Pipecat adapter) live
    in ``voiceos.infrastructure``; none is selected yet."""

    async def run(
        self,
        spec: CallSessionSpec,
        media: MediaSessionPort,
        providers: RuntimeProviders,
        binding: GatewayBinding,
        events: EventSink,
    ) -> SessionResult: ...
