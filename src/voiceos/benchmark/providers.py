"""STT / LLM / TTS provider adapters.

``Scripted*`` adapters are deterministic and offline. They replay fixture data, so they
are oracles: they prove the harness and the safety boundary, never provider quality.

``DeepgramSTT`` is a real streaming STT adapter (STT baseline gate). ``ElevenLabs*``,
``Cartesia*`` and ``ConfiguredTextLLM`` describe live candidates that only report why they
can not run yet. No model id is ever defaulted: it is configured explicitly at test time.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import importlib.metadata
import json
import os
import re
import time
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from voiceos.benchmark.ports import (
    AdapterInfo,
    AdapterKind,
    AdapterUnavailable,
    AudioSegment,
    LLMDelta,
    Message,
    Probe,
    Transcript,
)
from voiceos.core.tools import ToolName, ToolRequest
from voiceos.gateway.schemas import TOOL_SCHEMAS

# -- deterministic offline adapters -------------------------------------------------------


class ScriptedSTT:
    """Maps audio refs to fixture transcripts (ground truth)."""

    def __init__(self, transcripts: Mapping[str, str]) -> None:
        self._transcripts = dict(transcripts)

    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(AdapterKind.STT, "scripted", None, None, oracle=True)

    def probe(self) -> Probe:
        return Probe(True)

    def transcribe(self, segment: AudioSegment) -> Transcript:
        return Transcript(self._transcripts[segment.ref])


@dataclass(frozen=True, slots=True)
class ScriptedReply:
    text: str
    tool: ToolRequest | None = None


class ScriptedLLM:
    """Returns scripted replies in order, streamed word by word, tool proposal last."""

    def __init__(self, replies: Sequence[ScriptedReply]) -> None:
        self._replies = list(replies)

    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(AdapterKind.LLM, "scripted", None, None, oracle=True)

    def probe(self) -> Probe:
        return Probe(True)

    def stream(self, messages: Sequence[Message]) -> Iterator[LLMDelta]:
        reply = self._replies.pop(0)
        for word in reply.text.split(" "):
            if word:
                yield LLMDelta(text=word + " ")
        if reply.tool is not None:
            yield LLMDelta(tool=reply.tool)


class ScriptedTTS:
    """Deterministic bytes, one chunk per word; no audio quality meaning."""

    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(AdapterKind.TTS, "scripted", None, None, oracle=True)

    def probe(self) -> Probe:
        return Probe(True)

    def stream(self, text: str) -> Iterator[bytes]:
        for word in text.split(" ") or [""]:
            yield word.encode()


# -- live benchmark candidates (not runnable in this phase) -------------------------------


class ProviderError(Exception):
    """A provider call failed; carries only an error class / status, never a message."""


class _LiveCandidate:
    """Shared probe logic. Only names of environment variables are ever read for presence."""

    kind: AdapterKind
    provider: str
    key_env: str
    model_env: str

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = os.environ if env is None else env

    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(self.kind, self.provider, self._env.get(self.model_env) or None, None)

    def probe(self) -> Probe:
        missing = []
        if not self._env.get(self.key_env):
            missing.append(f"credential {self.key_env} not provided")
        if not self._env.get(self.model_env):
            missing.append(f"model id {self.model_env} not configured")
        missing.append("live provider execution not authorized (Phase 0 config refuses live)")
        missing.append("live network client not implemented (dependency decision pending)")
        return Probe(False, tuple(missing))

    def _unavailable(self) -> AdapterUnavailable:
        return AdapterUnavailable(self.probe())


@dataclass(frozen=True, slots=True)
class SttStreamEvent:
    """One provider event; carries no transcript text, only kind and timing."""

    kind: str  # open | speech_started | interim | final | utterance_end | metadata | error | close
    t_ms: float  # relative to the first audio chunk sent (negative: before, e.g. open)


@dataclass(frozen=True, slots=True)
class SttStreamResult:
    connected: bool
    final_transcript: str  # concatenated is_final segments
    interim_count: int
    final_count: int
    events: tuple[SttStreamEvent, ...]
    connect_ms: float | None  # connect start -> socket open
    first_transcript_ms: float | None  # first audio sent -> first transcript event
    last_final_ms: float | None  # first audio sent -> last final segment
    audio_sent_ms: float | None  # first audio sent -> last audio chunk sent
    close_ms: float | None  # first audio sent -> stream closed
    wall_ms: float | None  # connect start -> stream closed
    request_id: str | None  # provider request id (not a credential)
    error: str | None  # exception class (+ HTTP status), never a message


class DeepgramSTT(_LiveCandidate):
    """Deepgram streaming STT (v1 listen websocket). The only place Deepgram is imported.

    Live execution is opt-in per instance (``allow_live=True``), set only by the explicit
    STT gate. Model and language are configuration; nothing is defaulted.
    """

    kind, provider = AdapterKind.STT, "deepgram"
    key_env, model_env = "DEEPGRAM_API_KEY", "VOICEOS_BENCH_STT_MODEL"
    language_env = "VOICEOS_BENCH_STT_LANGUAGE"
    distribution, pinned = "deepgram-sdk", "7.12.0"

    def __init__(self, env: Mapping[str, str] | None = None, *, allow_live: bool = False) -> None:
        super().__init__(env)
        self._allow_live = allow_live

    @property
    def info(self) -> AdapterInfo:
        try:
            version: str | None = importlib.metadata.version(self.distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        return AdapterInfo(self.kind, self.provider, self._env.get(self.model_env) or None, version)

    @property
    def language(self) -> str | None:
        return self._env.get(self.language_env) or None

    def probe(self) -> Probe:
        missing = []
        if not self._env.get(self.key_env):
            missing.append(f"credential {self.key_env} not provided")
        if not self._env.get(self.model_env):
            missing.append(f"model id {self.model_env} not configured")
        if not self.language:
            missing.append(f"language {self.language_env} not configured")
        if self.info.version is None:
            missing.append("SDK deepgram-sdk not installed (uv sync --group stt-deepgram)")
        elif self.info.version != self.pinned:
            missing.append(f"SDK deepgram-sdk {self.info.version} is not the pinned {self.pinned}")
        if not self._allow_live:
            missing.append("live provider execution not authorized for this instance")
        return Probe(not missing, tuple(missing))

    def transcribe(self, segment: AudioSegment) -> Transcript:
        result = asyncio.run(self.stream(segment))
        if result.error is not None:
            raise ProviderError(result.error)
        return Transcript(result.final_transcript)

    async def stream(
        self,
        segment: AudioSegment,
        *,
        chunk_ms: int = 20,
        realtime: bool = True,
        timeout_s: float = 30.0,
    ) -> SttStreamResult:
        """Stream 16-bit mono PCM to Deepgram in ``chunk_ms`` chunks (paced like a caller)."""
        probe = self.probe()
        if not probe.available:
            raise AdapterUnavailable(probe)
        from deepgram import AsyncDeepgramClient

        model, language = self._env[self.model_env], self.language
        clock = time.monotonic
        start = clock()
        t0: float | None = None
        raw: list[tuple[str, float]] = []  # (kind, monotonic); converted once t0 is known
        finals: list[str] = []
        state: dict[str, Any] = {"interim": 0, "first": None, "last_final": None, "rid": None}
        opened = sent_end = closed = None
        error: str | None = None

        def mark(kind: str) -> None:
            raw.append((kind, clock()))

        async def receive(socket: Any) -> None:
            async for message in socket:
                kind = getattr(message, "type", None)
                if kind == "Results":
                    text = message.channel.alternatives[0].transcript if message.channel else ""
                    if not text:
                        continue
                    if state["first"] is None:
                        state["first"] = clock()
                    if message.is_final:
                        finals.append(text)
                        state["last_final"] = clock()
                        mark("final")
                    else:
                        state["interim"] += 1
                        mark("interim")
                elif kind == "Metadata":
                    state["rid"] = getattr(message, "request_id", None)
                    mark("metadata")
                elif kind == "UtteranceEnd":
                    mark("utterance_end")
                elif kind == "SpeechStarted":
                    mark("speech_started")

        client = AsyncDeepgramClient(api_key=self._env[self.key_env])
        try:
            async with asyncio.timeout(timeout_s):
                async with client.listen.v1.connect(
                    model=model,
                    language=language,
                    encoding="linear16",
                    sample_rate=str(segment.sample_rate_hz),
                    channels="1",
                    interim_results="true",
                    punctuate="true",
                    smart_format="true",
                ) as socket:
                    opened = clock()
                    mark("open")
                    receiver = asyncio.ensure_future(receive(socket))
                    step = segment.sample_rate_hz * 2 * chunk_ms // 1000
                    t0 = clock()
                    for offset in range(0, len(segment.pcm), step):
                        await socket.send_media(segment.pcm[offset : offset + step])
                        if realtime:
                            await asyncio.sleep(chunk_ms / 1000)
                    sent_end = clock()
                    await socket.send_close_stream()
                    await receiver
                closed = clock()
                mark("close")
        except Exception as exc:  # class name (+ HTTP status) only; messages may echo headers
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            error = type(exc).__name__ + (f":{status}" if status else "")
            mark("error")

        def rel(moment: float | None) -> float | None:
            return round((moment - t0) * 1000, 1) if moment is not None and t0 is not None else None

        reference = t0 if t0 is not None else start
        events = tuple(SttStreamEvent(k, round((m - reference) * 1000, 1)) for k, m in raw)

        return SttStreamResult(
            connected=opened is not None,
            final_transcript=" ".join(finals).strip(),
            interim_count=state["interim"],
            final_count=len(finals),
            events=events,
            connect_ms=round((opened - start) * 1000, 1) if opened is not None else None,
            first_transcript_ms=rel(state["first"]),
            last_final_ms=rel(state["last_final"]),
            audio_sent_ms=rel(sent_end),
            close_ms=rel(closed),
            wall_ms=round((closed - start) * 1000, 1) if closed is not None else None,
            request_id=state["rid"],
            error=error,
        )

    async def stream_live(
        self,
        frames: AsyncIterator[bytes],
        sample_rate_hz: int,
        *,
        endpointing_ms: int,
        on_event: Callable[[str], None] | None = None,
        timeout_s: float = 60.0,
    ) -> SttStreamResult:
        """Stream live 16-bit mono PCM frames; return at the first ``speech_final`` with text.

        Turn end is Deepgram's endpointing (``endpointing_ms`` of silence), set explicitly by
        the caller. Frames are read only until the utterance is final. ``on_event`` is called
        at the moment of ``open``, ``interim``, ``final`` and ``speech_final`` events.
        """
        probe = self.probe()
        if not probe.available:
            raise AdapterUnavailable(probe)
        from deepgram import AsyncDeepgramClient

        clock = time.monotonic
        start = clock()
        raw: list[tuple[str, float]] = []
        finals: list[str] = []
        state: dict[str, Any] = {"t0": None, "interim": 0, "first": None, "last": None}
        opened = closed = None
        error: str | None = None
        done = asyncio.Event()

        def mark(kind: str) -> None:
            raw.append((kind, clock()))
            if on_event is not None:
                on_event(kind)

        async def send(socket: Any) -> None:
            async for chunk in frames:
                if done.is_set():
                    break
                if state["t0"] is None:
                    state["t0"] = clock()
                await socket.send_media(chunk)
            if not done.is_set():  # input ended (participant left): flush what was sent
                await socket.send_close_stream()

        client = AsyncDeepgramClient(api_key=self._env[self.key_env])
        try:
            async with asyncio.timeout(timeout_s):
                async with client.listen.v1.connect(
                    model=self._env[self.model_env],
                    language=self.language,
                    encoding="linear16",
                    sample_rate=str(sample_rate_hz),
                    channels="1",
                    interim_results="true",
                    punctuate="true",
                    smart_format="true",
                    endpointing=str(endpointing_ms),
                ) as socket:
                    opened = clock()
                    mark("open")
                    sender = asyncio.ensure_future(send(socket))
                    try:
                        async for message in socket:
                            if getattr(message, "type", None) != "Results":
                                continue
                            text = (
                                message.channel.alternatives[0].transcript
                                if message.channel
                                else ""
                            )
                            if not text:
                                continue
                            if state["first"] is None:
                                state["first"] = clock()
                            if not message.is_final:
                                state["interim"] += 1
                                mark("interim")
                                continue
                            finals.append(text)
                            state["last"] = clock()
                            mark("final")
                            if message.speech_final:
                                mark("speech_final")
                                done.set()
                                break
                    finally:
                        done.set()
                        sender.cancel()
                        with contextlib.suppress(BaseException):
                            await sender
                closed = clock()
        except Exception as exc:  # class, HTTP status, provider code only; never the message
            error = safe_provider_error(exc)
            mark("error")

        t0 = state["t0"]

        def rel(moment: float | None) -> float | None:
            return round((moment - t0) * 1000, 1) if moment is not None and t0 is not None else None

        reference = t0 if t0 is not None else start
        return SttStreamResult(
            connected=opened is not None,
            final_transcript=" ".join(finals).strip(),
            interim_count=state["interim"],
            final_count=len(finals),
            events=tuple(SttStreamEvent(k, round((m - reference) * 1000, 1)) for k, m in raw),
            connect_ms=round((opened - start) * 1000, 1) if opened is not None else None,
            first_transcript_ms=rel(state["first"]),
            last_final_ms=rel(state["last"]),
            audio_sent_ms=None,  # live input has no defined end of audio
            close_ms=rel(closed),
            wall_ms=round((closed - start) * 1000, 1) if closed is not None else None,
            request_id=None,
            error=error,
        )

    @contextlib.asynccontextmanager
    async def open_live(
        self, sample_rate_hz: int, *, endpointing_ms: int
    ) -> AsyncIterator[DeepgramLiveSession]:
        """A continuous Deepgram stream for runtimes that decide turn ends themselves.

        The caller pushes PCM with ``send``, asks for the pending words with ``finalize``
        (Deepgram ``Finalize``) when its own VAD/turn logic sees the end of speech, and
        reads ``SttLiveEvent``s. Same connection options as ``stream_live``.
        """
        probe = self.probe()
        if not probe.available:
            raise AdapterUnavailable(probe)
        from deepgram import AsyncDeepgramClient

        client = AsyncDeepgramClient(api_key=self._env[self.key_env])
        async with client.listen.v1.connect(
            model=self._env[self.model_env],
            language=self.language,
            encoding="linear16",
            sample_rate=str(sample_rate_hz),
            channels="1",
            interim_results="true",
            punctuate="true",
            smart_format="true",
            endpointing=str(endpointing_ms),
        ) as socket:
            session = DeepgramLiveSession(socket)
            reader = asyncio.ensure_future(session._receive())
            try:
                yield session
            finally:
                with contextlib.suppress(Exception):
                    await socket.send_close_stream()
                reader.cancel()
                with contextlib.suppress(BaseException):
                    await reader


@dataclass(frozen=True, slots=True)
class SttLiveEvent:
    kind: str  # interim | final | speech_final | error | closed
    text: str
    t: float  # time.monotonic() when the event arrived
    from_finalize: bool = False


class DeepgramLiveSession:
    """Handle of one open Deepgram stream (see ``DeepgramSTT.open_live``)."""

    def __init__(self, socket: Any) -> None:
        self._socket = socket
        self._events: asyncio.Queue[SttLiveEvent | None] = asyncio.Queue()
        self.finalize_requests: list[float] = []

    async def send(self, pcm: bytes) -> None:
        await self._socket.send_media(pcm)

    async def finalize(self) -> None:
        """Flush words Deepgram still holds (e.g. digit sequences) as a final result."""
        self.finalize_requests.append(time.monotonic())
        await self._socket.send_finalize()

    async def events(self) -> AsyncIterator[SttLiveEvent]:
        while (event := await self._events.get()) is not None:
            yield event

    async def _receive(self) -> None:
        try:
            async for message in self._socket:
                if getattr(message, "type", None) != "Results":
                    continue
                text = message.channel.alternatives[0].transcript if message.channel else ""
                finalize = bool(getattr(message, "from_finalize", False))
                now = time.monotonic()
                if not message.is_final:
                    if text:
                        self._events.put_nowait(SttLiveEvent("interim", text, now))
                    continue
                if text or finalize:
                    self._events.put_nowait(SttLiveEvent("final", text, now, finalize))
                if message.speech_final:
                    self._events.put_nowait(SttLiveEvent("speech_final", text, now, finalize))
        except Exception as exc:  # class, HTTP status, provider code only; never the message
            self._events.put_nowait(
                SttLiveEvent("error", safe_provider_error(exc), time.monotonic())
            )
        finally:
            self._events.put_nowait(None)


# Model-facing tool names: OpenAI function names allow only [A-Za-z0-9_-], so the dotted
# allowlist names are mapped 1:1 and mapped back before anything reaches the gateway.
def model_tool_name(tool: str) -> str:
    return tool.replace(".", "__")


def gateway_tool_name(name: str) -> str:
    return name.replace("__", ".")


_TOOL_DESCRIPTIONS = {
    ToolName.CONTACT_COLLECT_CANDIDATE: "Kontaktkandidat (Name und Telefonnummer) erfassen. "
    "Der Server liest ihn dem Anrufer zur Bestätigung vor.",
    ToolName.QUALIFICATION_SUBMIT_CANDIDATE: "Anliegen (Leistungsart) und Budget in Euro erfassen.",
    ToolName.CALENDAR_LIST_SLOTS: "Freie Termine für ein Datum (YYYY-MM-DD) abfragen.",
    ToolName.CALENDAR_BOOK_SLOT: "Einen angebotenen Termin buchen. Nur nach ausdrücklicher "
    "Bestätigung des vorgelesenen Termins durch den Anrufer.",
    ToolName.BOOKING_GET_STATUS: "Status einer unsicheren Buchung prüfen.",
    ToolName.CRM_UPDATE_CONTACT: "Bestätigten Kontakt und Buchung ins CRM übertragen.",
}
_STRICT_KEYWORDS = {"type", "enum", "pattern", "minimum", "maximum", "description"}


def _strict_property(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in schema.items() if k in _STRICT_KEYWORDS}


def openai_tool_definitions() -> list[dict[str, Any]]:
    """Function tools derived from the gateway's own argument schemas (the allowlist).

    Strict mode: closed objects, every property required. Nothing beyond what the gateway
    accepts can be offered to the model, so no authority field can ever appear.
    """
    tools = []
    for tool, model in TOOL_SCHEMAS.items():
        schema = model.model_json_schema()
        properties = {k: _strict_property(v) for k, v in schema.get("properties", {}).items()}
        tools.append(
            {
                "type": "function",
                "name": model_tool_name(tool.value),
                "description": _TOOL_DESCRIPTIONS[tool],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties),
                    "additionalProperties": False,
                },
                "strict": True,
            }
        )
    return tools


@dataclass(frozen=True, slots=True)
class LlmProposal:
    tool_name: str  # gateway (dotted) name as proposed; may be unknown
    arguments: Mapping[str, Any]  # parsed JSON; {} if unparseable
    arguments_parsed: bool


@dataclass(frozen=True, slots=True)
class LlmTurnResult:
    ok: bool
    text: str
    proposals: tuple[LlmProposal, ...]
    first_output_ms: float | None  # request sent -> first text/argument delta
    total_ms: float | None  # request sent -> response completed
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    resolved_model: str | None  # model id reported by the provider response
    error: str | None  # exception class (+ HTTP status), never a message


_LLM_KEYS = {"openai": "OPENAI_API_KEY"}


class ConfiguredTextLLM(_LiveCandidate):
    """Text LLM candidate; provider, model and reasoning effort are configuration.

    Supported live provider: OpenAI Responses API (the only place ``openai`` is imported).
    The model only proposes tool calls; it never receives tenant, scopes or credentials.
    Live execution is opted in per instance (``allow_live=True``).
    """

    kind = AdapterKind.LLM
    model_env = "VOICEOS_BENCH_LLM_MODEL"
    reasoning_env = "VOICEOS_BENCH_LLM_REASONING_EFFORT"
    distribution, pinned = "openai", "2.54.0"

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        allow_live: bool = False,
        instructions: str = "",
    ) -> None:
        super().__init__(env)
        self.provider = self._env.get("VOICEOS_BENCH_LLM_PROVIDER") or "unconfigured"
        self.key_env = _LLM_KEYS.get(self.provider, "VOICEOS_BENCH_LLM_API_KEY")
        self._allow_live = allow_live
        self._instructions = instructions

    @property
    def info(self) -> AdapterInfo:
        try:
            version: str | None = importlib.metadata.version(self.distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        return AdapterInfo(self.kind, self.provider, self._env.get(self.model_env) or None, version)

    @property
    def reasoning_effort(self) -> str | None:
        return self._env.get(self.reasoning_env) or None

    def probe(self) -> Probe:
        missing = []
        if self.provider not in _LLM_KEYS:
            missing.append("provider VOICEOS_BENCH_LLM_PROVIDER not configured or unsupported")
        if not self._env.get(self.key_env):
            missing.append(f"credential {self.key_env} not provided")
        if not self._env.get(self.model_env):
            missing.append(f"model id {self.model_env} not configured")
        if not self.reasoning_effort:
            missing.append(f"reasoning effort {self.reasoning_env} not configured")
        if self.info.version is None:
            missing.append("SDK openai not installed (uv sync --group llm-openai)")
        elif self.info.version != self.pinned:
            missing.append(f"SDK openai {self.info.version} is not the pinned {self.pinned}")
        if not self._allow_live:
            missing.append("live provider execution not authorized for this instance")
        return Probe(not missing, tuple(missing))

    def stream(self, messages: Sequence[Message]) -> Iterator[LLMDelta]:
        result = asyncio.run(self.respond(messages))
        if result.error is not None:
            raise ProviderError(result.error)
        if result.text:
            yield LLMDelta(text=result.text)
        for i, proposal in enumerate(result.proposals[:1]):  # one proposal per turn
            yield LLMDelta(tool=ToolRequest(f"llm-{i}", proposal.tool_name, proposal.arguments))

    async def respond(
        self, messages: Sequence[Message], *, timeout_s: float = 60.0
    ) -> LlmTurnResult:
        probe = self.probe()
        if not probe.available:
            raise AdapterUnavailable(probe)
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._env[self.key_env], max_retries=0)
        items = [
            {"role": "developer" if m.role == "tool" else m.role, "content": m.content}
            for m in messages
        ]
        clock = time.monotonic
        texts: list[str] = []
        calls: list[LlmProposal] = []
        state: dict[str, Any] = {"first": None, "done": None, "usage": None, "model": None}
        error: str | None = None
        start = clock()
        try:
            async with asyncio.timeout(timeout_s):
                stream = await client.responses.create(
                    model=self._env[self.model_env],
                    instructions=self._instructions or None,
                    input=items,
                    tools=openai_tool_definitions(),
                    tool_choice="auto",
                    reasoning={"effort": self.reasoning_effort},
                    store=False,
                    stream=True,
                )
                async for event in stream:
                    kind = getattr(event, "type", "")
                    if kind in (
                        "response.output_text.delta",
                        "response.function_call_arguments.delta",
                    ):
                        if state["first"] is None:
                            state["first"] = clock()
                        if kind == "response.output_text.delta":
                            texts.append(event.delta)
                    elif kind == "response.output_item.done" and event.item.type == "function_call":
                        calls.append(_proposal(event.item.name, event.item.arguments))
                    elif kind == "response.completed":
                        state["done"] = clock()
                        state["usage"] = event.response.usage
                        state["model"] = event.response.model
                    elif kind in ("response.failed", "error"):
                        error = kind
        except Exception as exc:  # class, HTTP status, provider code only; never the message
            error = safe_provider_error(exc)
        finally:
            await client.close()

        usage = state["usage"]
        details = getattr(usage, "output_tokens_details", None)

        def ms(moment: float | None) -> float | None:
            return round((moment - start) * 1000, 1) if moment is not None else None

        return LlmTurnResult(
            ok=error is None and state["done"] is not None,
            text="".join(texts).strip(),
            proposals=tuple(calls),
            first_output_ms=ms(state["first"]),
            total_ms=ms(state["done"]),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            reasoning_tokens=getattr(details, "reasoning_tokens", None),
            resolved_model=state["model"],
            error=error,
        )


def _safe_code(code: object) -> str | None:
    """A provider error code is kept only if it is a plain identifier (never free text)."""
    return code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,64}", code) else None


def safe_provider_error(exc: Exception) -> str:
    """Exception class + HTTP status + provider error code (an identifier, never text).

    The code comes from ``exc.code`` or, where the SDK keeps it only in the parsed error
    body (Cartesia: ``{"error_code": "quota_exceeded", ...}``), from ``body["error_code"]``.
    The body's message is never read.
    """
    parts = [type(exc).__name__]
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        parts.append(str(status))
    code = _safe_code(getattr(exc, "code", None))
    body = getattr(exc, "body", None)
    if code is None and isinstance(body, dict):
        code = _safe_code(body.get("error_code"))
    if code is not None:
        parts.append(code)
    return ":".join(parts)


def _proposal(name: str, raw_arguments: str) -> LlmProposal:
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return LlmProposal(gateway_tool_name(name), {}, False)
    if not isinstance(parsed, dict):
        return LlmProposal(gateway_tool_name(name), {}, False)
    return LlmProposal(gateway_tool_name(name), parsed, True)


@dataclass(frozen=True, slots=True)
class TtsSynthesisResult:
    ok: bool
    pcm: bytes = field(repr=False)  # raw 16-bit little-endian mono; never written to results
    sample_rate_hz: int
    chunk_count: int
    first_audio_ms: float | None  # request sent -> first non-empty audio chunk received
    total_ms: float | None  # request sent -> stream fully received
    aligned_text: str  # characters the provider aligned to audio (truncation check)
    last_char_end_s: float | None  # end time of the last aligned character
    character_cost: int | None  # provider usage header, if present
    request_id: str | None  # provider request id header, if present
    error: str | None  # exception class (+ HTTP status / code), never a message


class ElevenLabsTTS(_LiveCandidate):
    """ElevenLabs streaming TTS (HTTP stream with character timestamps).

    The only place ``elevenlabs`` is imported. Model, voice and language are configuration;
    nothing is defaulted. Live execution is opted in per instance (``allow_live=True``).
    Output is raw PCM 16-bit mono at 24 kHz (``pcm_24000``).
    """

    kind, provider = AdapterKind.TTS, "elevenlabs"
    key_env, model_env = "ELEVENLABS_API_KEY", "VOICEOS_BENCH_TTS_MODEL"
    voice_env, language_env = "VOICEOS_BENCH_TTS_VOICE_ID", "VOICEOS_BENCH_TTS_LANGUAGE"
    distribution, pinned = "elevenlabs", "2.71.0"
    output_format, sample_rate_hz = "pcm_24000", 24_000
    _SAFE_HEADERS = (("character-cost", "character_cost"), ("request-id", "request_id"))

    def __init__(self, env: Mapping[str, str] | None = None, *, allow_live: bool = False) -> None:
        super().__init__(env)
        self._allow_live = allow_live

    @property
    def info(self) -> AdapterInfo:
        try:
            version: str | None = importlib.metadata.version(self.distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        return AdapterInfo(self.kind, self.provider, self._env.get(self.model_env) or None, version)

    @property
    def voice_id(self) -> str | None:
        return self._env.get(self.voice_env) or None

    @property
    def language(self) -> str | None:
        return self._env.get(self.language_env) or None

    def probe(self) -> Probe:
        missing = []
        if not self._env.get(self.key_env):
            missing.append(f"credential {self.key_env} not provided")
        if not self._env.get(self.model_env):
            missing.append(f"model id {self.model_env} not configured")
        if not self.voice_id:
            missing.append(f"voice id {self.voice_env} not configured")
        if not self.language:
            missing.append(f"language {self.language_env} not configured")
        if self.info.version is None:
            missing.append("SDK elevenlabs not installed (uv sync --group tts-elevenlabs)")
        elif self.info.version != self.pinned:
            missing.append(f"SDK elevenlabs {self.info.version} is not the pinned {self.pinned}")
        if not self._allow_live:
            missing.append("live provider execution not authorized for this instance")
        return Probe(not missing, tuple(missing))

    def stream(self, text: str) -> Iterator[bytes]:
        result = asyncio.run(self.synthesize(text))
        if result.error is not None:
            raise ProviderError(result.error)
        yield result.pcm

    async def synthesize(self, text: str, *, timeout_s: float = 60.0) -> TtsSynthesisResult:
        probe = self.probe()
        if not probe.available:
            raise AdapterUnavailable(probe)
        from elevenlabs import AsyncElevenLabs

        client = AsyncElevenLabs(api_key=self._env[self.key_env])
        clock = time.monotonic
        audio: list[bytes] = []
        chars: list[str] = []
        state: dict[str, Any] = {"first": None, "done": None, "end": None, "chunks": 0}
        headers: dict[str, Any] = {}
        error: str | None = None
        start = clock()
        try:
            async with asyncio.timeout(timeout_s):
                async with client.text_to_speech.with_raw_response.stream_with_timestamps(
                    self.voice_id or "",
                    text=text,
                    model_id=self._env[self.model_env],
                    language_code=self.language,
                    output_format=self.output_format,
                ) as response:
                    for name, field_name in self._SAFE_HEADERS:
                        value = response.headers.get(name)
                        if value is not None:
                            headers[field_name] = value
                    async for chunk in response.data:
                        state["chunks"] += 1
                        if chunk.audio_base_64:
                            if state["first"] is None:
                                state["first"] = clock()
                            audio.append(base64.b64decode(chunk.audio_base_64))
                        alignment = chunk.alignment
                        if alignment is not None and alignment.characters:
                            chars.extend(alignment.characters)
                            state["end"] = alignment.character_end_times_seconds[-1]
                    state["done"] = clock()
        except Exception as exc:  # class, HTTP status, provider code only; never the message
            error = safe_provider_error(exc)

        def ms(moment: float | None) -> float | None:
            return round((moment - start) * 1000, 1) if moment is not None else None

        cost = headers.get("character_cost")
        return TtsSynthesisResult(
            ok=error is None and state["done"] is not None,
            pcm=b"".join(audio),
            sample_rate_hz=self.sample_rate_hz,
            chunk_count=state["chunks"],
            first_audio_ms=ms(state["first"]),
            total_ms=ms(state["done"]),
            aligned_text="".join(chars),
            last_char_end_s=state["end"],
            character_cost=int(cost) if isinstance(cost, str) and cost.isdigit() else None,
            request_id=headers.get("request_id"),
            error=error,
        )


class CartesiaTTS(_LiveCandidate):
    """Cartesia streaming TTS (SSE with word timestamps); TTS challenger candidate.

    The only place ``cartesia`` is imported. Model, voice and language are configuration;
    nothing is defaulted. Live execution is opted in per instance (``allow_live=True``).
    Output is raw PCM s16le mono at 24 kHz, the same layout as the ElevenLabs gate.
    """

    kind, provider = AdapterKind.TTS, "cartesia"
    key_env, model_env = "CARTESIA_API_KEY", "VOICEOS_BENCH_TTS_CHALLENGER_MODEL"
    voice_env = "VOICEOS_BENCH_TTS_CHALLENGER_VOICE_ID"
    language_env = "VOICEOS_BENCH_TTS_CHALLENGER_LANGUAGE"
    distribution, pinned = "cartesia", "4.2.0"
    output_format, sample_rate_hz = "raw/pcm_s16le/24000", 24_000

    def __init__(self, env: Mapping[str, str] | None = None, *, allow_live: bool = False) -> None:
        super().__init__(env)
        self._allow_live = allow_live

    @property
    def info(self) -> AdapterInfo:
        try:
            version: str | None = importlib.metadata.version(self.distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        return AdapterInfo(self.kind, self.provider, self._env.get(self.model_env) or None, version)

    @property
    def voice_id(self) -> str | None:
        return self._env.get(self.voice_env) or None

    @property
    def language(self) -> str | None:
        return self._env.get(self.language_env) or None

    def probe(self) -> Probe:
        missing = []
        if not self._env.get(self.key_env):
            missing.append(f"credential {self.key_env} not provided")
        if not self._env.get(self.model_env):
            missing.append(f"model id {self.model_env} not configured")
        if not self.voice_id:
            missing.append(f"voice id {self.voice_env} not configured")
        if not self.language:
            missing.append(f"language {self.language_env} not configured")
        if self.info.version is None:
            missing.append("SDK cartesia not installed (uv sync --group tts-cartesia)")
        elif self.info.version != self.pinned:
            missing.append(f"SDK cartesia {self.info.version} is not the pinned {self.pinned}")
        if not self._allow_live:
            missing.append("live provider execution not authorized for this instance")
        return Probe(not missing, tuple(missing))

    def stream(self, text: str) -> Iterator[bytes]:
        result = asyncio.run(self.synthesize(text))
        if result.error is not None:
            raise ProviderError(result.error)
        yield result.pcm

    async def synthesize(
        self,
        text: str,
        *,
        timeout_s: float = 60.0,
        on_audio: Callable[[bytes], None] | None = None,
    ) -> TtsSynthesisResult:
        """``on_audio`` receives each PCM chunk as it arrives (must not block)."""
        probe = self.probe()
        if not probe.available:
            raise AdapterUnavailable(probe)
        from cartesia import AsyncCartesia

        client = AsyncCartesia(api_key=self._env[self.key_env], max_retries=0)
        clock = time.monotonic
        audio: list[bytes] = []
        words: list[str] = []
        state: dict[str, Any] = {"first": None, "done": None, "end": None, "chunks": 0}
        error: str | None = None
        start = clock()
        try:
            async with asyncio.timeout(timeout_s):
                stream = await client.tts.generate_sse(
                    model_id=self._env[self.model_env],
                    transcript=text,
                    voice={"id": self.voice_id or ""},
                    output_format={
                        "container": "raw",
                        "encoding": "pcm_s16le",
                        "sample_rate": self.sample_rate_hz,
                    },
                    language=self.language,
                    add_timestamps=True,
                )
                async for event in stream:
                    kind = getattr(event, "type", "")
                    if kind == "chunk":
                        state["chunks"] += 1
                        if event.data:
                            if state["first"] is None:
                                state["first"] = clock()
                            pcm = base64.b64decode(event.data)
                            audio.append(pcm)
                            if on_audio is not None:
                                on_audio(pcm)
                    elif kind == "timestamps" and event.word_timestamps is not None:
                        words.extend(event.word_timestamps.words)
                        if event.word_timestamps.end:
                            state["end"] = event.word_timestamps.end[-1]
                    elif kind == "done":
                        state["done"] = clock()
                    elif kind == "error":
                        status = getattr(event, "status_code", None)
                        code = _safe_code(getattr(event, "error_code", None))
                        error = (
                            "StreamErrorEvent"
                            + (f":{status}" if isinstance(status, int) else "")
                            + (f":{code}" if code else "")
                        )
        except Exception as exc:  # class, HTTP status, provider code only; never the message
            error = safe_provider_error(exc)
        finally:
            await client.close()

        def ms(moment: float | None) -> float | None:
            return round((moment - start) * 1000, 1) if moment is not None else None

        return TtsSynthesisResult(
            ok=error is None and state["done"] is not None,
            pcm=b"".join(audio),
            sample_rate_hz=self.sample_rate_hz,
            chunk_count=state["chunks"],
            first_audio_ms=ms(state["first"]),
            total_ms=ms(state["done"]),
            aligned_text=" ".join(words),  # word timestamps; the gate compares to the text
            last_char_end_s=state["end"],
            character_cost=None,  # no usage metadata in the SSE stream
            request_id=None,
            error=error,
        )
