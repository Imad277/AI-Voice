"""Domain value types of the product foundation (no database)."""

from __future__ import annotations

import dataclasses
from uuid import uuid4

import pytest

from voiceos.domain.agents.model import configuration_hash
from voiceos.domain.identity.model import (
    MembershipRole,
    OrganizationId,
    OrganizationScope,
    UserId,
)


def test_configuration_hash_is_canonical() -> None:
    first = configuration_hash({"language": "de", "goals": ["book", "qualify"], "n": 1})
    second = configuration_hash({"n": 1, "goals": ["book", "qualify"], "language": "de"})
    assert first == second and len(first) == 64
    assert configuration_hash({"goals": ["qualify", "book"]}) != configuration_hash(
        {"goals": ["book", "qualify"]}
    )
    assert configuration_hash({"text": "Grüße"}) == configuration_hash({"text": "Grüße"})


def test_configuration_hash_rejects_non_json_values() -> None:
    with pytest.raises(ValueError):
        configuration_hash({"x": float("nan")})
    with pytest.raises(TypeError):
        configuration_hash({"x": object()})


def test_organization_scope_is_immutable() -> None:
    scope = OrganizationScope(OrganizationId(uuid4()), UserId(uuid4()))
    with pytest.raises(dataclasses.FrozenInstanceError):
        scope.organization_id = OrganizationId(uuid4())  # type: ignore[misc]


def test_roles_are_the_blueprint_roles() -> None:
    assert [r.value for r in MembershipRole] == [
        "OWNER", "ADMIN", "DEVELOPER", "OPERATOR", "ANALYST", "BILLING", "READ_ONLY",
    ]  # fmt: skip
