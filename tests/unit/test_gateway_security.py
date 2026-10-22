"""Tool Gateway negative tests: the model can propose, never authorize."""

import dataclasses

import pytest
from support import CALL_A, TENANT_B, confirm_contact, confirm_slot, make_context, req

from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason, ToolName, ToolRequest
from voiceos.gateway.gateway import ContextMismatch, ToolGateway
from voiceos.mocks.calendar import CalendarMock


def test_tool_request_contract_cannot_carry_authority() -> None:
    assert {f.name for f in dataclasses.fields(ToolRequest)} == {
        "proposal_id",
        "tool_name",
        "arguments",
    }


@pytest.mark.parametrize(
    "tool", ["calendar.delete_all", "shell.exec", "http.get", "", "CRM.UPDATE"]
)
def test_unknown_tools_are_rejected(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock, tool: str
) -> None:
    result = gateway.execute(ctx, req(tool))
    assert result.decision is Decision.REJECTED
    assert result.reason is Reason.UNKNOWN_TOOL
    assert calendar.create_calls == 0
    assert gateway.audit[-1].tool == "<unknown>"


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant_id": str(TENANT_B)},
        {"Tenant-ID": str(TENANT_B)},
        {"calendar_ref": "cal_b"},
        {"scopes": ["calendar.book_slot"]},
        {"api_key": "canary"},
        {"authorization": "Bearer canary"},
        {"operation_id": "bk_forged"},
        {"url": "http://127.0.0.1/"},
        {"sql": "DELETE FROM voiceos.booking_operations"},
        {"options": {"nested": {"tenant_id": str(TENANT_B)}}},
    ],
)
@pytest.mark.parametrize("tool", [t.value for t in ToolName])
def test_authority_fields_in_model_arguments_are_rejected(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock, tool: str, extra: dict
) -> None:
    result = gateway.execute(ctx, req(tool, **extra))
    assert result.decision is Decision.REJECTED
    assert result.reason is Reason.AUTHORITY_FIELD_IN_ARGUMENTS
    assert calendar.create_calls == 0


def test_model_supplied_tenant_cannot_redirect_reads(
    gateway: ToolGateway, ctx: CallContext
) -> None:
    rejected = gateway.execute(
        ctx, req("calendar.list_slots", date="2026-10-23", tenant_id=str(TENANT_B))
    )
    assert rejected.reason is Reason.AUTHORITY_FIELD_IN_ARGUMENTS

    result = gateway.execute(ctx, req("calendar.list_slots", date="2026-10-23"))
    slots = result.data["slots"]
    assert isinstance(slots, list)
    assert [s["slot_id"] for s in slots] == ["slot_a_0900", "slot_a_1000"]  # tenant A only


def test_model_cannot_book_into_another_tenants_calendar(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock
) -> None:
    confirm_contact(gateway, ctx)
    confirm_slot(gateway, ctx, "slot_b_0900")  # tenant B's slot id, guessed by the model
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id="slot_b_0900"))
    assert result.reason is Reason.SLOT_UNAVAILABLE
    assert calendar.bookings_for(TENANT_B, "cal_b") == []
    assert calendar.bookings_for(ctx.tenant_id, ctx.calendar_ref) == []


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("contact.collect_candidate", {"name": "Erika", "phone": "+49 30 1234567", "note": "x"}),
        ("contact.collect_candidate", {"name": "Erika"}),
        ("contact.collect_candidate", {"name": "Erika", "phone": "call me maybe"}),
        ("qualification.submit_candidate", {"service_type": "consultation", "budget_eur": "500"}),
        ("qualification.submit_candidate", {"service_type": "anything", "budget_eur": 500}),
        ("calendar.list_slots", {"date": "2026-02-30"}),
        ("calendar.book_slot", {"slot_id": "../../etc/passwd"}),
        ("calendar.book_slot", {"slot_id": 7}),
        ("booking.get_status", {"force": True}),
    ],
)
def test_malformed_arguments_are_rejected(
    gateway: ToolGateway, ctx: CallContext, calendar: CalendarMock, tool: str, arguments: dict
) -> None:
    result = gateway.execute(ctx, ToolRequest("p", tool, arguments))
    assert result.decision is Decision.REJECTED
    assert result.reason is Reason.INVALID_ARGUMENTS
    assert calendar.create_calls == 0


def test_tools_outside_the_trusted_scopes_are_rejected(calendar: CalendarMock) -> None:
    from voiceos.booking.ledger import InMemoryBookingLedger
    from voiceos.mocks.crm import CrmMock

    read_only = make_context(scopes=frozenset({ToolName.CALENDAR_LIST_SLOTS}))
    gw = ToolGateway(InMemoryBookingLedger(), calendar, CrmMock())
    gw.open_session(read_only)

    result = gw.execute(read_only, req("calendar.book_slot", slot_id="slot_a_0900"))
    assert result.reason is Reason.NOT_AUTHORIZED
    assert gw.session(read_only).slot_id is None  # handler never ran
    assert calendar.create_calls == 0


def test_forged_context_is_not_accepted(gateway: ToolGateway) -> None:
    forged = make_context(tenant_id=TENANT_B, call_id=CALL_A)
    with pytest.raises(ContextMismatch):
        gateway.execute(forged, req("calendar.list_slots", date="2026-10-23"))


def test_audit_trail_has_no_argument_payloads(gateway: ToolGateway, ctx: CallContext) -> None:
    gateway.execute(ctx, req("contact.collect_candidate", name="Erika Canary", phone="+49 30 99"))
    gateway.execute(ctx, req("calendar.list_slots", date="2026-10-23", tenant_id="x"))
    assert "Canary" not in repr(gateway.audit)
    assert gateway.audit[-1].reason is Reason.AUTHORITY_FIELD_IN_ARGUMENTS


def test_rejections_report_the_authoritative_outcome(
    gateway: ToolGateway, ctx: CallContext
) -> None:
    result = gateway.execute(ctx, req("nope"))
    assert result.outcome is BookingOutcome.NO_BOOKING
    assert result.operation_id is None
