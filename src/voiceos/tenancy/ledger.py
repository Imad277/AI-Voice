"""PostgreSQL booking ledger, accessed only as the non-owner application role.

Every statement runs inside ``tenant_transaction``; RLS enforces the tenant boundary. The
explicit tenant_id predicates are defense in depth, not the isolation mechanism.
"""

from __future__ import annotations

from typing import Any

from voiceos.booking.ledger import CrmState, LedgerEntry, LedgerState
from voiceos.core.booking import BookingIntent
from voiceos.core.context import CallContext
from voiceos.tenancy.db import Conn, tenant_transaction

_COLUMNS = (
    "operation_id, call_id, calendar_ref, slot_id, payload_hash, state, calendar_booking_id, "
    "crm_state"
)


def _entry(row: tuple[Any, ...]) -> LedgerEntry:
    op, call_id, calendar_ref, slot_id, payload_hash, state, booking_id, crm_state = row
    return LedgerEntry(
        operation_id=op,
        call_id=call_id,
        calendar_ref=calendar_ref,
        slot_id=slot_id,
        payload_hash=payload_hash,
        state=LedgerState(state),
        calendar_booking_id=booking_id,
        crm_state=CrmState(crm_state),
    )


class PostgresBookingLedger:
    def __init__(self, conn: Conn) -> None:
        self._conn = conn

    def claim(self, context: CallContext, intent: BookingIntent) -> tuple[LedgerEntry, bool]:
        with tenant_transaction(self._conn, context) as tx:
            row = tx.execute(
                f"""
                INSERT INTO voiceos.booking_operations
                    (tenant_id, operation_id, call_id, calendar_ref, slot_id, payload_hash, state)
                VALUES (%s, %s, %s, %s, %s, %s, 'SUBMITTED')
                ON CONFLICT (tenant_id, operation_id) DO UPDATE
                    SET slot_id = EXCLUDED.slot_id,
                        payload_hash = EXCLUDED.payload_hash,
                        state = 'SUBMITTED',
                        calendar_booking_id = NULL,
                        updated_at = now()
                    WHERE voiceos.booking_operations.state = 'REJECTED'
                RETURNING {_COLUMNS}
                """,  # noqa: S608 - constant column list, values are parameters
                (
                    context.tenant_id,
                    intent.operation_id,
                    context.call_id,
                    context.calendar_ref,
                    intent.slot_id,
                    intent.payload_hash,
                ),
            ).fetchone()
            if row is not None:
                return _entry(row), True
            existing = tx.execute(
                f"SELECT {_COLUMNS} FROM voiceos.booking_operations "  # noqa: S608
                "WHERE tenant_id = %s AND operation_id = %s",
                (context.tenant_id, intent.operation_id),
            ).fetchone()
            if existing is None:  # conflict row must exist and be visible to this tenant
                raise RuntimeError("booking operation claim conflict without visible row")
            return _entry(existing), False

    def get(self, context: CallContext, operation_id: str) -> LedgerEntry | None:
        with tenant_transaction(self._conn, context) as tx:
            row = tx.execute(
                f"SELECT {_COLUMNS} FROM voiceos.booking_operations "  # noqa: S608
                "WHERE tenant_id = %s AND operation_id = %s",
                (context.tenant_id, operation_id),
            ).fetchone()
        return _entry(row) if row is not None else None

    def save(self, context: CallContext, entry: LedgerEntry) -> None:
        with tenant_transaction(self._conn, context) as tx:
            cur = tx.execute(
                """
                UPDATE voiceos.booking_operations
                   SET state = %s, calendar_booking_id = %s, crm_state = %s, updated_at = now()
                 WHERE tenant_id = %s AND operation_id = %s
                """,
                (
                    entry.state.value,
                    entry.calendar_booking_id,
                    entry.crm_state.value,
                    context.tenant_id,
                    entry.operation_id,
                ),
            )
            if cur.rowcount != 1:
                raise KeyError(entry.operation_id)
