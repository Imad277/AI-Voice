"""Identity and membership use cases of the control plane.

Authority is established server-side only:

1. ``resolve_identity``: a trusted, already authenticated external subject (the
   authentication provider is NOT DECIDED, D-12) is resolved to an active global user and
   its stored memberships.
2. ``select_organization``: the organization a request acts in is accepted only if it is
   one of the user's active memberships in an active organization; the resulting
   ``Principal`` carries the stored role. A client-supplied organization id is a choice,
   never authority, and a client never supplies role or permissions.
3. Every use case checks the central RBAC matrix through ``Principal.require`` before the
   privileged store operation, which re-checks the stored membership in the database.

Database-independent: the ``IdentityStore`` port is implemented in infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from voiceos.domain.identity.model import (
    MembershipRole,
    MembershipStatus,
    OrganizationId,
    OrganizationStatus,
    UserId,
)
from voiceos.domain.identity.rbac import (
    AuthenticatedUser,
    Permission,
    PermissionDenied,
    Principal,
    may_manage_membership,
)


class IdentityNotFound(Exception):
    """Unknown, disabled or unauthenticated identity (deliberately not distinguished)."""


class OrganizationNotAccessible(Exception):
    """The requested organization is not an active membership of the user."""


class MemberNotFound(Exception):
    pass


class LastOwnerError(Exception):
    """The change would leave an active organization without an active OWNER."""


@dataclass(frozen=True, slots=True)
class MembershipRecord:
    organization_id: OrganizationId
    role: MembershipRole
    status: MembershipStatus
    organization_status: OrganizationStatus


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    user: AuthenticatedUser
    memberships: tuple[MembershipRecord, ...]

    @property
    def active_memberships(self) -> tuple[MembershipRecord, ...]:
        return tuple(
            m for m in self.memberships
            if m.status is MembershipStatus.ACTIVE
            and m.organization_status is OrganizationStatus.ACTIVE
        )  # fmt: skip

    @property
    def pending_invitations(self) -> tuple[MembershipRecord, ...]:
        return tuple(
            m for m in self.memberships
            if m.status is MembershipStatus.INVITED
            and m.organization_status is OrganizationStatus.ACTIVE
        )  # fmt: skip


@dataclass(frozen=True, slots=True)
class MemberView:
    user_id: UserId
    display_name: str
    email: str
    role: MembershipRole
    status: MembershipStatus


class InvitationResult(StrEnum):
    """The only answer to ``add_member``: never reveals whether the identity exists."""

    RECORDED = "RECORDED"


class IdentityStore(Protocol):
    def find_active_user(self, external_subject: str) -> AuthenticatedUser | None: ...

    def memberships(self, user: AuthenticatedUser) -> list[MembershipRecord]: ...

    def create_organization(
        self, user: AuthenticatedUser, name: str, slug: str
    ) -> OrganizationId: ...

    def accept_invitation(
        self, user: AuthenticatedUser, organization_id: OrganizationId
    ) -> bool: ...

    def list_members(self, principal: Principal) -> list[MemberView]: ...

    def add_member(self, principal: Principal, identifier: str, role: MembershipRole) -> None: ...

    def change_role(self, principal: Principal, user_id: UserId, role: MembershipRole) -> None: ...

    def deactivate(self, principal: Principal, user_id: UserId) -> None: ...


class IdentityService:
    def __init__(self, store: IdentityStore) -> None:
        self._store = store

    # -- identity and organization selection --------------------------------------------

    def resolve_identity(self, external_subject: str) -> ResolvedIdentity:
        subject = external_subject.strip() if isinstance(external_subject, str) else ""
        user = self._store.find_active_user(subject) if subject else None
        if user is None:
            raise IdentityNotFound("identity not found")
        return ResolvedIdentity(user, tuple(self._store.memberships(user)))

    def select_organization(
        self, identity: ResolvedIdentity, organization_id: OrganizationId
    ) -> Principal:
        for membership in identity.active_memberships:
            if membership.organization_id == organization_id:
                return Principal(identity.user.user_id, organization_id, membership.role)
        raise OrganizationNotAccessible("organization not accessible")

    def create_organization(self, identity: ResolvedIdentity, name: str, slug: str) -> Principal:
        organization_id = self._store.create_organization(identity.user, name, slug)
        return Principal(identity.user.user_id, organization_id, MembershipRole.OWNER)

    def accept_invitation(
        self, identity: ResolvedIdentity, organization_id: OrganizationId
    ) -> Principal:
        if not any(m.organization_id == organization_id for m in identity.pending_invitations):
            raise OrganizationNotAccessible("organization not accessible")
        if not self._store.accept_invitation(identity.user, organization_id):
            raise OrganizationNotAccessible("organization not accessible")
        refreshed = ResolvedIdentity(identity.user, tuple(self._store.memberships(identity.user)))
        return self.select_organization(refreshed, organization_id)

    # -- membership management ----------------------------------------------------------

    def list_members(self, principal: Principal) -> list[MemberView]:
        principal.require(Permission.MEMBERS_READ)
        return self._store.list_members(principal)

    def add_member(
        self, principal: Principal, identifier: str, role: MembershipRole
    ) -> InvitationResult:
        principal.require(Permission.MEMBERS_MANAGE)
        if not may_manage_membership(principal.role, None, role):
            raise PermissionDenied(Permission.MEMBERS_MANAGE)
        self._store.add_member(principal, identifier, role)
        return InvitationResult.RECORDED

    def change_role(self, principal: Principal, user_id: UserId, role: MembershipRole) -> None:
        principal.require(Permission.MEMBERS_MANAGE)
        current = self._current_role(principal, user_id)
        if not may_manage_membership(principal.role, current, role):
            raise PermissionDenied(Permission.MEMBERS_MANAGE)
        self._store.change_role(principal, user_id, role)

    def deactivate(self, principal: Principal, user_id: UserId) -> None:
        """Idempotent: an already removed member is not listed any more; the store then
        decides (no-op for a removed membership, ``MemberNotFound`` for a non-member)."""
        principal.require(Permission.MEMBERS_MANAGE)
        try:
            current: MembershipRole | None = self._current_role(principal, user_id)
        except MemberNotFound:
            current = None
        if not may_manage_membership(principal.role, current, None):
            raise PermissionDenied(Permission.MEMBERS_MANAGE)
        self._store.deactivate(principal, user_id)

    def _current_role(self, principal: Principal, user_id: UserId) -> MembershipRole:
        for member in self._store.list_members(principal):
            if member.user_id == user_id:
                return member.role
        raise MemberNotFound("member not found")
