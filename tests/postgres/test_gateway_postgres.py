"""Full chain on PostgreSQL:

trusted CallContext -> Tool Gateway -> deterministic booking logic
-> tenant-isolated PostgreSQL ledger (non-owner role, FORCE RLS) -> authoritative result
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from support import CALL_B, TENANT_B, book, make_calendar, make_context, req

from voiceos.config import Settings
from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.calendar import CalendarFault, CalendarMock
from voiceos.mocks.crm import CrmFault, CrmMock
from voiceos.tenancy.db import Conn, connect_app
from voiceos.tenancy.ledger import PostgresBookingLedger
from voiceos.tenancy.preflight import assert_preflight


@pytest.fixture
def calendar() -> CalendarMock:
    return make_calendar()


@pytest.fixture
def ctx() -> CallContext:
    return make_context()


@pytest.fixture
def worker(settings: Settings, migrator: Conn) -> Iterator[Conn]:
    conn = connect_app(settings)
    assert_preflight(conn)  # refuse to run on an unsafe role/schema
    yield conn
    conn.close()


def _gateway(conn: Conn, calendar: CalendarMock, crm: CrmMock, ctx: CallContext) -> ToolGateway:
    gw = ToolGateway(PostgresBookingLedger(conn), calendar, crm)
    gw.open_session(ctx)
    return gw


def _rows(migrator: Conn) -> list[tuple[object, ...]]:
    return migrator.execute(
        "SELECT tenant_id, state, crm_state FROM voiceos.booking_operations ORDER BY tenant_id"
    ).fetchall()


def test_booking_is_persisted_for_the_trusted_tenant_only(
    worker: Conn, migrator: Conn, calendar: CalendarMock, ctx: CallContext
) -> None:
    result = book(_gateway(worker, calendar, CrmMock(), ctx), ctx)
    assert result.outcome is BookingOutcome.BOOKING_CONFIRMED
    assert _rows(migrator) == [(ctx.tenant_id, "CONFIRMED", "NOT_STARTED")]


def test_two_workers_on_separate_connections_book_once(
    settings: Settings, worker: Conn, migrator: Conn, calendar: CalendarMock, ctx: CallContext
) -> None:
    other = connect_app(settings)
    try:
        first = book(_gateway(worker, calendar, CrmMock(), ctx), ctx)
        second = _gateway(other, calendar, CrmMock(), ctx).execute(
            ctx, req("calendar.book_slot", slot_id="slot_a_0900")
        )
    finally:
        other.close()
    assert second.data["booking_id"] == first.data["booking_id"]
    assert calendar.create_calls == 1
    assert len(_rows(migrator)) == 1


def test_booking_unknown_survives_a_worker_restart_and_blocks_rebooking(
    settings: Settings, worker: Conn, migrator: Conn, calendar: CalendarMock, ctx: CallContext
) -> None:
    calendar.next_fault = CalendarFault.RESPONSE_LOST_AFTER_COMMIT
    assert book(_gateway(worker, calendar, CrmMock(), ctx), ctx).outcome is (
        BookingOutcome.BOOKING_UNKNOWN
    )
    assert _rows(migrator) == [(ctx.tenant_id, "UNKNOWN", "NOT_STARTED")]

    restarted = _gateway(worker, calendar, CrmMock(), ctx)  # fresh in-memory session
    retry = restarted.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert retry.decision is Decision.REJECTED
    assert retry.reason is Reason.RECONCILIATION_REQUIRED
    assert calendar.create_calls == 1

    assert restarted.reconcile(ctx) is BookingOutcome.BOOKING_CONFIRMED
    assert _rows(migrator) == [(ctx.tenant_id, "CONFIRMED", "NOT_STARTED")]


def test_negative_lookup_keeps_persisted_unknown_across_restart(
    worker: Conn, migrator: Conn, calendar: CalendarMock, ctx: CallContext
) -> None:
    calendar.next_fault = CalendarFault.TIMEOUT_BEFORE_COMMIT
    gw = _gateway(worker, calendar, CrmMock(), ctx)
    book(gw, ctx)
    assert gw.reconcile(ctx) is BookingOutcome.BOOKING_UNKNOWN  # lookup returned None
    assert _rows(migrator) == [(ctx.tenant_id, "UNKNOWN", "NOT_STARTED")]

    restarted = _gateway(worker, calendar, CrmMock(), ctx)
    retry = restarted.execute(ctx, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert retry.reason is Reason.RECONCILIATION_REQUIRED
    assert calendar.create_calls == 1
    assert _rows(migrator) == [(ctx.tenant_id, "UNKNOWN", "NOT_STARTED")]


def test_crm_failure_is_persisted_as_pending_without_touching_the_booking(
    worker: Conn, migrator: Conn, calendar: CalendarMock, ctx: CallContext
) -> None:
    crm = CrmMock(next_fault=CrmFault.SERVER_ERROR)
    gw = _gateway(worker, calendar, crm, ctx)
    book(gw, ctx)
    assert gw.execute(ctx, req("crm.update_contact")).outcome is BookingOutcome.BOOKED_CRM_PENDING
    assert _rows(migrator) == [(ctx.tenant_id, "CONFIRMED", "PENDING")]


def test_other_tenant_on_the_same_connection_sees_no_ledger_state(
    worker: Conn, migrator: Conn, calendar: CalendarMock, ctx: CallContext
) -> None:
    book(_gateway(worker, calendar, CrmMock(), ctx), ctx)

    ctx_b = make_context(TENANT_B, CALL_B)
    gw_b = _gateway(worker, calendar, CrmMock(), ctx_b)
    assert gw_b.outcome(ctx_b) is BookingOutcome.NO_BOOKING
    assert gw_b.execute(ctx_b, req("booking.get_status")).operation_id is None
    with worker.transaction():
        worker.execute("SELECT set_config('app.tenant_id', %s, true)", (str(TENANT_B),))
        assert worker.execute("SELECT count(*) FROM voiceos.booking_operations").fetchone() == (0,)
