"""Adapter contracts for the Phase 1 voice benchmark.

Layering (each layer only sees the one below it through these contracts):

    scenario -> RuntimeAdapter -> STTAdapter / LLMAdapter / TTSAdapter
                               -> ServerBinding (Tool Gateway, bound server-side)

Authority rules:
- No adapter receives a CallContext, tenant id, credential or scope.
- The runtime reaches business actions only through ``ServerBinding``, which the trusted
  server builds around the Tool Gateway for exactly one call.
- LLM output is a proposal (``ToolRequest``); the gateway decides.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from voiceos.core.tools import ToolRequest, ToolResult

Clock = Callable[[], int]  # monotonic nanoseconds


class AdapterKind(StrEnum):
    STT = "stt"
    LLM = "llm"
    TTS = "tts"
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class AdapterInfo:
    kind: AdapterKind
    provider: str
    model: str | None  # exact id as configured at test time; never filled from memory
    version: str | None
    # True if the adapter replays ground truth (scripted). Quality metrics measured through
    # an oracle adapter are meaningless and must be reported as NOT TESTED.
    oracle: bool = False


@dataclass(frozen=True, slots=True)
class Probe:
    """Whether an adapter can run right now, and if not, every concrete reason."""

    available: bool
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AudioSegment:
    ref: str  # stable id for telemetry; audio content never goes to telemetry
    pcm: bytes
    sample_rate_hz: int


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    is_final: bool = True


@dataclass(frozen=True, slots=True)
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str


@dataclass(frozen=True, slots=True)
class LLMDelta:
    """One streamed piece of an LLM reply: text, or (last) an untrusted tool proposal."""

    text: str = ""
    tool: ToolRequest | None = None


@runtime_checkable
class STTAdapter(Protocol):
    @property
    def info(self) -> AdapterInfo: ...
    def probe(self) -> Probe: ...
    def transcribe(self, segment: AudioSegment) -> Transcript: ...


@runtime_checkable
class LLMAdapter(Protocol):
    @property
    def info(self) -> AdapterInfo: ...
    def probe(self) -> Probe: ...
    def stream(self, messages: Sequence[Message]) -> Iterator[LLMDelta]: ...


@runtime_checkable
class TTSAdapter(Protocol):
    @property
    def info(self) -> AdapterInfo: ...
    def probe(self) -> Probe: ...
    def stream(self, text: str) -> Iterator[bytes]: ...


@runtime_checkable
class ServerBinding(Protocol):
    """Server-owned handle for one call. Holds the trusted context; never exposes it."""

    def user_reply(self, transcript: str) -> str | None:
        """Record the caller's reply server-side; optionally a server status note."""
        ...

    def execute(self, proposal: ToolRequest) -> ToolResult: ...
    def render(self, model_text: str, tool_name: str | None, result: ToolResult | None) -> str: ...


@dataclass(frozen=True, slots=True)
class UserTurn:
    segment: AudioSegment
    barge_in: bool = False  # caller starts speaking while the previous AI audio plays


@dataclass(frozen=True, slots=True)
class SessionSpec:
    scenario_id: str
    turns: Sequence[UserTurn]


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    t_ns: int  # monotonic, relative to session start
    turn: int | None = None
    attrs: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TurnTrace:
    transcript: str
    spoken: str
    proposal: ToolRequest | None  # untrusted, exactly as the LLM produced it
    result: ToolResult | None  # authoritative gateway answer


@dataclass(frozen=True, slots=True)
class SessionTrace:
    events: tuple[Event, ...]
    turns: tuple[TurnTrace, ...]
    startup_ns: int | None
    errors: tuple[str, ...] = ()


class AdapterUnavailable(Exception):
    def __init__(self, probe: Probe) -> None:
        super().__init__("; ".join(probe.missing))
        self.probe = probe


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Session lifecycle, turn orchestration, interruption, events. No business authority."""

    @property
    def info(self) -> AdapterInfo: ...
    def probe(self) -> Probe: ...
    def run_session(
        self,
        spec: SessionSpec,
        stt: STTAdapter,
        llm: LLMAdapter,
        tts: TTSAdapter,
        binding: ServerBinding,
        clock: Clock,
    ) -> SessionTrace: ...


# -- local transport gate (Phase 1): join/leave on a local LiveKit dev server -------------


@dataclass(frozen=True, slots=True)
class LocalSessionSpec:
    """What the trusted harness hands a runtime for one local join/leave check.

    Transport access only: a room-scoped join token minted by the harness. The LiveKit
    Agents worker protocol additionally needs API key/secret to register; they are set only
    for that adapter and only for the local dev server. Never a CallContext or tenant.
    """

    url: str
    room: str
    identity: str
    join_token: str = field(repr=False)
    worker_api_key: str | None = field(default=None, repr=False)
    worker_api_secret: str | None = field(default=None, repr=False)
    # Harness hooks: explicit agent dispatch, and observing server state while joined.
    dispatch: Callable[[str], Coroutine[Any, Any, None]] | None = None
    on_joined: Callable[[], Coroutine[Any, Any, None]] | None = None
    timeout_s: float = 15.0
    media_timeout_s: float = 10.0


@dataclass(frozen=True, slots=True)
class LocalObservation:
    """What the runtime itself observed. The harness verifies it against the server."""

    joined_identity: str | None
    media_frame_received: bool | None  # None: no media expected/checked
    error: str | None  # exception class name only
