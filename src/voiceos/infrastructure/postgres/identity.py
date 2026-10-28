"""PostgreSQL implementation of the identity store (migration 0003 privileged functions).

The application role never writes memberships directly: every mutation goes through a
SECURITY DEFINER function that takes tenant and acting user from the transaction binding
and re-checks the stored membership. Database errors are mapped to application errors by
SQLSTATE only (class VO from 0003); messages are never interpreted.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg

from voiceos.application.control_plane.identity import (
    IdentityNotFound,
    LastOwnerError,
    MemberNotFound,
    MembershipRecord,
    MemberView,
)
from voiceos.domain.identity.model import (
    MembershipRole,
    MembershipStatus,
    OrganizationId,
    OrganizationStatus,
    UserId,
)
from voiceos.domain.identity.rbac import AuthenticatedUser, Permission, PermissionDenied, Principal
from voiceos.infrastructure.postgres.scope import organization_transaction, user_transaction
from voiceos.tenancy.db import Conn

LAST_OWNER = "VOA01"
MEMBER_NOT_FOUND = "VOA02"
NOT_PERMITTED = "VOA03"
INVALID_REQUEST = "VOA04"


class InvalidIdentityRequest(ValueError):
    pass


@contextmanager
def _mapped_errors() -> Iterator[None]:
    try:
        yield
    except psycopg.Error as exc:
        code = exc.sqlstate
        if code == LAST_OWNER:
            raise LastOwnerError("an active organization needs at least one active owner") from None
        if code == MEMBER_NOT_FOUND:
            raise MemberNotFound("member not found") from None
        if code == NOT_PERMITTED:
            raise PermissionDenied(Permission.MEMBERS_MANAGE) from None
        if code == INVALID_REQUEST:
            raise InvalidIdentityRequest("invalid request") from None
        raise


class PostgresIdentityStore:
    def __init__(self, conn: Conn) -> None:
        self._conn = conn

    def find_active_user(self, external_subject: str) -> AuthenticatedUser | None:
        row = self._conn.execute(
            "SELECT voiceos.resolve_external_subject(%s)", (external_subject,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return AuthenticatedUser(UserId(row[0]))

    def memberships(self, user: AuthenticatedUser) -> list[MembershipRecord]:
        with user_transaction(self._conn, user) as tx:
            rows = tx.execute(
                "SELECT tenant_id, role, status, organization_status FROM voiceos.my_memberships()"
            ).fetchall()
        return [
            MembershipRecord(
                OrganizationId(tenant_id), MembershipRole(role), MembershipStatus(status),
                OrganizationStatus(organization_status),
            )
            for tenant_id, role, status, organization_status in rows
        ]  # fmt: skip

    def create_organization(self, user: AuthenticatedUser, name: str, slug: str) -> OrganizationId:
        with _mapped_errors(), user_transaction(self._conn, user) as tx:
            row = tx.execute("SELECT voiceos.create_organization(%s, %s)", (name, slug)).fetchone()
        if row is None or not isinstance(row[0], UUID):
            raise IdentityNotFound("organization was not created")
        return OrganizationId(row[0])

    def accept_invitation(self, user: AuthenticatedUser, organization_id: OrganizationId) -> bool:
        with user_transaction(self._conn, user) as tx:
            row = tx.execute("SELECT voiceos.accept_membership(%s)", (organization_id,)).fetchone()
        return bool(row and row[0])

    def list_members(self, principal: Principal) -> list[MemberView]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                """SELECT m.user_id, u.display_name, u.email, m.role, m.status
                   FROM voiceos.organization_memberships m
                   JOIN voiceos.users u ON u.user_id = m.user_id
                   WHERE m.status IN ('ACTIVE', 'SUSPENDED')
                   ORDER BY u.display_name, m.user_id"""
            ).fetchall()
        return [
            MemberView(UserId(user_id), display_name, email, MembershipRole(role),
                       MembershipStatus(status))
            for user_id, display_name, email, role, status in rows
        ]  # fmt: skip

    def add_member(self, principal: Principal, identifier: str, role: MembershipRole) -> None:
        with _mapped_errors(), organization_transaction(self._conn, principal.scope) as tx:
            tx.execute("SELECT voiceos.add_member(%s, %s)", (identifier, role.value))

    def change_role(self, principal: Principal, user_id: UserId, role: MembershipRole) -> None:
        with _mapped_errors(), organization_transaction(self._conn, principal.scope) as tx:
            tx.execute("SELECT voiceos.change_member_role(%s, %s)", (user_id, role.value))

    def deactivate(self, principal: Principal, user_id: UserId) -> None:
        with _mapped_errors(), organization_transaction(self._conn, principal.scope) as tx:
            tx.execute("SELECT voiceos.deactivate_member(%s)", (user_id,))
