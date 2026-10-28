"""Agent value types: agents, versions and deployments.

Database-independent. The enum values are the values stored by the
``0002_product_foundation`` migration and checked by its constraints.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import NewType
from uuid import UUID

AgentId = NewType("AgentId", UUID)
AgentVersionId = NewType("AgentVersionId", UUID)
DeploymentId = NewType("DeploymentId", UUID)


class AgentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AgentVersionStatus(StrEnum):
    DRAFT = "DRAFT"  # editable
    PUBLISHED = "PUBLISHED"  # immutable; may only be archived
    ARCHIVED = "ARCHIVED"  # immutable


class DeploymentEnvironment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class DeploymentStatus(StrEnum):
    ACTIVE = "ACTIVE"  # requires a published version
    INACTIVE = "INACTIVE"


def configuration_hash(configuration: Mapping[str, object]) -> str:
    """SHA-256 over the canonical JSON form (sorted keys, no whitespace, UTF-8)."""
    canonical = json.dumps(
        configuration, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
