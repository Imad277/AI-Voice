"""Booking contracts: business outcome vocabulary and the normalized booking intent."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class BookingOutcome(StrEnum):
    NO_BOOKING = "NO_BOOKING"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_UNKNOWN = "BOOKING_UNKNOWN"  # requires reconciliation, never blind rebooking
    BOOKED_CRM_PENDING = "BOOKED_CRM_PENDING"  # booking authoritative, CRM sync outstanding
    BLOCKED = "BLOCKED"
    CALL_DROPPED = "CALL_DROPPED"


def booking_operation_id(tenant_id: UUID, call_id: UUID, calendar_ref: str) -> str:
    """Deterministic id of the (single) semantic booking operation of a call."""
    parts = ("voiceos.booking.v1", str(tenant_id), str(call_id), calendar_ref)
    return "bk_" + hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class BookingIntent:
    """Validated, confirmed intent required before any booking write.

    Built by the gateway from the trusted ``CallContext`` and server-held confirmation
    state, never from model arguments alone. ``operation_id`` identifies the semantic
    booking of this call (one booking per call in Phase 0), so repeated proposals across
    turns map to the same operation. ``payload_hash`` detects a changed payload under
    the same operation.
    """

    tenant_id: UUID
    call_id: UUID
    calendar_ref: str
    slot_id: str
    contact_name: str
    contact_phone: str

    @property
    def operation_id(self) -> str:
        return booking_operation_id(self.tenant_id, self.call_id, self.calendar_ref)

    @property
    def payload_hash(self) -> str:
        payload = {
            "slot_id": self.slot_id,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
