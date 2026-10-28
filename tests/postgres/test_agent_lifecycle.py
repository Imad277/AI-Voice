"""Agent lifecycle (migration 0004) against the real database, through the application
service and the PostgreSQL store.

Organizations, users and memberships are seeded by the migrator; principals are built
directly so forged principals can prove that the database re-checks the stored membership
role for every write instead of trusting the caller.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from itertools import pairwise
from uuid import UUID, uuid4

import pytest
from psycopg import errors
from support import TENANT_A, TENANT_B, agent_configuration

from voiceos.application.control_plane.agents import (
    AgentNotFound,
    AgentService,
    AgentView,
    InvalidAgentConfiguration,
    LifecycleConflict,
    StaleDraftRevision,
    VersionNotFound,
    VersionView,
)
from voiceos.config import Settings
from voiceos.domain.agents.model import (
    AgentId,
    AgentVersionId,
    AgentVersionStatus,
    DeploymentEnvironment,
    DeploymentStatus,
    configuration_hash,
)
from voiceos.domain.identity.model import MembershipRole, OrganizationId, UserId
from voiceos.domain.identity.rbac import PermissionDenied, Principal
from voiceos.infrastructure.postgres.agents import PostgresAgentStore
from voiceos.infrastructure.postgres.scope import organization_transaction
from voiceos.tenancy.db import Conn, connect_app

R = MembershipRole
PROD = DeploymentEnvironment.PRODUCTION
DEV = DeploymentEnvironment.DEVELOPMENT
OWNER_A = UUID("00000000-0000-4000-8000-0000000001a0")
VIEWER_A = UUID("00000000-0000-4000-8000-0000000001a1")  # READ_ONLY in A
DEVELOPER_A = UUID("00000000-0000-4000-8000-0000000001a2")
OWNER_B = UUID("00000000-0000-4000-8000-0000000001b0")
A = OrganizationId(TENANT_A)
B = OrganizationId(TENANT_B)


def _p(user: UUID, organization: OrganizationId, role: MembershipRole) -> Principal:
    return Principal(UserId(user), organization, role)


ALICE = _p(OWNER_A, A, R.OWNER)
VIEWER = _p(VIEWER_A, A, R.READ_ONLY)
DEVELOPER = _p(DEVELOPER_A, A, R.DEVELOPER)
BOB = _p(OWNER_B, B, R.OWNER)
FORGED = _p(VIEWER_A, A, R.OWNER)  # claims a role the stored membership does not have
INTRUDER = _p(OWNER_B, A, R.OWNER)  # no membership in A at all


@pytest.fixture
def people(migrator: Conn) -> None:
    migrator.execute(
        "INSERT INTO voiceos.organizations (tenant_id, name, slug) VALUES"
        " (%s, 'Org A', 'org-a'), (%s, 'Org B', 'org-b')",
        (TENANT_A, TENANT_B),
    )
    migrator.execute(
        "INSERT INTO voiceos.users (user_id, external_subject, email, display_name) VALUES"
        " (%s, 'sub-oa', 'oa@example.org', 'OA'), (%s, 'sub-va', 'va@example.org', 'VA'),"
        " (%s, 'sub-da', 'da@example.org', 'DA'), (%s, 'sub-ob', 'ob@example.org', 'OB')",
        (OWNER_A, VIEWER_A, DEVELOPER_A, OWNER_B),
    )
    migrator.execute(
        "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role) VALUES"
        " (%s, %s, 'OWNER'), (%s, %s, 'READ_ONLY'), (%s, %s, 'DEVELOPER'), (%s, %s, 'OWNER')",
        (TENANT_A, OWNER_A, TENANT_A, VIEWER_A, TENANT_A, DEVELOPER_A, TENANT_B, OWNER_B),
    )


@pytest.fixture
def store(app_conn: Conn, people: None) -> PostgresAgentStore:
    return PostgresAgentStore(app_conn)


@pytest.fixture
def service(store: PostgresAgentStore) -> AgentService:
    return AgentService(store)


def _count(conn: Conn, sql: str, *params: object) -> int:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return int(row[0])


def _agent(service: AgentService, principal: Principal = ALICE) -> AgentView:
    return service.create_agent(principal, "Reception", draft=agent_configuration())


def _published(
    service: AgentService, agent: AgentView, principal: Principal = ALICE
) -> VersionView:
    revision = service.get_agent(principal, agent.agent_id).draft_revision
    version = service.create_version(principal, agent.agent_id, revision)
    return service.publish_version(principal, version.agent_version_id)


def _in_threads(*targets: Callable[[], object]) -> list[object]:
    """Run each target on its own thread at the same moment; return results or errors."""
    barrier = threading.Barrier(len(targets))
    results: list[object] = [None] * len(targets)

    def run(index: int, target: Callable[[], object]) -> None:
        barrier.wait(5)
        try:
            results[index] = target()
        except BaseException as exc:  # recorded for the assertion
            results[index] = exc

    threads = [threading.Thread(target=run, args=(i, t)) for i, t in enumerate(targets)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert not any(thread.is_alive() for thread in threads)
    return results


# -- agents and drafts --------------------------------------------------------------------------


def test_create_read_and_update_draft(service: AgentService, migrator: Conn) -> None:
    agent = _agent(service)
    assert agent.draft_revision == 0 and agent.draft["name"] == "Reception"
    tenant = migrator.execute(
        "SELECT tenant_id FROM voiceos.agents WHERE agent_id = %s", (agent.agent_id,)
    ).fetchone()
    assert tenant == (TENANT_A,)  # tenant from the bound organization, never a parameter
    updated = service.update_agent_draft(
        ALICE, agent.agent_id, 0, agent_configuration(name="Front desk")
    )
    assert updated.draft_revision == 1 and updated.name == "Front desk"
    same = service.update_agent_draft(ALICE, agent.agent_id, 1, updated.draft)
    assert same.draft_revision == 1  # an identical autosave does not advance the revision
    with pytest.raises(StaleDraftRevision):
        service.update_agent_draft(ALICE, agent.agent_id, 0, agent_configuration())
    assert service.get_agent(VIEWER, agent.agent_id).draft_revision == 1


def test_database_enforces_the_draft_revision_step(
    store: PostgresAgentStore, app_conn: Conn
) -> None:
    agent = store.create_agent(ALICE, "R", "", {})
    for sql in (
        "UPDATE voiceos.agents SET draft_configuration = '{\"a\": 1}' WHERE agent_id = %s",
        "UPDATE voiceos.agents SET draft_revision = 5 WHERE agent_id = %s",
        "UPDATE voiceos.agents SET draft_configuration = '{\"a\": 1}',"
        " draft_revision = draft_revision + 2 WHERE agent_id = %s",
        "UPDATE voiceos.agents SET draft_configuration = '[]', draft_revision = 1"
        " WHERE agent_id = %s",
    ):
        with (
            pytest.raises(errors.CheckViolation),
            organization_transaction(app_conn, ALICE.scope) as tx,
        ):
            tx.execute(sql, (agent.agent_id,))
    oversized = {"blob": "x" * (256 * 1024)}
    with pytest.raises(LifecycleConflict):  # the size limit holds in the database as well
        store.update_draft(ALICE, agent.agent_id, 0, oversized, "R", "")


def test_agent_identity_is_immutable(store: PostgresAgentStore, migrator: Conn) -> None:
    agent = store.create_agent(ALICE, "R", "", {})
    with pytest.raises(errors.CheckViolation):
        migrator.execute(
            "UPDATE voiceos.agents SET tenant_id = %s WHERE agent_id = %s",
            (TENANT_B, agent.agent_id),
        )


# -- tenant isolation and authorization ------------------------------------------------------


def test_other_organization_cannot_see_or_change_anything(
    service: AgentService, store: PostgresAgentStore, app_conn: Conn
) -> None:
    agent = _agent(service)
    version = _published(service, agent)
    service.deploy_version(ALICE, agent.agent_id, version.agent_version_id, PROD)
    own = _agent(service, BOB)
    with pytest.raises(AgentNotFound):
        service.get_agent(BOB, agent.agent_id)
    with pytest.raises(AgentNotFound):
        service.update_agent_draft(BOB, agent.agent_id, 0, {})
    with pytest.raises(AgentNotFound):
        service.create_version(BOB, agent.agent_id, 0)
    with pytest.raises(VersionNotFound):
        service.publish_version(BOB, version.agent_version_id)
    with pytest.raises(VersionNotFound):  # A's version cannot be bound to B's agent
        service.deploy_version(BOB, own.agent_id, version.agent_version_id, PROD)
    with pytest.raises(AgentNotFound):
        service.deployment_history(BOB, agent.agent_id, PROD)
    # The store alone (no application checks) does not cross the boundary either.
    assert store.get_agent(BOB, agent.agent_id) is None
    assert store.get_version(BOB, version.agent_version_id) is None
    assert store.list_versions(BOB, agent.agent_id) == []
    assert store.deployment_history(BOB, agent.agent_id, PROD) == []
    with pytest.raises(AgentNotFound):
        store.update_draft(BOB, agent.agent_id, 0, {}, "x", "")
    with pytest.raises(AgentNotFound):
        store.create_version(BOB, agent.agent_id, 0, {}, configuration_hash({}))
    with pytest.raises(VersionNotFound):
        store.publish_version(BOB, version.agent_version_id, version.configuration_hash)
    with pytest.raises(VersionNotFound):
        store.archive_version(BOB, version.agent_version_id)
    with pytest.raises((AgentNotFound, LifecycleConflict, PermissionDenied)):
        store.deploy(BOB, own.agent_id, version.agent_version_id, PROD)
    with (
        pytest.raises((errors.InsufficientPrivilege, errors.ForeignKeyViolation)),
        organization_transaction(app_conn, BOB.scope) as tx,
    ):
        tx.execute(
            "INSERT INTO voiceos.agent_versions (tenant_id, agent_id, version_number,"
            " status, configuration, configuration_hash) VALUES (%s, %s, 99, 'DRAFT',"
            " '{}', %s)",
            (TENANT_A, agent.agent_id, configuration_hash({})),
        )
    assert service.get_agent(ALICE, agent.agent_id).draft_revision == 0


def test_read_only_member_is_refused_by_application_and_database(
    service: AgentService, store: PostgresAgentStore, app_conn: Conn
) -> None:
    agent = _agent(service)
    version = _published(service, agent)
    with pytest.raises(PermissionDenied):
        service.create_agent(VIEWER, "X")
    with pytest.raises(PermissionDenied):
        service.deploy_version(VIEWER, agent.agent_id, version.agent_version_id, PROD)
    # A forged principal passes Principal.require; the stored role decides in the database.
    for principal in (FORGED, INTRUDER):
        with pytest.raises(PermissionDenied):
            store.create_agent(principal, "X", "", {})
        with pytest.raises(PermissionDenied):
            store.update_draft(principal, agent.agent_id, 0, {}, "X", "")
        with pytest.raises(PermissionDenied):
            store.create_version(principal, agent.agent_id, 0, {}, configuration_hash({}))
        with pytest.raises(PermissionDenied):
            store.archive_version(principal, version.agent_version_id)
        with pytest.raises(PermissionDenied):
            store.deploy(principal, agent.agent_id, version.agent_version_id, PROD)
    # Direct SQL as the read-only member: RLS refuses inserts and sees nothing to update.
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, VIEWER.scope) as tx,
    ):
        tx.execute("INSERT INTO voiceos.agents (tenant_id, name) VALUES (%s, 'X')", (A,))
    with organization_transaction(app_conn, VIEWER.scope) as tx:
        cursor = tx.execute(
            "UPDATE voiceos.agents SET name = 'Hijacked' WHERE agent_id = %s", (agent.agent_id,)
        )
        assert cursor.rowcount == 0
        cursor = tx.execute(
            "UPDATE voiceos.deployments SET status = 'INACTIVE' WHERE agent_id = %s",
            (agent.agent_id,),
        )
        assert cursor.rowcount == 0
    assert service.get_agent(VIEWER, agent.agent_id).name == "Reception"


def test_developer_may_manage(service: AgentService) -> None:
    agent = _agent(service, DEVELOPER)
    version = _published(service, agent, DEVELOPER)
    deployed = service.deploy_version(DEVELOPER, agent.agent_id, version.agent_version_id, DEV)
    assert deployed.status is DeploymentStatus.ACTIVE


def test_suspended_member_loses_write_access(store: PostgresAgentStore, migrator: Conn) -> None:
    migrator.execute(
        "UPDATE voiceos.organization_memberships SET status = 'SUSPENDED' WHERE user_id = %s",
        (DEVELOPER_A,),
    )
    with pytest.raises(PermissionDenied):
        store.create_agent(DEVELOPER, "X", "", {})


# -- versions -----------------------------------------------------------------------------------


def test_versions_are_monotonic_snapshots(service: AgentService) -> None:
    agent = _agent(service)
    v1 = service.create_version(ALICE, agent.agent_id, 0)
    service.update_agent_draft(ALICE, agent.agent_id, 0, agent_configuration(personality="calm"))
    v2 = service.create_version(ALICE, agent.agent_id, 1)
    assert (v1.version_number, v2.version_number) == (1, 2)
    assert "personality" in v1.configuration and v1.configuration["personality"] == ""
    assert v2.configuration["personality"] == "calm"
    stored = service.get_version(ALICE, v1.agent_version_id)
    assert stored.configuration == v1.configuration  # later draft edits do not leak in
    assert stored.configuration_hash == configuration_hash(dict(stored.configuration))
    assert [v.version_number for v in service.list_versions(ALICE, agent.agent_id)] == [1, 2]


def test_invalid_draft_creates_no_version(service: AgentService, migrator: Conn) -> None:
    agent = service.create_agent(ALICE, "Incomplete")
    with pytest.raises(InvalidAgentConfiguration):
        service.create_version(ALICE, agent.agent_id, 0)
    assert _count(migrator, "SELECT count(*) FROM voiceos.agent_versions") == 0


def test_published_version_is_immutable(service: AgentService, app_conn: Conn) -> None:
    agent = _agent(service)
    version = _published(service, agent)
    assert version.status is AgentVersionStatus.PUBLISHED and version.published_at is not None
    for sql in (
        "UPDATE voiceos.agent_versions SET configuration = '{}' WHERE agent_version_id = %s",
        "UPDATE voiceos.agent_versions SET status = 'DRAFT', published_at = NULL"
        " WHERE agent_version_id = %s",
        "DELETE FROM voiceos.agent_versions WHERE agent_version_id = %s",
    ):
        with (
            pytest.raises((errors.CheckViolation, errors.InsufficientPrivilege)),
            organization_transaction(app_conn, ALICE.scope) as tx,
        ):
            tx.execute(sql, (version.agent_version_id,))
    assert service.get_version(ALICE, version.agent_version_id) == version


def test_publish_refuses_tampered_or_stale_snapshots(
    service: AgentService, store: PostgresAgentStore, migrator: Conn
) -> None:
    agent = _agent(service)
    version = service.create_version(ALICE, agent.agent_id, 0)
    with pytest.raises(LifecycleConflict):  # the store re-checks the hash it was given
        store.publish_version(ALICE, version.agent_version_id, "0" * 64)
    migrator.execute(
        "UPDATE voiceos.agent_versions SET configuration = configuration"
        ' || \'{"opening_message": "changed"}\' WHERE agent_version_id = %s',
        (version.agent_version_id,),
    )
    with pytest.raises(LifecycleConflict):
        service.publish_version(ALICE, version.agent_version_id)
    assert service.get_version(ALICE, version.agent_version_id).status is AgentVersionStatus.DRAFT


def test_archive_rules(service: AgentService) -> None:
    agent = _agent(service)
    v1, v2 = _published(service, agent), _published(service, agent)
    service.deploy_version(ALICE, agent.agent_id, v1.agent_version_id, PROD)
    with pytest.raises(LifecycleConflict):  # still served by an active deployment
        service.archive_version(ALICE, v1.agent_version_id)
    archived = service.archive_version(ALICE, v2.agent_version_id)
    assert archived.status is AgentVersionStatus.ARCHIVED
    with pytest.raises(LifecycleConflict):
        service.deploy_version(ALICE, agent.agent_id, v2.agent_version_id, DEV)


def test_archived_agent_gets_no_new_versions_or_deployments(
    service: AgentService, store: PostgresAgentStore, migrator: Conn
) -> None:
    agent = _agent(service)
    version = _published(service, agent)
    migrator.execute(
        "UPDATE voiceos.agents SET status = 'ARCHIVED' WHERE agent_id = %s", (agent.agent_id,)
    )
    with pytest.raises(LifecycleConflict):
        service.create_version(ALICE, agent.agent_id, 0)
    with pytest.raises(LifecycleConflict):
        store.deploy(ALICE, agent.agent_id, version.agent_version_id, PROD)


# -- deployments ---------------------------------------------------------------------------------


def test_unpublished_version_cannot_be_deployed(
    service: AgentService, store: PostgresAgentStore
) -> None:
    agent = _agent(service)
    draft = service.create_version(ALICE, agent.agent_id, 0)
    with pytest.raises(LifecycleConflict):
        service.deploy_version(ALICE, agent.agent_id, draft.agent_version_id, PROD)
    with pytest.raises(LifecycleConflict):  # the database guard, without the application
        store.deploy(ALICE, agent.agent_id, draft.agent_version_id, PROD)
    assert store.deployment_history(ALICE, agent.agent_id, PROD) == []


def test_one_active_deployment_per_environment(service: AgentService, migrator: Conn) -> None:
    agent = _agent(service)
    v1, v2 = _published(service, agent), _published(service, agent)
    first = service.deploy_version(ALICE, agent.agent_id, v1.agent_version_id, PROD)
    again = service.deploy_version(ALICE, agent.agent_id, v1.agent_version_id, PROD)
    assert again.deployment_id == first.deployment_id  # idempotent re-deploy
    service.deploy_version(ALICE, agent.agent_id, v2.agent_version_id, PROD)
    service.deploy_version(ALICE, agent.agent_id, v1.agent_version_id, DEV)
    current = service.get_deployment(ALICE, agent.agent_id, PROD)
    assert current is not None and current.agent_version_id == v2.agent_version_id
    development = service.get_deployment(ALICE, agent.agent_id, DEV)
    assert development is not None and development.agent_version_id == v1.agent_version_id
    history = service.deployment_history(ALICE, agent.agent_id, PROD)
    assert [(d.version_number, d.status) for d in history] == [
        (2, DeploymentStatus.ACTIVE), (1, DeploymentStatus.INACTIVE),
    ]  # fmt: skip
    with pytest.raises(errors.UniqueViolation):
        migrator.execute(
            "INSERT INTO voiceos.deployments (tenant_id, agent_id, agent_version_id,"
            " environment, status) VALUES (%s, %s, %s, 'production', 'ACTIVE')",
            (TENANT_A, agent.agent_id, v1.agent_version_id),
        )


def test_rollback_rebinds_without_touching_versions(service: AgentService) -> None:
    agent = _agent(service)
    v1, v2 = _published(service, agent), _published(service, agent)
    service.deploy_version(ALICE, agent.agent_id, v1.agent_version_id, PROD)
    service.deploy_version(ALICE, agent.agent_id, v2.agent_version_id, PROD)
    before = service.list_versions(ALICE, agent.agent_id)
    rolled = service.rollback_deployment(ALICE, agent.agent_id, PROD)
    assert (
        rolled.agent_version_id == v1.agent_version_id and rolled.status is DeploymentStatus.ACTIVE
    )
    assert service.list_versions(ALICE, agent.agent_id) == before
    history = service.deployment_history(ALICE, agent.agent_id, PROD)
    assert [d.version_number for d in history] == [1, 2, 1]
    assert [d.status for d in history].count(DeploymentStatus.ACTIVE) == 1
    with pytest.raises(PermissionDenied):
        service.rollback_deployment(VIEWER, agent.agent_id, PROD)


# -- concurrency ----------------------------------------------------------------------------------


def _service(settings: Settings) -> tuple[AgentService, Conn]:
    conn = connect_app(settings)
    return AgentService(PostgresAgentStore(conn)), conn


def test_parallel_draft_updates_lose_no_update(service: AgentService, settings: Settings) -> None:
    agent = _agent(service)
    workers = [_service(settings) for _ in range(6)]
    try:
        results = _in_threads(*(
            (lambda s=s, i=i: s.update_agent_draft(
                ALICE, agent.agent_id, 0, agent_configuration(personality=f"variant {i}")))
            for i, (s, _) in enumerate(workers)
        ))  # fmt: skip
    finally:
        for _, conn in workers:
            conn.close()
    winners = [r for r in results if isinstance(r, AgentView)]
    assert len(winners) == 1, results
    assert all(isinstance(r, StaleDraftRevision) for r in results if r not in winners)
    final = service.get_agent(ALICE, agent.agent_id)
    assert final.draft_revision == 1 and final.draft == winners[0].draft


def test_parallel_version_creation_numbers_without_gaps(
    service: AgentService, settings: Settings, migrator: Conn
) -> None:
    agent = _agent(service)
    workers = [_service(settings) for _ in range(6)]
    try:
        results = _in_threads(*(
            (lambda s=s: s.create_version(ALICE, agent.agent_id, 0)) for s, _ in workers
        ))  # fmt: skip
    finally:
        for _, conn in workers:
            conn.close()
    assert all(isinstance(r, VersionView) for r in results), results
    numbers = sorted(r.version_number for r in results if isinstance(r, VersionView))
    assert numbers == [1, 2, 3, 4, 5, 6]
    assert (
        _count(migrator, "SELECT count(DISTINCT version_number) FROM voiceos.agent_versions") == 6
    )


def test_parallel_deployments_leave_exactly_one_active(
    service: AgentService, settings: Settings, migrator: Conn
) -> None:
    agent = _agent(service)
    versions = [_published(service, agent) for _ in range(3)]
    workers = [_service(settings) for _ in range(6)]
    try:
        results = _in_threads(*(
            (lambda s=s, v=versions[i % 3]: s.deploy_version(
                ALICE, agent.agent_id, v.agent_version_id, PROD))
            for i, (s, _) in enumerate(workers)
        ))  # fmt: skip
    finally:
        for _, conn in workers:
            conn.close()
    assert not [r for r in results if isinstance(r, BaseException)], results
    active = _count(
        migrator,
        "SELECT count(*) FROM voiceos.deployments WHERE agent_id = %s AND environment ="
        " 'production' AND status = 'ACTIVE'",
        agent.agent_id,
    )
    assert active == 1
    current = service.get_deployment(ALICE, agent.agent_id, PROD)
    assert current is not None
    history = service.deployment_history(ALICE, agent.agent_id, PROD)
    assert history[0] == current  # the newest binding is the active one
    assert all(  # consecutive history entries never bind the same version twice
        a.agent_version_id != b.agent_version_id for a, b in pairwise(history)
    )


def test_parallel_draft_update_and_version_creation_never_snapshot_a_stale_revision(
    service: AgentService, settings: Settings
) -> None:
    agent = _agent(service)
    (editor, editor_conn), (releaser, releaser_conn) = _service(settings), _service(settings)
    try:
        results = _in_threads(
            lambda: editor.update_agent_draft(
                ALICE, agent.agent_id, 0, agent_configuration(personality="new")
            ),
            lambda: releaser.create_version(ALICE, agent.agent_id, 0),
        )
    finally:
        editor_conn.close()
        releaser_conn.close()
    assert isinstance(results[0], AgentView)
    if isinstance(results[1], VersionView):  # snapshot taken before the edit committed
        assert results[1].configuration["personality"] == ""
    else:
        assert isinstance(results[1], StaleDraftRevision)


def test_unknown_ids_are_not_found(service: AgentService) -> None:
    with pytest.raises(AgentNotFound):
        service.get_agent(ALICE, AgentId(uuid4()))
    with pytest.raises(VersionNotFound):
        service.get_version(ALICE, AgentVersionId(uuid4()))
