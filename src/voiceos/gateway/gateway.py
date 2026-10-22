"""Tool Gateway.

Pipeline for every proposal:

    untrusted ToolRequest
      -> allowlist lookup            (unknown tool: reject)
      -> authority-key screen        (tenant/credential/scope/url/... in args: reject)
      -> strict schema validation    (unknown or malformed args: reject)
      -> trusted CallContext binding (session must have been opened with this context)
      -> authorization               (tool must be in the context's scopes)
      -> policy                      (call ended / execution blocked: reject)
      -> handler: idempotency + mock adapter execution
      -> authoritative ToolResult

Tenant identity and integration references are taken only from the CallContext. The
model never reaches the calendar or CRM directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import cast

from pydantic import BaseModel, ValidationError

from voiceos.booking.ledger import BookingLedger, CrmState, LedgerEntry, LedgerState
from voiceos.booking.session import CallSession
from voiceos.core.booking import BookingIntent, BookingOutcome, booking_operation_id
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason, ToolName, ToolRequest, ToolResult
from voiceos.gateway.schemas import (
    TOOL_SCHEMAS,
    BookSlotArgs,
    ContactCollectArgs,
    ListSlotsArgs,
    QualificationArgs,
    contains_authority_key,
    is_qualified,
)
from voiceos.mocks.calendar import (
    CalendarMock,
    CalendarTimeout,
    IdempotencyConflict,
    SlotUnavailable,
)
from voiceos.mocks.crm import CrmError, CrmMock


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Audit trail without argument payloads (no PII, no injected text)."""

    call_id: str
    proposal_id: str
    tool: str
    decision: Decision
    reason: Reason | None


class ContextMismatch(Exception):
    pass


Handler = Callable[[CallSession, str, BaseModel], ToolResult]


class ToolGateway:
    def __init__(self, ledger: BookingLedger, calendar: CalendarMock, crm: CrmMock) -> None:
        self._ledger = ledger
        self._calendar = calendar
        self._crm = crm
        self._sessions: dict[tuple[object, object], CallSession] = {}
        self.audit: list[AuditRecord] = []
        self._handlers: dict[ToolName, Handler] = {
            ToolName.CONTACT_COLLECT_CANDIDATE: self._contact_collect,
            ToolName.QUALIFICATION_SUBMIT_CANDIDATE: self._qualification_submit,
            ToolName.CALENDAR_LIST_SLOTS: self._list_slots,
            ToolName.CALENDAR_BOOK_SLOT: self._book_slot,
            ToolName.BOOKING_GET_STATUS: self._get_status,
            ToolName.CRM_UPDATE_CONTACT: self._crm_update,
        }

    # -- trusted server-side API (never reachable from model output) -------------------

    def open_session(self, context: CallContext) -> CallSession:
        key = (context.tenant_id, context.call_id)
        if key in self._sessions:
            raise ContextMismatch("session already open for this call")
        session = CallSession(context=context)
        self._sessions[key] = session
        return session

    def session(self, context: CallContext) -> CallSession:
        session = self._find_session(context)
        if session is None:
            raise ContextMismatch("no session bound to this context")
        return session

    def _find_session(self, context: CallContext) -> CallSession | None:
        session = self._sessions.get((context.tenant_id, context.call_id))
        return session if session is not None and session.context == context else None

    def block(self, context: CallContext) -> None:
        self.session(context).blocked = True

    def end_call(self, context: CallContext, *, dropped: bool = False) -> None:
        session = self.session(context)
        session.ended = True
        session.dropped = dropped

    def outcome(self, context: CallContext) -> BookingOutcome:
        session = self.session(context)
        return self._outcome(session, self._entry(session))

    def reconcile(self, context: CallContext) -> BookingOutcome:
        """Server-side reconciliation; also allowed after the call has ended."""
        session = self.session(context)
        return self._reconcile(session, "server-reconcile").outcome

    # -- untrusted entry point ----------------------------------------------------------

    def execute(self, context: CallContext, request: ToolRequest) -> ToolResult:
        try:
            tool = ToolName(request.tool_name)
        except ValueError:
            return self._reject(context, request, "<unknown>", Reason.UNKNOWN_TOOL)

        if contains_authority_key(request.arguments):
            return self._reject(context, request, tool, Reason.AUTHORITY_FIELD_IN_ARGUMENTS)
        try:
            args = TOOL_SCHEMAS[tool].model_validate(dict(request.arguments))
        except (ValidationError, TypeError):
            return self._reject(context, request, tool, Reason.INVALID_ARGUMENTS)

        session = self.session(context)  # raises if the context is not the trusted one
        if tool not in context.scopes:
            return self._reject(context, request, tool, Reason.NOT_AUTHORIZED, session)
        if session.ended:
            return self._reject(context, request, tool, Reason.CALL_ENDED, session)
        if session.blocked:
            return self._reject(context, request, tool, Reason.EXECUTION_BLOCKED, session)

        result = self._handlers[tool](session, request.proposal_id, args)
        self._record(context, request, tool, result)
        return result

    # -- handlers -------------------------------------------------------------------------

    def _contact_collect(self, session: CallSession, pid: str, args: BaseModel) -> ToolResult:
        args = cast(ContactCollectArgs, args)
        revision = session.propose_contact(args.name, args.phone)
        return self._result(
            session,
            pid,
            data={
                "readback": f"{args.name}, {args.phone}",
                "readback_revision": revision,
                "contact_state": session.contact_state.value,
            },
        )

    def _qualification_submit(self, session: CallSession, pid: str, args: BaseModel) -> ToolResult:
        args = cast(QualificationArgs, args)
        session.qualified = is_qualified(args)
        return self._result(session, pid, data={"qualified": session.qualified})

    def _list_slots(self, session: CallSession, pid: str, args: BaseModel) -> ToolResult:
        args = cast(ListSlotsArgs, args)
        ctx = session.context
        slots = self._calendar.list_slots(ctx.tenant_id, ctx.calendar_ref, args.date)
        return self._result(
            session,
            pid,
            data={"slots": [{"slot_id": s.slot_id, "start_local": s.start_local} for s in slots]},
        )

    def _book_slot(self, session: CallSession, pid: str, args: BaseModel) -> ToolResult:
        args = cast(BookSlotArgs, args)
        ctx = session.context
        entry = self._entry(session)

        if entry is not None and entry.state is not LedgerState.REJECTED:
            return self._existing_booking(session, pid, entry, args.slot_id)
        contact = session.confirmed_contact()
        if contact is None:
            return self._result(session, pid, Decision.REJECTED, Reason.CONTACT_NOT_CONFIRMED)
        if session.slot_id != args.slot_id or not session.slot_confirmed:
            revision = session.propose_slot(args.slot_id)
            return self._result(
                session,
                pid,
                Decision.REJECTED,
                Reason.SLOT_CONFIRMATION_REQUIRED,
                data={"slot_id": args.slot_id, "readback_revision": revision},
            )

        intent = BookingIntent(
            tenant_id=ctx.tenant_id,
            call_id=ctx.call_id,
            calendar_ref=ctx.calendar_ref,
            slot_id=args.slot_id,
            contact_name=contact[0],
            contact_phone=contact[1],
        )
        entry, claimed = self._ledger.claim(ctx, intent)
        if not claimed:
            return self._existing_booking(session, pid, entry, args.slot_id)

        try:
            booking = self._calendar.create_booking(
                ctx.tenant_id,
                ctx.calendar_ref,
                intent.operation_id,
                intent.payload_hash,
                intent.slot_id,
            )
        except (CalendarTimeout, IdempotencyConflict):
            entry = replace(entry, state=LedgerState.UNKNOWN)
            self._ledger.save(ctx, entry)
            return self._result(session, pid, reason=Reason.RECONCILIATION_REQUIRED, entry=entry)
        except SlotUnavailable:
            entry = replace(entry, state=LedgerState.REJECTED)
            self._ledger.save(ctx, entry)
            session.clear_slot()
            return self._result(
                session, pid, Decision.REJECTED, Reason.SLOT_UNAVAILABLE, entry=entry
            )

        entry = replace(entry, state=LedgerState.CONFIRMED, calendar_booking_id=booking.booking_id)
        self._ledger.save(ctx, entry)
        return self._result(
            session,
            pid,
            entry=entry,
            data={"booking_id": booking.booking_id, "slot_id": booking.slot_id},
        )

    def _existing_booking(
        self, session: CallSession, pid: str, entry: LedgerEntry, slot_id: str
    ) -> ToolResult:
        if entry.state is LedgerState.CONFIRMED and entry.slot_id == slot_id:
            # Idempotent repeat of the same semantic intent: same authoritative answer.
            return self._result(
                session,
                pid,
                entry=entry,
                data={"booking_id": entry.calendar_booking_id, "slot_id": entry.slot_id},
            )
        if entry.state is LedgerState.CONFIRMED:
            return self._result(
                session, pid, Decision.REJECTED, Reason.BOOKING_ALREADY_EXISTS, entry=entry
            )
        # SUBMITTED or UNKNOWN: a write may have happened. Never resubmit.
        return self._result(
            session, pid, Decision.REJECTED, Reason.RECONCILIATION_REQUIRED, entry=entry
        )

    def _get_status(self, session: CallSession, pid: str, args: BaseModel) -> ToolResult:
        return self._reconcile(session, pid)

    def _reconcile(self, session: CallSession, pid: str) -> ToolResult:
        ctx = session.context
        entry = self._entry(session)
        if entry is None or entry.state in (LedgerState.CONFIRMED, LedgerState.REJECTED):
            return self._result(session, pid, entry=entry)
        try:
            booking = self._calendar.get_by_operation(
                ctx.tenant_id, ctx.calendar_ref, entry.operation_id
            )
        except CalendarTimeout:
            return self._result(session, pid, reason=Reason.RECONCILIATION_REQUIRED, entry=entry)

        if booking is not None and booking.payload_hash == entry.payload_hash:
            entry = replace(
                entry, state=LedgerState.CONFIRMED, calendar_booking_id=booking.booking_id
            )
        else:
            # "Not found" is not proof that no booking exists (the write may still land or
            # the lookup may lag), and a different payload needs manual review. Either way
            # the booking stays UNKNOWN and is never released for rebooking. A final,
            # authoritative negative proof from a calendar provider is NOT DECIDED.
            entry = replace(entry, state=LedgerState.UNKNOWN)
        self._ledger.save(ctx, entry)
        reason = Reason.RECONCILIATION_REQUIRED if entry.state is LedgerState.UNKNOWN else None
        return self._result(session, pid, reason=reason, entry=entry)

    def _crm_update(self, session: CallSession, pid: str, args: BaseModel) -> ToolResult:
        ctx = session.context
        entry = self._entry(session)
        if entry is None or entry.state is not LedgerState.CONFIRMED:
            return self._result(session, pid, Decision.REJECTED, Reason.NO_BOOKING, entry=entry)
        if entry.crm_state is CrmState.SYNCED:
            return self._result(session, pid, entry=entry)
        contact = session.confirmed_contact()
        if contact is None:
            return self._result(
                session, pid, Decision.REJECTED, Reason.CONTACT_NOT_CONFIRMED, entry=entry
            )
        try:
            self._crm.update_contact(
                ctx.tenant_id,
                ctx.crm_ref,
                "crm_" + entry.operation_id,
                {
                    "name": contact[0],
                    "phone": contact[1],
                    "booking_id": entry.calendar_booking_id or "",
                    "slot_id": entry.slot_id,
                },
            )
        except CrmError:
            # The booking stays valid; only the CRM sync is outstanding.
            entry = replace(entry, crm_state=CrmState.PENDING)
            self._ledger.save(ctx, entry)
            return self._result(session, pid, reason=Reason.CRM_UNAVAILABLE, entry=entry)
        entry = replace(entry, crm_state=CrmState.SYNCED)
        self._ledger.save(ctx, entry)
        return self._result(session, pid, entry=entry)

    # -- helpers --------------------------------------------------------------------------

    def _entry(self, session: CallSession) -> LedgerEntry | None:
        ctx = session.context
        return self._ledger.get(
            ctx, booking_operation_id(ctx.tenant_id, ctx.call_id, ctx.calendar_ref)
        )

    @staticmethod
    def _outcome(session: CallSession, entry: LedgerEntry | None) -> BookingOutcome:
        """Outcome derives from the authoritative ledger first, then server-side flags."""
        if entry is not None:
            if entry.state is LedgerState.CONFIRMED:
                if entry.crm_state is CrmState.PENDING:
                    return BookingOutcome.BOOKED_CRM_PENDING
                return BookingOutcome.BOOKING_CONFIRMED
            if entry.state in (LedgerState.SUBMITTED, LedgerState.UNKNOWN):
                return BookingOutcome.BOOKING_UNKNOWN
        if session.blocked:
            return BookingOutcome.BLOCKED
        if session.dropped:
            return BookingOutcome.CALL_DROPPED
        return BookingOutcome.NO_BOOKING

    def _result(
        self,
        session: CallSession,
        pid: str,
        decision: Decision = Decision.EXECUTED,
        reason: Reason | None = None,
        *,
        entry: LedgerEntry | None = None,
        data: dict[str, object] | None = None,
    ) -> ToolResult:
        if entry is None:
            entry = self._entry(session)
        return ToolResult(
            proposal_id=pid,
            decision=decision,
            outcome=self._outcome(session, entry),
            reason=reason,
            operation_id=entry.operation_id if entry is not None else None,
            data=data or {},
        )

    def _reject(
        self,
        context: CallContext,
        request: ToolRequest,
        tool: str,
        reason: Reason,
        session: CallSession | None = None,
    ) -> ToolResult:
        session = session or self._find_session(context)
        outcome = BookingOutcome.NO_BOOKING
        if session is not None:
            outcome = self._outcome(session, self._entry(session))
        result = ToolResult(request.proposal_id, Decision.REJECTED, outcome, reason)
        self._record(context, request, tool, result)
        return result

    def _record(
        self, context: CallContext, request: ToolRequest, tool: str, result: ToolResult
    ) -> None:
        self.audit.append(
            AuditRecord(
                str(context.call_id), request.proposal_id, tool, result.decision, result.reason
            )
        )
