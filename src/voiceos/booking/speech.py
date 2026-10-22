"""Speech guard: business statements come from authoritative results, never from the model.

The model's free text is never allowed to talk about booking state. If it does, the text
is dropped. Booking statements are rendered only from fixed templates keyed by the
gateway's authoritative ``ToolResult``. A success sentence therefore can not exist without
an authoritative BOOKING_CONFIRMED / BOOKED_CRM_PENDING result.

The keyword filter is defense in depth; the templates are the primary control.
"""

from __future__ import annotations

from voiceos.core.booking import BookingOutcome
from voiceos.core.tools import Decision, Reason, ToolName, ToolResult

_BOOKING_CLAIM_MARKERS = (
    "gebucht",
    "buchung",
    "bestätigt",
    "reserviert",
    "eingetragen",
    "termin steht",
    "booked",
    "booking",
    "confirmed",
)

BOOKING_SUCCESS = "Ihr Termin ist verbindlich gebucht."
BOOKING_UNKNOWN = (
    "Ich kann die Buchung gerade nicht bestätigen. Wir prüfen den Status und melden uns bei Ihnen."
)
SLOT_UNAVAILABLE = "Dieser Termin ist leider nicht mehr verfügbar."
BLOCKED = "Diese Aktion kann ich leider nicht ausführen."

_BOOKING_TOOLS = {ToolName.CALENDAR_BOOK_SLOT.value, ToolName.BOOKING_GET_STATUS.value}


def strip_booking_claims(model_text: str) -> str:
    lowered = model_text.lower()
    return "" if any(marker in lowered for marker in _BOOKING_CLAIM_MARKERS) else model_text


def booking_statement(tool_name: str, result: ToolResult) -> str | None:
    """Template for a gateway result, or None if the result carries no booking statement."""
    if result.outcome is BookingOutcome.BLOCKED:
        return BLOCKED
    if tool_name not in _BOOKING_TOOLS:
        return None
    if result.outcome is BookingOutcome.BOOKING_UNKNOWN:
        return BOOKING_UNKNOWN
    if result.reason is Reason.SLOT_UNAVAILABLE:
        return SLOT_UNAVAILABLE
    if result.decision is Decision.EXECUTED and result.outcome in (
        BookingOutcome.BOOKING_CONFIRMED,
        BookingOutcome.BOOKED_CRM_PENDING,
    ):
        return BOOKING_SUCCESS
    return None


def readback_prompt(result: ToolResult) -> str | None:
    """Readback rendered from server-held data, so the caller confirms what the server stores."""
    if "readback" in result.data:
        return f"Ich habe notiert: {result.data['readback']}. Ist das korrekt?"
    if result.reason is Reason.SLOT_CONFIRMATION_REQUIRED:
        return f"Soll ich den Termin {result.data['slot_id']} verbindlich buchen?"
    return None


def render_turn(model_text: str, tool_name: str | None, result: ToolResult | None) -> str:
    parts = [strip_booking_claims(model_text)]
    if tool_name is not None and result is not None:
        parts.append(booking_statement(tool_name, result) or "")
        parts.append(readback_prompt(result) or "")
    return " ".join(p for p in parts if p)
