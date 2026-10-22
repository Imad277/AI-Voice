from __future__ import annotations

from collections.abc import Iterator

import pytest
from support import make_calendar, make_context

from voiceos.booking.ledger import InMemoryBookingLedger
from voiceos.core.context import CallContext
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.calendar import CalendarMock
from voiceos.mocks.crm import CrmMock


@pytest.fixture
def calendar() -> CalendarMock:
    return make_calendar()


@pytest.fixture
def crm() -> CrmMock:
    return CrmMock()


@pytest.fixture
def ctx() -> CallContext:
    return make_context()


@pytest.fixture
def gateway(calendar: CalendarMock, crm: CrmMock, ctx: CallContext) -> Iterator[ToolGateway]:
    gw = ToolGateway(InMemoryBookingLedger(), calendar, crm)
    gw.open_session(ctx)
    yield gw
