"""Turn-taking gate: the two runtime arms with their *native* turn mechanics.

LiveKit Agents 1.8.3: ``AgentSession`` with its local Silero VAD (``inference.VAD``), the
local end-of-turn model (``TurnDetector(version="v1-mini")``), VAD-based interruption and
endpointing defaults. Our adapters are wired in through thin bridges: an ``stt.STT`` that
streams through ``DeepgramSTT``, and an ``Agent`` whose ``llm_node``/``tts_node`` call the
shared ``TurnTakingAgent`` (gateway, speech guard, ``CartesiaTTS``). The ``llm.LLM`` and
``tts.TTS`` objects are placeholders AgentSession requires; they never call a provider.
No livekit plugin, no LiveKit Cloud inference, no recording.

Pipecat 1.12.0: ``LiveKitTransport`` -> ``VADProcessor(SileroVADAnalyzer)`` -> STT bridge
-> ``UserTurnProcessor`` (default strategies: VAD/transcription start, local Smart Turn
v3 stop, interruptions on) -> turn bridge -> ``LiveKitTransport.output()``. No Pipecat
STT/LLM/TTS service.

Both arms: Deepgram ``Finalize`` on the runtime's VAD end; replies only from final STT
results (``TurnTakingAgent.commit``); explicit settings that would otherwise reach a
cloud service or act on partial text are switched off and documented.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterable, AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from voiceos.benchmark.ports import AdapterUnavailable, Probe
from voiceos.benchmark.runtimes import (
    LiveKitRuntimeAdapter,
    LiveObservation,
    PipecatRuntimeAdapter,
    _first_done,
)
from voiceos.benchmark.turn_taking import TurnTakingAgent
from voiceos.benchmark.voice_loop import AgentTurn

FRAME_MS = 20


@dataclass(frozen=True, slots=True)
class TurnSessionSpec:
    url: str
    room: str
    caller_identity: str
    identity: str = "voiceos-runtime"
    join_token: str | None = field(default=None, repr=False)  # room-scoped (Pipecat)
    worker_api_key: str | None = field(default=None, repr=False)  # dev placeholder (LiveKit)
    worker_api_secret: str | None = field(default=None, repr=False)
    dispatch: Callable[[str], Coroutine[Any, Any, None]] | None = None
    input_sample_rate_hz: int = 16_000
    output_sample_rate_hz: int = 24_000
    timeout_s: float = 20.0
    session_timeout_s: float = 120.0


# Settings that are pinned explicitly (documented in BENCHMARK_METHOD.md).
LIVEKIT_SETTINGS: dict[str, Any] = {
    "vad": "livekit.agents.inference.VAD(silero, defaults: min_speech 0.05 s, "
    "min_silence 0.25 s, activation 0.5)",
    "turn_detection": "TurnDetector(version='v1-mini') local; default 'v1' uses LiveKit Cloud",
    "endpointing": "defaults min_delay 0.5 s, max_delay 3.0 s",
    "interruption": "mode 'vad' (adaptive uses LiveKit Cloud); defaults min_duration 0.5 s, "
    "resume_false_interruption True, false_interruption_timeout 2.0 s",
    "preemptive_generation": "disabled (default enabled would start replies on non-final text)",
    "aec_warmup_duration": "None (default 3.0 s blocks interruptions; no acoustic echo path)",
    "record": "False",
    "text_input/text_output": "disabled",
}
PIPECAT_SETTINGS: dict[str, Any] = {
    "vad": "VADProcessor(SileroVADAnalyzer()) defaults: confidence 0.7, start 0.2 s, "
    "stop 0.2 s, min_volume 0.6",
    "turn_detection": "UserTurnProcessor default strategies: start VAD + transcription; "
    "stop TurnAnalyzer(LocalSmartTurnAnalyzerV3) waiting for a finalized transcript",
    "interruption": "enable_interruptions True (default), InterruptionFrame clears output",
    "user_turn_stop_timeout": "5.0 s (default)",
    "audio_out_end_silence_secs": "0",
}


def _chunks(pcm: bytes, rate: int) -> list[bytes]:
    size = rate * FRAME_MS // 1000 * 2
    return [pcm[i : i + size] for i in range(0, len(pcm), size)]


# =========================================================================================
# LiveKit Agents arm
# =========================================================================================


async def run_livekit_turn_session(
    adapter: LiveKitRuntimeAdapter, spec: TurnSessionSpec, agent: TurnTakingAgent
) -> LiveObservation:
    if not adapter.sdk_status().importable:
        raise AdapterUnavailable(Probe(False, ("livekit-agents not importable",)))
    from livekit import rtc
    from livekit.agents import (
        Agent,
        AgentServer,
        AgentSession,
        AutoSubscribe,
        JobContext,
        JobExecutorType,
        inference,
        llm,
        stt,
        tts,
    )
    from livekit.agents.inference.eot import TurnDetector
    from livekit.agents.voice import room_io

    dispatch = spec.dispatch
    if not (spec.worker_api_key and spec.worker_api_secret and dispatch):
        return LiveObservation(None, False, "WorkerRegistrationNotConfigured")

    class BridgeSTT(stt.STT):  # type: ignore[misc]
        """LiveKit STT interface over the existing DeepgramSTT adapter (no plugin)."""

        def __init__(self) -> None:
            super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
            self.active: Any = None

        @property
        def model(self) -> str:
            return "deepgram-adapter"

        @property
        def provider(self) -> str:
            return "voiceos"

        async def _recognize_impl(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("streaming only")

        def stream(self, *, language: Any = None, conn_options: Any = None) -> Any:
            from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

            return BridgeStream(
                stt=self, conn_options=conn_options or DEFAULT_API_CONNECT_OPTIONS,
                sample_rate=spec.input_sample_rate_hz,
            )  # fmt: skip

        async def finalize(self) -> None:
            if self.active is not None:
                agent.on_finalize_sent()
                with contextlib.suppress(Exception):
                    await self.active.finalize()

    class BridgeStream(stt.RecognizeStream):  # type: ignore[misc]
        async def _run(self) -> None:
            parent: BridgeSTT = self._stt
            async with agent.stt_session() as dg:
                parent.active = dg

                async def forward() -> None:
                    async for item in self._input_ch:
                        if isinstance(item, self._FlushSentinel):
                            continue  # turn ends are driven by VAD (see finalize)
                        await dg.send(bytes(item.data))

                sender = asyncio.ensure_future(forward())
                try:
                    async for ev in dg.events():
                        agent.on_stt(ev)
                        kinds = {
                            "interim": stt.SpeechEventType.INTERIM_TRANSCRIPT,
                            "final": stt.SpeechEventType.FINAL_TRANSCRIPT,
                        }
                        kind = kinds.get(ev.kind)
                        if kind is None or not ev.text:
                            continue
                        data = stt.SpeechData(language="de", text=ev.text)
                        self._event_ch.send_nowait(stt.SpeechEvent(type=kind, alternatives=[data]))
                finally:
                    parent.active = None
                    sender.cancel()
                    with contextlib.suppress(BaseException):
                        await sender

    class PlaceholderLLM(llm.LLM):  # type: ignore[misc]
        @property
        def model(self) -> str:
            return "voiceos-turn-agent"

        @property
        def provider(self) -> str:
            return "voiceos"

        def chat(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("llm_node is overridden; no provider call here")

    class PlaceholderTTS(tts.TTS):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(
                capabilities=tts.TTSCapabilities(streaming=False),
                sample_rate=spec.output_sample_rate_hz, num_channels=1,
            )  # fmt: skip

        def synthesize(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("tts_node is overridden; no provider call here")

    class TurnAgent(Agent):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(instructions="")
            self._index: int | None = None

        async def llm_node(
            self, chat_ctx: Any, tools: Any, model_settings: Any
        ) -> AsyncIterator[str]:
            committed = await agent.commit()  # final STT results only
            if committed is None:
                return
            self._index, transcript = committed
            reply = await agent.reply(self._index, transcript)
            agent.loop.turns.append(
                AgentTurn(self._index, transcript, reply.model_texts, reply.steps, reply.spoken,
                          0.0, reply.errors)
            )  # fmt: skip
            yield reply.spoken

        async def tts_node(
            self, text: AsyncIterable[str], model_settings: Any
        ) -> AsyncIterator[Any]:
            index = self._index if self._index is not None else -1
            spoken = "".join([part async for part in text])
            queue: asyncio.Queue[bytes | None] = asyncio.Queue()
            synth = asyncio.ensure_future(agent.speak(index, spoken, queue.put_nowait))
            synth.add_done_callback(lambda _: queue.put_nowait(None))
            rate = spec.output_sample_rate_hz
            first = True
            finished = False
            pending = b""
            try:
                while (pcm := await queue.get()) is not None:
                    pending += pcm
                    cut = len(pending) - len(pending) % (rate * FRAME_MS // 1000 * 2)
                    for chunk in _chunks(pending[:cut], rate):
                        if first:
                            first = False
                            agent.published(index)
                        yield rtc.AudioFrame(chunk, rate, 1, len(chunk) // 2)
                    pending = pending[cut:]
                if pending:
                    yield rtc.AudioFrame(pending, rate, 1, len(pending) // 2)
                finished = True
            finally:
                if not finished:  # cancelled by AgentSession (interruption)
                    agent.tts_stopped(index)
                    synth.cancel()

    loop = asyncio.get_running_loop()
    registered, finished = asyncio.Event(), asyncio.Event()
    seen: dict[str, Any] = {}
    server = AgentServer(
        job_executor_type=JobExecutorType.THREAD, ws_url=spec.url,
        api_key=spec.worker_api_key, api_secret=spec.worker_api_secret,
        host="127.0.0.1", port=0, num_idle_processes=0, max_retry=0,
    )  # fmt: skip
    server.on("worker_registered", lambda *_: loop.call_soon_threadsafe(registered.set))

    async def entrypoint(ctx: JobContext) -> None:  # job thread, own event loop
        try:
            await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
            seen["identity"] = ctx.room.local_participant.identity
            await asyncio.wait_for(
                ctx.wait_for_participant(identity=spec.caller_identity), spec.timeout_s
            )
            bridge = BridgeSTT()
            session = AgentSession(
                stt=bridge,
                llm=PlaceholderLLM(),
                tts=PlaceholderTTS(),
                vad=inference.VAD(),
                turn_handling={
                    "turn_detection": TurnDetector(version="v1-mini"),
                    "interruption": {"mode": "vad"},
                    "preemptive_generation": {"enabled": False},
                },
                aec_warmup_duration=None,
                user_away_timeout=None,
            )
            closed = asyncio.Event()
            pending: set[asyncio.Future[None]] = set()

            def on_user_state(ev: Any) -> None:
                if ev.new_state == "speaking":
                    agent.on_vad("start")
                elif ev.old_state == "speaking":
                    agent.on_vad("end")
                    pending.add(asyncio.ensure_future(bridge.finalize()))

            def on_speech(ev: Any) -> None:
                handle = ev.speech_handle
                handle._interrupt_fut.add_done_callback(lambda _: agent.interrupted())

            session.on("user_state_changed", on_user_state)
            session.on("speech_created", on_speech)
            session.on("close", lambda _ev: closed.set())
            await session.start(
                TurnAgent(),
                room=ctx.room,
                room_options=room_io.RoomOptions(
                    participant_identity=spec.caller_identity,
                    text_input=False,
                    text_output=False,
                    close_on_disconnect=True,
                ),
                record=False,
            )
            audio_out = session.output.audio  # observe pause/clear (no behavior change)
            if audio_out is not None:
                for name, kind in (("pause", "pause"), ("clear_buffer", "clear")):
                    original = getattr(audio_out, name)

                    def observed(*a: Any, _o: Any = original, _k: str = kind, **kw: Any) -> Any:
                        agent.audio_stop_requested(_k)
                        return _o(*a, **kw)

                    setattr(audio_out, name, observed)
                resume = audio_out.resume

                def resumed(*a: Any, **kw: Any) -> Any:
                    agent.audio_resumed()
                    return resume(*a, **kw)

                audio_out.resume = resumed
            await asyncio.wait_for(closed.wait(), spec.session_timeout_s)
            seen["completed"] = True
        except Exception as exc:  # recorded by class name only
            seen["error"] = type(exc).__name__
        finally:
            ctx.shutdown("voiceos turn-taking session done")
            loop.call_soon_threadsafe(finished.set)

    server.rtc_session(entrypoint, agent_name=adapter.agent_name)
    runner = asyncio.ensure_future(server.run(devmode=True))
    try:
        await _first_done(runner, registered, spec.timeout_s)
        await dispatch(adapter.agent_name)
        await _first_done(runner, finished, spec.session_timeout_s + spec.timeout_s)
    finally:
        await server.aclose()
        runner.cancel()
        with contextlib.suppress(BaseException):
            await runner
    return LiveObservation(seen.get("identity"), bool(seen.get("completed")), seen.get("error"))


# =========================================================================================
# Pipecat arm
# =========================================================================================


async def run_pipecat_turn_session(
    adapter: PipecatRuntimeAdapter, spec: TurnSessionSpec, agent: TurnTakingAgent
) -> LiveObservation:
    if not adapter.sdk_status().importable:
        raise AdapterUnavailable(Probe(False, ("pipecat-ai not importable",)))
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        BotStoppedSpeakingFrame,
        CancelFrame,
        EndFrame,
        InputAudioRawFrame,
        InterimTranscriptionFrame,
        InterruptionFrame,
        StartFrame,
        TranscriptionFrame,
        TTSAudioRawFrame,
        TTSStartedFrame,
        TTSStoppedFrame,
        UserStoppedSpeakingFrame,
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
    from pipecat.turns.user_turn_processor import UserTurnProcessor
    from pipecat.workers.runner import WorkerRunner

    if not spec.join_token:
        return LiveObservation(None, False, "JoinTokenNotConfigured")
    seen: dict[str, Any] = {}
    started, caller_left = asyncio.Event(), asyncio.Event()

    def stamp() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    class SttBridge(FrameProcessor):  # type: ignore[misc]
        """Caller audio -> DeepgramSTT; Finalize on VAD end; transcripts as frames."""

        def __init__(self) -> None:
            super().__init__()
            self._audio: asyncio.Queue[bytes | None] = asyncio.Queue()
            self._pending = bytearray()
            self._task: asyncio.Future[None] | None = None
            self._dg: Any = None
            self._last_text = ""

        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                await self.push_frame(frame, direction)
                self._task = asyncio.ensure_future(self._run())
                return
            if isinstance(frame, InputAudioRawFrame):
                if getattr(frame, "user_id", None) == spec.caller_identity:
                    self._pending += frame.audio
                    size = spec.input_sample_rate_hz * FRAME_MS // 1000 * 2
                    while len(self._pending) >= size:
                        self._audio.put_nowait(bytes(self._pending[:size]))
                        del self._pending[:size]
                await self.push_frame(frame, direction)  # Smart Turn analyses the audio
                return
            if isinstance(frame, VADUserStartedSpeakingFrame):
                agent.on_vad("start")
            elif isinstance(frame, VADUserStoppedSpeakingFrame):
                agent.on_vad("end")
                if self._dg is not None:
                    agent.on_finalize_sent()
                    with contextlib.suppress(Exception):
                        await self._dg.finalize()
            elif isinstance(frame, EndFrame | CancelFrame):
                self._audio.put_nowait(None)
            await self.push_frame(frame, direction)

        async def _run(self) -> None:
            async with agent.stt_session() as dg:
                self._dg = dg

                async def forward() -> None:
                    while (chunk := await self._audio.get()) is not None:
                        await dg.send(chunk)

                sender = asyncio.ensure_future(forward())
                try:
                    async for ev in dg.events():
                        agent.on_stt(ev)
                        if ev.kind == "interim" and ev.text:
                            await self.push_frame(
                                InterimTranscriptionFrame(ev.text, spec.caller_identity, stamp())
                            )
                        elif ev.kind == "final" and (ev.text or ev.from_finalize):
                            self._last_text = ev.text or self._last_text
                            await self.push_frame(
                                TranscriptionFrame(
                                    ev.text or self._last_text, spec.caller_identity, stamp(),
                                    finalized=ev.from_finalize,
                                )
                            )  # fmt: skip
                finally:
                    self._dg = None
                    sender.cancel()
                    with contextlib.suppress(BaseException):
                        await sender

    class TurnBridge(FrameProcessor):  # type: ignore[misc]
        """Native turn end -> shared reply -> TTS frames; native interruption -> stop."""

        def __init__(self) -> None:
            super().__init__()
            self._task: asyncio.Future[None] | None = None
            self._index = -1
            self.bot_stopped = asyncio.Event()
            self._bot_speaking = False

        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, InputAudioRawFrame):
                return  # caller audio is never echoed to the output
            upstream = direction == FrameDirection.UPSTREAM
            if isinstance(frame, StartFrame):
                started.set()
            elif isinstance(frame, UserStoppedSpeakingFrame):
                self._task = asyncio.ensure_future(self._respond())
            elif isinstance(frame, InterruptionFrame):
                agent.interrupted()
                if self._bot_speaking:  # forwarded to the output, which clears its audio
                    agent.audio_stop_requested("interruption_frame")
                if self._task is not None and not self._task.done():
                    agent.tts_stopped(self._index)
                    self._task.cancel()
            elif isinstance(frame, BotStartedSpeakingFrame) and upstream:
                self._bot_speaking = True
                agent.published(self._index)
            elif isinstance(frame, BotStoppedSpeakingFrame) and upstream:
                self._bot_speaking = False
                self.bot_stopped.set()
            await self.push_frame(frame, direction)

        async def _respond(self) -> None:
            committed = await agent.commit()  # final STT results only
            if committed is None:
                return
            self._index, transcript = committed
            reply = await agent.reply(self._index, transcript)
            agent.loop.turns.append(
                AgentTurn(self._index, transcript, reply.model_texts, reply.steps, reply.spoken,
                          0.0, reply.errors)
            )  # fmt: skip
            await self.push_frame(TTSStartedFrame())
            queue: asyncio.Queue[bytes | None] = asyncio.Queue()
            synth = asyncio.ensure_future(agent.speak(self._index, reply.spoken, queue.put_nowait))
            synth.add_done_callback(lambda _: queue.put_nowait(None))
            try:
                while (pcm := await queue.get()) is not None:
                    await self.push_frame(TTSAudioRawFrame(pcm, spec.output_sample_rate_hz, 1))
                await self.push_frame(TTSStoppedFrame())
            finally:
                if not synth.done():
                    synth.cancel()

    transport = LiveKitTransport(
        url=spec.url,
        token=spec.join_token,
        room_name=spec.room,
        params=LiveKitParams(
            audio_in_enabled=True, audio_out_enabled=True, audio_out_end_silence_secs=0
        ),
    )

    @transport.event_handler("on_connected")  # type: ignore[untyped-decorator]
    async def _on_connected(*_: Any) -> None:
        seen["identity"] = transport.participant_id

    @transport.event_handler("on_participant_left")  # type: ignore[untyped-decorator]
    async def _on_left(_transport: Any, participant_id: str, *_: Any) -> None:
        if participant_id == spec.caller_identity:
            caller_left.set()

    worker = PipelineWorker(
        Pipeline([
            transport.input(), VADProcessor(vad_analyzer=SileroVADAnalyzer()), SttBridge(),
            UserTurnProcessor(), TurnBridge(), transport.output(),
        ]),
        params=PipelineParams(
            audio_in_sample_rate=spec.input_sample_rate_hz,
            audio_out_sample_rate=spec.output_sample_rate_hz,
        ),
        enable_rtvi=False,
        idle_timeout_secs=None,
    )  # fmt: skip
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    run = asyncio.ensure_future(runner.run())
    try:
        await _first_done(run, started, spec.timeout_s)
        await asyncio.wait_for(caller_left.wait(), spec.session_timeout_s)
        seen["completed"] = True
    except Exception as exc:  # recorded by class name only
        seen["error"] = type(exc).__name__
    finally:
        if not run.done():
            await worker.queue_frame(EndFrame())
            try:
                await asyncio.wait_for(asyncio.shield(run), spec.timeout_s)
            except TimeoutError:
                seen.setdefault("error", "EndTimeout")
                await worker.cancel()
                with contextlib.suppress(BaseException):
                    await asyncio.wait_for(run, spec.timeout_s)
    return LiveObservation(seen.get("identity"), bool(seen.get("completed")), seen.get("error"))
