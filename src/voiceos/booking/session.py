"""Per-call confirmation state.

Readback confirmation is server-side state, not model output. The model may propose a
contact or slot; it becomes confirmed only when trusted server code records the
caller's affirmation of the *current* readback revision. Any change creates a new
revision and invalidates the earlier confirmation.

How caller affirmation is detected in production is NOT DECIDED. Phase 0 uses the
deterministic ``classify_reply`` below so offline tests stay reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from voiceos.core.context import CallContext


class ContactState(StrEnum):
    EMPTY = "EMPTY"
    CANDIDATE = "CANDIDATE"  # proposed and read back, awaiting affirmation
    CONFIRMED = "CONFIRMED"


class Reply(StrEnum):
    AFFIRM = "AFFIRM"
    NEGATE = "NEGATE"
    OTHER = "OTHER"


_AFFIRM = {"ja", "ja richtig", "ja genau", "richtig", "korrekt", "genau", "stimmt"}
_NEGATE = {"nein", "nein falsch", "falsch", "stimmt nicht"}


def classify_reply(transcript: str) -> Reply:
    """Deterministic placeholder: exact phrases only, anything ambiguous is OTHER."""
    normalized = " ".join(transcript.lower().replace(",", " ").replace(".", " ").split())
    if normalized in _AFFIRM:
        return Reply.AFFIRM
    if normalized in _NEGATE:
        return Reply.NEGATE
    return Reply.OTHER


@dataclass
class CallSession:
    context: CallContext
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_state: ContactState = ContactState.EMPTY
    contact_revision: int = 0
    slot_id: str | None = None
    slot_confirmed: bool = False
    slot_revision: int = 0
    qualified: bool | None = None  # independent of booking outcome
    blocked: bool = False
    ended: bool = False
    dropped: bool = False  # ended abnormally (connection lost), not a normal hang-up

    def propose_contact(self, name: str, phone: str) -> int:
        if (name, phone) != (self.contact_name, self.contact_phone):
            self.contact_name, self.contact_phone = name, phone
            self.contact_revision += 1
            self.contact_state = ContactState.CANDIDATE
        elif self.contact_state is not ContactState.CONFIRMED:
            self.contact_state = ContactState.CANDIDATE
        return self.contact_revision

    def affirm_contact(self, revision: int) -> bool:
        if self.contact_state is ContactState.EMPTY or revision != self.contact_revision:
            return False  # stale or unknown readback
        self.contact_state = ContactState.CONFIRMED
        return True

    def confirmed_contact(self) -> tuple[str, str] | None:
        """(name, phone) only if the current revision was affirmed by the caller."""
        if self.contact_state is not ContactState.CONFIRMED:
            return None
        if self.contact_name is None or self.contact_phone is None:
            return None
        return self.contact_name, self.contact_phone

    def reject_contact(self) -> None:
        if self.contact_state is not ContactState.EMPTY:
            self.contact_state = ContactState.CANDIDATE
            self.contact_revision += 1

    def propose_slot(self, slot_id: str) -> int:
        if slot_id != self.slot_id:
            self.slot_id = slot_id
            self.slot_revision += 1
            self.slot_confirmed = False
        return self.slot_revision

    def affirm_slot(self, revision: int) -> bool:
        if self.slot_id is None or revision != self.slot_revision:
            return False
        self.slot_confirmed = True
        return True

    def clear_slot(self) -> None:
        self.slot_id = None
        self.slot_confirmed = False
        self.slot_revision += 1
