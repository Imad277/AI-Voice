"""Runtime adapters behind one contract (``ports.RuntimeAdapter``).

- ``ReferenceRuntime``: deterministic in-process turn loop. It validates the harness, the
  gateway boundary and the result pipeline. It is not a runtime candidate and its
  timings describe only in-process overhead.
- ``LiveKitRuntimeAdapter`` / ``PipecatRuntimeAdapter``: the two candidates. Their SDKs
  come from the optional ``voice-sdk`` dependency group and are imported only inside
  ``_import_capabilities`` and ``check_local_session`` (lazily). The first reports a
  local SDK capability status without any connection; the second joins and leaves a room
  on a loopback-only LiveKit dev server, with no providers and no business tools. The
  synchronous ``run_session`` contract still refuses (it has no live audio path).
- ``run_live_session`` (both candidates): the end-to-end gates' live path. The
  provider-neutral ``VoiceAgentLoop`` runs the turns through the existing adapters and the
  server-side binding. LiveKit Agents owns worker registration, explicit dispatch, the
  job and the room. Pipecat runs the loop inside the pipeline
  ``LiveKitTransport.input() -> turns -> LiveKitTransport.output()`` and owns lifecycle,
  frame flow, transport and audio I/O. Neither uses its own STT/LLM/TTS plugins or
  services: that would be a second provider implementation beside the verified adapters.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.metadata
import os
import time
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from voiceos.benchmark.ports import (
    AdapterInfo,
    AdapterKind,
    AdapterUnavailable,
    Clock,
    Event,
    LLMAdapter,
    LocalObservation,
    LocalSessionSpec,
    Message,
    Probe,
    ServerBinding,
    SessionSpec,
    SessionTrace,
    STTAdapter,
    TTSAdapter,
    TurnTrace,
)
from voiceos.core.tools import ToolName, ToolRequest, ToolResult

if TYPE_CHECKING:
    from voiceos.benchmark.voice_loop import VoiceAgentLoop

_KNOWN_TOOLS = {t.value for t in ToolName}


def safe_tool_name(name: str) -> str:
    """Model-proposed tool names are untrusted text; only allowlisted names reach telemetry."""
    return name if name in _KNOWN_TOOLS else "<unknown>"


class ReferenceRuntime:
    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(AdapterKind.RUNTIME, "voiceos-reference", None, "phase1")

    def probe(self) -> Probe:
        return Probe(True)

    def run_session(
        self,
        spec: SessionSpec,
        stt: STTAdapter,
        llm: LLMAdapter,
        tts: TTSAdapter,
        binding: ServerBinding,
        clock: Clock,
    ) -> SessionTrace:
        start = clock()
        events: list[Event] = []

        def emit(name: str, turn: int | None = None, **attrs: str) -> None:
            events.append(Event(name, clock() - start, turn, attrs))

        emit("SESSION_STARTED")
        startup_ns = events[-1].t_ns
        history: list[Message] = []
        turns: list[TurnTrace] = []
        errors: list[str] = []

        for i, turn in enumerate(spec.turns):
            try:
                if turn.barge_in:
                    emit("INTERRUPT_OPPORTUNITY", i)
                emit("USER_AUDIO_END", i)
                transcript = stt.transcribe(turn.segment).text
                emit("STT_FINAL", i)
                binding.user_reply(transcript)
                history.append(Message("user", transcript))

                emit("LLM_REQUESTED", i)
                parts: list[str] = []
                proposal: ToolRequest | None = None
                for n, delta in enumerate(llm.stream(history)):
                    if n == 0:
                        emit("LLM_FIRST_TOKEN", i)
                    parts.append(delta.text)
                    proposal = delta.tool or proposal
                model_text = "".join(parts).strip()

                result: ToolResult | None = None
                if proposal is not None:
                    tool = safe_tool_name(proposal.tool_name)
                    emit("TOOL_PROPOSED", i, tool=tool)
                    result = binding.execute(proposal)
                    emit(
                        f"TOOL_{result.decision.value}",
                        i,
                        tool=tool,
                        outcome=result.outcome.value,
                        reason=result.reason.value if result.reason else "",
                    )
                    history.append(
                        Message("tool", f"{tool} {result.decision.value} {result.outcome.value}")
                    )

                spoken = binding.render(
                    model_text, proposal.tool_name if proposal else None, result
                )
                history.append(Message("assistant", spoken))
                emit("TTS_REQUESTED", i)
                for n, _chunk in enumerate(tts.stream(spoken)):
                    if n == 0:
                        emit("TTS_FIRST_AUDIO", i)
                        emit("AI_AUDIO_START", i)
                emit("AI_AUDIO_END", i)
                turns.append(TurnTrace(transcript, spoken, proposal, result))
            except AdapterUnavailable:
                raise
            except Exception as exc:  # any adapter failure: recorded, session aborted
                errors.append(f"turn {i}: {type(exc).__name__}")
                emit("SESSION_ERROR", i, error=type(exc).__name__)
                break

        emit("SESSION_ENDED")
        return SessionTrace(tuple(events), tuple(turns), startup_ns, tuple(errors))


@dataclass(frozen=True, slots=True)
class SdkStatus:
    """Local, offline SDK check: installed version, importability, expected entry points."""

    distribution: str
    pinned: str
    installed_version: str | None
    importable: bool
    import_error: str | None  # exception class name only
    capabilities: Mapping[str, bool]


def _attr(module: str, name: str) -> object | None:
    """Import ``module`` (no instances, no connections) and return ``name`` or None."""
    try:
        return getattr(importlib.import_module(module), name, None)
    except Exception:  # any import-time failure means "not usable here"
        return None


class _SdkRuntimeCandidate:
    provider: str
    distribution: str  # PyPI distribution name
    pinned: str  # exact version from the voice-sdk dependency group

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = os.environ if env is None else env

    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(AdapterKind.RUNTIME, self.provider, None, self._installed_version())

    def _installed_version(self) -> str | None:
        try:
            return importlib.metadata.version(self.distribution)
        except importlib.metadata.PackageNotFoundError:
            return None

    def _import_capabilities(self) -> dict[str, bool]:
        raise NotImplementedError

    def sdk_status(self) -> SdkStatus:
        version = self._installed_version()
        capabilities: dict[str, bool] = {}
        error: str | None = None
        if version is not None:
            try:
                capabilities = self._import_capabilities()
            except Exception as exc:  # recorded by class name; messages may leak paths
                error = type(exc).__name__
        return SdkStatus(
            self.distribution,
            self.pinned,
            version,
            version is not None and error is None,
            error,
            capabilities,
        )

    def probe(self) -> Probe:
        sdk = self.sdk_status()
        missing = []
        if sdk.installed_version is None:
            missing.append(f"SDK {self.distribution} not installed (uv sync --group voice-sdk)")
        elif not sdk.importable:
            missing.append(f"SDK {self.distribution} import failed: {sdk.import_error}")
        elif sdk.installed_version != sdk.pinned:
            missing.append(
                f"SDK {self.distribution} {sdk.installed_version} is not the pinned {sdk.pinned}"
            )
        missing.extend(
            f"SDK capability missing: {name}" for name, ok in sdk.capabilities.items() if not ok
        )
        for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
            if not self._env.get(name):
                missing.append(f"{name} not provided (shared LiveKit transport)")
        missing.append("provider credentials for the shared STT/LLM/TTS baseline not provided")
        missing.append("SDK session wiring not implemented in Phase 1 (blocked on the above)")
        return Probe(False, tuple(missing))

    def run_session(
        self,
        spec: SessionSpec,
        stt: STTAdapter,
        llm: LLMAdapter,
        tts: TTSAdapter,
        binding: ServerBinding,
        clock: Clock,
    ) -> SessionTrace:
        raise AdapterUnavailable(self.probe())

    needs_worker_credentials = False

    async def check_local_session(self, spec: LocalSessionSpec) -> LocalObservation:
        """Join a room on the local dev server, see one media frame, leave. No providers."""
        sdk = self.sdk_status()
        if not sdk.importable:
            raise AdapterUnavailable(Probe(False, (f"SDK {self.distribution} not importable",)))
        try:
            return await self._local_session(spec)
        except Exception as exc:  # recorded by class name only
            return LocalObservation(None, None, type(exc).__name__)

    async def _local_session(self, spec: LocalSessionSpec) -> LocalObservation:
        raise NotImplementedError


async def _first_audio_frame(rtc: Any, room: Any, timeout_s: float) -> bool:
    """True once any subscribed remote audio track delivers a non-empty frame."""
    got = asyncio.Event()
    readers: list[asyncio.Task[None]] = []

    def watch(track: Any, *_: Any) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return

        async def read() -> None:
            async for event in rtc.AudioStream(track):
                if event.frame.samples_per_channel:
                    got.set()
                    return

        readers.append(asyncio.ensure_future(read()))

    room.on("track_subscribed", watch)
    for participant in room.remote_participants.values():
        for publication in participant.track_publications.values():
            if publication.track is not None:
                watch(publication.track)
    try:
        await asyncio.wait_for(got.wait(), timeout_s)
    except TimeoutError:
        return False
    finally:
        for reader in readers:
            reader.cancel()
    return True


async def _first_done(task: asyncio.Future[Any], event: asyncio.Event, timeout_s: float) -> None:
    """Wait for ``event``; fail fast if ``task`` ends first (e.g. connection refused)."""
    waiter = asyncio.ensure_future(event.wait())
    try:
        await asyncio.wait({task, waiter}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED)
    finally:
        waiter.cancel()
    if event.is_set():
        return
    if task.done() and task.exception() is not None:
        raise task.exception()  # type: ignore[misc]
    raise TimeoutError


@dataclass(frozen=True, slots=True)
class LiveSessionSpec:
    """Everything the runtime needs for one live job. No tenant, scopes or provider keys."""

    url: str
    room: str
    caller_identity: str
    max_turns: int
    identity: str = "voiceos-runtime"  # used by runtimes that join with a token
    join_token: str | None = field(default=None, repr=False)  # room-scoped (Pipecat)
    worker_api_key: str | None = field(default=None, repr=False)  # dev placeholder (LiveKit)
    worker_api_secret: str | None = field(default=None, repr=False)
    dispatch: Callable[[str], Coroutine[Any, Any, None]] | None = None
    input_sample_rate_hz: int = 16_000
    output_sample_rate_hz: int = 24_000
    timeout_s: float = 20.0
    session_timeout_s: float = 300.0


@dataclass(frozen=True, slots=True)
class LiveObservation:
    joined_identity: str | None
    completed: bool  # the agent loop returned normally (caller left or max turns)
    error: str | None  # exception class name only


async def _subscribed_audio(rtc: Any, room: Any, participant: Any, timeout_s: float) -> Any:
    """The participant's first subscribed audio track."""
    for publication in participant.track_publications.values():
        if publication.track is not None and publication.kind == rtc.TrackKind.KIND_AUDIO:
            return publication.track
    found: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

    def on_subscribed(track: Any, _publication: Any, who: Any) -> None:
        audio = track.kind == rtc.TrackKind.KIND_AUDIO
        if audio and who.identity == participant.identity and not found.done():
            found.set_result(track)

    room.on("track_subscribed", on_subscribed)
    try:
        return await asyncio.wait_for(found, timeout_s)
    finally:
        room.off("track_subscribed", on_subscribed)


class _TrackSink:
    """Assistant PCM -> 20 ms frames -> LiveKit ``AudioSource`` (published track)."""

    def __init__(self, rtc: Any, source: Any, sample_rate_hz: int) -> None:
        self._rtc, self._source, self._rate = rtc, source, sample_rate_hz
        self._samples = sample_rate_hz // 50
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._pump: asyncio.Future[None] | None = None
        self._first: float | None = None

    def write(self, pcm: bytes) -> None:
        if self._pump is None:
            self._pump = asyncio.ensure_future(self._run())
        self._queue.put_nowait(pcm)

    async def _run(self) -> None:
        size = self._samples * 2
        pending = bytearray()
        while (chunk := await self._queue.get()) is not None:
            pending += chunk
            while len(pending) >= size:
                await self._capture(bytes(pending[:size]))
                del pending[:size]
        if pending:
            await self._capture(bytes(pending) + b"\x00" * (size - len(pending)))

    async def _capture(self, data: bytes) -> None:
        frame = self._rtc.AudioFrame(data, self._rate, 1, self._samples)
        if self._first is None:
            self._first = time.monotonic()
        await self._source.capture_frame(frame)

    async def drain(self) -> float | None:
        if self._pump is None:
            return None
        self._queue.put_nowait(None)
        await self._pump
        self._pump = None
        await self._source.wait_for_playout()
        first, self._first = self._first, None
        return first


class LiveKitRuntimeAdapter(_SdkRuntimeCandidate):
    provider, distribution, pinned = "livekit-agents", "livekit-agents", "1.8.3"
    needs_worker_credentials = True  # worker registration protocol requires API key/secret
    agent_name = "voiceos-bench-local"  # explicit dispatch only; never auto-joins other rooms

    async def _local_session(self, spec: LocalSessionSpec) -> LocalObservation:
        from livekit import rtc
        from livekit.agents import AgentServer, JobContext, JobExecutorType

        if not (spec.worker_api_key and spec.worker_api_secret and spec.dispatch):
            return LocalObservation(None, None, "WorkerRegistrationNotConfigured")

        loop = asyncio.get_running_loop()
        registered, finished = asyncio.Event(), asyncio.Event()
        seen: dict[str, Any] = {}
        server = AgentServer(
            job_executor_type=JobExecutorType.THREAD,  # in-process; no extra process pool
            ws_url=spec.url,
            api_key=spec.worker_api_key,
            api_secret=spec.worker_api_secret,
            host="127.0.0.1",
            port=0,
            num_idle_processes=0,
            max_retry=0,
        )
        server.on("worker_registered", lambda *_: loop.call_soon_threadsafe(registered.set))

        async def entrypoint(ctx: JobContext) -> None:  # runs on the job thread's own loop
            try:
                await ctx.connect()
                seen["identity"] = ctx.room.local_participant.identity
                if spec.on_joined is not None:
                    await asyncio.wrap_future(
                        asyncio.run_coroutine_threadsafe(spec.on_joined(), loop)
                    )
                seen["media"] = await _first_audio_frame(rtc, ctx.room, spec.media_timeout_s)
            except Exception as exc:
                seen["error"] = type(exc).__name__
            finally:
                ctx.shutdown("voiceos local session check done")
                loop.call_soon_threadsafe(finished.set)

        server.rtc_session(entrypoint, agent_name=self.agent_name)
        runner = asyncio.ensure_future(server.run(devmode=True))
        try:
            await _first_done(runner, registered, spec.timeout_s)
            await spec.dispatch(self.agent_name)
            await _first_done(runner, finished, spec.timeout_s)
        finally:
            await server.aclose()
            runner.cancel()
            with contextlib.suppress(BaseException):
                await runner
        return LocalObservation(seen.get("identity"), seen.get("media"), seen.get("error"))

    async def run_live_session(
        self, spec: LiveSessionSpec, agent: VoiceAgentLoop
    ) -> LiveObservation:
        """Serve one dispatched job: hear the caller, run ``agent`` turns, speak back, leave."""
        sdk = self.sdk_status()
        if not sdk.importable:
            raise AdapterUnavailable(Probe(False, (f"SDK {self.distribution} not importable",)))
        from livekit import rtc
        from livekit.agents import AgentServer, AutoSubscribe, JobContext, JobExecutorType

        dispatch = spec.dispatch
        if not (spec.worker_api_key and spec.worker_api_secret and dispatch):
            return LiveObservation(None, False, "WorkerRegistrationNotConfigured")
        loop = asyncio.get_running_loop()
        registered, finished = asyncio.Event(), asyncio.Event()
        seen: dict[str, Any] = {}
        server = AgentServer(
            job_executor_type=JobExecutorType.THREAD,
            ws_url=spec.url,
            api_key=spec.worker_api_key,
            api_secret=spec.worker_api_secret,
            host="127.0.0.1",
            port=0,
            num_idle_processes=0,
            max_retry=0,
        )
        server.on("worker_registered", lambda *_: loop.call_soon_threadsafe(registered.set))

        async def entrypoint(ctx: JobContext) -> None:  # runs on the job thread's own loop
            reader: asyncio.Future[None] | None = None
            try:
                await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
                seen["identity"] = ctx.room.local_participant.identity
                caller = await asyncio.wait_for(
                    ctx.wait_for_participant(identity=spec.caller_identity), spec.timeout_s
                )
                track = await _subscribed_audio(rtc, ctx.room, caller, spec.timeout_s)
                frames: asyncio.Queue[bytes | None] = asyncio.Queue()
                state = {"listening": False, "gone": False}

                async def read() -> None:
                    stream = rtc.AudioStream(
                        track, sample_rate=spec.input_sample_rate_hz, num_channels=1,
                        frame_size_ms=20,
                    )  # fmt: skip
                    async for event in stream:
                        if state[
                            "listening"
                        ]:  # half duplex: caller audio while speaking is dropped
                            frames.put_nowait(bytes(event.frame.data))
                    frames.put_nowait(None)

                def left(participant: Any) -> None:
                    if participant.identity == spec.caller_identity:
                        frames.put_nowait(None)

                ctx.room.on("participant_disconnected", left)
                reader = asyncio.ensure_future(read())

                source = rtc.AudioSource(spec.output_sample_rate_hz, 1)
                published = rtc.LocalAudioTrack.create_audio_track("assistant", source)
                options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
                await ctx.room.local_participant.publish_track(published, options)

                async def caller_audio() -> AsyncIterator[bytes]:
                    try:
                        while (chunk := await frames.get()) is not None:
                            yield chunk
                        state["gone"] = True
                    finally:
                        state["listening"] = False

                async def next_frames() -> AsyncIterator[bytes] | None:
                    if state["gone"]:
                        return None
                    while not frames.empty():  # stale audio from before this turn
                        if frames.get_nowait() is None:
                            state["gone"] = True
                            return None
                    state["listening"] = True
                    return caller_audio()

                sink = _TrackSink(rtc, source, spec.output_sample_rate_hz)
                await asyncio.wait_for(
                    agent.run(next_frames, sink, max_turns=spec.max_turns), spec.session_timeout_s
                )
                seen["completed"] = True
            except Exception as exc:  # recorded by class name only
                seen["error"] = type(exc).__name__
            finally:
                if reader is not None:
                    reader.cancel()
                ctx.shutdown("voiceos e2e session done")
                loop.call_soon_threadsafe(finished.set)

        server.rtc_session(entrypoint, agent_name=self.agent_name)
        runner = asyncio.ensure_future(server.run(devmode=True))
        try:
            await _first_done(runner, registered, spec.timeout_s)
            await dispatch(self.agent_name)
            await _first_done(runner, finished, spec.session_timeout_s + spec.timeout_s)
        finally:
            await server.aclose()
            runner.cancel()
            with contextlib.suppress(BaseException):
                await runner
        return LiveObservation(seen.get("identity"), bool(seen.get("completed")), seen.get("error"))

    def _import_capabilities(self) -> dict[str, bool]:
        from livekit import agents

        capabilities = {
            name: hasattr(agents, name) for name in ("AgentSession", "Agent", "JobContext")
        }
        capabilities["LiveKitRtcRoom"] = _attr("livekit.rtc", "Room") is not None
        return capabilities


class PipecatRuntimeAdapter(_SdkRuntimeCandidate):
    provider, distribution, pinned = "pipecat", "pipecat-ai", "1.12.0"

    def _import_capabilities(self) -> dict[str, bool]:
        from pipecat.pipeline import pipeline, worker
        from pipecat.processors import frame_processor
        from pipecat.workers import runner

        # Transport parity: Pipecat's LiveKit transport (pipecat-ai[livekit] extra) must sit
        # on the very same livekit.rtc media layer that livekit-agents uses.
        transport = "pipecat.transports.livekit.transport"
        transport_rtc = _attr(transport, "rtc")
        return {
            "Pipeline": hasattr(pipeline, "Pipeline"),
            "PipelineWorker": hasattr(worker, "PipelineWorker"),
            "WorkerRunner": hasattr(runner, "WorkerRunner"),
            "FrameProcessor": hasattr(frame_processor, "FrameProcessor"),
            "LiveKitTransport": _attr(transport, "LiveKitTransport") is not None,
            "LiveKitParams": _attr(transport, "LiveKitParams") is not None,
            "SharedLiveKitRtc": transport_rtc is not None
            and transport_rtc is _attr("livekit", "rtc"),
        }

    async def run_live_session(
        self, spec: LiveSessionSpec, agent: VoiceAgentLoop
    ) -> LiveObservation:
        """Join with a room-scoped token, run ``agent`` turns in a pipeline, speak, leave."""
        sdk = self.sdk_status()
        if not sdk.importable:
            raise AdapterUnavailable(Probe(False, (f"SDK {self.distribution} not importable",)))
        from pipecat.frames.frames import (
            BotStartedSpeakingFrame,
            BotStoppedSpeakingFrame,
            EndFrame,
            InputAudioRawFrame,
            StartFrame,
            TTSAudioRawFrame,
            TTSStartedFrame,
            TTSStoppedFrame,
        )
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.worker import PipelineParams, PipelineWorker
        from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
        from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
        from pipecat.workers.runner import WorkerRunner

        if not spec.join_token:
            return LiveObservation(None, False, "JoinTokenNotConfigured")
        seen: dict[str, Any] = {}
        started = asyncio.Event()
        frames: asyncio.Queue[bytes | None] = asyncio.Queue()
        state = {"listening": False, "gone": False}
        chunk = spec.input_sample_rate_hz // 50 * 2  # 20 ms, as in the LiveKit arm

        class VoiceTurns(FrameProcessor):  # type: ignore[misc]
            """Caller audio in (half duplex), assistant audio out; everything else passes."""

            def __init__(self) -> None:
                super().__init__()
                self.pending = bytearray()
                self.bot_started: asyncio.Event = asyncio.Event()
                self.bot_stopped: asyncio.Event = asyncio.Event()
                self.started_at: float | None = None

            async def process_frame(self, frame: Any, direction: Any) -> None:
                await super().process_frame(frame, direction)
                if isinstance(frame, InputAudioRawFrame):  # consumed here, never echoed
                    if state["listening"] and getattr(frame, "user_id", None) == (
                        spec.caller_identity
                    ):
                        self.pending += frame.audio
                        while len(self.pending) >= chunk:
                            frames.put_nowait(bytes(self.pending[:chunk]))
                            del self.pending[:chunk]
                    return
                upstream = direction == FrameDirection.UPSTREAM
                if isinstance(frame, BotStartedSpeakingFrame) and upstream:
                    if self.started_at is None:
                        self.started_at = time.monotonic()
                    self.bot_started.set()
                elif isinstance(frame, BotStoppedSpeakingFrame) and upstream:
                    self.bot_stopped.set()
                await self.push_frame(frame, direction)
                if isinstance(frame, StartFrame):
                    started.set()

        turns = VoiceTurns()

        class PipelineSink:
            """Assistant PCM -> TTS frames -> Pipecat output transport (published track)."""

            def __init__(self) -> None:
                self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()
                self._pump: asyncio.Future[None] | None = None

            def write(self, pcm: bytes) -> None:
                if self._pump is None:
                    turns.bot_stopped.clear()
                    turns.started_at = None
                    self._pump = asyncio.ensure_future(self._run())
                self._queue.put_nowait(pcm)

            async def _run(self) -> None:
                await turns.push_frame(TTSStartedFrame())
                while (pcm := await self._queue.get()) is not None:
                    await turns.push_frame(TTSAudioRawFrame(pcm, spec.output_sample_rate_hz, 1))
                await turns.push_frame(TTSStoppedFrame())

            async def drain(self) -> float | None:
                if self._pump is None:
                    return None
                self._queue.put_nowait(None)
                await self._pump
                self._pump = None
                # BotStoppedSpeaking: all audio handed to the LiveKit audio source
                await asyncio.wait_for(turns.bot_stopped.wait(), spec.session_timeout_s)
                return turns.started_at

        transport = LiveKitTransport(
            url=spec.url,
            token=spec.join_token,
            room_name=spec.room,
            params=LiveKitParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_out_end_silence_secs=0,  # no trailing silence after EndFrame
            ),
        )

        @transport.event_handler("on_connected")  # type: ignore[untyped-decorator]
        async def _on_connected(*_: Any) -> None:
            seen["identity"] = transport.participant_id

        @transport.event_handler("on_participant_left")  # type: ignore[untyped-decorator]
        async def _on_left(_transport: Any, participant_id: str, *_: Any) -> None:
            if participant_id == spec.caller_identity:
                frames.put_nowait(None)

        async def caller_audio() -> AsyncIterator[bytes]:
            try:
                while (item := await frames.get()) is not None:
                    yield item
                state["gone"] = True
            finally:
                state["listening"] = False

        async def next_frames() -> AsyncIterator[bytes] | None:
            if state["gone"]:
                return None
            while not frames.empty():  # stale audio from before this turn
                if frames.get_nowait() is None:
                    state["gone"] = True
                    return None
            turns.pending.clear()
            state["listening"] = True
            return caller_audio()

        worker = PipelineWorker(
            Pipeline([transport.input(), turns, transport.output()]),
            params=PipelineParams(
                audio_in_sample_rate=spec.input_sample_rate_hz,
                audio_out_sample_rate=spec.output_sample_rate_hz,
            ),
            enable_rtvi=False,
            idle_timeout_secs=None,
        )
        runner = WorkerRunner(handle_sigint=False)
        await runner.add_workers(worker)
        run = asyncio.ensure_future(runner.run())
        try:
            await _first_done(run, started, spec.timeout_s)
            await asyncio.wait_for(
                agent.run(next_frames, PipelineSink(), max_turns=spec.max_turns),
                spec.session_timeout_s,
            )
            seen["completed"] = True
        except Exception as exc:  # recorded by class name only
            seen["error"] = type(exc).__name__
        finally:
            if not run.done():
                await worker.queue_frame(EndFrame())  # graceful: flush, stop, disconnect
                try:
                    await asyncio.wait_for(asyncio.shield(run), spec.timeout_s)
                except TimeoutError:
                    seen.setdefault("error", "EndTimeout")
                    await worker.cancel()
                    with contextlib.suppress(BaseException):
                        await asyncio.wait_for(run, spec.timeout_s)
        return LiveObservation(seen.get("identity"), bool(seen.get("completed")), seen.get("error"))

    async def _local_session(self, spec: LocalSessionSpec) -> LocalObservation:
        from pipecat.frames.frames import InputAudioRawFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.worker import PipelineWorker
        from pipecat.processors.frame_processor import FrameProcessor
        from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
        from pipecat.workers.runner import WorkerRunner

        connected, first_audio = asyncio.Event(), asyncio.Event()

        class AudioProbe(FrameProcessor):  # type: ignore[misc]
            async def process_frame(self, frame: Any, direction: Any) -> None:
                await super().process_frame(frame, direction)
                if isinstance(frame, InputAudioRawFrame):
                    first_audio.set()
                await self.push_frame(frame, direction)

        transport = LiveKitTransport(
            url=spec.url,
            token=spec.join_token,
            room_name=spec.room,
            params=LiveKitParams(audio_in_enabled=True, audio_out_enabled=False),
        )

        @transport.event_handler("on_connected")  # type: ignore[untyped-decorator]
        async def _on_connected(*_: Any) -> None:
            connected.set()

        worker = PipelineWorker(
            Pipeline([transport.input(), AudioProbe()]), enable_rtvi=False, idle_timeout_secs=None
        )
        runner = WorkerRunner(handle_sigint=False)
        await runner.add_workers(worker)
        run = asyncio.ensure_future(runner.run())
        media: bool | None = None
        try:
            await _first_done(run, connected, spec.timeout_s)
            if spec.on_joined is not None:
                await spec.on_joined()
            try:
                await asyncio.wait_for(first_audio.wait(), spec.media_timeout_s)
                media = True
            except TimeoutError:
                media = False
        finally:
            await worker.cancel()
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(run, spec.timeout_s)
        return LocalObservation(spec.identity, media, None)
