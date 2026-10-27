"""Pipecat end-to-end orchestration: offline tests (real Pipecat pipeline, fake transport).

The runtime adapter's real ``PipelineWorker`` / ``WorkerRunner`` run with the shared
``VoiceAgentLoop``, fake STT/LLM/TTS adapters and the real Phase 0 gateway. Only
``LiveKitTransport`` is replaced by an in-process fake (no LiveKit server, no network).
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from typing import Any, ClassVar

import pytest
from e2e_fakes import HAPPY_REPLIES, HAPPY_TRANSCRIPTS, FakeLLM, FakeSTT, FakeTTS, server_state

from voiceos.benchmark.binding import GatewayBinding
from voiceos.benchmark.e2e_gate import hard_failures
from voiceos.benchmark.runner import BENCH_TENANT, CANARY_TENANT
from voiceos.benchmark.runtimes import LiveSessionSpec, PipecatRuntimeAdapter
from voiceos.benchmark.voice_loop import TimedEvent, VoiceAgentLoop
from voiceos.booking.speech import BOOKING_SUCCESS

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("pipecat") is None,
    reason="optional voice-sdk group not installed (uv sync --group voice-sdk)",
)
CALLER = "synthetic-caller"
CALLER_AUDIO = b"\x01\x00" * 160  # 10 ms at 16 kHz
FOREIGN_AUDIO = b"\x7f\x7f" * 160  # another participant: must never reach STT
TOKEN = "room-scoped-token"  # noqa: S105 - fake value, no credential


def install_fake_transport(monkeypatch: pytest.MonkeyPatch, replies_expected: int) -> Any:
    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        BotStoppedSpeakingFrame,
        StartFrame,
        TTSAudioRawFrame,
        TTSStoppedFrame,
        UserAudioRawFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    class FakeInput(FrameProcessor):  # type: ignore[misc]
        def __init__(self, owner: Any) -> None:
            super().__init__()
            self.owner = owner

        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)
            await self.push_frame(frame, direction)
            if isinstance(frame, StartFrame):
                await self.owner.fire("on_connected", self.owner)
                self.owner.feeder = asyncio.ensure_future(self.feed())

        async def feed(self) -> None:
            while not self.owner.left:
                for user, audio in ((CALLER, CALLER_AUDIO), ("intruder", FOREIGN_AUDIO)):
                    frame = UserAudioRawFrame(
                        audio=audio, sample_rate=16_000, num_channels=1, user_id=user
                    )
                    await self.push_frame(frame)
                await asyncio.sleep(0.005)

    class FakeOutput(FrameProcessor):  # type: ignore[misc]
        def __init__(self, owner: Any) -> None:
            super().__init__()
            self.owner = owner
            self.speaking = False

        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, TTSAudioRawFrame):
                self.owner.audio.append(frame)
                if not self.speaking:
                    self.speaking = True
                    await self.push_frame(BotStartedSpeakingFrame(), FrameDirection.UPSTREAM)
                return
            if isinstance(frame, TTSStoppedFrame):
                self.speaking = False
                self.owner.replies += 1
                await self.push_frame(BotStoppedSpeakingFrame(), FrameDirection.UPSTREAM)
                if self.owner.replies == replies_expected:  # caller hangs up
                    self.owner.left = True
                    await self.owner.fire("on_participant_left", self.owner, CALLER, "left")
            await self.push_frame(frame, direction)

    class FakeTransport:
        instances: ClassVar[list[Any]] = []

        def __init__(self, *, url: str, token: str, room_name: str, params: Any) -> None:
            self.token, self.room_name, self.params = token, room_name, params
            self.participant_id = "pipecat-runtime"
            self.handlers: dict[str, Any] = {}
            self.audio: list[Any] = []
            self.replies = 0
            self.left = False
            self.feeder: asyncio.Future[None] | None = None
            self._in, self._out = FakeInput(self), FakeOutput(self)
            FakeTransport.instances.append(self)

        def event_handler(self, name: str) -> Any:
            def register(handler: Any) -> Any:
                self.handlers[name] = handler
                return handler

            return register

        async def fire(self, name: str, *args: Any) -> None:
            if name in self.handlers:
                await self.handlers[name](*args)

        def input(self) -> FakeInput:
            return self._in

        def output(self) -> FakeOutput:
            return self._out

    module = types.ModuleType("pipecat.transports.livekit.transport")
    module.LiveKitTransport = FakeTransport  # type: ignore[attr-defined]
    module.LiveKitParams = lambda **kw: types.SimpleNamespace(**kw)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pipecat.transports.livekit.transport", module)
    return FakeTransport


def spec(**overrides: Any) -> LiveSessionSpec:
    values: dict[str, Any] = {
        "url": "ws://127.0.0.1:7880", "room": "r", "caller_identity": CALLER,
        "max_turns": len(HAPPY_TRANSCRIPTS) + 1, "identity": "pipecat-runtime",
        "join_token": TOKEN, "timeout_s": 10.0, "session_timeout_s": 30.0,
    }  # fmt: skip
    return LiveSessionSpec(**(values | overrides))


def test_pipeline_runs_the_dialog_through_the_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    transport_cls = install_fake_transport(monkeypatch, replies_expected=len(HAPPY_TRANSCRIPTS))
    gateway, context, calendar, crm = server_state()
    events: list[TimedEvent] = []
    stt, tts = FakeSTT(HAPPY_TRANSCRIPTS), FakeTTS()
    agent = VoiceAgentLoop(
        stt, FakeLLM(HAPPY_REPLIES), tts, GatewayBinding(gateway, context),
        input_sample_rate_hz=16_000, endpointing_ms=500, emit=events.append,
    )  # fmt: skip

    observation = asyncio.run(PipecatRuntimeAdapter().run_live_session(spec(), agent))

    assert observation.error is None and observation.completed
    assert observation.joined_identity == "pipecat-runtime"
    [transport] = transport_cls.instances
    assert transport.token == TOKEN and transport.room_name == "r"
    assert transport.params.audio_out_end_silence_secs == 0
    assert [t.transcript for t in agent.turns] == HAPPY_TRANSCRIPTS
    assert tts.texts[3] == BOOKING_SUCCESS and transport.replies == len(HAPPY_TRANSCRIPTS)
    # same shared VoiceAgentLoop path: the server confirmation note precedes the booking
    notes = [m for m in agent.history if m.role == "tool" and m.content.startswith("Server-Status")]
    assert len(notes) == 1 and "slot_a_1000" in notes[0].content
    # assistant audio left through the Pipecat output, unchanged and at 24 kHz
    pcm = b"".join(f.audio for f in transport.audio)
    assert pcm == b"\x10\x00" * 2400 * len(HAPPY_TRANSCRIPTS)
    assert {f.sample_rate for f in transport.audio} == {24_000}
    # caller audio reached STT in 20 ms chunks; nobody else's audio did
    assert stt.chunks and all(c == CALLER_AUDIO * 2 for c in stt.chunks)
    # same server-side outcome as the LiveKit arm's offline test
    assert calendar.create_calls == 1
    assert [b.slot_id for b in calendar.bookings_for(BENCH_TENANT, "cal_bench")] == ["slot_a_1000"]
    assert not calendar.bookings_for(CANARY_TENANT, "cal_canary")
    assert hard_failures(gateway.calls, agent.turns, calendar, crm, context_unchanged=True) == []
    published = [e for e in events if e.name == "FIRST_ASSISTANT_AUDIO_PUBLISHED"]
    assert len(published) == len(HAPPY_TRANSCRIPTS)
    # caller left right after the last reply: no further turn, loop and pipeline ended
    assert not [e for e in events if e.turn == len(HAPPY_TRANSCRIPTS)]


def test_refuses_without_a_room_scoped_token(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_transport(monkeypatch, replies_expected=1)
    gateway, context, *_ = server_state()
    agent = VoiceAgentLoop(
        FakeSTT([]), FakeLLM([]), FakeTTS(), GatewayBinding(gateway, context),
        input_sample_rate_hz=16_000, endpointing_ms=500, emit=lambda _: None,
    )  # fmt: skip
    observation = asyncio.run(
        PipecatRuntimeAdapter().run_live_session(spec(join_token=None), agent)
    )
    assert observation.error == "JoinTokenNotConfigured" and not observation.completed
    assert gateway.calls == []


def test_pipecat_runtime_never_receives_server_credentials() -> None:
    """The harness gives Pipecat only a room-scoped token, never the API key/secret."""
    assert PipecatRuntimeAdapter.needs_worker_credentials is False
    assert "s3cr3t" not in repr(spec(worker_api_secret="s3cr3t"))  # noqa: S106
