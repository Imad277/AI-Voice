"""Authoritative booking ledger.

The ledger is written *before* the calendar is called (state SUBMITTED), so a crash or
lost response leaves evidence that a write may have happened. Only one claimant can
move an operation into SUBMITTED; that is what prevents duplicate bookings.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from voiceos.core.booking import BookingIntent
from voiceos.core.context import CallContext


class LedgerState(StrEnum):
    SUBMITTED = "SUBMITTED"  # write may be in flight; treat as unknown if seen later
    CONFIRMED = "CONFIRMED"  # calendar confirmed authoritatively
    UNKNOWN = "UNKNOWN"  # result uncertain; reconcile, never resubmit
    # Calendar synchronously and authoritatively refused the write (e.g. slot unavailable),
    # so no booking was created. Never reached from UNKNOWN via a negative lookup.
    REJECTED = "REJECTED"


class CrmState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SYNCED = "SYNCED"
    PENDING = "PENDING"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    operation_id: str
    call_id: UUID
    calendar_ref: str
    slot_id: str
    payload_hash: str
    state: LedgerState
    calendar_booking_id: str | None = None
    crm_state: CrmState = CrmState.NOT_STARTED


class BookingLedger(Protocol):
    def claim(self, context: CallContext, intent: BookingIntent) -> tuple[LedgerEntry, bool]:
        """Atomically move the intent's operation into SUBMITTED.

        Succeeds for a new operation or one that is REJECTED. Returns the current entry
        and whether this caller now owns the submission.
        """
        ...

    def get(self, context: CallContext, operation_id: str) -> LedgerEntry | None: ...

    def save(self, context: CallContext, entry: LedgerEntry) -> None: ...


class InMemoryBookingLedger:
    """Ledger for fast offline unit tests. Isolation proofs use the PostgreSQL ledger."""

    def __init__(self) -> None:
        self._entries: dict[tuple[UUID, str], LedgerEntry] = {}

    def claim(self, context: CallContext, intent: BookingIntent) -> tuple[LedgerEntry, bool]:
        key = (context.tenant_id, intent.operation_id)
        existing = self._entries.get(key)
        if existing is not None and existing.state is not LedgerState.REJECTED:
            return existing, False
        entry = LedgerEntry(
            operation_id=intent.operation_id,
            call_id=intent.call_id,
            calendar_ref=intent.calendar_ref,
            slot_id=intent.slot_id,
            payload_hash=intent.payload_hash,
            state=LedgerState.SUBMITTED,
        )
        self._entries[key] = entry
        return entry, True

    def get(self, context: CallContext, operation_id: str) -> LedgerEntry | None:
        return self._entries.get((context.tenant_id, operation_id))

    def save(self, context: CallContext, entry: LedgerEntry) -> None:
        key = (context.tenant_id, entry.operation_id)
        if key not in self._entries:
            raise KeyError(entry.operation_id)
        self._entries[key] = replace(entry)
