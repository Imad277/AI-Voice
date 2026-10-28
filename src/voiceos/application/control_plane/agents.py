"""Agent lifecycle use cases: agents, drafts, versions, publishing and deployments.

    agent (identity) -> draft (editable, revisioned) -> version (validated snapshot)
      -> published version (immutable) -> deployment (environment -> published version)

Every use case takes a server-side ``Principal``; the organization always comes from it,
never from an argument. RBAC runs through ``Principal.require`` only; the database
re-checks write authorization and tenant isolation independently (0004). An id of another
organization behaves exactly like an unknown id. Database-independent: the
``AgentLifecycleStore`` port is implemented in infrastructure.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, TypeGuard

from voiceos.domain.agents.configuration import (
    MAX_DRAFT_BYTES,
    AgentConfiguration,
    ConfigurationCheck,
    validate_configuration,
)
from voiceos.domain.agents.model import (
    AgentId,
    AgentStatus,
    AgentVersionId,
    AgentVersionStatus,
    DeploymentEnvironment,
    DeploymentId,
    DeploymentStatus,
)
from voiceos.domain.identity.rbac import Permission, Principal


class AgentNotFound(Exception):
    pass


class VersionNotFound(Exception):
    pass


class StaleDraftRevision(Exception):
    """The draft changed since the caller read it (optimistic concurrency)."""


class InvalidAgentConfiguration(Exception):
    def __init__(self, issues: tuple[str, ...]) -> None:
        super().__init__(f"invalid agent configuration ({len(issues)} issues)")
        self.issues = issues


class LifecycleConflict(Exception):
    """The requested transition is not allowed in the current state."""


class UnusableToolReferences(Exception):
    """The version names tool instances the organization cannot use (see issues)."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        super().__init__(f"unusable tool references ({len(issues)} issues)")
        self.issues = issues


@dataclass(frozen=True, slots=True)
class AgentView:
    agent_id: AgentId
    name: str
    description: str
    status: AgentStatus
    draft: Mapping[str, object] = field(repr=False)
    draft_revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VersionView:
    agent_version_id: AgentVersionId
    agent_id: AgentId
    version_number: int
    status: AgentVersionStatus
    configuration: Mapping[str, object] = field(repr=False)
    configuration_hash: str
    created_at: datetime
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class DeploymentView:
    deployment_id: DeploymentId
    agent_id: AgentId
    agent_version_id: AgentVersionId
    version_number: int
    environment: DeploymentEnvironment
    status: DeploymentStatus
    created_at: datetime


class AgentLifecycleStore(Protocol):
    def create_agent(
        self, principal: Principal, name: str, description: str, draft: Mapping[str, object]
    ) -> AgentView: ...

    def get_agent(self, principal: Principal, agent_id: AgentId) -> AgentView | None: ...

    def update_draft(
        self, principal: Principal, agent_id: AgentId, expected_revision: int,
        draft: Mapping[str, object], name: str, description: str,
    ) -> AgentView: ...  # fmt: skip

    def create_version(
        self, principal: Principal, agent_id: AgentId, draft_revision: int,
        configuration: Mapping[str, object], configuration_hash: str,
    ) -> VersionView: ...  # fmt: skip

    def get_version(
        self, principal: Principal, version_id: AgentVersionId
    ) -> VersionView | None: ...

    def list_versions(self, principal: Principal, agent_id: AgentId) -> list[VersionView]: ...

    def publish_version(
        self, principal: Principal, version_id: AgentVersionId, configuration_hash: str
    ) -> VersionView: ...

    def archive_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView: ...

    def deploy(
        self, principal: Principal, agent_id: AgentId, version_id: AgentVersionId,
        environment: DeploymentEnvironment,
    ) -> DeploymentView: ...  # fmt: skip

    def deployment_history(
        self, principal: Principal, agent_id: AgentId, environment: DeploymentEnvironment
    ) -> list[DeploymentView]: ...


class ToolReferenceValidator(Protocol):
    """Checks the tool instance refs of a configuration (implemented by the integration
    use cases); returns issues, empty if every ref is usable."""

    def validate_agent_tool_references(
        self, principal: Principal, refs: Sequence[str]
    ) -> tuple[str, ...]: ...


class AgentService:
    def __init__(self, store: AgentLifecycleStore, tools: ToolReferenceValidator) -> None:
        self._store = store
        self._tools = tools

    # -- agents and drafts --------------------------------------------------------------

    def create_agent(
        self, principal: Principal, name: str, description: str = "",
        draft: Mapping[str, object] | None = None,
    ) -> AgentView:  # fmt: skip
        principal.require(Permission.AGENTS_MANAGE)
        initial = dict(draft or {})
        initial.setdefault("name", name)
        initial.setdefault("description", description)
        _check_draft_size(initial)
        return self._store.create_agent(principal, name, description, initial)

    def get_agent(self, principal: Principal, agent_id: AgentId) -> AgentView:
        principal.require(Permission.AGENTS_READ)
        agent = self._store.get_agent(principal, agent_id)
        if agent is None:
            raise AgentNotFound("agent not found")
        return agent

    def update_agent_draft(
        self, principal: Principal, agent_id: AgentId, expected_revision: int,
        draft: Mapping[str, object],
    ) -> AgentView:  # fmt: skip
        """Autosave-friendly: an incomplete draft is stored; validity is checked by
        ``validate_agent_draft`` and enforced by ``create_version``."""
        principal.require(Permission.AGENTS_MANAGE)
        _check_draft_size(draft)
        current = self.get_agent(principal, agent_id)
        name = draft.get("name")
        description = draft.get("description")
        return self._store.update_draft(
            principal, agent_id, expected_revision, dict(draft),
            name if _usable(name, 200) else current.name,
            description if _usable(description, 2000, allow_empty=True) else current.description,
        )  # fmt: skip

    def validate_agent_draft(self, principal: Principal, agent_id: AgentId) -> ConfigurationCheck:
        return validate_configuration(self.get_agent(principal, agent_id).draft)

    # -- versions -----------------------------------------------------------------------

    def create_version(
        self, principal: Principal, agent_id: AgentId, expected_revision: int
    ) -> VersionView:
        """Snapshot of exactly the validated draft revision the caller saw."""
        principal.require(Permission.AGENTS_MANAGE)
        agent = self.get_agent(principal, agent_id)
        if agent.draft_revision != expected_revision:
            raise StaleDraftRevision("draft changed")
        if agent.status is not AgentStatus.ACTIVE:
            raise LifecycleConflict("agent is not active")
        configuration = self._valid(agent.draft)
        return self._store.create_version(
            principal, agent_id, expected_revision, configuration.canonical(), configuration.hash()
        )

    def list_versions(self, principal: Principal, agent_id: AgentId) -> list[VersionView]:
        self.get_agent(principal, agent_id)  # agents.read + existence in this organization
        return self._store.list_versions(principal, agent_id)

    def get_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView:
        principal.require(Permission.AGENTS_READ)
        version = self._store.get_version(principal, version_id)
        if version is None:
            raise VersionNotFound("version not found")
        return version

    def publish_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView:
        principal.require(Permission.AGENTS_MANAGE)
        version = self.get_version(principal, version_id)
        if version.status is not AgentVersionStatus.DRAFT:
            raise LifecycleConflict("only an unpublished version can be published")
        configuration = self._valid(version.configuration)
        if configuration.hash() != version.configuration_hash:
            raise LifecycleConflict("configuration does not match its hash")
        # Every tool ref must name a usable tool instance of this organization (re-checked
        # by the database when the status changes); knowledge refs are still checked for
        # syntax and duplicates only (see domain configuration).
        issues = self._tools.validate_agent_tool_references(principal, configuration.tool_refs)
        if issues:
            raise UnusableToolReferences(issues)
        return self._store.publish_version(principal, version_id, version.configuration_hash)

    def archive_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView:
        principal.require(Permission.AGENTS_MANAGE)
        if self.get_version(principal, version_id).status is not AgentVersionStatus.PUBLISHED:
            raise LifecycleConflict("only a published version can be archived")
        return self._store.archive_version(principal, version_id)

    # -- deployments --------------------------------------------------------------------

    def deploy_version(
        self, principal: Principal, agent_id: AgentId, version_id: AgentVersionId,
        environment: DeploymentEnvironment,
    ) -> DeploymentView:  # fmt: skip
        principal.require(Permission.DEPLOYMENTS_MANAGE)
        version = self.get_version(principal, version_id)
        if version.agent_id != agent_id:
            raise VersionNotFound("version not found")
        if version.status is not AgentVersionStatus.PUBLISHED:
            raise LifecycleConflict("only a published version can be deployed")
        return self._store.deploy(principal, agent_id, version_id, environment)

    def get_deployment(
        self, principal: Principal, agent_id: AgentId, environment: DeploymentEnvironment
    ) -> DeploymentView | None:
        principal.require(Permission.DEPLOYMENTS_READ)
        self._require_agent(principal, agent_id)
        active = [d for d in self._store.deployment_history(principal, agent_id, environment)
                  if d.status is DeploymentStatus.ACTIVE]  # fmt: skip
        return active[0] if active else None

    def deployment_history(
        self, principal: Principal, agent_id: AgentId, environment: DeploymentEnvironment
    ) -> list[DeploymentView]:
        principal.require(Permission.DEPLOYMENTS_READ)
        self._require_agent(principal, agent_id)
        return self._store.deployment_history(principal, agent_id, environment)

    def rollback_deployment(
        self, principal: Principal, agent_id: AgentId, environment: DeploymentEnvironment,
        to_version_id: AgentVersionId | None = None,
    ) -> DeploymentView:  # fmt: skip
        """Re-bind the environment to an earlier published version. No version is changed;
        the previous binding stays in the deployment history."""
        principal.require(Permission.DEPLOYMENTS_MANAGE)
        current = self.get_deployment(principal, agent_id, environment)
        if current is None:
            raise LifecycleConflict("nothing is deployed")
        if to_version_id is None:
            earlier = [d for d in self._store.deployment_history(principal, agent_id, environment)
                       if d.agent_version_id != current.agent_version_id
                       and d.version_number < current.version_number]  # fmt: skip
            if not earlier:
                raise LifecycleConflict("no earlier deployment to roll back to")
            to_version_id = max(earlier, key=lambda d: d.created_at).agent_version_id
        target = self.get_version(principal, to_version_id)
        if target.agent_id != agent_id or target.version_number >= current.version_number:
            raise LifecycleConflict("rollback needs an earlier version of this agent")
        return self.deploy_version(principal, agent_id, to_version_id, environment)

    # -- helpers ------------------------------------------------------------------------

    def _require_agent(self, principal: Principal, agent_id: AgentId) -> None:
        if self._store.get_agent(principal, agent_id) is None:
            raise AgentNotFound("agent not found")

    @staticmethod
    def _valid(raw: Mapping[str, object]) -> AgentConfiguration:
        check = validate_configuration(raw)
        if check.configuration is None:
            raise InvalidAgentConfiguration(check.issues)
        return check.configuration


def _usable(value: object, limit: int, *, allow_empty: bool = False) -> TypeGuard[str]:
    return isinstance(value, str) and (allow_empty or bool(value.strip())) and len(value) <= limit


def _check_draft_size(draft: Mapping[str, object]) -> None:
    """Drafts must be JSON objects within the size limit (re-checked by the database)."""
    try:
        size = len(json.dumps(dict(draft), allow_nan=False, ensure_ascii=False).encode())
    except (TypeError, ValueError):
        raise InvalidAgentConfiguration(("<root>: not_json",)) from None
    if size > MAX_DRAFT_BYTES:
        raise InvalidAgentConfiguration(("<root>: too_large",))
