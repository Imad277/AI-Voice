"""Integration value types: providers, tenant connections and credential references.

Database-independent. The enum values are the values stored by the ``0005_tool_registry``
migration and checked by its constraints.

Credentials never enter VoiceOS tables: a connection holds an opaque ``credential_ref``
only. Its format is syntactic; the secret store and the credential broker that resolve it
are decided later (D-16). Configuration objects of connections and tool instances are
screened so that they cannot carry secrets, authority fields or egress targets.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import NewType
from uuid import UUID

ProviderKey = NewType("ProviderKey", str)
ConnectionId = NewType("ConnectionId", UUID)
CredentialRef = NewType("CredentialRef", str)

# <namespace>.<name>, e.g. ``calendar.list_slots``; shared by provider and tool type keys.
CATALOG_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}\.[a-z][a-z0-9_]{0,63}$")
# Opaque pointer into a future secret store. Lowercase only, no whitespace, no scheme
# other than ``cred:``; the value behind it is never stored here.
CREDENTIAL_REF = re.compile(r"^cred:[a-z0-9][a-z0-9._/-]{0,199}$")

MAX_CONFIGURATION_BYTES = 16 * 1024  # also enforced by the database (0005)
MAX_CONFIGURATION_DEPTH = 4
MAX_VALUE_LENGTH = 1000
_CONFIG_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Names that would carry tenant/principal authority, credentials or egress targets. Kept
# equal to the Phase 0 gateway's AUTHORITY_KEYS (asserted by a test); the domain layer
# must not import the gateway.
AUTHORITY_NAMES = frozenset({
    "tenant", "tenant_id", "tenantid", "client_id", "agent_id", "call_id", "principal",
    "user_id", "role", "roles", "scope", "scopes", "permission", "permissions",
    "authorization", "auth", "credential", "credentials", "password", "secret", "token",
    "access_token", "api_key", "apikey", "calendar_ref", "crm_ref", "operation_id",
    "idempotency_key", "intent_id", "url", "uri", "endpoint", "host", "sql", "query",
    "command", "shell", "exec",
})  # fmt: skip
# Substrings that mark a configuration key as secret-bearing.
SECRET_MARKERS = (
    "password", "passwd", "secret", "token", "apikey", "api_key", "credential",
    "private_key", "privatekey", "access_key", "authorization", "bearer", "cookie",
    "signing", "session_key",
)  # fmt: skip
# Value prefixes of well-known secret formats; matched case-insensitively.
_SECRET_VALUE = re.compile(
    r"^\s*(sk-|sk_|pk_live|rk_live|xox[abprs]-|ghp_|gho_|github_pat_|glpat-|akia|asia|aiza|"
    r"bearer\s|basic\s|eyj|-----begin)",
    re.IGNORECASE,
)


class ProviderCategory(StrEnum):
    CALENDAR = "CALENDAR"
    CRM = "CRM"
    WEBHOOK = "WEBHOOK"


class AuthType(StrEnum):
    """How a connection authenticates. Metadata only: no auth flow exists yet."""

    NONE = "NONE"  # the provider needs no credential
    OAUTH2 = "OAUTH2"
    API_KEY = "API_KEY"
    HMAC_SIGNATURE = "HMAC_SIGNATURE"

    @property
    def needs_credential(self) -> bool:
        return self is not AuthType.NONE


class ConnectionStatus(StrEnum):
    PENDING = "PENDING"  # created, not verified
    ACTIVE = "ACTIVE"  # usable by tool instances
    DISCONNECTED = "DISCONNECTED"  # turned off by the organization
    ERROR = "ERROR"  # verification or use failed
    REVOKED = "REVOKED"  # credential withdrawn; terminal


# Allowed transitions. The database enforces the same table (0005, asserted by a test).
CONNECTION_TRANSITIONS: Mapping[ConnectionStatus, frozenset[ConnectionStatus]] = {
    ConnectionStatus.PENDING: frozenset({
        ConnectionStatus.ACTIVE, ConnectionStatus.ERROR, ConnectionStatus.DISCONNECTED,
        ConnectionStatus.REVOKED,
    }),
    ConnectionStatus.ACTIVE: frozenset({
        ConnectionStatus.DISCONNECTED, ConnectionStatus.ERROR, ConnectionStatus.REVOKED,
    }),
    ConnectionStatus.ERROR: frozenset({
        ConnectionStatus.ACTIVE, ConnectionStatus.DISCONNECTED, ConnectionStatus.REVOKED,
    }),
    ConnectionStatus.DISCONNECTED: frozenset({
        ConnectionStatus.PENDING, ConnectionStatus.REVOKED,
    }),
    ConnectionStatus.REVOKED: frozenset(),
}  # fmt: skip


def can_transition(current: ConnectionStatus, new: ConnectionStatus) -> bool:
    return new is current or new in CONNECTION_TRANSITIONS[current]


def initial_connection_status(auth_type: AuthType) -> ConnectionStatus:
    """A credential-less connection has nothing to verify; any other connection stays
    PENDING until a verification path exists (later PR)."""
    return ConnectionStatus.PENDING if auth_type.needs_credential else ConnectionStatus.ACTIVE


def credential_ref_issues(auth_type: AuthType, credential_ref: str | None) -> tuple[str, ...]:
    if not auth_type.needs_credential:
        return () if credential_ref is None else ("credential_ref: not_allowed",)
    if credential_ref is None:
        return ("credential_ref: missing",)
    return () if CREDENTIAL_REF.match(credential_ref) else ("credential_ref: invalid_format",)


def configuration_issues(raw: Mapping[str, object]) -> tuple[str, ...]:
    """Screen a non-secret configuration object. Issues name the location and the rule,
    never the value."""
    try:
        size = len(json.dumps(dict(raw), allow_nan=False, ensure_ascii=False).encode())
    except (TypeError, ValueError):
        return ("<root>: not_json",)
    if size > MAX_CONFIGURATION_BYTES:
        return ("<root>: too_large",)
    issues: list[str] = []
    _screen(raw, "", 1, issues)
    return tuple(issues)


def _screen(value: object, path: str, depth: int, issues: list[str]) -> None:
    where = path or "<root>"
    if isinstance(value, Mapping):
        if depth > MAX_CONFIGURATION_DEPTH:
            issues.append(f"{where}: too_deep")
            return
        for key, item in value.items():
            name = str(key)
            child = f"{path}.{name}" if path else name
            if not _CONFIG_KEY.match(name):
                issues.append(f"{child}: invalid_key")
            elif name in AUTHORITY_NAMES or any(m in name for m in SECRET_MARKERS):
                issues.append(f"{child}: forbidden_key")
            else:
                _screen(item, child, depth + 1, issues)
    elif isinstance(value, list):
        if depth > MAX_CONFIGURATION_DEPTH:
            issues.append(f"{where}: too_deep")
            return
        for index, item in enumerate(value):
            _screen(item, f"{where}[{index}]", depth + 1, issues)
    elif isinstance(value, str):
        if len(value) > MAX_VALUE_LENGTH:
            issues.append(f"{where}: too_long")
        elif "://" in value:
            issues.append(f"{where}: url_not_allowed")  # no egress before egress control
        elif _SECRET_VALUE.match(value):
            issues.append(f"{where}: secret_like_value")
