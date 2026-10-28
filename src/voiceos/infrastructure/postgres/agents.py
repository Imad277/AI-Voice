"""PostgreSQL implementation of the agent lifecycle store.

Every operation runs in an organization-scoped transaction built from the principal; the
tenant of new rows is taken from ``voiceos.current_tenant_id()``, never from a parameter.
Writes first ask the database whether the acting user may manage agents/deployments
(0004) and then rely on RLS policies as the second line. Concurrency is handled by
PostgreSQL: the agent row lock serializes draft updates, version creation and deployment
switches; the partial unique index allows one active deployment per environment.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from psycopg import errors
from psycopg.types.json import Jsonb

from voiceos.application.control_plane.agents import (
    AgentNotFound,
    AgentView,
    DeploymentView,
    LifecycleConflict,
    StaleDraftRevision,
    VersionNotFound,
    VersionView,
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
from voiceos.domain.identity.rbac import Permission, PermissionDenied, Principal
from voiceos.infrastructure.postgres.scope import organization_transaction
from voiceos.tenancy.db import Conn

_AGENT = """SELECT agent_id, name, description, status, draft_configuration, draft_revision,
                   updated_at FROM voiceos.agents"""
_VERSION = """SELECT agent_version_id, agent_id, version_number, status, configuration,
                     configuration_hash, created_at, published_at FROM voiceos.agent_versions"""
_DEPLOYMENT = """SELECT d.deployment_id, d.agent_id, d.agent_version_id, v.version_number,
                        d.environment, d.status, d.created_at
                 FROM voiceos.deployments d
                 JOIN voiceos.agent_versions v ON v.agent_version_id = d.agent_version_id"""


def _agent(row: tuple[Any, ...]) -> AgentView:
    agent_id, name, description, status, draft, revision, updated_at = row
    return AgentView(AgentId(agent_id), name, description, AgentStatus(status), draft, revision,
                     updated_at)  # fmt: skip


def _version(row: tuple[Any, ...]) -> VersionView:
    version_id, agent_id, number, status, configuration, digest, created, published = row
    return VersionView(AgentVersionId(version_id), AgentId(agent_id), number,
                       AgentVersionStatus(status), configuration, digest, created,
                       published)  # fmt: skip


def _deployment(row: tuple[Any, ...]) -> DeploymentView:
    deployment_id, agent_id, version_id, number, environment, status, created = row
    return DeploymentView(DeploymentId(deployment_id), AgentId(agent_id),
                          AgentVersionId(version_id), number, DeploymentEnvironment(environment),
                          DeploymentStatus(status), created)  # fmt: skip


def _returned(row: tuple[Any, ...] | None) -> tuple[Any, ...]:
    if row is None:  # INSERT/UPDATE ... RETURNING on a checked path always yields a row
        raise RuntimeError("statement returned no row")
    return row


@contextmanager
def _mapped(permission: Permission) -> Iterator[None]:
    try:
        yield
    except errors.InsufficientPrivilege:
        raise PermissionDenied(permission) from None
    except errors.CheckViolation:
        raise LifecycleConflict("transition not allowed") from None


class PostgresAgentStore:
    def __init__(self, conn: Conn) -> None:
        self._conn = conn

    def _require(self, tx: Conn, check: str, permission: Permission) -> None:
        row = tx.execute(f"SELECT voiceos.{check}()").fetchone()
        if row is None or row[0] is not True:
            raise PermissionDenied(permission)

    # -- agents and drafts --------------------------------------------------------------

    def create_agent(
        self, principal: Principal, name: str, description: str, draft: Mapping[str, object]
    ) -> AgentView:
        with (
            _mapped(Permission.AGENTS_MANAGE),
            organization_transaction(self._conn, principal.scope) as tx,
        ):
            self._require(tx, "caller_can_manage_agents", Permission.AGENTS_MANAGE)
            row = tx.execute(
                """INSERT INTO voiceos.agents (tenant_id, name, description, draft_configuration)
                   VALUES (voiceos.current_tenant_id(), %s, %s, %s)
                   RETURNING agent_id, name, description, status, draft_configuration,
                             draft_revision, updated_at""",
                (name, description, Jsonb(dict(draft))),
            ).fetchone()
        return _agent(_returned(row))

    def get_agent(self, principal: Principal, agent_id: AgentId) -> AgentView | None:
        with organization_transaction(self._conn, principal.scope) as tx:
            row = tx.execute(f"{_AGENT} WHERE agent_id = %s", (agent_id,)).fetchone()
        return _agent(row) if row else None

    def update_draft(
        self, principal: Principal, agent_id: AgentId, expected_revision: int,
        draft: Mapping[str, object], name: str, description: str,
    ) -> AgentView:  # fmt: skip
        with (
            _mapped(Permission.AGENTS_MANAGE),
            organization_transaction(self._conn, principal.scope) as tx,
        ):
            self._require(tx, "caller_can_manage_agents", Permission.AGENTS_MANAGE)
            row = tx.execute(
                """UPDATE voiceos.agents
                   SET draft_configuration = %(draft)s,
                       draft_revision = CASE WHEN draft_configuration = %(draft)s
                                             THEN draft_revision ELSE draft_revision + 1 END,
                       name = %(name)s, description = %(description)s
                   WHERE agent_id = %(agent)s AND draft_revision = %(expected)s
                   RETURNING agent_id, name, description, status, draft_configuration,
                             draft_revision, updated_at""",
                {"draft": Jsonb(dict(draft)), "name": name, "description": description,
                 "agent": agent_id, "expected": expected_revision},
            ).fetchone()  # fmt: skip
            if row is None:
                exists = tx.execute(
                    "SELECT 1 FROM voiceos.agents WHERE agent_id = %s", (agent_id,)
                ).fetchone()
                if exists is None:
                    raise AgentNotFound("agent not found")
                raise StaleDraftRevision("draft changed")
        return _agent(row)

    # -- versions -----------------------------------------------------------------------

    def create_version(
        self, principal: Principal, agent_id: AgentId, draft_revision: int,
        configuration: Mapping[str, object], configuration_hash: str,
    ) -> VersionView:  # fmt: skip
        with (
            _mapped(Permission.AGENTS_MANAGE),
            organization_transaction(self._conn, principal.scope) as tx,
        ):
            self._require(tx, "caller_can_manage_agents", Permission.AGENTS_MANAGE)
            agent = tx.execute(
                "SELECT status, draft_revision FROM voiceos.agents WHERE agent_id = %s FOR UPDATE",
                (agent_id,),
            ).fetchone()
            if agent is None:
                raise AgentNotFound("agent not found")
            if agent[1] != draft_revision:
                raise StaleDraftRevision("draft changed")
            if agent[0] != AgentStatus.ACTIVE:
                raise LifecycleConflict("agent is not active")
            row = tx.execute(
                """INSERT INTO voiceos.agent_versions
                       (tenant_id, agent_id, version_number, status, configuration,
                        configuration_hash)
                   SELECT voiceos.current_tenant_id(), %(agent)s,
                          coalesce(max(version_number), 0) + 1, 'DRAFT', %(config)s, %(hash)s
                   FROM voiceos.agent_versions WHERE agent_id = %(agent)s
                   RETURNING agent_version_id, agent_id, version_number, status, configuration,
                             configuration_hash, created_at, published_at""",
                {"agent": agent_id, "config": Jsonb(dict(configuration)),
                 "hash": configuration_hash},
            ).fetchone()  # fmt: skip
        return _version(_returned(row))

    def get_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView | None:
        with organization_transaction(self._conn, principal.scope) as tx:
            row = tx.execute(f"{_VERSION} WHERE agent_version_id = %s", (version_id,)).fetchone()
        return _version(row) if row else None

    def list_versions(self, principal: Principal, agent_id: AgentId) -> list[VersionView]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                f"{_VERSION} WHERE agent_id = %s ORDER BY version_number", (agent_id,)
            ).fetchall()
        return [_version(r) for r in rows]

    def publish_version(
        self, principal: Principal, version_id: AgentVersionId, configuration_hash: str
    ) -> VersionView:
        with (
            _mapped(Permission.AGENTS_MANAGE),
            organization_transaction(self._conn, principal.scope) as tx,
        ):
            self._require(tx, "caller_can_manage_agents", Permission.AGENTS_MANAGE)
            row = tx.execute(
                """UPDATE voiceos.agent_versions v
                   SET status = 'PUBLISHED', published_at = now()
                   WHERE v.agent_version_id = %s AND v.status = 'DRAFT'
                     AND v.configuration_hash = %s
                     AND EXISTS (SELECT 1 FROM voiceos.agents a
                                 WHERE a.agent_id = v.agent_id AND a.status = 'ACTIVE')
                   RETURNING agent_version_id, agent_id, version_number, status, configuration,
                             configuration_hash, created_at, published_at""",
                (version_id, configuration_hash),
            ).fetchone()
            if row is None:
                self._missing_version(tx, version_id)
                raise LifecycleConflict("version cannot be published")
        return _version(row)

    def archive_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView:
        with (
            _mapped(Permission.AGENTS_MANAGE),
            organization_transaction(self._conn, principal.scope) as tx,
        ):
            self._require(tx, "caller_can_manage_agents", Permission.AGENTS_MANAGE)
            row = tx.execute(
                """UPDATE voiceos.agent_versions SET status = 'ARCHIVED'
                   WHERE agent_version_id = %s AND status = 'PUBLISHED'
                   RETURNING agent_version_id, agent_id, version_number, status, configuration,
                             configuration_hash, created_at, published_at""",
                (version_id,),
            ).fetchone()
            if row is None:
                self._missing_version(tx, version_id)
                raise LifecycleConflict("version cannot be archived")
        return _version(row)

    @staticmethod
    def _missing_version(tx: Conn, version_id: AgentVersionId) -> None:
        found = tx.execute(
            "SELECT 1 FROM voiceos.agent_versions WHERE agent_version_id = %s", (version_id,)
        ).fetchone()
        if found is None:
            raise VersionNotFound("version not found")

    # -- deployments --------------------------------------------------------------------

    def deploy(
        self, principal: Principal, agent_id: AgentId, version_id: AgentVersionId,
        environment: DeploymentEnvironment,
    ) -> DeploymentView:  # fmt: skip
        with (
            _mapped(Permission.DEPLOYMENTS_MANAGE),
            organization_transaction(self._conn, principal.scope) as tx,
        ):
            self._require(tx, "caller_can_manage_deployments", Permission.DEPLOYMENTS_MANAGE)
            agent = tx.execute(
                "SELECT status FROM voiceos.agents WHERE agent_id = %s FOR UPDATE", (agent_id,)
            ).fetchone()  # serializes deployment switches of this agent
            if agent is None:
                raise AgentNotFound("agent not found")
            if agent[0] != AgentStatus.ACTIVE:
                raise LifecycleConflict("agent is not active")
            current = tx.execute(
                f"{_DEPLOYMENT} WHERE d.agent_id = %s AND d.environment = %s"
                " AND d.status = 'ACTIVE'",
                (agent_id, environment.value),
            ).fetchone()
            if current is not None and current[2] == version_id:
                return _deployment(current)  # already serving this version (idempotent)
            if current is not None:
                tx.execute(
                    "UPDATE voiceos.deployments SET status = 'INACTIVE' WHERE deployment_id = %s",
                    (current[0],),
                )
            inserted = tx.execute(
                """INSERT INTO voiceos.deployments
                       (tenant_id, agent_id, agent_version_id, environment, status)
                   VALUES (voiceos.current_tenant_id(), %s, %s, %s, 'ACTIVE')
                   RETURNING deployment_id""",
                (agent_id, version_id, environment.value),
            ).fetchone()
            row = tx.execute(
                f"{_DEPLOYMENT} WHERE d.deployment_id = %s", (_returned(inserted)[0],)
            ).fetchone()
        return _deployment(_returned(row))

    def deployment_history(
        self, principal: Principal, agent_id: AgentId, environment: DeploymentEnvironment
    ) -> list[DeploymentView]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                f"{_DEPLOYMENT} WHERE d.agent_id = %s AND d.environment = %s"
                " ORDER BY d.created_at DESC, d.deployment_id",
                (agent_id, environment.value),
            ).fetchall()
        return [_deployment(r) for r in rows]
