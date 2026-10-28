"""Role-based access control: permissions, the role matrix and the server-side principal.

The single source of truth for what a membership role may do. Authorization decisions are
made against a ``Principal``, which trusted server code builds from an authenticated
identity and a stored, active membership; a client can never supply its organization,
role or permissions. Pure and database-independent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from voiceos.domain.identity.model import (
    MembershipRole,
    OrganizationId,
    OrganizationScope,
    UserId,
)


class Permission(StrEnum):
    ORGANIZATION_READ = "organization.read"
    ORGANIZATION_MANAGE = "organization.manage"
    MEMBERS_READ = "members.read"
    MEMBERS_MANAGE = "members.manage"
    AGENTS_READ = "agents.read"
    AGENTS_MANAGE = "agents.manage"
    DEPLOYMENTS_READ = "deployments.read"
    DEPLOYMENTS_MANAGE = "deployments.manage"
    INTEGRATIONS_READ = "integrations.read"
    INTEGRATIONS_MANAGE = "integrations.manage"
    CALLS_READ = "calls.read"
    ANALYTICS_READ = "analytics.read"
    USAGE_READ = "usage.read"
    BILLING_READ = "billing.read"
    BILLING_MANAGE = "billing.manage"
    AUDIT_READ = "audit.read"
    DEVELOPER_API_MANAGE = "developer_api.manage"


P = Permission
_READ_BASE = frozenset({P.ORGANIZATION_READ, P.MEMBERS_READ, P.AGENTS_READ, P.DEPLOYMENTS_READ,
                        P.ANALYTICS_READ, P.USAGE_READ})  # fmt: skip

# Role matrix (PHASE2_SECURITY_AND_TENANCY.md §4). Change only together with its tests and
# the SQL role list in the 0003 migration (members.manage roles).
ROLE_PERMISSIONS: Mapping[MembershipRole, frozenset[Permission]] = {
    MembershipRole.OWNER: frozenset(Permission),
    MembershipRole.ADMIN: frozenset(Permission) - {P.BILLING_READ, P.BILLING_MANAGE},
    MembershipRole.DEVELOPER: _READ_BASE | {
        P.AGENTS_MANAGE, P.DEPLOYMENTS_MANAGE, P.INTEGRATIONS_READ, P.INTEGRATIONS_MANAGE,
        P.CALLS_READ, P.DEVELOPER_API_MANAGE,
    },
    MembershipRole.OPERATOR: _READ_BASE | {P.CALLS_READ},
    MembershipRole.ANALYST: _READ_BASE | {P.CALLS_READ},
    MembershipRole.BILLING: frozenset({P.ORGANIZATION_READ, P.ANALYTICS_READ, P.USAGE_READ,
                                       P.BILLING_READ, P.BILLING_MANAGE}),
    MembershipRole.READ_ONLY: _READ_BASE | {P.INTEGRATIONS_READ},
}  # fmt: skip


def permissions_for(role: MembershipRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def roles_with(permission: Permission) -> frozenset[MembershipRole]:
    return frozenset(role for role, granted in ROLE_PERMISSIONS.items() if permission in granted)


class PermissionDenied(Exception):
    def __init__(self, permission: Permission) -> None:
        super().__init__(f"permission denied: {permission}")
        self.permission = permission


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """A global user resolved server-side from a trusted, authenticated external subject."""

    user_id: UserId


@dataclass(frozen=True, slots=True)
class Principal:
    """Server-side authority for one request: a user acting in one organization with the
    role of an active stored membership. Permissions derive from the role only."""

    user_id: UserId
    organization_id: OrganizationId
    role: MembershipRole

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.role)

    @property
    def scope(self) -> OrganizationScope:
        return OrganizationScope(self.organization_id, self.user_id)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise PermissionDenied(permission)


def may_manage_membership(
    actor: MembershipRole, target_current: MembershipRole | None, target_new: MembershipRole | None
) -> bool:
    """Owner protection: only an OWNER may grant the OWNER role or change/remove an OWNER.
    Requires members.manage in any case."""
    if Permission.MEMBERS_MANAGE not in permissions_for(actor):
        return False
    touches_owner = MembershipRole.OWNER in (target_current, target_new)
    return actor is MembershipRole.OWNER or not touches_owner
