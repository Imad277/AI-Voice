"""Argument schemas for the tool allowlist.

Strict and closed: unknown keys are rejected, no type coercion. None of these schemas
has a field for tenant identity, credentials, scopes, integration references,
idempotency keys, URLs, SQL or shell commands.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from voiceos.core.tools import ToolName

# Keys that indicate an attempt to supply authority or reach outside the allowlist.
# Checked (recursively, case-insensitive) before schema validation so the rejection is
# explicit in the audit trail.
AUTHORITY_KEYS = frozenset(
    {
        "tenant",
        "tenant_id",
        "tenantid",
        "client_id",
        "agent_id",
        "call_id",
        "principal",
        "user_id",
        "role",
        "roles",
        "scope",
        "scopes",
        "permission",
        "permissions",
        "authorization",
        "auth",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
        "access_token",
        "api_key",
        "apikey",
        "calendar_ref",
        "crm_ref",
        "operation_id",
        "idempotency_key",
        "intent_id",
        "url",
        "uri",
        "endpoint",
        "host",
        "sql",
        "query",
        "command",
        "shell",
        "exec",
    }
)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ContactCollectArgs(_Args):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    phone: Annotated[str, StringConstraints(pattern=r"^\+?[0-9][0-9 ]{4,19}$")]


class QualificationArgs(_Args):
    service_type: Literal["consultation", "installation", "maintenance"]
    budget_eur: Annotated[int, Field(ge=0, le=10_000_000)]


class ListSlotsArgs(_Args):
    date: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]

    @field_validator("date")
    @classmethod
    def _real_date(cls, value: str) -> str:
        dt.date.fromisoformat(value)
        return value


class BookSlotArgs(_Args):
    slot_id: Annotated[str, StringConstraints(pattern=r"^slot_[a-z0-9_]{1,40}$")]


class NoArgs(_Args):
    pass


TOOL_SCHEMAS: Mapping[ToolName, type[_Args]] = {
    ToolName.CONTACT_COLLECT_CANDIDATE: ContactCollectArgs,
    ToolName.QUALIFICATION_SUBMIT_CANDIDATE: QualificationArgs,
    ToolName.CALENDAR_LIST_SLOTS: ListSlotsArgs,
    ToolName.CALENDAR_BOOK_SLOT: BookSlotArgs,
    ToolName.BOOKING_GET_STATUS: NoArgs,
    ToolName.CRM_UPDATE_CONTACT: NoArgs,
}


def contains_authority_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in AUTHORITY_KEYS or contains_authority_key(item):
                return True
    elif isinstance(value, list | tuple):
        return any(contains_authority_key(item) for item in value)
    return False


def is_qualified(args: QualificationArgs) -> bool:
    """Deterministic demo rule (fixture only, not a business decision)."""
    return args.service_type in ("consultation", "installation") and args.budget_eur >= 500
