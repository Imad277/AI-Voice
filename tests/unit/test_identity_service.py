"""Identity use cases against an in-memory store (no database): authority and checks."""

from __future__ import annotations

from uuid import uuid4

import pytest

from voiceos.application.control_plane.identity import (
    IdentityNotFound,
    IdentityService,
    InvitationResult,
    MemberNotFound,
    MembershipRecord,
    MemberView,
    OrganizationNotAccessible,
)
from voiceos.domain.identity.model import (
    MembershipRole,
    MembershipStatus,
    OrganizationId,
    OrganizationStatus,
    UserId,
)
from voiceos.domain.identity.rbac import AuthenticatedUser, PermissionDenied, Principal

R, S, ORG = MembershipRole, MembershipStatus, OrganizationStatus
ORG_A, ORG_B, ORG_C = (OrganizationId(uuid4()) for _ in range(3))
ALICE, BOB = UserId(uuid4()), UserId(uuid4())


class FakeStore:
    def __init__(self) -> None:
        self.users = {"sub-alice": ALICE}
        self.records = [
            MembershipRecord(ORG_A, R.ADMIN, S.ACTIVE, ORG.ACTIVE),
            MembershipRecord(ORG_B, R.OWNER, S.SUSPENDED, ORG.ACTIVE),  # inactive membership
            MembershipRecord(ORG_C, R.OWNER, S.ACTIVE, ORG.SUSPENDED),  # inactive organization
        ]
        self.members = [MemberView(ALICE, "Alice", "a@example.org", R.ADMIN, S.ACTIVE),
                        MemberView(BOB, "Owner", "o@example.org", R.OWNER, S.ACTIVE)]  # fmt: skip
        self.calls: list[str] = []

    def find_active_user(self, external_subject: str) -> AuthenticatedUser | None:
        user = self.users.get(external_subject)
        return AuthenticatedUser(user) if user else None

    def memberships(self, user: AuthenticatedUser) -> list[MembershipRecord]:
        return list(self.records)

    def create_organization(self, user: AuthenticatedUser, name: str, slug: str) -> OrganizationId:
        self.calls.append("create")
        return ORG_C

    def accept_invitation(self, user: AuthenticatedUser, organization_id: OrganizationId) -> bool:
        self.calls.append("accept")
        return False

    def list_members(self, principal: Principal) -> list[MemberView]:
        return list(self.members)

    def add_member(self, principal: Principal, identifier: str, role: MembershipRole) -> None:
        self.calls.append("add")

    def change_role(self, principal: Principal, user_id: UserId, role: MembershipRole) -> None:
        self.calls.append("change")

    def deactivate(self, principal: Principal, user_id: UserId) -> None:
        self.calls.append("deactivate")


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


def test_unknown_empty_and_non_string_subjects_fail_closed_identically(store: FakeStore) -> None:
    service = IdentityService(store)
    messages = set()
    for subject in ("sub-unknown", "", "   ", None):
        with pytest.raises(IdentityNotFound) as caught:
            service.resolve_identity(subject)  # type: ignore[arg-type]
        messages.add(str(caught.value))
    assert messages == {"identity not found"}


def test_only_active_memberships_of_active_organizations_are_authority(store: FakeStore) -> None:
    service = IdentityService(store)
    identity = service.resolve_identity(" sub-alice ")
    principal = service.select_organization(identity, ORG_A)
    assert principal == Principal(ALICE, ORG_A, R.ADMIN)  # role from the stored membership
    for org in (ORG_B, ORG_C, OrganizationId(uuid4())):
        with pytest.raises(OrganizationNotAccessible):
            service.select_organization(identity, org)


def test_create_organization_yields_an_owner_principal(store: FakeStore) -> None:
    service = IdentityService(store)
    principal = service.create_organization(service.resolve_identity("sub-alice"), "X", "x")
    assert principal == Principal(ALICE, ORG_C, R.OWNER)


def test_accepting_requires_a_pending_invitation(store: FakeStore) -> None:
    service = IdentityService(store)
    with pytest.raises(OrganizationNotAccessible):
        service.accept_invitation(service.resolve_identity("sub-alice"), ORG_A)
    assert "accept" not in store.calls  # no pending invitation: the store is not asked


@pytest.mark.parametrize("role", [R.DEVELOPER, R.OPERATOR, R.ANALYST, R.BILLING, R.READ_ONLY])
def test_missing_permission_stops_before_the_store(store: FakeStore, role: MembershipRole) -> None:
    service = IdentityService(store)
    principal = Principal(ALICE, ORG_A, role)
    with pytest.raises(PermissionDenied):
        service.add_member(principal, "someone@example.org", R.READ_ONLY)
    with pytest.raises(PermissionDenied):
        service.change_role(principal, BOB, R.ANALYST)
    with pytest.raises(PermissionDenied):
        service.deactivate(principal, BOB)
    assert store.calls == []
    if role is not R.BILLING:
        assert len(service.list_members(principal)) == 2
    else:
        with pytest.raises(PermissionDenied):
            service.list_members(principal)


def test_admin_cannot_touch_owners(store: FakeStore) -> None:
    service = IdentityService(store)
    admin = Principal(ALICE, ORG_A, R.ADMIN)
    for action in (
        lambda: service.add_member(admin, "x@example.org", R.OWNER),
        lambda: service.change_role(admin, BOB, R.ADMIN),
        lambda: service.deactivate(admin, BOB),
    ):
        with pytest.raises(PermissionDenied):
            action()
    assert store.calls == []


def test_add_member_always_answers_the_same(store: FakeStore) -> None:
    service = IdentityService(store)
    owner = Principal(BOB, ORG_A, R.OWNER)
    assert service.add_member(owner, "known@example.org", R.ADMIN) is InvitationResult.RECORDED
    assert service.add_member(owner, "unknown@example.org", R.OWNER) is InvitationResult.RECORDED


def test_change_role_of_a_non_member_and_idempotent_deactivate(store: FakeStore) -> None:
    service = IdentityService(store)
    owner = Principal(BOB, ORG_A, R.OWNER)
    with pytest.raises(MemberNotFound):
        service.change_role(owner, UserId(uuid4()), R.ANALYST)
    service.deactivate(owner, UserId(uuid4()))  # not listed: the store decides
    assert store.calls == ["deactivate"]
