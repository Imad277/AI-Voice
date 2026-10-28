"""Identity resolution, organization creation and membership management (migration 0003)
against the real database, through the application service and the PostgreSQL store.

Forged principals are passed straight to the store to prove the database re-checks the
stored membership instead of trusting the caller.
"""

# Table and function names in the SQL below are fixed test constants, never input.
# ruff: noqa: S608

from __future__ import annotations

import threading
import time
from uuid import UUID, uuid4

import pytest
from psycopg import errors

from voiceos.application.control_plane.identity import (
    IdentityNotFound,
    IdentityService,
    InvitationResult,
    LastOwnerError,
    MemberNotFound,
    OrganizationNotAccessible,
    ResolvedIdentity,
)
from voiceos.config import Settings
from voiceos.domain.identity.model import MembershipRole, OrganizationId, UserId
from voiceos.domain.identity.rbac import AuthenticatedUser, PermissionDenied, Principal
from voiceos.infrastructure.postgres.identity import PostgresIdentityStore
from voiceos.infrastructure.postgres.scope import organization_transaction, user_transaction
from voiceos.tenancy.db import Conn, connect_app

R = MembershipRole
ALICE = UUID("00000000-0000-4000-8000-0000000a11ce")
BOB = UUID("00000000-0000-4000-8000-0000000000b0")
CAROL = UUID("00000000-0000-4000-8000-0000000ca201")
DAVE = UUID("00000000-0000-4000-8000-0000000da7e0")  # disabled
PUBLIC_FUNCTIONS = {
    "resolve_external_subject", "my_memberships", "create_organization", "add_member",
    "accept_membership", "change_member_role", "deactivate_member",
}  # fmt: skip
INTERNAL_FUNCTIONS = {"caller_membership_role", "guard_last_owner"}


@pytest.fixture
def people(migrator: Conn) -> None:
    migrator.execute(
        "INSERT INTO voiceos.users (user_id, external_subject, email, display_name, status)"
        " VALUES (%s, 'sub-alice', 'alice@example.org', 'Alice', 'ACTIVE'),"
        " (%s, 'sub-bob', 'bob@example.org', 'Bob', 'ACTIVE'),"
        " (%s, 'sub-carol', 'Carol@Example.org', 'Carol', 'ACTIVE'),"
        " (%s, 'sub-dave', 'dave@example.org', 'Dave', 'DISABLED')",
        (ALICE, BOB, CAROL, DAVE),
    )


@pytest.fixture
def service(app_conn: Conn, people: None) -> IdentityService:
    return IdentityService(PostgresIdentityStore(app_conn))


def _owner_org(
    service: IdentityService, subject: str = "sub-alice", slug: str = "acme"
) -> Principal:
    return service.create_organization(service.resolve_identity(subject), "Acme", slug)


def _join(
    service: IdentityService, owner: Principal, subject: str, role: MembershipRole
) -> Principal:
    service.add_member(owner, subject, role)
    return service.accept_invitation(service.resolve_identity(subject), owner.organization_id)


def _count(conn: Conn, sql: str, *params: object) -> int:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return int(row[0])


# -- identity resolution ----------------------------------------------------------------------


def test_identity_resolution_fails_closed(service: IdentityService) -> None:
    identity = service.resolve_identity("sub-alice")
    assert identity.user == AuthenticatedUser(UserId(ALICE)) and identity.memberships == ()
    messages = set()
    for subject in ("sub-unknown", "sub-dave", "", "alice@example.org"):  # email is no subject
        with pytest.raises(IdentityNotFound) as caught:
            service.resolve_identity(subject)
        messages.add(str(caught.value))
    assert messages == {"identity not found"}


def test_multiple_organizations_and_selection_only_from_own_memberships(
    service: IdentityService,
) -> None:
    first = _owner_org(service, slug="acme")
    second = service.create_organization(service.resolve_identity("sub-alice"), "Beta", "beta")
    foreign = _owner_org(service, "sub-bob", "bobco")
    identity = service.resolve_identity("sub-alice")
    assert {m.organization_id for m in identity.active_memberships} == {
        first.organization_id, second.organization_id,
    }  # fmt: skip
    assert service.select_organization(identity, second.organization_id).role is R.OWNER
    for organization in (foreign.organization_id, OrganizationId(uuid4())):
        with pytest.raises(OrganizationNotAccessible):
            service.select_organization(identity, organization)


def test_inactive_membership_or_organization_is_not_authority(
    service: IdentityService, migrator: Conn
) -> None:
    owner = _owner_org(service)
    _join(service, owner, "sub-bob", R.ADMIN)
    migrator.execute(
        "UPDATE voiceos.organization_memberships SET status = 'SUSPENDED' WHERE user_id = %s",
        (BOB,),
    )
    with pytest.raises(OrganizationNotAccessible):
        service.select_organization(service.resolve_identity("sub-bob"), owner.organization_id)
    migrator.execute("UPDATE voiceos.organizations SET status = 'SUSPENDED'")
    with pytest.raises(OrganizationNotAccessible):
        service.select_organization(service.resolve_identity("sub-alice"), owner.organization_id)


# -- organization creation --------------------------------------------------------------------


def test_create_organization_is_atomic_with_owner_membership(
    service: IdentityService, migrator: Conn
) -> None:
    owner = _owner_org(service)
    rows = migrator.execute(
        "SELECT o.slug, m.user_id, m.role, m.status FROM voiceos.organizations o"
        " JOIN voiceos.organization_memberships m USING (tenant_id) WHERE o.tenant_id = %s",
        (owner.organization_id,),
    ).fetchall()
    assert rows == [("acme", ALICE, "OWNER", "ACTIVE")]
    assert _count(migrator, "SELECT count(*) FROM voiceos.tenants WHERE tenant_id = %s",
                  owner.organization_id) == 1  # fmt: skip


@pytest.mark.parametrize(("name", "slug"), [("Dup", "acme"), ("", "valid-slug"), ("X", "Bad Slug")])
def test_failed_creation_rolls_back_everything(
    service: IdentityService, migrator: Conn, name: str, slug: str
) -> None:
    _owner_org(service)
    before = [_count(migrator, f"SELECT count(*) FROM voiceos.{t}")
              for t in ("tenants", "organizations", "organization_memberships")]  # fmt: skip
    with pytest.raises((errors.UniqueViolation, errors.CheckViolation)):
        service.create_organization(service.resolve_identity("sub-bob"), name, slug)
    after = [_count(migrator, f"SELECT count(*) FROM voiceos.{t}")
             for t in ("tenants", "organizations", "organization_memberships")]  # fmt: skip
    assert before == after


def test_create_organization_requires_a_bound_active_user(app_conn: Conn, people: None) -> None:
    with pytest.raises(errors.DatabaseError) as caught:
        app_conn.execute("SELECT voiceos.create_organization('X', 'x')")  # no user bound
    assert caught.value.sqlstate == "VOA03"


# -- membership management --------------------------------------------------------------------


def test_add_accept_change_role_and_deactivate(service: IdentityService) -> None:
    owner = _owner_org(service)
    assert service.add_member(owner, "bob@example.org", R.DEVELOPER) is InvitationResult.RECORDED
    assert [m.user_id for m in service.list_members(owner)] == [ALICE]  # invitation hidden
    bob_identity = service.resolve_identity("sub-bob")
    assert bob_identity.active_memberships == () and len(bob_identity.pending_invitations) == 1
    bob = service.accept_invitation(bob_identity, owner.organization_id)
    assert bob.role is R.DEVELOPER
    assert {(m.user_id, m.role) for m in service.list_members(owner)} == {
        (ALICE, R.OWNER), (BOB, R.DEVELOPER),
    }  # fmt: skip
    service.change_role(owner, UserId(BOB), R.ADMIN)
    assert service.select_organization(service.resolve_identity("sub-bob"),
                                       owner.organization_id).role is R.ADMIN  # fmt: skip
    service.deactivate(owner, UserId(BOB))
    service.deactivate(owner, UserId(BOB))  # idempotent
    with pytest.raises(OrganizationNotAccessible):
        service.select_organization(service.resolve_identity("sub-bob"), owner.organization_id)
    assert service.add_member(owner, "sub-bob", R.ANALYST) is InvitationResult.RECORDED  # re-invite
    assert service.accept_invitation(service.resolve_identity("sub-bob"),
                                     owner.organization_id).role is R.ANALYST  # fmt: skip


def test_email_lookup_is_case_insensitive(service: IdentityService) -> None:
    owner = _owner_org(service)
    service.add_member(owner, "  CAROL@example.ORG ", R.ANALYST)
    carol = service.accept_invitation(service.resolve_identity("sub-carol"), owner.organization_id)
    assert carol.role is R.ANALYST


def test_missing_permission_is_refused_in_application_and_database(
    service: IdentityService, app_conn: Conn
) -> None:
    owner = _owner_org(service)
    reader = _join(service, owner, "sub-bob", R.READ_ONLY)
    with pytest.raises(PermissionDenied):
        service.add_member(reader, "carol@example.org", R.READ_ONLY)
    store = PostgresIdentityStore(app_conn)
    forged = Principal(UserId(BOB), owner.organization_id, R.ADMIN)  # claims a role it lacks
    for action in (
        lambda: store.add_member(forged, "carol@example.org", R.READ_ONLY),
        lambda: store.change_role(forged, UserId(ALICE), R.READ_ONLY),
        lambda: store.deactivate(forged, UserId(ALICE)),
    ):
        with pytest.raises(PermissionDenied):
            action()


def test_cross_tenant_membership_changes_are_blocked(
    service: IdentityService, app_conn: Conn
) -> None:
    alice = _owner_org(service)
    bob = _owner_org(service, "sub-bob", "bobco")
    with pytest.raises(MemberNotFound):  # Bob is not a member of Alice's organization
        service.change_role(alice, UserId(BOB), R.READ_ONLY)
    store = PostgresIdentityStore(app_conn)
    forged = Principal(UserId(ALICE), bob.organization_id, R.OWNER)  # not a member there
    with pytest.raises(PermissionDenied):
        store.change_role(forged, UserId(BOB), R.READ_ONLY)
    with pytest.raises(PermissionDenied):
        store.add_member(forged, "carol@example.org", R.ADMIN)
    assert service.select_organization(service.resolve_identity("sub-bob"),
                                       bob.organization_id).role is R.OWNER  # fmt: skip


def test_admin_cannot_grant_or_change_owner_even_through_the_store(
    service: IdentityService, app_conn: Conn
) -> None:
    owner = _owner_org(service)
    admin = _join(service, owner, "sub-bob", R.ADMIN)
    with pytest.raises(PermissionDenied):
        service.change_role(admin, UserId(ALICE), R.ADMIN)
    store = PostgresIdentityStore(app_conn)
    for action in (
        lambda: store.change_role(admin, UserId(ALICE), R.ADMIN),
        lambda: store.deactivate(admin, UserId(ALICE)),
        lambda: store.add_member(admin, "carol@example.org", R.OWNER),
    ):
        with pytest.raises(PermissionDenied):
            action()


# -- enumeration and direct access ------------------------------------------------------------


def test_add_member_reveals_nothing_about_identity_existence(
    service: IdentityService, app_conn: Conn
) -> None:
    owner = _owner_org(service)

    def observe() -> tuple[object, ...]:
        with organization_transaction(app_conn, owner.scope) as tx:
            memberships = tx.execute(
                "SELECT user_id, role, status FROM voiceos.organization_memberships ORDER BY 1"
            ).fetchall()
            users = tx.execute("SELECT user_id FROM voiceos.users ORDER BY 1").fetchall()
        return (tuple(memberships), tuple(users), tuple(service.list_members(owner)))

    baseline = observe()
    results = []
    for identifier in (
        "carol@example.org",
        "nobody@example.org",
        "sub-carol",
        "sub-nobody",
        "dave@example.org",
    ):  # existing, unknown, existing, unknown, disabled
        results.append(service.add_member(owner, identifier, R.ANALYST))
        assert observe() == baseline  # identical for existing and unknown identities
    assert set(results) == {InvitationResult.RECORDED}


def test_app_role_still_cannot_write_memberships_directly(
    service: IdentityService, app_conn: Conn
) -> None:
    owner = _owner_org(service)
    for statement in (
        "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role)"
        " VALUES (%s, '00000000-0000-4000-8000-0000000000b0', 'ADMIN')",
        "UPDATE voiceos.organization_memberships SET role = 'ADMIN' WHERE tenant_id = %s",
    ):
        with (
            pytest.raises(errors.InsufficientPrivilege),
            organization_transaction(app_conn, owner.scope) as tx,
        ):
            tx.execute(statement, (owner.organization_id,))


# -- owner safety -----------------------------------------------------------------------------


def test_last_owner_cannot_be_demoted_or_removed(service: IdentityService, migrator: Conn) -> None:
    owner = _owner_org(service)
    with pytest.raises(LastOwnerError):
        service.change_role(owner, UserId(ALICE), R.ADMIN)  # self-demotion as last owner
    with pytest.raises(LastOwnerError):
        service.deactivate(owner, UserId(ALICE))
    with pytest.raises(errors.DatabaseError) as caught:  # also for the migrator
        migrator.execute(
            "UPDATE voiceos.organization_memberships SET role = 'ADMIN' WHERE user_id = %s",
            (ALICE,),
        )
    assert caught.value.sqlstate == "VOA01"
    with pytest.raises(errors.DatabaseError):
        migrator.execute(
            "DELETE FROM voiceos.organization_memberships WHERE user_id = %s", (ALICE,)
        )
    assert service.select_organization(service.resolve_identity("sub-alice"),
                                       owner.organization_id).role is R.OWNER  # fmt: skip


def test_with_two_owners_one_may_step_down(service: IdentityService) -> None:
    owner = _owner_org(service)
    _join(service, owner, "sub-bob", R.OWNER)
    service.change_role(owner, UserId(ALICE), R.ADMIN)
    bob = service.select_organization(service.resolve_identity("sub-bob"), owner.organization_id)
    with pytest.raises(LastOwnerError):
        service.deactivate(bob, UserId(BOB))


def test_concurrent_demotions_of_two_owners_leave_one_owner(
    service: IdentityService, settings: Settings
) -> None:
    owner = _owner_org(service)
    _join(service, owner, "sub-bob", R.OWNER)
    alice = owner
    bob = service.select_organization(service.resolve_identity("sub-bob"), owner.organization_id)
    first_done, release = threading.Event(), threading.Event()
    outcome: dict[str, BaseException | None] = {}

    def demote_alice() -> None:
        with connect_app(settings) as conn:
            try:
                with organization_transaction(conn, alice.scope) as tx:
                    tx.execute("SELECT voiceos.change_member_role(%s, 'ADMIN')", (ALICE,))
                    first_done.set()
                    release.wait(5)  # hold the transaction (and the organization lock) open
                outcome["alice"] = None
            except BaseException as exc:  # recorded for the assertion
                first_done.set()
                outcome["alice"] = exc

    def demote_bob() -> None:
        with connect_app(settings) as conn:
            try:
                with organization_transaction(conn, bob.scope) as tx:
                    tx.execute("SELECT voiceos.change_member_role(%s, 'ADMIN')", (BOB,))
                outcome["bob"] = None
            except BaseException as exc:  # recorded for the assertion
                outcome["bob"] = exc

    first = threading.Thread(target=demote_alice)
    first.start()
    assert first_done.wait(5)
    second = threading.Thread(target=demote_bob)
    second.start()
    time.sleep(0.3)  # the second demotion is now waiting for the organization lock
    assert second.is_alive()
    release.set()
    first.join(5)
    second.join(5)
    assert outcome["alice"] is None
    failure = outcome["bob"]
    assert isinstance(failure, errors.DatabaseError) and failure.sqlstate == "VOA01"
    members = {m.user_id: m.role for m in service.list_members(bob)}  # bob is still owner
    assert members == {UserId(ALICE): R.ADMIN, UserId(BOB): R.OWNER}


# -- security of the privileged functions -----------------------------------------------------


def test_privileged_functions_are_owned_locked_down_and_pinned(migrator: Conn) -> None:
    rows = migrator.execute(
        """SELECT p.proname, pg_get_userbyid(p.proowner), p.prosecdef, p.proconfig,
                  has_function_privilege('voiceos_app', p.oid, 'EXECUTE'),
                  coalesce(p.proacl::text, '')
           FROM pg_proc p WHERE p.pronamespace = 'voiceos'::regnamespace
             AND p.proname = ANY(%s)""",
        (sorted(PUBLIC_FUNCTIONS | INTERNAL_FUNCTIONS),),
    ).fetchall()
    found = {name: rest for name, *rest in rows}
    assert set(found) == PUBLIC_FUNCTIONS | INTERNAL_FUNCTIONS
    for name, (owner, definer, config, app_execute, acl) in found.items():
        assert owner == "voiceos_migrator", name
        assert config == ["search_path=pg_catalog"], name
        assert "=X/" not in acl.replace("voiceos_app=X/", "").replace("voiceos_migrator=X/", ""), (
            name
        )
        assert app_execute is (name in PUBLIC_FUNCTIONS), name
        assert definer is (name != "guard_last_owner"), name


def test_user_and_organization_binding_is_cleared(service: IdentityService, app_conn: Conn) -> None:
    identity: ResolvedIdentity = service.resolve_identity("sub-alice")
    with user_transaction(app_conn, identity.user) as tx:
        row = tx.execute("SELECT voiceos.current_user_id()").fetchone()
        assert row == (ALICE,)
    assert app_conn.execute("SELECT voiceos.current_user_id()").fetchone() == (None,)
    with pytest.raises(RuntimeError), user_transaction(app_conn, identity.user):
        raise RuntimeError("rollback")
    assert app_conn.execute("SELECT voiceos.current_user_id()").fetchone() == (None,)
    assert app_conn.execute("SELECT voiceos.current_tenant_id()").fetchone() == (None,)
    with pytest.raises(TypeError), user_transaction(app_conn, ALICE):  # type: ignore[arg-type]
        pass
