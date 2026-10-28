"""Speech and language provider ports (STT, LLM, TTS) of the data plane.

Only the boundaries Phase 1 evidence showed to be real: streaming STT with explicit
finalization, a model that returns text plus untrusted tool proposals, and streaming TTS.
No adapter is implemented here and no provider is selected; credentials reach adapters
through a credential broker, never through these contracts.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

from voiceos.core.tools import ToolRequest
from voiceos.runtime.audio import AudioFrame

_ERROR_CLASS = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_PROVIDER = re.compile(r"[a-z0-9_-]{1,32}")
_PROVIDER_CODE = re.compile(r"[a-z0-9_]{1,64}")


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    """A failed provider call in safe fields only: no message text, no credentials."""

    component: Literal["stt", "llm", "tts"]
    provider: str
    error_class: str
    http_status: int | None = None
    provider_code: str | None = None

    def __post_init__(self) -> None:
        if not _PROVIDER.fullmatch(self.provider):
            raise ValueError("provider must be a plain identifier")
        if not _ERROR_CLASS.fullmatch(self.error_class):
            raise ValueError("error_class must be a plain identifier")
        if self.http_status is not None and not 100 <= self.http_status <= 599:
            raise ValueError("http_status out of range")
        if self.provider_code is not None and not _PROVIDER_CODE.fullmatch(self.provider_code):
            raise ValueError("provider_code must be a plain identifier")

    def __str__(self) -> str:
        tail = [str(self.http_status)] if self.http_status is not None else []
        tail += [self.provider_code] if self.provider_code else []
        return ":".join([self.component, self.provider, self.error_class, *tail])


class ProviderError(Exception):
    """Raised by provider adapters; carries only the safe ``ProviderFailure``."""

    def __init__(self, failure: ProviderFailure) -> None:
        super().__init__(str(failure))
        self.failure = failure


class TranscriptKind(StrEnum):
    INTERIM = "INTERIM"  # partial text: never committed, never a business action
    FINAL = "FINAL"


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    kind: TranscriptKind
    text: str = field(repr=False)
    t: float  # time.monotonic() seconds when received
    from_finalize: bool = False  # final result produced by an explicit finalize request


class SpeechToTextStream(Protocol):
    async def send(self, frame: AudioFrame) -> None: ...

    async def finalize(self) -> None:
        """Ask the provider to flush a final result for the audio sent so far."""
        ...

    def events(self) -> AsyncIterator[TranscriptEvent]: ...


class SpeechToTextPort(Protocol):
    def open_stream(
        self, *, sample_rate_hz: int, language: str
    ) -> AbstractAsyncContextManager[SpeechToTextStream]: ...


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Tool description exposed to the model: name, description and JSON schema only."""

    name: str
    description: str
    parameters: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str = field(repr=False)
    proposals: tuple[ToolRequest, ...] = ()  # untrusted; the gateway decides


class LanguageModelPort(Protocol):
    async def respond(
        self, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec]
    ) -> ModelResponse: ...


class TextToSpeechPort(Protocol):
    def synthesize(self, text: str, *, language: str) -> AsyncIterator[AudioFrame]:
        """Stream audio for ``text``; raise ``ProviderError`` when synthesis fails."""
        ...
