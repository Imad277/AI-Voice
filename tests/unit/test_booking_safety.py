"""Booking safety: idempotency, BOOKING_UNKNOWN, confirmation invalidation, no false success."""

from support import CALL_B, book, confirm_contact, confirm_slot, make_context, req

from voiceos.booking.ledger import InMemoryBookingLedger
from voiceos.booking.session import ContactState
from voiceos.booking.speech import BOOKING_SUCCESS, render_turn
from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.calendar import CalendarFault, CalendarMock
from voiceos.mocks.crm import CrmMock


def test_confirmed_booking(gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock) -> None:
    result = book(gateway, ctx)
    assert result.decision is Decision.EXECUTED
    assert result.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert result.operation_id is not None and result.operation_id.startswith("bk_")
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 1


def test_repeated_intent_does_not_create_a_second_booking(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    first = book(gateway, ctx)
    again = gateway.execute(ctx, req("calendar.book_slot", pid="p2", slot_id="slot_a_0900"))
    assert again.decision is Decision.EXECUTED
    assert again.data["booking_id"] == first.data["booking_id"]
    assert again.operation_id == first.operation_id
    assert calendar.create_calls == 1
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 1


def test_different_slot_after_confirmation_is_not_booked(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    book(gateway, ctx)
    other = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_1000"))
    assert other.reason is Reason.BOOKING_ALREADY_EXISTS
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 1


def test_second_worker_with_shared_ledger_does_not_double_book(
    calendar: CalendarMock, ctx: CallContext
) -> None:
    ledger = InMemoryBookingLedger()
    worker_1 = ToolGateway(ledger, calendar, CrmMock())
    worker_2 = ToolGateway(ledger, calendar, CrmMock())
    worker_1.open_session(ctx)
    worker_2.open_session(ctx)

    first = book(worker_1, ctx)
    # The second worker sees the authoritative ledger entry and returns it; no new write.
    result = worker_2.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert result.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert result.data["booking_id"] == first.data["booking_id"]
    assert calendar.create_calls == 1


def test_booking_requires_confirmed_contact(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    gateway.execute(ctx, req("contact.collect_candidate", name="Erika", phone="+49 30 1234567"))
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert result.reason is Reason.CONTACT_NOT_CONFIRMED
    assert calendar.create_calls == 0


def test_booking_requires_slot_readback_confirmation(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    confirm_contact(gateway, ctx)
    first = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    second = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert first.reason is second.reason is Reason.SLOT_CONFIRMATION_REQUIRED
    assert calendar.create_calls == 0


def test_contact_correction_invalidates_confirmation(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    first = confirm_contact(gateway, ctx)
    confirm_slot(gateway, ctx)
    gateway.execute(
        ctx, req("contact.collect_candidate", name="Erika Muster", phone="+49 30 7654321")
    )
    session = gateway.session(ctx)
    assert session.contact_state is ContactState.CANDIDATE
    revision = first.data["readback_revision"]
    assert isinstance(revision, int)
    assert session.affirm_contact(revision) is False  # stale readback can not re-confirm

    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert result.reason is Reason.CONTACT_NOT_CONFIRMED
    assert calendar.create_calls == 0


def test_slot_change_invalidates_slot_confirmation(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    confirm_contact(gateway, ctx)
    confirm_slot(gateway, ctx, "slot_a_0900")
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_1000"))
    assert result.reason is Reason.SLOT_CONFIRMATION_REQUIRED
    assert gateway.session(ctx).slot_confirmed is False
    assert calendar.create_calls == 0


def test_lost_response_enters_booking_unknown_and_never_rebooks(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.RESPONSE_LOST_AFTER_COMMIT
    result = book(gateway, ctx)
    assert result.outcome is BookingOutcome.BOOKING_UNKNOWN
    assert result.reason is Reason.RECONCILIATION_REQUIRED

    for pid in ("retry-1", "retry-2"):
        retry = gateway.execute(ctx, req("calendar.book_slot", pid=pid, slot_id="slot_a_0900"))
        assert retry.decision is Decision.REJECTED
        assert retry.reason is Reason.RECONCILIATION_REQUIRED
    retry = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_1000"))
    assert retry.reason is Reason.RECONCILIATION_REQUIRED
    assert calendar.create_calls == 1

    status = gateway.execute(ctx, req("booking.get_status"))
    assert status.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 1


def test_timeout_before_commit_with_negative_lookup_stays_unknown_and_blocks_rebooking(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.TIMEOUT_BEFORE_COMMIT
    assert book(gateway, ctx).outcome is BookingOutcome.BOOKING_UNKNOWN
    assert calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref) == []  # lookup will be None

    status = gateway.execute(ctx, req("booking.get_status"))
    assert status.outcome is BookingOutcome.BOOKING_UNKNOWN
    assert status.reason is Reason.RECONCILIATION_REQUIRED
    assert gateway.outcome(ctx) is BookingOutcome.BOOKING_UNKNOWN

    retry = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert retry.decision is Decision.REJECTED
    assert retry.reason is Reason.RECONCILIATION_REQUIRED
    assert retry.outcome is BookingOutcome.BOOKING_UNKNOWN
    assert BOOKING_SUCCESS not in render_turn("", "calendar.book_slot", retry)
    assert calendar.create_calls == 1


def test_repeated_negative_lookups_never_release_rebooking(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.TIMEOUT_BEFORE_COMMIT
    book(gateway, ctx)

    for attempt in range(3):
        status = gateway.execute(ctx, req("booking.get_status", pid=f"status-{attempt}"))
        assert status.outcome is BookingOutcome.BOOKING_UNKNOWN
        assert gateway.reconcile(ctx) is BookingOutcome.BOOKING_UNKNOWN
        for slot_id in ("slot_a_0900", "slot_a_1000"):
            retry = gateway.execute(
                ctx, req("calendar.book_slot", pid=f"r{attempt}", slot_id=slot_id)
            )
            assert retry.decision is Decision.REJECTED
            assert retry.reason is Reason.RECONCILIATION_REQUIRED

    assert calendar.create_calls == 1  # only the original, uncertain write
    assert calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref) == []


def test_synchronous_slot_unavailable_is_rejected_and_allows_another_slot(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    other_call = make_context(call_id=CALL_B)
    gateway.open_session(other_call)
    book(gateway, other_call, "slot_a_0900")  # slot taken by another call of the same tenant

    taken = book(gateway, ctx, "slot_a_0900")
    assert taken.decision is Decision.REJECTED
    assert taken.reason is Reason.SLOT_UNAVAILABLE
    assert taken.outcome is BookingOutcome.NO_BOOKING

    confirm_slot(gateway, ctx, "slot_a_1000")
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_1000"))
    assert result.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert len(calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref)) == 2  # one per call


def test_failed_reconciliation_stays_unknown(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.RESPONSE_LOST_AFTER_COMMIT
    book(gateway, ctx)
    calendar.status_fault = True
    status = gateway.execute(ctx, req("booking.get_status"))
    assert status.outcome is BookingOutcome.BOOKING_UNKNOWN
    assert status.reason is Reason.RECONCILIATION_REQUIRED


def test_no_success_statement_without_authoritative_confirmation(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    calendar.next_fault = CalendarFault.RESPONSE_LOST_AFTER_COMMIT
    unknown = book(gateway, ctx)
    spoken = render_turn("Super, Ihr Termin ist gebucht!", "calendar.book_slot", unknown)
    assert BOOKING_SUCCESS not in spoken
    assert "gebucht!" not in spoken  # the model's claim is dropped

    status = gateway.execute(ctx, req("booking.get_status"))
    assert BOOKING_SUCCESS in render_turn("", "booking.get_status", status)


def test_model_text_cannot_claim_a_booking_on_its_own() -> None:
    for claim in ("Ihr Termin ist gebucht.", "Die Buchung ist bestätigt.", "You are booked!"):
        assert render_turn(claim, None, None) == ""
    assert render_turn("Guten Tag, wie kann ich helfen?", None, None) != ""


def test_rejected_booking_attempts_never_render_success(
    gateway: ToolGateway, ctx: CallContext
) -> None:
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert BOOKING_SUCCESS not in render_turn("", "calendar.book_slot", result)


def test_qualification_is_independent_of_booking(gateway: ToolGateway, ctx: CallContext) -> None:
    result = gateway.execute(
        ctx, req("qualification.submit_candidate", service_type="maintenance", budget_eur=100)
    )
    assert result.data["qualified"] is False
    assert result.outcome is BookingOutcome.NO_BOOKING

    booked = book(gateway, ctx)
    assert booked.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert gateway.session(ctx).qualified is False
