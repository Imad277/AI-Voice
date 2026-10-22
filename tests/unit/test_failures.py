"""Failure behavior: CRM failure after booking, blocked execution, dropped call."""

from support import book, req

from voiceos.booking.speech import BLOCKED, BOOKING_SUCCESS, render_turn
from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.calendar import CalendarFault, CalendarMock
from voiceos.mocks.crm import CrmFault, CrmMock


def test_crm_failure_after_booking_keeps_the_booking(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock, crm: CrmMock
) -> None:
    book(gateway, ctx)
    crm.next_fault = CrmFault.SERVER_ERROR
    result = gateway.execute(ctx, req("crm.update_contact"))

    assert result.outcome is BookingOutcome.BOOKED_CRM_PENDING
    assert result.reason is Reason.CRM_UNAVAILABLE
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 1
    assert gateway.outcome(ctx) is BookingOutcome.BOOKED_CRM_PENDING


def test_crm_pending_resolves_on_successful_retry(
    gateway: ToolGateway, ctx: CallContext, crm: CrmMock
) -> None:
    book(gateway, ctx)
    crm.next_fault = CrmFault.RATE_LIMITED
    gateway.execute(ctx, req("crm.update_contact"))
    result = gateway.execute(ctx, req("crm.update_contact"))
    assert result.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert crm.records_for(ctx.tenant_id, ctx.crm_ref) == [
        {
            "name": "Erika Muster",
            "phone": "+49 30 1234567",
            "booking_id": "cal_1",
            "slot_id": "slot_a_0900",
        }
    ]


def test_crm_update_is_refused_without_a_booking(
    gateway: ToolGateway, ctx: CallContext, crm: CrmMock
) -> None:
    result = gateway.execute(ctx, req("crm.update_contact"))
    assert result.reason is Reason.NO_BOOKING
    assert crm.update_calls == 0


def test_crm_sync_happens_once(gateway: ToolGateway, ctx: CallContext, crm: CrmMock) -> None:
    book(gateway, ctx)
    gateway.execute(ctx, req("crm.update_contact"))
    gateway.execute(ctx, req("crm.update_contact"))
    assert crm.update_calls == 1


def test_blocked_execution_has_no_side_effects(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    gateway.block(ctx)
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert result.decision is Decision.REJECTED
    assert result.reason is Reason.EXECUTION_BLOCKED
    assert result.outcome is BookingOutcome.BLOCKED
    assert calendar.create_calls == 0
    assert render_turn("Ihr Termin ist gebucht", "calendar.book_slot", result) == BLOCKED


def test_dropped_call_without_booking(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    gateway.end_call(ctx, dropped=True)
    assert gateway.outcome(ctx) is BookingOutcome.CALL_DROPPED
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert result.reason is Reason.CALL_ENDED
    assert calendar.create_calls == 0


def test_dropped_call_keeps_unknown_and_server_reconciles_afterwards(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.RESPONSE_LOST_AFTER_COMMIT
    book(gateway, ctx)
    gateway.end_call(ctx, dropped=True)
    assert gateway.outcome(ctx) is BookingOutcome.BOOKING_UNKNOWN

    assert gateway.reconcile(ctx) is BookingOutcome.BOOKING_CONFIRMED
    assert calendar.create_calls == 1


def test_dropped_call_after_confirmed_booking_stays_confirmed(
    gateway: ToolGateway, ctx: CallContext
) -> None:
    result = book(gateway, ctx)
    assert BOOKING_SUCCESS in render_turn("", "calendar.book_slot", result)
    gateway.end_call(ctx, dropped=True)
    assert gateway.outcome(ctx) is BookingOutcome.BOOKING_CONFIRMED
