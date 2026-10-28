"""Product foundation tables (migration 0002) against the real database.

Statements run as the non-owner application role WITHOUT tenant filters, so only the
database policies, constraints and triggers stand between organizations. The migrator is
used to seed data and as the independent observer.
"""

# Table and schema names in the SQL below are fixed test constants, never input.
# ruff: noqa: S608

from __future__ import annotations

import json
from collections.abc import Callable
from enum import StrEnum
from uuid import UUID, uuid4

import pytest
from psycopg import errors
from support import TENANT_A, TENANT_B

from voiceos.domain.agents.model import (
    AgentStatus,
    AgentVersionStatus,
    DeploymentEnvironment,
    DeploymentStatus,
    configuration_hash,
)
from voiceos.domain.identity.model import (
    MembershipRole,
    MembershipStatus,
    OrganizationId,
    OrganizationScope,
    OrganizationStatus,
    UserId,
    UserStatus,
)
from voiceos.infrastructure.postgres.scope import organization_transaction
from voiceos.tenancy.db import Conn
from voiceos.tenancy.preflight import preflight_violations

USER_A = UUID("00000000-0000-4000-8000-0000000000aa")
USER_B = UUID("00000000-0000-4000-8000-0000000000bb")
USER_LONER = UUID("00000000-0000-4000-8000-0000000000cc")
SCOPE_A = OrganizationScope(OrganizationId(TENANT_A), UserId(USER_A))
SCOPE_B = OrganizationScope(OrganizationId(TENANT_B), UserId(USER_B))
CONFIG = {"language": "de", "greeting": "Guten Tag"}
TENANT_TABLES = ("organization_memberships", "agents", "agent_versions", "deployments")


def _one(conn: Conn, query: str, *params: object) -> object:
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def _agent(conn: Conn, tenant: UUID, name: str = "Assistant") -> UUID:
    value = _one(
        conn, "INSERT INTO voiceos.agents (tenant_id, name) VALUES (%s, %s) RETURNING agent_id",
        tenant, name,
    )  # fmt: skip
    assert isinstance(value, UUID)
    return value


def _version(
    conn: Conn, tenant: UUID, agent: UUID, number: int = 1, *, published: bool = False
) -> UUID:
    value = _one(
        conn,
        """INSERT INTO voiceos.agent_versions
           (tenant_id, agent_id, version_number, status, configuration, configuration_hash,
            published_at)
           VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s THEN now() END)
           RETURNING agent_version_id""",
        tenant, agent, number, "PUBLISHED" if published else "DRAFT", json.dumps(CONFIG),
        configuration_hash(CONFIG), published,
    )  # fmt: skip
    assert isinstance(value, UUID)
    return value


def _deployment(
    conn: Conn, tenant: UUID, agent: UUID, version: UUID, status: str = "ACTIVE"
) -> UUID:
    value = _one(
        conn,
        """INSERT INTO voiceos.deployments
           (tenant_id, agent_id, agent_version_id, environment, status)
           VALUES (%s, %s, %s, 'production', %s) RETURNING deployment_id""",
        tenant, agent, version, status,
    )  # fmt: skip
    assert isinstance(value, UUID)
    return value


@pytest.fixture
def world(migrator: Conn) -> dict[str, UUID]:
    """Two organizations, one member each, a user without membership, one published agent
    version and an active deployment per organization (seeded by the migrator)."""
    migrator.execute(
        "INSERT INTO voiceos.organizations (tenant_id, name, slug) VALUES"
        " (%s, 'Org A', 'org-a'), (%s, 'Org B', 'org-b')",
        (TENANT_A, TENANT_B),
    )
    migrator.execute(
        "INSERT INTO voiceos.users (user_id, external_subject, email, display_name) VALUES"
        " (%s, 'sub-a', 'a@example.org', 'A'), (%s, 'sub-b', 'b@example.org', 'B'),"
        " (%s, 'sub-c', 'c@example.org', 'C')",
        (USER_A, USER_B, USER_LONER),
    )
    migrator.execute(
        "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role) VALUES"
        " (%s, %s, 'OWNER'), (%s, %s, 'OWNER')",
        (TENANT_A, USER_A, TENANT_B, USER_B),
    )
    ids: dict[str, UUID] = {}
    for key, tenant in (("a", TENANT_A), ("b", TENANT_B)):
        ids[f"agent_{key}"] = _agent(migrator, tenant)
        ids[f"version_{key}"] = _version(migrator, tenant, ids[f"agent_{key}"], published=True)
        ids[f"deployment_{key}"] = _deployment(
            migrator, tenant, ids[f"agent_{key}"], ids[f"version_{key}"]
        )
    return ids


# -- tenant isolation per table ----------------------------------------------------------------


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_organization_sees_only_its_own_rows(
    app_conn: Conn, world: dict[str, UUID], table: str
) -> None:
    with organization_transaction(app_conn, SCOPE_A) as tx:
        tenants = {r[0] for r in tx.execute(f"SELECT tenant_id FROM voiceos.{table}").fetchall()}
    assert tenants == {TENANT_A}
    with organization_transaction(app_conn, SCOPE_B) as tx:
        tenants = {r[0] for r in tx.execute(f"SELECT tenant_id FROM voiceos.{table}").fetchall()}
    assert tenants == {TENANT_B}


@pytest.mark.parametrize("table", (*TENANT_TABLES, "organizations", "users"))
def test_without_organization_binding_nothing_is_visible(
    app_conn: Conn, world: dict[str, UUID], table: str
) -> None:
    count = _one(app_conn, f"SELECT count(*) FROM voiceos.{table}")
    assert count == 0


def test_cross_tenant_inserts_are_blocked(app_conn: Conn, world: dict[str, UUID]) -> None:
    inserts: list[Callable[[Conn], object]] = [
        lambda c: c.execute(
            "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role)"
            " VALUES (%s, %s, 'ADMIN')", (TENANT_B, USER_A)),
        lambda c: _agent(c, TENANT_B),
        lambda c: _version(c, TENANT_B, world["agent_b"], 2),
        lambda c: _deployment(c, TENANT_B, world["agent_b"], world["version_b"]),
    ]  # fmt: skip
    # Refused by the RLS check, or for deployments already by the guard trigger, which fires
    # first and cannot see another organization's version.
    blocked = (errors.InsufficientPrivilege, errors.CheckViolation)
    for insert in inserts:
        with (
            pytest.raises(blocked),
            organization_transaction(app_conn, SCOPE_A) as tx,
        ):
            insert(tx)
    with pytest.raises(errors.InsufficientPrivilege):  # without a bound organization
        _agent(app_conn, TENANT_A)


@pytest.mark.parametrize(
    ("table", "assignment"),
    [("agents", "name = 'taken'"), ("deployments", "status = 'INACTIVE'"),
     ("organizations", "name = 'taken'")],
)  # fmt: skip
def test_cross_tenant_updates_affect_nothing(
    app_conn: Conn, migrator: Conn, world: dict[str, UUID], table: str, assignment: str
) -> None:
    with organization_transaction(app_conn, SCOPE_A) as tx:
        cursor = tx.execute(
            f"UPDATE voiceos.{table} SET {assignment} WHERE tenant_id = %s", (TENANT_B,)
        )
        assert cursor.rowcount == 0
    # Moving own rows to another organization is refused by the RLS check (or, for
    # deployments, already by the identity guard trigger that fires before it).
    blocked = (errors.InsufficientPrivilege, errors.CheckViolation)
    with pytest.raises(blocked), organization_transaction(app_conn, SCOPE_A) as tx:
        tx.execute(f"UPDATE voiceos.{table} SET tenant_id = %s", (TENANT_B,))


@pytest.mark.parametrize("table", (*TENANT_TABLES, "organizations", "users"))
def test_delete_is_not_granted(app_conn: Conn, world: dict[str, UUID], table: str) -> None:
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, SCOPE_A) as tx,
    ):
        tx.execute(f"DELETE FROM voiceos.{table}")


def test_organization_reads_only_its_own_row_and_cannot_create(
    app_conn: Conn, world: dict[str, UUID]
) -> None:
    with organization_transaction(app_conn, SCOPE_A) as tx:
        rows = tx.execute("SELECT tenant_id, slug FROM voiceos.organizations").fetchall()
        assert rows == [(TENANT_A, "org-a")]
        cursor = tx.execute("UPDATE voiceos.organizations SET name = 'Org A renamed'")
        assert cursor.rowcount == 1
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, SCOPE_A) as tx,
    ):
        tx.execute(
            "INSERT INTO voiceos.organizations (tenant_id, name, slug) VALUES (%s, 'x', 'x')",
            (uuid4(),),
        )


def test_users_are_visible_only_as_self_or_co_member(
    app_conn: Conn, world: dict[str, UUID]
) -> None:
    with organization_transaction(app_conn, SCOPE_A) as tx:
        visible = {r[0] for r in tx.execute("SELECT user_id FROM voiceos.users").fetchall()}
    assert visible == {USER_A}  # B and the user without membership stay invisible
    loner = OrganizationScope(OrganizationId(TENANT_A), UserId(USER_LONER))
    with organization_transaction(app_conn, loner) as tx:
        visible = {r[0] for r in tx.execute("SELECT user_id FROM voiceos.users").fetchall()}
    assert visible == {USER_A, USER_LONER}  # self + members of the bound organization
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, SCOPE_A) as tx,
    ):
        tx.execute(
            "INSERT INTO voiceos.users (external_subject, email) VALUES ('x', 'x@example.org')"
        )
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, SCOPE_A) as tx,
    ):
        tx.execute("UPDATE voiceos.users SET display_name = 'changed'")


def test_organization_member_can_manage_agents_of_its_organization(
    app_conn: Conn, migrator: Conn, world: dict[str, UUID]
) -> None:
    with organization_transaction(app_conn, SCOPE_A) as tx:
        agent = _agent(tx, TENANT_A, "Second")
        draft = _version(tx, TENANT_A, agent)
        tx.execute(
            "UPDATE voiceos.agent_versions SET status = 'PUBLISHED', published_at = now()"
            " WHERE agent_version_id = %s", (draft,),
        )  # fmt: skip
        _deployment(tx, TENANT_A, agent, draft)
    owner = _one(migrator, "SELECT tenant_id FROM voiceos.deployments WHERE agent_id = %s", agent)
    assert owner == TENANT_A


def test_app_role_cannot_create_or_change_memberships(
    app_conn: Conn, world: dict[str, UUID]
) -> None:
    """Memberships are read-only for the app role until a privileged membership/invite path
    exists, so the foreign key to the global users table can never answer whether a user
    id exists: existing and unknown ids fail identically, before any constraint check."""
    failures: list[tuple[str | None, str]] = []
    for user_id in (USER_LONER, USER_B, uuid4()):  # existing (no membership), other org, unknown
        with (
            pytest.raises(errors.InsufficientPrivilege) as caught,
            organization_transaction(app_conn, SCOPE_A) as tx,
        ):
            tx.execute(
                "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role)"
                " VALUES (%s, %s, 'ADMIN')", (TENANT_A, user_id),
            )  # fmt: skip
        failures.append((caught.value.sqlstate, str(caught.value).splitlines()[0]))
    assert len(set(failures)) == 1  # indistinguishable
    for assignment in ("user_id = %s", "role = 'ADMIN'", "status = 'REMOVED'"):
        params = (USER_LONER,) if "%s" in assignment else ()
        with (
            pytest.raises(errors.InsufficientPrivilege),
            organization_transaction(app_conn, SCOPE_A) as tx,
        ):
            tx.execute(f"UPDATE voiceos.organization_memberships SET {assignment}", params)
    with organization_transaction(app_conn, SCOPE_A) as tx:  # reading stays tenant-isolated
        rows = tx.execute(
            "SELECT tenant_id, user_id, role FROM voiceos.organization_memberships"
        ).fetchall()
    assert rows == [(TENANT_A, USER_A, "OWNER")]


# -- relationships -----------------------------------------------------------------------------


def test_membership_requires_existing_user_and_organization(
    migrator: Conn, world: dict[str, UUID]
) -> None:
    with pytest.raises(errors.ForeignKeyViolation):
        migrator.execute(
            "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role)"
            " VALUES (%s, %s, 'ADMIN')", (TENANT_A, uuid4()),
        )  # fmt: skip
    with pytest.raises(errors.ForeignKeyViolation):
        migrator.execute(
            "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role)"
            " VALUES (%s, %s, 'ADMIN')", (uuid4(), USER_A),
        )  # fmt: skip


def test_agent_belongs_to_an_existing_organization(migrator: Conn, world: dict[str, UUID]) -> None:
    with pytest.raises(errors.ForeignKeyViolation):
        _agent(migrator, uuid4())


def test_version_must_belong_to_an_agent_of_the_same_organization(
    migrator: Conn, world: dict[str, UUID]
) -> None:
    with pytest.raises(errors.ForeignKeyViolation):
        _version(migrator, TENANT_A, world["agent_b"], 2)  # agent of another organization
    with pytest.raises(errors.UniqueViolation):
        _version(migrator, TENANT_A, world["agent_a"], 1)  # version number taken


def test_deployment_must_match_version_agent_and_organization(
    migrator: Conn, world: dict[str, UUID]
) -> None:
    other = _agent(migrator, TENANT_A, "Other")
    with pytest.raises(errors.ForeignKeyViolation):  # version of another agent
        _deployment(migrator, TENANT_A, other, world["version_a"], "INACTIVE")
    with pytest.raises(errors.ForeignKeyViolation):  # version of another organization
        _deployment(migrator, TENANT_B, world["agent_a"], world["version_a"], "INACTIVE")
    draft = _version(migrator, TENANT_A, world["agent_a"], 2)
    migrator.execute(
        "UPDATE voiceos.deployments SET status = 'INACTIVE' WHERE deployment_id = %s",
        (world["deployment_a"],),
    )
    with pytest.raises(errors.CheckViolation, match="published"):
        _deployment(migrator, TENANT_A, world["agent_a"], draft)  # active needs published
    with pytest.raises(errors.UniqueViolation):
        _deployment(migrator, TENANT_B, world["agent_b"], world["version_b"])  # 2nd active


# -- agent version immutability ----------------------------------------------------------------


@pytest.mark.parametrize(
    "assignment",
    ["configuration = '{\"language\": \"en\"}'", "configuration_hash = repeat('0', 64)",
     "version_number = 9", "status = 'DRAFT', published_at = NULL", "published_at = now()"],
)  # fmt: skip
def test_published_version_cannot_be_changed_by_any_role(
    app_conn: Conn, migrator: Conn, world: dict[str, UUID], assignment: str
) -> None:
    query = f"UPDATE voiceos.agent_versions SET {assignment} WHERE agent_version_id = %s"
    with pytest.raises(errors.CheckViolation):
        migrator.execute(query, (world["version_a"],))
    with pytest.raises(errors.CheckViolation), organization_transaction(app_conn, SCOPE_A) as tx:
        tx.execute(query, (world["version_a"],))


def test_version_lifecycle_draft_published_archived(migrator: Conn, world: dict[str, UUID]) -> None:
    draft = _version(migrator, TENANT_A, world["agent_a"], 2)
    migrator.execute(
        "UPDATE voiceos.agent_versions SET configuration = '{\"language\": \"en\"}'"
        " WHERE agent_version_id = %s", (draft,),
    )  # fmt: skip
    with pytest.raises(errors.CheckViolation):  # published_at must accompany publishing
        migrator.execute(
            "UPDATE voiceos.agent_versions SET status = 'PUBLISHED' WHERE agent_version_id = %s",
            (draft,),
        )
    with pytest.raises(errors.CheckViolation):  # a draft cannot be archived
        migrator.execute(
            "UPDATE voiceos.agent_versions SET status = 'ARCHIVED', published_at = now()"
            " WHERE agent_version_id = %s", (draft,),
        )  # fmt: skip
    migrator.execute(
        "UPDATE voiceos.agent_versions SET status = 'PUBLISHED', published_at = now()"
        " WHERE agent_version_id = %s", (draft,),
    )  # fmt: skip
    migrator.execute(
        "UPDATE voiceos.agent_versions SET status = 'ARCHIVED' WHERE agent_version_id = %s",
        (draft,),
    )
    with pytest.raises(errors.CheckViolation):  # archived stays archived
        migrator.execute(
            "UPDATE voiceos.agent_versions SET status = 'PUBLISHED' WHERE agent_version_id = %s",
            (draft,),
        )
    with pytest.raises(errors.CheckViolation):  # evidence cannot be deleted
        migrator.execute("DELETE FROM voiceos.agent_versions WHERE agent_version_id = %s", (draft,))
    disposable = _version(migrator, TENANT_A, world["agent_a"], 3)
    migrator.execute(
        "DELETE FROM voiceos.agent_versions WHERE agent_version_id = %s", (disposable,)
    )


# -- schema values match the domain enums ------------------------------------------------------


@pytest.mark.parametrize(
    ("table", "column", "values", "key_sql"),
    [
        ("organizations", "status", OrganizationStatus, "tenant_id = %s"),
        ("users", "status", UserStatus, "user_id = %s"),
        ("organization_memberships", "role", MembershipRole, "user_id = %s"),
        ("organization_memberships", "status", MembershipStatus, "user_id = %s"),
        ("agents", "status", AgentStatus, "agent_id = %s"),
        ("deployments", "status", DeploymentStatus, "deployment_id = %s"),
    ],
)
def test_database_accepts_exactly_the_domain_values(
    migrator: Conn, world: dict[str, UUID], table: str, column: str,
    values: type[StrEnum], key_sql: str,
) -> None:  # fmt: skip
    key = {
        "organizations": TENANT_A, "users": USER_A, "organization_memberships": USER_A,
        "agents": world["agent_a"], "deployments": world["deployment_a"],
    }[table]  # fmt: skip
    for value in values:
        migrator.execute(f"UPDATE voiceos.{table} SET {column} = %s WHERE {key_sql}", (value, key))
    with pytest.raises(errors.CheckViolation):
        migrator.execute(f"UPDATE voiceos.{table} SET {column} = 'BOGUS' WHERE {key_sql}", (key,))


def test_version_and_environment_values_match_the_domain(
    migrator: Conn, world: dict[str, UUID]
) -> None:
    rows = migrator.execute("SELECT DISTINCT status FROM voiceos.agent_versions").fetchall()
    assert {r[0] for r in rows} <= {s.value for s in AgentVersionStatus}
    for number, env in enumerate(DeploymentEnvironment, start=2):
        version = _version(migrator, TENANT_A, world["agent_a"], number, published=True)
        migrator.execute(
            "INSERT INTO voiceos.deployments (tenant_id, agent_id, agent_version_id, environment,"
            " status) VALUES (%s, %s, %s, %s, 'INACTIVE')",
            (TENANT_A, world["agent_a"], version, env.value),
        )
    with pytest.raises(errors.CheckViolation):
        migrator.execute(
            "INSERT INTO voiceos.deployments (tenant_id, agent_id, agent_version_id, environment,"
            " status) VALUES (%s, %s, %s, 'staging', 'INACTIVE')",
            (TENANT_A, world["agent_a"], world["version_a"]),
        )


# -- security of the new tables ----------------------------------------------------------------


@pytest.mark.parametrize(
    "table", ("organizations", "users", "organization_memberships", "agents", "agent_versions",
              "deployments"),
)  # fmt: skip
@pytest.mark.parametrize("statement", ["DISABLE ROW LEVEL SECURITY", "NO FORCE ROW LEVEL SECURITY"])
def test_app_role_cannot_disable_rls_on_new_tables(
    app_conn: Conn, table: str, statement: str
) -> None:
    with pytest.raises(errors.InsufficientPrivilege):
        app_conn.execute(f"ALTER TABLE voiceos.{table} {statement}")


def test_new_tables_have_forced_rls_and_are_not_owned_by_the_app_role(migrator: Conn) -> None:
    rows = migrator.execute(
        """SELECT c.relname, pg_get_userbyid(c.relowner), c.relrowsecurity, c.relforcerowsecurity
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'voiceos' AND c.relkind = 'r'"""
    ).fetchall()
    tables = {name: (owner, rls, force) for name, owner, rls, force in rows}
    for table in ("organizations", "users", *TENANT_TABLES):
        assert tables[table] == ("voiceos_migrator", True, True), table


def test_preflight_passes_with_users_as_the_only_documented_global_table(
    app_conn: Conn, migrator: Conn
) -> None:
    assert preflight_violations(app_conn) == []
    migrator.execute("ALTER TABLE voiceos.users NO FORCE ROW LEVEL SECURITY")
    try:
        violations = preflight_violations(app_conn)
    finally:
        migrator.execute("ALTER TABLE voiceos.users FORCE ROW LEVEL SECURITY")
    assert violations == ["table users: row level security not forced"]


def test_scope_binding_is_cleared_after_commit_and_rollback(
    app_conn: Conn, world: dict[str, UUID]
) -> None:
    with organization_transaction(app_conn, SCOPE_A) as tx:
        assert _one(tx, "SELECT count(*) FROM voiceos.agents") == 1
    assert _one(app_conn, "SELECT count(*) FROM voiceos.agents") == 0
    assert _one(app_conn, "SELECT voiceos.current_user_id()") is None
    with pytest.raises(RuntimeError), organization_transaction(app_conn, SCOPE_A):
        raise RuntimeError("rollback")
    assert _one(app_conn, "SELECT count(*) FROM voiceos.users") == 0
    assert _one(app_conn, "SELECT voiceos.current_tenant_id()") is None


def test_scope_binding_requires_a_trusted_scope_object(app_conn: Conn) -> None:
    raw_id: object = TENANT_A  # a raw id from a request is not a scope
    with pytest.raises(TypeError), organization_transaction(app_conn, raw_id):  # type: ignore[arg-type]
        pass
