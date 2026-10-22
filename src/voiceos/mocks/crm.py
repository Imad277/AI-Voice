"""Deterministic CRM mock. Idempotent per operation_id; failures can be injected."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class CrmFault(StrEnum):
    SERVER_ERROR = "SERVER_ERROR"
    RATE_LIMITED = "RATE_LIMITED"


class CrmError(Exception):
    pass


@dataclass
class CrmMock:
    next_fault: CrmFault | None = None
    update_calls: int = 0
    _records: dict[tuple[UUID, str, str], dict[str, str]] = field(default_factory=dict)

    def update_contact(
        self, tenant_id: UUID, crm_ref: str, operation_id: str, fields: Mapping[str, str]
    ) -> None:
        self.update_calls += 1
        fault, self.next_fault = self.next_fault, None
        if fault is not None:
            raise CrmError(fault.value)
        self._records[(tenant_id, crm_ref, operation_id)] = dict(fields)

    def records_for(self, tenant_id: UUID, crm_ref: str) -> list[dict[str, str]]:
        """Observer view for tests."""
        return [r for (t, c, _), r in self._records.items() if (t, c) == (tenant_id, crm_ref)]
