"""RBAC matrix, principal and owner-protection rules (pure domain)."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest

from voiceos.domain.identity.model import MembershipRole, OrganizationId, UserId
from voiceos.domain.identity.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    PermissionDenied,
    Principal,
    may_manage_membership,
    permissions_for,
    roles_with,
)

R, P = MembershipRole, Permission
ROOT = Path(__file__).resolve().parents[2]

# Expected matrix, written out independently of the implementation.
EXPECTED: dict[MembershipRole, set[Permission]] = {
    R.OWNER: set(Permission),
    R.ADMIN: set(Permission) - {P.BILLING_READ, P.BILLING_MANAGE},
    R.DEVELOPER: {P.ORGANIZATION_READ, P.MEMBERS_READ, P.AGENTS_READ, P.AGENTS_MANAGE,
                  P.DEPLOYMENTS_READ, P.DEPLOYMENTS_MANAGE, P.INTEGRATIONS_READ,
                  P.INTEGRATIONS_MANAGE, P.CALLS_READ, P.ANALYTICS_READ, P.USAGE_READ,
                  P.DEVELOPER_API_MANAGE},
    R.OPERATOR: {P.ORGANIZATION_READ, P.MEMBERS_READ, P.AGENTS_READ, P.DEPLOYMENTS_READ,
                 P.CALLS_READ, P.ANALYTICS_READ, P.USAGE_READ},
    R.ANALYST: {P.ORGANIZATION_READ, P.MEMBERS_READ, P.AGENTS_READ, P.DEPLOYMENTS_READ,
                P.CALLS_READ, P.ANALYTICS_READ, P.USAGE_READ},
    R.BILLING: {P.ORGANIZATION_READ, P.ANALYTICS_READ, P.USAGE_READ, P.BILLING_READ,
                P.BILLING_MANAGE},
    R.READ_ONLY: {P.ORGANIZATION_READ, P.MEMBERS_READ, P.AGENTS_READ, P.DEPLOYMENTS_READ,
                  P.INTEGRATIONS_READ, P.ANALYTICS_READ, P.USAGE_READ},
}  # fmt: skip


def test_permission_catalog_is_the_blueprint_set() -> None:
    assert {p.value for p in Permission} == {
        "organization.read", "organization.manage", "members.read", "members.manage",
        "agents.read", "agents.manage", "deployments.read", "deployments.manage",
        "integrations.read", "integrations.manage", "calls.read", "analytics.read",
        "usage.read", "billing.read", "billing.manage", "audit.read", "developer_api.manage",
    }  # fmt: skip


@pytest.mark.parametrize("role", list(MembershipRole))
def test_each_role_has_exactly_the_expected_permissions(role: MembershipRole) -> None:
    assert set(permissions_for(role)) == EXPECTED[role]


def test_matrix_covers_every_role_and_is_immutable() -> None:
    assert set(ROLE_PERMISSIONS) == set(MembershipRole)
    assert all(isinstance(granted, frozenset) for granted in ROLE_PERMISSIONS.values())


def test_owner_is_complete_and_read_only_is_minimal() -> None:
    assert permissions_for(R.OWNER) == frozenset(Permission)
    read_only = permissions_for(R.READ_ONLY)
    assert all(p.value.endswith(".read") for p in read_only)
    assert not {P.CALLS_READ, P.BILLING_READ, P.AUDIT_READ} & read_only


def test_every_manage_permission_implies_its_read_permission() -> None:
    for role, granted in ROLE_PERMISSIONS.items():
        for permission in granted:
            if permission.value.endswith(".manage") and permission is not P.DEVELOPER_API_MANAGE:
                read = Permission(permission.value.replace(".manage", ".read"))
                assert read in granted, (role, permission)


def test_sql_member_managers_match_the_matrix() -> None:
    """The 0003 functions re-check members.manage with a fixed role list; it must equal
    the roles that hold members.manage here."""
    sql = (ROOT / "db" / "migrations" / "0003_identity_rbac.sql").read_text()
    lists = set(re.findall(r"v_caller NOT IN \(([^)]*)\)", sql))
    assert lists == {"'OWNER', 'ADMIN'"}
    assert roles_with(P.MEMBERS_MANAGE) == {R.OWNER, R.ADMIN}


def test_principal_permissions_derive_from_the_role_only() -> None:
    principal = Principal(UserId(uuid4()), OrganizationId(uuid4()), R.ANALYST)
    assert principal.permissions == permissions_for(R.ANALYST)
    assert principal.has(P.CALLS_READ) and not principal.has(P.AGENTS_MANAGE)
    with pytest.raises(PermissionDenied):
        principal.require(P.AGENTS_MANAGE)
    principal.require(P.ANALYTICS_READ)
    assert principal.scope.organization_id == principal.organization_id
    assert principal.scope.user_id == principal.user_id
    assert not hasattr(principal, "__dict__")  # no ad-hoc permission attributes


@pytest.mark.parametrize(
    ("actor", "current", "new", "allowed"),
    [
        (R.OWNER, R.OWNER, R.ADMIN, True),
        (R.OWNER, None, R.OWNER, True),
        (R.ADMIN, R.DEVELOPER, R.ANALYST, True),
        (R.ADMIN, None, R.ADMIN, True),
        (R.ADMIN, R.OWNER, R.ADMIN, False),  # admin cannot demote an owner
        (R.ADMIN, None, R.OWNER, False),  # admin cannot grant owner
        (R.ADMIN, R.OWNER, None, False),  # admin cannot remove an owner
        (R.DEVELOPER, R.READ_ONLY, R.ANALYST, False),  # no members.manage
        (R.READ_ONLY, None, R.READ_ONLY, False),
    ],
)
def test_membership_management_rules(
    actor: MembershipRole,
    current: MembershipRole | None,
    new: MembershipRole | None,
    allowed: bool,
) -> None:
    assert may_manage_membership(actor, current, new) is allowed
