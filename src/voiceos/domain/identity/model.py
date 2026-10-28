"""Identity value types: organizations (tenants), users and memberships.

Database-independent. The string values of the enums are the values stored by the
``0002_product_foundation`` migration and checked by its constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType
from uuid import UUID

OrganizationId = NewType("OrganizationId", UUID)  # = tenant_id of every tenant-owned row
UserId = NewType("UserId", UUID)


class OrganizationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class MembershipRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    BILLING = "BILLING"
    READ_ONLY = "READ_ONLY"


class MembershipStatus(StrEnum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REMOVED = "REMOVED"


@dataclass(frozen=True, slots=True)
class OrganizationScope:
    """Trusted, server-issued scope of a control plane request.

    Built only by trusted server code from an authenticated principal and its verified
    membership (authentication is NOT DECIDED, D-12) - never from a client-supplied
    organization id, model output or webhook payload. It is the only input from which the
    persistence layer binds the tenant of a transaction.
    """

    organization_id: OrganizationId
    user_id: UserId | None = None
