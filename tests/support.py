"""Shared synthetic fixtures and helpers for the test suite (no real customer data)."""

from __future__ import annotations

from uuid import UUID

from voiceos.core.context import CallContext
from voiceos.core.tools import ToolName, ToolRequest, ToolResult
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.calendar import CalendarMock, Slot

# Synthetic canary tenants. No real customer data anywhere in the test suite.
TENANT_A = UUID("00000000-0000-4000-8000-00000000000a")
TENANT_B = UUID("00000000-0000-4000-8000-00000000000b")
CALL_A = UUID("00000000-0000-4000-8000-0000000000a1")
CALL_B = UUID("00000000-0000-4000-8000-0000000000b1")
DAY = "2026-10-23"


def make_context(
    tenant_id: UUID = TENANT_A,
    call_id: UUID = CALL_A,
    scopes: frozenset[ToolName] = frozenset(ToolName),
) -> CallContext:
    suffix = "a" if tenant_id == TENANT_A else "b"
    return CallContext(
        tenant_id=tenant_id,
        call_id=call_id,
        agent_id=f"agent_{suffix}",
        agent_release_id=f"release_{suffix}_1",
        principal=f"principal_{suffix}",
        calendar_ref=f"cal_{suffix}",
        crm_ref=f"crm_{suffix}",
        scopes=scopes,
    )


def make_calendar() -> CalendarMock:
    return CalendarMock(
        slots={
            (TENANT_A, "cal_a"): [
                Slot("slot_a_0900", f"{DAY}T09:00"),
                Slot("slot_a_1000", f"{DAY}T10:00"),
            ],
            (TENANT_B, "cal_b"): [Slot("slot_b_0900", f"{DAY}T09:00")],
        }
    )


def req(tool: str, pid: str = "p1", **arguments: object) -> ToolRequest:
    return ToolRequest(proposal_id=pid, tool_name=tool, arguments=arguments)


def confirm_contact(gateway: ToolGateway, ctx: CallContext) -> ToolResult:
    result = gateway.execute(
        ctx, req("contact.collect_candidate", name="Erika Muster", phone="+49 30 1234567")
    )
    revision = result.data["readback_revision"]
    assert isinstance(revision, int)
    assert gateway.session(ctx).affirm_contact(revision)
    return result


def confirm_slot(gateway: ToolGateway, ctx: CallContext, slot_id: str = "slot_a_0900") -> None:
    result = gateway.execute(ctx, req("calendar.book_slot", slot_id=slot_id))
    revision = result.data["readback_revision"]
    assert isinstance(revision, int)
    assert gateway.session(ctx).affirm_slot(revision)


def book(gateway: ToolGateway, ctx: CallContext, slot_id: str = "slot_a_0900") -> ToolResult:
    confirm_contact(gateway, ctx)
    confirm_slot(gateway, ctx, slot_id)
    return gateway.execute(ctx, req("calendar.book_slot", pid="book", slot_id=slot_id))
