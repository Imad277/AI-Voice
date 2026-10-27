"""Server-side binding between one call and the Tool Gateway.

Built by trusted server code. It closes over the CallContext, so runtimes and adapters
can submit proposals and caller replies but can never choose or see the tenant, scopes
or integration references.

Benchmark harness only (Phase 1): when the caller's reply has just recorded a slot
confirmation in the trusted session, ``user_reply`` returns a fixed server status note
for the model's context. The note is rendered from session state alone (the validated
slot id), never from transcript or model text, carries no tenant, scope or credential,
and executes nothing: booking still needs a ``calendar.book_slot`` proposal that the
gateway checks as before.
"""

from __future__ import annotations

from voiceos.booking.session import CallSession, Reply, classify_reply
from voiceos.booking.speech import render_turn
from voiceos.core.context import CallContext
from voiceos.core.tools import Reason, ToolName, ToolRequest, ToolResult
from voiceos.gateway.gateway import ToolGateway


def slot_confirmation_note(session: CallSession) -> str | None:
    """Server status note for a slot confirmation recorded in the trusted session."""
    if session.slot_id is None or not session.slot_confirmed:
        return None
    return (
        f"Server-Status: Der Anrufer hat den vorgelesenen Termin {session.slot_id} "
        "ausdrücklich bestätigt. Die Bestätigung ist serverseitig gespeichert."
    )


class GatewayBinding:
    __slots__ = ("__context", "__gateway", "__pending")

    def __init__(self, gateway: ToolGateway, context: CallContext) -> None:
        self.__gateway = gateway
        self.__context = context
        self.__pending: tuple[ToolName, int] | None = None

    def execute(self, proposal: ToolRequest) -> ToolResult:
        result = self.__gateway.execute(self.__context, proposal)
        revision = result.data.get("readback_revision")
        if isinstance(revision, int):
            kind = (
                ToolName.CALENDAR_BOOK_SLOT
                if result.reason is Reason.SLOT_CONFIRMATION_REQUIRED
                else ToolName.CONTACT_COLLECT_CANDIDATE
            )
            self.__pending = (kind, revision)
        return result

    def user_reply(self, transcript: str) -> str | None:
        """Apply the caller's reply to the pending readback (deterministic classifier).

        Returns the server status note if this reply recorded a slot confirmation.
        """
        if self.__pending is None:
            return None
        kind, revision = self.__pending
        self.__pending = None  # any reply consumes the readback
        session = self.__gateway.session(self.__context)
        reply = classify_reply(transcript)
        if kind is ToolName.CONTACT_COLLECT_CANDIDATE:
            if reply is Reply.AFFIRM:
                session.affirm_contact(revision)
            elif reply is Reply.NEGATE:
                session.reject_contact()
        elif reply is Reply.AFFIRM:
            if session.affirm_slot(revision):
                return slot_confirmation_note(session)
        elif reply is Reply.NEGATE:
            session.clear_slot()
        return None

    def render(self, model_text: str, tool_name: str | None, result: ToolResult | None) -> str:
        return render_turn(model_text, tool_name, result)
