"""End-to-end offline scenarios through the fake STT/LLM/TTS runtime."""

import pytest

from voiceos.benchmark.harness import ScriptedTurn, TransportClass, run_offline_scenario
from voiceos.booking.speech import BOOKING_SUCCESS, BOOKING_UNKNOWN
from voiceos.config import ConfigError, Settings, load_settings
from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.core.tools import ToolRequest
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.calendar import CalendarFault, CalendarMock
from voiceos.mocks.voice import LLMReply


def turn(transcript: str, text: str, tool: str | None = None, **args: object) -> ScriptedTurn:
    request = ToolRequest(f"p-{transcript[:8]}", tool, args) if tool else None
    return ScriptedTurn(transcript, LLMReply(text, request))


BOOKING_DIALOG = [
    turn("Hallo, ich brauche einen Termin.", "Gern. Wie ist Ihr Name und Ihre Nummer?"),
    turn(
        "Erika Muster, plus 49 30 1234567",
        "Danke.",
        "contact.collect_candidate",
        name="Erika Muster",
        phone="+49 30 1234567",
    ),
    turn("Ja, richtig.", "Worum geht es?"),
    turn(
        "Installation, Budget 800 Euro.",
        "Verstanden.",
        "qualification.submit_candidate",
        service_type="installation",
        budget_eur=800,
    ),
    turn("Morgen bitte.", "Ich schaue nach.", "calendar.list_slots", date="2026-10-23"),
    turn("Um neun.", "", "calendar.book_slot", slot_id="slot_a_0900"),
    turn(
        "Ja.", "Einen Moment, Ihr Termin ist gebucht!", "calendar.book_slot", slot_id="slot_a_0900"
    ),
]


def test_scripted_booking_call_reaches_authoritative_confirmation(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    result = run_offline_scenario(load_settings({}), gateway, ctx, BOOKING_DIALOG)

    assert result.transport is TransportClass.OFFLINE
    assert result.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert result.qualified is True
    assert [i for i, s in enumerate(result.spoken) if BOOKING_SUCCESS in s] == [6]
    assert "Ist das korrekt?" in result.spoken[1]
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 1


def test_model_claiming_success_after_lost_response_is_not_spoken(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.RESPONSE_LOST_AFTER_COMMIT
    result = run_offline_scenario(load_settings({}), gateway, ctx, BOOKING_DIALOG)

    assert result.outcome is BookingOutcome.BOOKING_UNKNOWN
    assert not any(BOOKING_SUCCESS in s or "gebucht!" in s for s in result.spoken)
    assert BOOKING_UNKNOWN in result.spoken[-1]


def test_ambiguous_reply_does_not_confirm_contact(gateway: ToolGateway, ctx: CallContext) -> None:
    dialog = [*BOOKING_DIALOG]
    dialog[2] = turn("Hm, ich glaube schon.", "Worum geht es?")
    result = run_offline_scenario(load_settings({}), gateway, ctx, dialog)
    assert result.outcome is BookingOutcome.NO_BOOKING  # never booked, normal hang-up
    assert not any(BOOKING_SUCCESS in s for s in result.spoken)


def test_offline_runner_refuses_live_configuration(gateway: ToolGateway, ctx: CallContext) -> None:
    with pytest.raises(ConfigError):
        run_offline_scenario(Settings(live_enabled=True), gateway, ctx, [])
