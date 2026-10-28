"""Tool value types: global tool types, tenant tool instances and their policies.

Database-independent. The enum values are the values stored by the ``0005_tool_registry``
migration and checked by its constraints.

A tool type is data, never code: its input/output schemas are a closed JSON Schema subset
that is JSON-only, size-limited, validated here and hashed deterministically. Side-effect
class and confirmation policy belong to the platform-defined tool type; neither a tenant
nor model output can change them. Execution stays in the Tool Gateway
(tool instance -> tool type -> gateway execution); nothing here executes anything.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import NewType
from uuid import UUID

from voiceos.domain.agents.model import configuration_hash
from voiceos.domain.integrations.model import AUTHORITY_NAMES

ToolTypeKey = NewType("ToolTypeKey", str)
ToolInstanceId = NewType("ToolInstanceId", UUID)
ToolInstanceRef = NewType("ToolInstanceRef", str)

# Same syntax as agent configuration references, so agent versions can name instances.
TOOL_INSTANCE_REF = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")

MAX_SCHEMA_BYTES = 16 * 1024  # also enforced by the database (0005)
MAX_SCHEMA_DEPTH = 8
MAX_PROPERTIES = 50
MAX_ENUM = 100
MAX_PATTERN = 200
_PROPERTY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_COMMON = frozenset({"type", "description", "title"})
_KEYWORDS: Mapping[str, frozenset[str]] = {
    "object": _COMMON | {"properties", "required", "additionalProperties"},
    "string": _COMMON | {"minLength", "maxLength", "pattern", "enum", "format"},
    "integer": _COMMON | {"minimum", "maximum", "enum"},
    "number": _COMMON | {"minimum", "maximum"},
    "boolean": _COMMON,
    "array": _COMMON | {"items", "minItems", "maxItems"},
}
_FORMATS = frozenset({"date", "date-time", "email"})


class SideEffectClass(StrEnum):
    READ_ONLY = "READ_ONLY"  # no external state changes
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"  # changes state that can be corrected later
    IRREVERSIBLE_WRITE = "IRREVERSIBLE_WRITE"  # e.g. a booking; operation ledger required
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION"  # sends data to a third party


class ConfirmationPolicy(StrEnum):
    """Ordered from weakest to strongest."""

    NONE = "NONE"
    EXPLICIT_USER_CONFIRMATION = "EXPLICIT_USER_CONFIRMATION"  # caller affirms explicitly
    SERVER_VERIFIED_CONFIRMATION = "SERVER_VERIFIED_CONFIRMATION"  # server-held readback state

    @property
    def strength(self) -> int:
        return list(ConfirmationPolicy).index(self)


# Weakest confirmation policy a tool type of each class may declare (also a database
# CHECK in 0005).
MINIMUM_CONFIRMATION: Mapping[SideEffectClass, ConfirmationPolicy] = {
    SideEffectClass.READ_ONLY: ConfirmationPolicy.NONE,
    SideEffectClass.REVERSIBLE_WRITE: ConfirmationPolicy.EXPLICIT_USER_CONFIRMATION,
    SideEffectClass.IRREVERSIBLE_WRITE: ConfirmationPolicy.SERVER_VERIFIED_CONFIRMATION,
    SideEffectClass.EXTERNAL_COMMUNICATION: ConfirmationPolicy.EXPLICIT_USER_CONFIRMATION,
}


def policy_is_sufficient(side_effect: SideEffectClass, policy: ConfirmationPolicy) -> bool:
    return policy.strength >= MINIMUM_CONFIRMATION[side_effect].strength


class ToolInstanceStatus(StrEnum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


def schema_hash(
    schema_version: int, input_schema: Mapping[str, object], output_schema: Mapping[str, object]
) -> str:
    """Deterministic hash of a tool type's contract (canonical JSON, SHA-256)."""
    return configuration_hash(
        {"schema_version": schema_version, "input": input_schema, "output": output_schema}
    )


def schema_issues(schema: Mapping[str, object]) -> tuple[str, ...]:
    """Validate a tool schema against the closed subset. The root is an object schema;
    every object is closed (``additionalProperties: false``); no references, no
    combinators, no defaults, no names that could carry authority."""
    try:
        size = len(json.dumps(dict(schema), allow_nan=False, ensure_ascii=False).encode())
    except (TypeError, ValueError):
        return ("<root>: not_json",)
    if size > MAX_SCHEMA_BYTES:
        return ("<root>: too_large",)
    issues: list[str] = []
    if schema.get("type") != "object":
        issues.append("<root>: root_must_be_object")
    _check(schema, "<root>", 1, issues)
    return tuple(issues)


def _check(node: object, path: str, depth: int, issues: list[str]) -> None:
    if depth > MAX_SCHEMA_DEPTH:
        issues.append(f"{path}: too_deep")
        return
    if not isinstance(node, Mapping):
        issues.append(f"{path}: not_a_schema")
        return
    kind = node.get("type")
    if not isinstance(kind, str) or kind not in _KEYWORDS:
        issues.append(f"{path}.type: unsupported")
        return
    for keyword in node:
        if keyword not in _KEYWORDS[kind]:
            issues.append(f"{path}.{keyword}: keyword_not_allowed")
    for keyword in ("description", "title"):
        if keyword in node and not (isinstance(node[keyword], str) and len(node[keyword]) <= 500):
            issues.append(f"{path}.{keyword}: invalid")
    if kind == "object":
        _check_object(node, path, depth, issues)
    elif kind == "array":
        if "items" not in node:
            issues.append(f"{path}.items: missing")
        else:
            _check(node["items"], f"{path}.items", depth + 1, issues)
        _bounds(node, path, "minItems", "maxItems", issues)
    elif kind == "string":
        _bounds(node, path, "minLength", "maxLength", issues)
        pattern = node.get("pattern")
        if pattern is not None and not (
            isinstance(pattern, str) and len(pattern) <= MAX_PATTERN and _compiles(pattern)
        ):
            issues.append(f"{path}.pattern: invalid")
        if "format" in node and node["format"] not in _FORMATS:
            issues.append(f"{path}.format: unsupported")
        _enum(node, path, str, issues)
    elif kind in ("integer", "number"):
        for keyword in ("minimum", "maximum"):
            value = node.get(keyword)
            if keyword in node and (isinstance(value, bool) or not isinstance(value, int | float)):
                issues.append(f"{path}.{keyword}: invalid")
        if kind == "integer":
            _enum(node, path, int, issues)


def _check_object(node: Mapping[str, object], path: str, depth: int, issues: list[str]) -> None:
    if node.get("additionalProperties") is not False:
        issues.append(f"{path}.additionalProperties: must_be_false")
    properties = node.get("properties", {})
    if not isinstance(properties, Mapping) or len(properties) > MAX_PROPERTIES:
        issues.append(f"{path}.properties: invalid")
        return
    for name, child in properties.items():
        where = f"{path}.properties.{name}"
        if not _PROPERTY.match(str(name)):
            issues.append(f"{where}: invalid_name")
        elif name in AUTHORITY_NAMES:
            issues.append(f"{where}: forbidden_name")
        else:
            _check(child, where, depth + 1, issues)
    required = node.get("required", [])
    if (
        not isinstance(required, list)
        or len(set(map(str, required))) != len(required)
        or not all(isinstance(r, str) and r in properties for r in required)
    ):
        issues.append(f"{path}.required: invalid")


def _bounds(node: Mapping[str, object], path: str, low: str, high: str, issues: list[str]) -> None:
    raw = [node[k] for k in (low, high) if k in node]
    values = [v for v in raw if isinstance(v, int) and not isinstance(v, bool) and v >= 0]
    if len(values) != len(raw) or (len(values) == 2 and values[0] > values[1]):
        issues.append(f"{path}.{low}/{high}: invalid")


def _enum(node: Mapping[str, object], path: str, kind: type, issues: list[str]) -> None:
    if "enum" not in node:
        return
    values = node["enum"]
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= MAX_ENUM
        or any(isinstance(v, bool) or not isinstance(v, kind) for v in values)
        or len(set(values)) != len(values)
    ):
        issues.append(f"{path}.enum: invalid")


def _compiles(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True
