"""Tool request/result contracts.

``ToolRequest`` is untrusted, model-originated input: a proposal, never an
authorization. It has no field that could carry tenant identity, credentials,
scopes or permissions; anything like that inside ``arguments`` is rejected by the
gateway.

``ToolResult`` is produced only by the Tool Gateway and is the authoritative answer
about what actually happened.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from voiceos.core.booking import BookingOutcome


class ToolName(StrEnum):
    CONTACT_COLLECT_CANDIDATE = "contact.collect_candidate"
    QUALIFICATION_SUBMIT_CANDIDATE = "qualification.submit_candidate"
    CALENDAR_LIST_SLOTS = "calendar.list_slots"
    CALENDAR_BOOK_SLOT = "calendar.book_slot"
    BOOKING_GET_STATUS = "booking.get_status"
    CRM_UPDATE_CONTACT = "crm.update_contact"


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """Untrusted proposal from the model. ``tool_name`` may be anything, including unknown."""

    proposal_id: str
    tool_name: str
    arguments: Mapping[str, object]


class Decision(StrEnum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class Reason(StrEnum):
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    AUTHORITY_FIELD_IN_ARGUMENTS = "AUTHORITY_FIELD_IN_ARGUMENTS"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    CALL_ENDED = "CALL_ENDED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    CONTACT_NOT_CONFIRMED = "CONTACT_NOT_CONFIRMED"
    SLOT_CONFIRMATION_REQUIRED = "SLOT_CONFIRMATION_REQUIRED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    BOOKING_ALREADY_EXISTS = "BOOKING_ALREADY_EXISTS"
    SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"
    NO_BOOKING = "NO_BOOKING"
    CRM_UNAVAILABLE = "CRM_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ToolResult:
    proposal_id: str
    decision: Decision
    outcome: BookingOutcome  # authoritative business outcome of the call after this step
    reason: Reason | None = None
    operation_id: str | None = None  # gateway-issued, never model-supplied
    data: Mapping[str, object] = field(default_factory=dict)
