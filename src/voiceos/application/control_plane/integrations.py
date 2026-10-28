"""Tool registry and integration use cases: catalog, connections, tool instances and the
tool-reference check used when an agent version is published.

    tool type (global) <- provider capability (global) -> integration provider (global)
    tool instance (tenant) -> tool type [+ integration connection (tenant)]
    agent version tool_refs -> tool instance refs

Every use case takes a server-side ``Principal``; the organization always comes from it.
RBAC runs through ``Principal.require``; the database re-checks write authorization and
tenant isolation independently (0005). Ids of another organization behave like unknown
ids. Nothing here executes a tool or calls a provider: execution stays in the Tool
Gateway (tool instance -> tool type -> gateway execution), and connections hold an
opaque credential reference only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from voiceos.domain.identity.rbac import Permission, Principal
from voiceos.domain.integrations.model import (
    AuthType,
    ConnectionId,
    ConnectionStatus,
    CredentialRef,
    ProviderCategory,
    ProviderKey,
    can_transition,
    configuration_issues,
    credential_ref_issues,
    initial_connection_status,
)
from voiceos.domain.tools.model import (
    TOOL_INSTANCE_REF,
    ConfirmationPolicy,
    SideEffectClass,
    ToolInstanceId,
    ToolInstanceRef,
    ToolInstanceStatus,
    ToolTypeKey,
)

MAX_TOOL_REFS = 50  # same bound as the agent configuration


class ToolTypeNotFound(Exception):
    pass


class ProviderNotFound(Exception):
    pass


class ConnectionNotFound(Exception):
    pass


class ToolInstanceNotFound(Exception):
    pass


class StaleRevision(Exception):
    """The record changed since the caller read it (optimistic concurrency)."""


class InvalidIntegrationInput(Exception):
    def __init__(self, issues: tuple[str, ...]) -> None:
        super().__init__(f"invalid integration input ({len(issues)} issues)")
        self.issues = issues


class IntegrationConflict(Exception):
    """The requested change is not allowed in the current state."""


@dataclass(frozen=True, slots=True)
class ToolTypeView:
    key: ToolTypeKey
    name: str
    description: str
    schema_version: int
    input_schema: Mapping[str, object] = field(repr=False)
    output_schema: Mapping[str, object] = field(repr=False)
    schema_hash: str
    side_effect_class: SideEffectClass
    confirmation_policy: ConfirmationPolicy
    requires_connection: bool
    enabled: bool


@dataclass(frozen=True, slots=True)
class ProviderView:
    key: ProviderKey
    category: ProviderCategory
    display_name: str
    auth_type: AuthType
    enabled: bool
    capabilities: frozenset[ToolTypeKey]


@dataclass(frozen=True, slots=True)
class ConnectionView:
    connection_id: ConnectionId
    provider_key: ProviderKey
    display_name: str
    credential_ref: CredentialRef | None = field(repr=False)
    status: ConnectionStatus
    configuration: Mapping[str, object] = field(repr=False)
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ToolInstanceView:
    tool_instance_id: ToolInstanceId
    ref: ToolInstanceRef
    tool_type_key: ToolTypeKey
    connection_id: ConnectionId | None
    display_name: str
    configuration: Mapping[str, object] = field(repr=False)
    status: ToolInstanceStatus
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ToolRefState:
    """What the organization's data says about one referenced tool instance (``None``
    where nothing was found)."""

    ref: str
    instance_status: ToolInstanceStatus | None
    tool_type_enabled: bool | None
    uses_connection: bool
    connection_status: ConnectionStatus | None
    provider_enabled: bool | None


class IntegrationStore(Protocol):
    def list_tool_types(self, principal: Principal) -> list[ToolTypeView]: ...

    def list_providers(self, principal: Principal) -> list[ProviderView]: ...

    def create_connection(
        self, principal: Principal, provider_key: ProviderKey, display_name: str,
        credential_ref: CredentialRef | None, status: ConnectionStatus,
        configuration: Mapping[str, object],
    ) -> ConnectionView: ...  # fmt: skip

    def get_connection(
        self, principal: Principal, connection_id: ConnectionId
    ) -> ConnectionView | None: ...

    def update_connection(
        self, principal: Principal, connection_id: ConnectionId, expected_revision: int,
        display_name: str, configuration: Mapping[str, object], status: ConnectionStatus,
    ) -> ConnectionView: ...  # fmt: skip

    def create_tool_instance(
        self, principal: Principal, ref: ToolInstanceRef, tool_type_key: ToolTypeKey,
        connection_id: ConnectionId | None, display_name: str,
        configuration: Mapping[str, object],
    ) -> ToolInstanceView: ...  # fmt: skip

    def get_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId
    ) -> ToolInstanceView | None: ...

    def list_tool_instances(self, principal: Principal) -> list[ToolInstanceView]: ...

    def update_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId, expected_revision: int,
        display_name: str, configuration: Mapping[str, object], status: ToolInstanceStatus,
    ) -> ToolInstanceView: ...  # fmt: skip

    def tool_ref_states(self, principal: Principal, refs: Sequence[str]) -> list[ToolRefState]: ...


class IntegrationService:
    def __init__(self, store: IntegrationStore) -> None:
        self._store = store

    # -- catalog ------------------------------------------------------------------------

    def list_tool_types(self, principal: Principal) -> list[ToolTypeView]:
        principal.require(Permission.INTEGRATIONS_READ)
        return self._store.list_tool_types(principal)

    def list_integration_providers(self, principal: Principal) -> list[ProviderView]:
        principal.require(Permission.INTEGRATIONS_READ)
        return self._store.list_providers(principal)

    # -- connections --------------------------------------------------------------------

    def create_connection(
        self, principal: Principal, provider_key: str, display_name: str,
        configuration: Mapping[str, object] | None = None, credential_ref: str | None = None,
    ) -> ConnectionView:  # fmt: skip
        """A connection without a credential (auth type NONE) is ACTIVE at once; any other
        stays PENDING until a verification path exists (later PR)."""
        principal.require(Permission.INTEGRATIONS_MANAGE)
        provider = self._provider(principal, provider_key)
        if not provider.enabled:
            raise IntegrationConflict("integration provider is not available")
        config = dict(configuration or {})
        _raise_issues(
            _name_issues(display_name)
            + configuration_issues(config)
            + credential_ref_issues(provider.auth_type, credential_ref)
        )
        return self._store.create_connection(
            principal, provider.key, display_name.strip(),
            CredentialRef(credential_ref) if credential_ref is not None else None,
            initial_connection_status(provider.auth_type), config,
        )  # fmt: skip

    def get_connection(self, principal: Principal, connection_id: ConnectionId) -> ConnectionView:
        principal.require(Permission.INTEGRATIONS_READ)
        connection = self._store.get_connection(principal, connection_id)
        if connection is None:
            raise ConnectionNotFound("connection not found")
        return connection

    def update_connection_configuration(
        self, principal: Principal, connection_id: ConnectionId, expected_revision: int,
        configuration: Mapping[str, object], display_name: str | None = None,
    ) -> ConnectionView:  # fmt: skip
        principal.require(Permission.INTEGRATIONS_MANAGE)
        current = self.get_connection(principal, connection_id)
        if current.status is ConnectionStatus.REVOKED:
            raise IntegrationConflict("a revoked connection cannot be changed")
        name = current.display_name if display_name is None else display_name
        config = dict(configuration)
        _raise_issues(_name_issues(name) + configuration_issues(config))
        return self._store.update_connection(
            principal, connection_id, expected_revision, name.strip(), config, current.status
        )

    def disable_connection(
        self, principal: Principal, connection_id: ConnectionId, expected_revision: int
    ) -> ConnectionView:
        principal.require(Permission.INTEGRATIONS_MANAGE)
        current = self.get_connection(principal, connection_id)
        target = ConnectionStatus.DISCONNECTED
        if current.status is target:
            return current
        if not can_transition(current.status, target):
            raise IntegrationConflict("connection cannot be disconnected")
        return self._store.update_connection(
            principal, connection_id, expected_revision, current.display_name,
            current.configuration, target,
        )  # fmt: skip

    # -- tool instances -----------------------------------------------------------------

    def create_tool_instance(
        self, principal: Principal, ref: str, tool_type_key: str, display_name: str,
        connection_id: ConnectionId | None = None,
        configuration: Mapping[str, object] | None = None,
    ) -> ToolInstanceView:  # fmt: skip
        principal.require(Permission.INTEGRATIONS_MANAGE)
        tool_type = self._tool_type(principal, tool_type_key)
        if not tool_type.enabled:
            raise IntegrationConflict("tool type is not available")
        config = dict(configuration or {})
        issues = _name_issues(display_name) + configuration_issues(config)
        if not TOOL_INSTANCE_REF.match(ref):
            issues += ("ref: invalid_format",)
        if tool_type.requires_connection != (connection_id is not None):
            issues += ("connection_id: required" if tool_type.requires_connection
                       else "connection_id: not_allowed",)  # fmt: skip
        _raise_issues(issues)
        if connection_id is not None:
            connection = self.get_connection(principal, connection_id)
            if connection.status is ConnectionStatus.REVOKED:
                raise IntegrationConflict("connection is revoked")
            provider = self._provider(principal, connection.provider_key)
            if tool_type.key not in provider.capabilities:
                raise IntegrationConflict("the connection's provider does not serve this tool")
        return self._store.create_tool_instance(
            principal, ToolInstanceRef(ref), tool_type.key, connection_id,
            display_name.strip(), config,
        )  # fmt: skip

    def get_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId
    ) -> ToolInstanceView:
        principal.require(Permission.INTEGRATIONS_READ)
        instance = self._store.get_tool_instance(principal, tool_instance_id)
        if instance is None:
            raise ToolInstanceNotFound("tool instance not found")
        return instance

    def list_tool_instances(self, principal: Principal) -> list[ToolInstanceView]:
        principal.require(Permission.INTEGRATIONS_READ)
        return self._store.list_tool_instances(principal)

    def update_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId, expected_revision: int,
        configuration: Mapping[str, object] | None = None, display_name: str | None = None,
    ) -> ToolInstanceView:  # fmt: skip
        principal.require(Permission.INTEGRATIONS_MANAGE)
        current = self.get_tool_instance(principal, tool_instance_id)
        name = current.display_name if display_name is None else display_name
        config = dict(current.configuration if configuration is None else configuration)
        _raise_issues(_name_issues(name) + configuration_issues(config))
        return self._store.update_tool_instance(
            principal, tool_instance_id, expected_revision, name.strip(), config, current.status
        )

    def disable_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId, expected_revision: int
    ) -> ToolInstanceView:
        principal.require(Permission.INTEGRATIONS_MANAGE)
        current = self.get_tool_instance(principal, tool_instance_id)
        if current.status is ToolInstanceStatus.DISABLED:
            return current
        return self._store.update_tool_instance(
            principal, tool_instance_id, expected_revision, current.display_name,
            current.configuration, ToolInstanceStatus.DISABLED,
        )  # fmt: skip

    # -- agent versions -----------------------------------------------------------------

    def validate_agent_tool_references(
        self, principal: Principal, refs: Sequence[str]
    ) -> tuple[str, ...]:
        """Issues for tool instance refs an agent version may not use; empty if all are
        usable. Unknown and other organizations' refs are reported alike. Point-in-time
        check: the gateway must re-check at execution time."""
        principal.require(Permission.AGENTS_READ)
        if not refs:
            return ()
        if len(refs) > MAX_TOOL_REFS:
            return ("tool_refs: too_many",)
        states = self._store.tool_ref_states(principal, refs)
        return tuple(
            f"tool_refs.{index}: {problem}"
            for index, state in enumerate(states)
            if (problem := _unusable(state)) is not None
        )

    # -- helpers ------------------------------------------------------------------------

    def _provider(self, principal: Principal, key: str) -> ProviderView:
        found = [p for p in self._store.list_providers(principal) if p.key == key]
        if not found:
            raise ProviderNotFound("integration provider not found")
        return found[0]

    def _tool_type(self, principal: Principal, key: str) -> ToolTypeView:
        found = [t for t in self._store.list_tool_types(principal) if t.key == key]
        if not found:
            raise ToolTypeNotFound("tool type not found")
        return found[0]


def _unusable(state: ToolRefState) -> str | None:
    if state.instance_status is None:
        return "unknown_tool_instance"
    if state.instance_status is not ToolInstanceStatus.ENABLED:
        return "tool_instance_disabled"
    if not state.tool_type_enabled:
        return "tool_type_disabled"
    if state.uses_connection and not (
        state.connection_status is ConnectionStatus.ACTIVE and state.provider_enabled
    ):
        return "connection_not_active"
    return None


def _name_issues(display_name: str) -> tuple[str, ...]:
    return () if 1 <= len(display_name.strip()) <= 120 else ("display_name: invalid_length",)


def _raise_issues(issues: tuple[str, ...]) -> None:
    if issues:
        raise InvalidIntegrationInput(issues)
