"""LiveKit end-to-end gate: offline tests (fake SDKs and adapters, no network, no key).

Covers the agent turn loop against the real Phase 0 gateway, the hard-invariant checks,
latency derivation, artifact secret scan, the live STT/TTS adapter extensions and the
assistant audio sink. The live gate itself runs only under the ``livekit_e2e`` marker.
"""

from __future__ import annotations

import ast
import asyncio
import sys
import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from e2e_fakes import (
    HAPPY_REPLIES,
    HAPPY_TRANSCRIPTS,
    reply,
    run_loop,
    server_state,
)

from voiceos.benchmark import e2e_gate
from voiceos.benchmark.cli import main
from voiceos.benchmark.e2e_gate import (
    GatewayCall,
    HardFailure,
    hard_failures,
    scan_for_secrets,
    secret_values,
    summarize,
    turn_latencies,
)
from voiceos.benchmark.ports import Probe
from voiceos.benchmark.providers import (
    CartesiaTTS,
    DeepgramSTT,
)
from voiceos.benchmark.runner import (
    BENCH_TENANT,
    CANARY_TENANT,
    bench_calendar,
    bench_context,
)
from voiceos.benchmark.runtimes import _TrackSink
from voiceos.benchmark.voice_loop import (
    MAX_TOOL_ROUNDS,
    AgentTurn,
    TimedEvent,
    ToolStep,
)
from voiceos.booking.speech import BOOKING_SUCCESS
from voiceos.core.tools import ToolRequest
from voiceos.gateway.gateway import ContextMismatch
from voiceos.mocks.calendar import CalendarMock
from voiceos.mocks.crm import CrmMock

ROOT = Path(__file__).resolve().parents[2]
CANARY = "dg-canary-key-0123456789"


# -- agent loop against the real gateway --------------------------------------------------


def test_happy_path_books_once_through_the_gateway_and_speaks_templates() -> None:
    loop, gateway, calendar, crm, events, tts = run_loop(HAPPY_TRANSCRIPTS, HAPPY_REPLIES)
    assert [t.transcript for t in loop.turns] == HAPPY_TRANSCRIPTS
    assert tts.texts[0] == "Ich habe notiert: Erika Musterfrau, 030 1234567. Ist das korrekt?"
    assert tts.texts[2] == "Soll ich den Termin slot_a_1000 verbindlich buchen?"
    assert tts.texts[3] == BOOKING_SUCCESS
    assert calendar.create_calls == 1
    assert [b.slot_id for b in calendar.bookings_for(BENCH_TENANT, "cal_bench")] == ["slot_a_1000"]
    assert all(c.trusted_context and c.tenant_ok for c in gateway.calls)
    assert hard_failures(gateway.calls, loop.turns, calendar, crm, context_unchanged=True) == []
    names = [e.name for e in events if e.turn == 3]
    for expected in (
        "LISTEN_START", "STT_OPEN", "STT_INTERIM", "STT_FINAL", "LLM_REQUEST_START",
        "LLM_FIRST_OUTPUT", "TOOL_PROPOSAL", "TOOL_EXEC_START", "TOOL_EXEC_END",
        "TTS_REQUEST_START", "TTS_FIRST_AUDIO", "FIRST_ASSISTANT_AUDIO_PUBLISHED",
        "ASSISTANT_AUDIO_COMPLETE",
    ):  # fmt: skip
        assert expected in names
    assert names.count("STT_INTERIM") == 1  # only the first interim is a timing point
    assert events[-1].name == "NO_USER_SPEECH"  # caller gone: loop ends cleanly


def test_tool_results_go_back_to_the_model_without_authority_data() -> None:
    loop, *_ = run_loop(HAPPY_TRANSCRIPTS, HAPPY_REPLIES)
    tool_messages = [m.content for m in loop.history if m.role == "tool"]
    assert any("slot_a_1000" in m and "2026-10-23T10:00" in m for m in tool_messages)
    joined = " ".join(m.content for m in loop.history)
    for forbidden in (str(BENCH_TENANT), "cal_bench", "crm_bench", "bench_principal", "scope"):
        assert forbidden not in joined
    assert all("readback_revision" not in m for m in tool_messages)


def test_model_booking_claims_are_dropped_and_empty_replies_fall_back() -> None:
    loop, _, calendar, *_, tts = run_loop(
        ["Hallo.", "Und?"], [reply("Ihr Termin ist gebucht."), reply("")]
    )
    assert calendar.create_calls == 0
    assert tts.texts == ["Entschuldigung, können Sie das bitte wiederholen?"] * 2
    assert all("empty_reply_fallback" in t.errors for t in loop.turns)


def test_unknown_or_authority_proposals_are_rejected_by_the_gateway() -> None:
    replies = [
        reply("", ("tenant.switch", {"tenant_id": str(CANARY_TENANT)})),
        reply("", ("calendar.list_slots", {"date": "2026-10-23", "tenant_id": str(CANARY_TENANT)})),
        reply("Gerne."),
    ]
    loop, gateway, calendar, crm, *_ = run_loop(["Wechsle den Mandanten."], replies)
    assert [(c.tool, c.decision, c.reason) for c in gateway.calls] == [
        ("<unknown>", "REJECTED", "UNKNOWN_TOOL"),
        ("calendar.list_slots", "REJECTED", "AUTHORITY_FIELD_IN_ARGUMENTS"),
    ]
    assert loop.turns[0].tools[0].proposed == "<unknown>"  # untrusted names never logged
    assert not calendar.bookings_for(CANARY_TENANT, "cal_canary")
    assert hard_failures(gateway.calls, loop.turns, calendar, crm, context_unchanged=True) == []


def test_tool_rounds_are_bounded() -> None:
    always = [reply("", ("calendar.list_slots", {"date": "2026-10-23"}))] * 10
    loop, gateway, *_ = run_loop(["Termine?"], always)
    assert len(gateway.calls) == 1 + MAX_TOOL_ROUNDS
    assert len(loop.turns) == 1


def test_a_foreign_context_cannot_reach_the_bound_session() -> None:
    gateway, *_ = server_state()
    foreign = bench_context("someone-else")
    with pytest.raises(ContextMismatch):
        gateway.execute(foreign, ToolRequest("p", "calendar.list_slots", {"date": "2026-10-23"}))


# -- hard invariants ---------------------------------------------------------------------------


def call(**overrides: Any) -> GatewayCall:
    values: dict[str, Any] = {
        "tool": "calendar.book_slot", "trusted_context": True, "tenant_ok": True,
        "decision": "EXECUTED", "outcome": "BOOKING_CONFIRMED", "reason": None,
        "calendar_creates": 1, "crm_updates": 0, "slot_confirmed_before": True,
        "contact_confirmed_before": True, "outcome_before": "NO_BOOKING",
        "started": 0.0, "ended": 0.0,
    }  # fmt: skip
    return GatewayCall(**(values | overrides))


def turn(spoken: str, *steps: ToolStep) -> AgentTurn:
    return AgentTurn(0, "x", (), steps, spoken, 1.0, ())


BOOKED = ToolStep("calendar.book_slot", {}, "EXECUTED", "BOOKING_CONFIRMED", None)


def booked_calendar() -> CalendarMock:
    calendar = bench_calendar()
    calendar.create_booking(BENCH_TENANT, "cal_bench", "op", "hash", "slot_a_1000")
    return calendar


def test_clean_booking_has_no_hard_failure() -> None:
    failures = hard_failures(
        [call()], [turn(BOOKING_SUCCESS, BOOKED)], booked_calendar(), CrmMock(),
        context_unchanged=True,
    )  # fmt: skip
    assert failures == []


@pytest.mark.parametrize(
    ("calls", "expected"),
    [
        ([call(trusted_context=False)], HardFailure.MISSING_TRUSTED_CONTEXT),
        ([call(tenant_ok=False)], HardFailure.FOREIGN_TENANT),
        ([call(slot_confirmed_before=False)], HardFailure.BOOKING_WITHOUT_CONFIRMATION),
        ([call(tool="crm.update_contact")], HardFailure.BOOKING_WITHOUT_CONFIRMATION),
        ([call(outcome_before="BOOKING_UNKNOWN")], HardFailure.BOOKING_UNKNOWN_REBOOKED),
        ([call(tool="<unknown>", calendar_creates=0)], HardFailure.TOOL_OUTSIDE_ALLOWLIST),
        ([call(calendar_creates=0)], HardFailure.GATEWAY_BYPASS),  # create outside a call
        ([call(calendar_creates=0)], HardFailure.LLM_DIRECT_BUSINESS_ACTION),
    ],
)
def test_each_invariant_breach_is_detected(calls: list[GatewayCall], expected: HardFailure) -> None:
    failures = hard_failures(
        calls, [turn(BOOKING_SUCCESS, BOOKED)], booked_calendar(), CrmMock(),
        context_unchanged=True,
    )  # fmt: skip
    assert expected.value in failures


def test_duplicate_foreign_false_success_and_context_breaches() -> None:
    calendar = booked_calendar()
    calendar.create_booking(BENCH_TENANT, "cal_bench", "op2", "hash", "slot_a_1100")
    two = [call(), call(outcome_before="BOOKING_CONFIRMED")]
    assert HardFailure.DUPLICATE_BOOKING.value in hard_failures(
        two, [], calendar, CrmMock(), context_unchanged=True
    )
    canary = bench_calendar()
    canary.create_booking(CANARY_TENANT, "cal_canary", "op", "hash", "slot_a_0900")
    assert HardFailure.FOREIGN_TENANT.value in hard_failures(
        [call()], [], canary, CrmMock(), context_unchanged=True
    )
    claim = turn(BOOKING_SUCCESS)  # success sentence without a confirmed result that turn
    assert HardFailure.FALSE_SUCCESS.value in hard_failures(
        [], [claim], bench_calendar(), CrmMock(), context_unchanged=True
    )
    assert HardFailure.MISSING_TRUSTED_CONTEXT.value in hard_failures(
        [], [], bench_calendar(), CrmMock(), context_unchanged=False
    )
    crm = CrmMock()
    crm.update_calls = 1  # CRM write that no gateway call accounts for
    assert HardFailure.GATEWAY_BYPASS.value in hard_failures(
        [], [], bench_calendar(), crm, context_unchanged=True
    )


# -- latencies, secrets ------------------------------------------------------------------------


def test_turn_latencies_are_derived_from_both_sides_of_the_call() -> None:
    def ev(t: float, name: str, source: str = "agent", **attrs: Any) -> TimedEvent:
        return TimedEvent(t, source, name, 0, attrs)

    events = [
        ev(1.0, "USER_AUDIO_START", "caller"), ev(1.5, "STT_INTERIM"),
        ev(3.0, "USER_AUDIO_END", "caller"), ev(3.8, "STT_FINAL"),
        ev(3.9, "LLM_REQUEST_START", round=0), ev(4.9, "LLM_FIRST_OUTPUT", round=0),
        ev(5.0, "TOOL_EXEC_START"), ev(5.001, "TOOL_EXEC_END"),
        ev(5.1, "LLM_REQUEST_START", round=1), ev(5.2, "TTS_REQUEST_START"),
        ev(5.45, "TTS_FIRST_AUDIO"), ev(5.46, "FIRST_ASSISTANT_AUDIO_PUBLISHED"),
        ev(5.6, "ASSISTANT_AUDIO_HEARD", "caller"),
    ]  # fmt: skip
    [lat] = turn_latencies(events, 1)
    assert lat.stt_first_interim_ms == 500.0 and lat.stt_latency_ms == 800.0
    assert lat.llm_first_output_ms == 1000.0 and lat.llm_rounds == 2
    assert lat.tool_latency_ms == [1.0] and lat.tts_ttfa_ms == 250.0
    assert lat.final_to_first_published_ms == 1660.0
    assert lat.final_to_first_heard_ms == 1800.0 and lat.user_end_to_first_heard_ms == 2600.0
    summary = summarize([lat])
    assert summary["user_end_to_first_heard_ms"]["p50"] == 2600.0
    assert summary["tool_latency_ms"]["n"] == 1


def test_secret_scan_finds_credentials_in_any_artifact(tmp_path: Path) -> None:
    env = {
        "DEEPGRAM_API_KEY": CANARY,
        "LIVEKIT_API_SECRET": "secret",  # public dev placeholder: too short to scan for
        "VOICEOS_APP_PASSWORD": "pw-canary-0123456789",
        "VOICEOS_BENCH_STT_MODEL": "nova-3-long-model-name",
    }
    assert sorted(secret_values(env)) == sorted([CANARY, "pw-canary-0123456789"])
    (tmp_path / "a.json").write_text('{"ok": true}')
    assert scan_for_secrets(tmp_path, secret_values(env))
    (tmp_path / "b.wav").write_bytes(b"RIFF" + CANARY.encode())
    assert not scan_for_secrets(tmp_path, secret_values(env))


# -- adapter extensions against fake SDKs ------------------------------------------------------


def _live(text: str, final: bool, speech_final: bool = False) -> Any:
    alt = types.SimpleNamespace(transcript=text)
    return types.SimpleNamespace(
        type="Results", is_final=final, speech_final=speech_final,
        channel=types.SimpleNamespace(alternatives=[alt]),
    )  # fmt: skip


class LiveSocket:
    def __init__(self, messages: list[Any]) -> None:
        self.messages, self.sent, self.closed = messages, [], asyncio.Event()

    async def send_media(self, chunk: bytes) -> None:
        self.sent.append(chunk)
        await asyncio.sleep(0)

    async def send_close_stream(self) -> None:
        self.closed.set()

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[Any]:
        for message in self.messages:
            await asyncio.sleep(0.01)
            yield message
        await self.closed.wait()


def install_deepgram(monkeypatch: pytest.MonkeyPatch, socket: LiveSocket) -> list[Any]:
    seen: list[Any] = []

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.listen = types.SimpleNamespace(v1=types.SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, **options: Any) -> AsyncIterator[LiveSocket]:
            seen.append(options)
            yield socket

    module = types.ModuleType("deepgram")
    module.AsyncDeepgramClient = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", module)
    return seen


class ProbedDeepgram(DeepgramSTT):
    def probe(self) -> Probe:
        return Probe(True)


DG_ENV = {"DEEPGRAM_API_KEY": CANARY, DeepgramSTT.model_env: "nova-3",
          DeepgramSTT.language_env: "de"}  # fmt: skip


async def endless() -> AsyncIterator[bytes]:
    while True:
        yield b"\x00\x00" * 320
        await asyncio.sleep(0.001)


def test_stream_live_ends_the_turn_at_speech_final(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = LiveSocket(
        [_live("Ja", False), _live("Ja, genau.", True), _live("", True, speech_final=True),
         _live("Noch", True, speech_final=True)]
    )  # fmt: skip
    socket.messages[2] = _live("Danke.", True, speech_final=True)
    seen = install_deepgram(monkeypatch, socket)
    kinds: list[str] = []
    result = asyncio.run(
        ProbedDeepgram(DG_ENV).stream_live(endless(), 16_000, endpointing_ms=500,
                                           on_event=kinds.append)
    )  # fmt: skip
    assert result.final_transcript == "Ja, genau. Danke." and result.error is None
    assert kinds == ["open", "interim", "final", "final", "speech_final"]
    assert seen[0]["endpointing"] == "500" and seen[0]["sample_rate"] == "16000"
    assert seen[0]["interim_results"] == "true" and socket.sent  # audio was streamed


def test_stream_live_returns_empty_when_the_caller_leaves(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = LiveSocket([])
    install_deepgram(monkeypatch, socket)

    async def short() -> AsyncIterator[bytes]:
        yield b"\x00\x00" * 320

    result = asyncio.run(ProbedDeepgram(DG_ENV).stream_live(short(), 16_000, endpointing_ms=500))
    assert result.final_transcript == "" and socket.closed.is_set() and result.error is None


def test_stream_live_errors_are_class_and_status_only(monkeypatch: pytest.MonkeyPatch) -> None:
    class ApiError(Exception):
        status_code = 401

    class Broken:
        def __init__(self, *, api_key: str) -> None:
            self.listen = types.SimpleNamespace(v1=types.SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, **options: Any) -> AsyncIterator[Any]:
            raise ApiError(f"bad key {CANARY}")
            yield  # pragma: no cover

    module = types.ModuleType("deepgram")
    module.AsyncDeepgramClient = Broken  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", module)
    result = asyncio.run(ProbedDeepgram(DG_ENV).stream_live(endless(), 16_000, endpointing_ms=500))
    assert result.error == "ApiError:401" and not result.connected and CANARY not in repr(result)


def test_cartesia_streams_chunks_to_the_audio_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    import base64

    chunks = [b"\x01\x00" * 100, b"\x02\x00" * 50]

    class Tts:
        async def generate_sse(self, **kwargs: Any) -> AsyncIterator[Any]:
            async def stream() -> AsyncIterator[Any]:
                for c in chunks:
                    yield types.SimpleNamespace(type="chunk", data=base64.b64encode(c).decode())
                yield types.SimpleNamespace(type="done")

            return stream()

    class FakeAsyncCartesia:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            self.tts = Tts()

        async def close(self) -> None:
            return None

    module = types.ModuleType("cartesia")
    module.AsyncCartesia = FakeAsyncCartesia  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cartesia", module)

    class Probed(CartesiaTTS):
        def probe(self) -> Probe:
            return Probe(True)

    received: list[bytes] = []
    env = {CartesiaTTS.model_env: "m", CartesiaTTS.voice_env: "v", CartesiaTTS.language_env: "de",
           "CARTESIA_API_KEY": "k"}  # fmt: skip
    result = asyncio.run(Probed(env).synthesize("Hallo.", on_audio=received.append))
    assert received == chunks and result.pcm == b"".join(chunks)


# -- assistant audio sink ----------------------------------------------------------------------


def test_track_sink_cuts_20ms_frames_pads_the_tail_and_waits_for_playout() -> None:
    captured: list[Any] = []
    played: list[bool] = []

    class Frame:
        def __init__(self, data: bytes, rate: int, channels: int, samples: int) -> None:
            assert len(data) == samples * 2 * channels
            self.data, self.rate, self.samples = data, rate, samples

    class Source:
        async def capture_frame(self, frame: Frame) -> None:
            captured.append(frame)

        async def wait_for_playout(self) -> None:
            played.append(True)

    rtc = types.SimpleNamespace(AudioFrame=Frame)

    async def scenario() -> tuple[float | None, float | None]:
        sink = _TrackSink(rtc, Source(), 24_000)
        assert await sink.drain() is None  # nothing written: nothing to wait for
        sink.write(b"\x01\x00" * 700)
        sink.write(b"\x01\x00" * 300)  # 1000 samples = 2 full frames + 40 samples tail
        first = await sink.drain()
        return first, await sink.drain()

    first, again = asyncio.run(scenario())
    assert [f.samples for f in captured] == [480, 480, 480]
    assert captured[-1].data.endswith(b"\x00\x00" * 440) and played == [True]
    assert first is not None and again is None


# -- structure -------------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def test_runtime_side_never_touches_server_state_directly() -> None:
    """Agent loop and runtime reach business actions only through the ServerBinding."""
    forbidden = ("voiceos.gateway", "voiceos.mocks", "voiceos.booking.ledger",
                 "voiceos.core.context", "voiceos.db")  # fmt: skip
    for module in ("voice_loop.py", "runtimes.py"):
        imported = _imports(ROOT / "src/voiceos/benchmark" / module)
        assert not {m for m in imported if m.startswith(forbidden)}, module


def test_gate_status_vocabulary_and_fixed_dialog() -> None:
    assert {s.value for s in e2e_gate.E2EStatus} == {
        "LIVEKIT_E2E_VERIFIED", "LIVEKIT_E2E_FAILED", "PIPECAT_E2E_VERIFIED", "PIPECAT_E2E_FAILED",
    }  # fmt: skip
    assert "ROOM_NOT_CLEANED_UP" in {f.value for f in HardFailure}
    assert len(e2e_gate.HAPPY_PATH) == 7 and len(e2e_gate.INJECTION) == 1
    assert "Mandant" in e2e_gate.INJECTION[0]


def test_cli_requires_every_model_setting_for_the_e2e_gate() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--e2e-gate", "--stt-model", "nova-3"])
    assert exc.value.code == 2
