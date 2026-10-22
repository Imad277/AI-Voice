"""Deterministic calendar mock.

Plays the role of the external, authoritative calendar system. Bookings are unique per
(tenant_id, calendar_ref, slot_id) and idempotent per operation_id. Faults can be
injected to simulate a timeout before commit or a response lost after commit; the
caller can not tell these apart, which is exactly why the gateway must enter
BOOKING_UNKNOWN and reconcile instead of retrying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Slot:
    slot_id: str
    start_local: str  # ISO 8601 local time, Europe/Berlin
    zone: str = "Europe/Berlin"


class CalendarFault(StrEnum):
    TIMEOUT_BEFORE_COMMIT = "TIMEOUT_BEFORE_COMMIT"
    RESPONSE_LOST_AFTER_COMMIT = "RESPONSE_LOST_AFTER_COMMIT"


class CalendarTimeout(Exception):
    """No response. The booking may or may not have been committed."""


class SlotUnavailable(Exception):
    pass


class IdempotencyConflict(Exception):
    """Same operation_id submitted with a different payload."""


@dataclass(frozen=True, slots=True)
class CalendarBooking:
    booking_id: str
    slot_id: str
    operation_id: str
    payload_hash: str


@dataclass
class CalendarMock:
    slots: dict[tuple[UUID, str], list[Slot]]
    next_fault: CalendarFault | None = None
    status_fault: bool = False  # make the next get_by_operation time out
    create_calls: int = 0
    _bookings: dict[tuple[UUID, str, str], CalendarBooking] = field(default_factory=dict)

    def list_slots(self, tenant_id: UUID, calendar_ref: str, date: str) -> list[Slot]:
        taken = {
            b.slot_id
            for (t, c, _), b in self._bookings.items()
            if (t, c) == (tenant_id, calendar_ref)
        }
        return [
            s
            for s in self.slots.get((tenant_id, calendar_ref), [])
            if s.start_local.startswith(date) and s.slot_id not in taken
        ]

    def create_booking(
        self, tenant_id: UUID, calendar_ref: str, operation_id: str, payload_hash: str, slot_id: str
    ) -> CalendarBooking:
        self.create_calls += 1
        fault, self.next_fault = self.next_fault, None
        if fault is CalendarFault.TIMEOUT_BEFORE_COMMIT:
            raise CalendarTimeout

        existing = self._bookings.get((tenant_id, calendar_ref, operation_id))
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise IdempotencyConflict
            booking = existing
        else:
            known = {s.slot_id for s in self.slots.get((tenant_id, calendar_ref), [])}
            if slot_id not in known or slot_id in self._booked_slots(tenant_id, calendar_ref):
                raise SlotUnavailable
            booking = CalendarBooking(
                booking_id=f"cal_{len(self._bookings) + 1}",
                slot_id=slot_id,
                operation_id=operation_id,
                payload_hash=payload_hash,
            )
            self._bookings[(tenant_id, calendar_ref, operation_id)] = booking

        if fault is CalendarFault.RESPONSE_LOST_AFTER_COMMIT:
            raise CalendarTimeout
        return booking

    def get_by_operation(
        self, tenant_id: UUID, calendar_ref: str, operation_id: str
    ) -> CalendarBooking | None:
        if self.status_fault:
            self.status_fault = False
            raise CalendarTimeout
        return self._bookings.get((tenant_id, calendar_ref, operation_id))

    def bookings_for(self, tenant_id: UUID, calendar_ref: str) -> list[CalendarBooking]:
        """Observer view for tests: the calendar's actual end state."""
        return [b for (t, c, _), b in self._bookings.items() if (t, c) == (tenant_id, calendar_ref)]

    def _booked_slots(self, tenant_id: UUID, calendar_ref: str) -> set[str]:
        return {b.slot_id for b in self.bookings_for(tenant_id, calendar_ref)}
