"""Tool registry and integration domain rules: classes, policies, transitions, schemas,
configuration screening and credential references (pure, no database)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from voiceos.domain.identity.rbac import Permission, roles_with
from voiceos.domain.integrations.model import (
    AUTHORITY_NAMES,
    CONNECTION_TRANSITIONS,
    AuthType,
    ConnectionStatus,
    can_transition,
    configuration_issues,
    credential_ref_issues,
    initial_connection_status,
)
from voiceos.domain.tools.model import (
    MINIMUM_CONFIRMATION,
    ConfirmationPolicy,
    SideEffectClass,
    policy_is_sufficient,
    schema_hash,
    schema_issues,
)
from voiceos.gateway.schemas import AUTHORITY_KEYS

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "db" / "migrations" / "0005_tool_registry.sql").read_text()
S, C = SideEffectClass, ConfirmationPolicy
OBJECT = {"type": "object", "properties": {}, "additionalProperties": False}


def _obj(**properties: object) -> dict[str, object]:
    return {"type": "object", "properties": properties, "additionalProperties": False}


# -- side effects and confirmation -------------------------------------------------------------


def test_side_effect_classes_and_policies_are_the_closed_sets() -> None:
    assert {s.value for s in SideEffectClass} == {
        "READ_ONLY", "REVERSIBLE_WRITE", "IRREVERSIBLE_WRITE", "EXTERNAL_COMMUNICATION",
    }  # fmt: skip
    assert [p.value for p in ConfirmationPolicy] == [
        "NONE", "EXPLICIT_USER_CONFIRMATION", "SERVER_VERIFIED_CONFIRMATION",
    ]  # fmt: skip
    with pytest.raises(ValueError):
        SideEffectClass("read")  # never derived from free strings
    with pytest.raises(ValueError):
        ConfirmationPolicy("explicit")


@pytest.mark.parametrize(
    ("effect", "policy", "allowed"),
    [
        (S.READ_ONLY, C.NONE, True),
        (S.REVERSIBLE_WRITE, C.NONE, False),
        (S.REVERSIBLE_WRITE, C.EXPLICIT_USER_CONFIRMATION, True),
        (S.IRREVERSIBLE_WRITE, C.EXPLICIT_USER_CONFIRMATION, False),
        (S.IRREVERSIBLE_WRITE, C.SERVER_VERIFIED_CONFIRMATION, True),
        (S.EXTERNAL_COMMUNICATION, C.NONE, False),
        (S.EXTERNAL_COMMUNICATION, C.SERVER_VERIFIED_CONFIRMATION, True),
    ],
)
def test_minimum_confirmation_per_side_effect(
    effect: SideEffectClass, policy: ConfirmationPolicy, allowed: bool
) -> None:
    assert policy_is_sufficient(effect, policy) is allowed


def test_sql_minimum_confirmation_check_matches_the_domain() -> None:
    block = SQL[SQL.index("CHECK (CASE side_effect_class") :]
    block = block[: block.index("END)")]
    sql_rule = dict(re.findall(r"WHEN '(\w+)' THEN (.+)", block))
    expected = {
        "READ_ONLY": "true",
        "REVERSIBLE_WRITE": "confirmation_policy <> 'NONE'",
        "IRREVERSIBLE_WRITE": "confirmation_policy = 'SERVER_VERIFIED_CONFIRMATION'",
        "EXTERNAL_COMMUNICATION": "confirmation_policy <> 'NONE'",
    }
    assert sql_rule == expected
    for effect, minimum in MINIMUM_CONFIRMATION.items():
        accepted = {p for p in ConfirmationPolicy if policy_is_sufficient(effect, p)}
        assert minimum in accepted and len(accepted) == 3 - minimum.strength


# -- connection status ---------------------------------------------------------------------------


def test_connection_statuses_and_transitions() -> None:
    assert {s.value for s in ConnectionStatus} == {
        "PENDING", "ACTIVE", "DISCONNECTED", "ERROR", "REVOKED",
    }  # fmt: skip
    assert set(CONNECTION_TRANSITIONS) == set(ConnectionStatus)
    assert CONNECTION_TRANSITIONS[ConnectionStatus.REVOKED] == frozenset()  # terminal
    assert not can_transition(ConnectionStatus.REVOKED, ConnectionStatus.ACTIVE)
    assert not can_transition(ConnectionStatus.DISCONNECTED, ConnectionStatus.ACTIVE)
    assert can_transition(ConnectionStatus.ACTIVE, ConnectionStatus.ACTIVE)


def test_sql_transition_table_matches_the_domain() -> None:
    body = SQL[SQL.index("NOT IN (VALUES") : SQL.index("connection status transition not allowed")]
    pairs = set(re.findall(r"\('(\w+)', '(\w+)'\)", body))
    expected = {
        (a.value, b.value) for a, targets in CONNECTION_TRANSITIONS.items() for b in targets
    }
    assert pairs == expected


def test_initial_status_and_credential_refs() -> None:
    assert initial_connection_status(AuthType.NONE) is ConnectionStatus.ACTIVE
    assert initial_connection_status(AuthType.OAUTH2) is ConnectionStatus.PENDING
    assert credential_ref_issues(AuthType.NONE, None) == ()
    assert credential_ref_issues(AuthType.NONE, "cred:x") == ("credential_ref: not_allowed",)
    assert credential_ref_issues(AuthType.API_KEY, None) == ("credential_ref: missing",)
    assert credential_ref_issues(AuthType.API_KEY, "cred:tenant-a/crm/v1") == ()
    for raw in ("sk-live-abcdef", "cred:Upper", "cred: space", "https://vault/x", "cred:"):
        assert credential_ref_issues(AuthType.API_KEY, raw) == ("credential_ref: invalid_format",)


# -- tool schemas --------------------------------------------------------------------------------


def test_valid_schema_and_stable_hash() -> None:
    schema = _obj(
        date={"type": "string", "format": "date", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
        count={"type": "integer", "minimum": 1, "maximum": 5},
        items={"type": "array", "maxItems": 3, "items": {"type": "string", "enum": ["a", "b"]}},
    )
    schema["required"] = ["date"]
    assert schema_issues(schema) == ()
    reordered = dict(reversed(list(schema.items())))
    assert schema_hash(1, schema, OBJECT) == schema_hash(1, reordered, OBJECT)
    assert schema_hash(1, schema, OBJECT) != schema_hash(2, schema, OBJECT)  # versioned
    assert re.fullmatch(r"[0-9a-f]{64}", schema_hash(1, schema, OBJECT))


@pytest.mark.parametrize(
    ("schema", "issue"),
    [
        ({"type": "string"}, "<root>: root_must_be_object"),
        ({"type": "object", "properties": {}}, "<root>.additionalProperties: must_be_false"),
        ({**OBJECT, "additionalProperties": True}, "<root>.additionalProperties: must_be_false"),
        ({**OBJECT, "$ref": "#/defs/x"}, "<root>.$ref: keyword_not_allowed"),
        ({**OBJECT, "oneOf": []}, "<root>.oneOf: keyword_not_allowed"),
        ({**OBJECT, "default": {}}, "<root>.default: keyword_not_allowed"),
        (_obj(tenant_id={"type": "string"}), "<root>.properties.tenant_id: forbidden_name"),
        (_obj(url={"type": "string"}), "<root>.properties.url: forbidden_name"),
        (_obj(Name={"type": "string"}), "<root>.properties.Name: invalid_name"),
        (_obj(x={"type": "null"}), "<root>.properties.x.type: unsupported"),
        (_obj(x={"type": "string", "pattern": "("}), "<root>.properties.x.pattern: invalid"),
        (_obj(x={"type": "string", "format": "uri"}), "<root>.properties.x.format: unsupported"),
        (_obj(x={"type": "string", "minLength": 5, "maxLength": 2}),
         "<root>.properties.x.minLength/maxLength: invalid"),
        (_obj(x={"type": "integer", "minimum": True}), "<root>.properties.x.minimum: invalid"),
        (_obj(x={"type": "string", "enum": []}), "<root>.properties.x.enum: invalid"),
        (_obj(x={"type": "array"}), "<root>.properties.x.items: missing"),
        ({**OBJECT, "required": ["missing"]}, "<root>.required: invalid"),
        (_obj(x={"type": "object", "properties": {}}),
         "<root>.properties.x.additionalProperties: must_be_false"),
    ],
)  # fmt: skip
def test_invalid_schemas_are_rejected(schema: dict[str, object], issue: str) -> None:
    assert issue in schema_issues(schema)


def test_schema_limits() -> None:
    deep: dict[str, object] = {"type": "string"}
    for _ in range(9):
        deep = _obj(x=deep)
    assert any(i.endswith("too_deep") for i in schema_issues(deep))
    huge = _obj(x={"type": "string", "description": "d" * 400})
    huge["properties"] = {f"p{i}": {"type": "string", "description": "d" * 400} for i in range(45)}
    assert schema_issues(huge) == ("<root>: too_large",)
    assert schema_issues({"type": "object", "x": float("nan")}) == ("<root>: not_json",)
    assert schema_issues({"type": "object", "x": print}) == ("<root>: not_json",)  # no callables


def test_domain_authority_names_equal_the_gateway_screen() -> None:
    assert AUTHORITY_KEYS == AUTHORITY_NAMES


# -- configuration screening ---------------------------------------------------------------------


def test_plain_configuration_is_accepted() -> None:
    assert configuration_issues({"calendar_id": "primary", "slot_minutes": 30}) == ()
    assert configuration_issues({"owners": ["team-a", "team-b"], "options": {"days": 7}}) == ()


@pytest.mark.parametrize(
    ("configuration", "issue"),
    [
        ({"api_key": "x"}, "api_key: forbidden_key"),
        ({"client_secret": "x"}, "client_secret: forbidden_key"),
        ({"refresh_token": "x"}, "refresh_token: forbidden_key"),
        ({"db_password": "x"}, "db_password: forbidden_key"),
        ({"nested": {"private_key": "x"}}, "nested.private_key: forbidden_key"),
        ({"tenant_id": "x"}, "tenant_id: forbidden_key"),
        ({"endpoint": "x"}, "endpoint: forbidden_key"),
        ({"note": "https://example.org/hook"}, "note: url_not_allowed"),
        ({"note": "sk-live-abcdefghijklmnop"}, "note: secret_like_value"),
        ({"note": "Bearer abc.def"}, "note: secret_like_value"),
        ({"note": "-----BEGIN PRIVATE KEY-----"}, "note: secret_like_value"),
        ({"items": ["ok", "xoxb-123"]}, "items[1]: secret_like_value"),
        ({"Bad-Key": 1}, "Bad-Key: invalid_key"),
        ({"note": "x" * 1001}, "note: too_long"),
        ({"a": {"b": {"c": {"d": {"e": 1}}}}}, "a.b.c.d: too_deep"),
    ],
)
def test_secret_like_or_authority_configuration_is_rejected(
    configuration: dict[str, object], issue: str
) -> None:
    assert issue in configuration_issues(configuration)


def test_configuration_issues_never_echo_values_and_respect_the_size_limit() -> None:
    marker = "sk-proj-marker-7f3a"
    issues = configuration_issues({"note": marker, "token": marker})
    assert issues and all(marker not in issue for issue in issues)
    assert configuration_issues({"blob": "x" * 999, **{f"k{i}": "x" * 999 for i in range(20)}}) == (
        "<root>: too_large",
    )
    assert configuration_issues({"x": float("inf")}) == ("<root>: not_json",)


def test_sql_integration_managers_match_the_matrix() -> None:
    match = re.search(
        r"FUNCTION voiceos\.caller_can_manage_integrations\(\).*?IN \(([^)]*)\)", SQL, re.DOTALL
    )
    assert match is not None
    listed = {r.strip().strip("'") for r in match.group(1).split(",")}
    assert listed == {r.value for r in roles_with(Permission.INTEGRATIONS_MANAGE)}


def test_production_migration_seeds_no_providers_or_capabilities() -> None:
    """D-27 is open: providers arrive with the migration that decides them; test doubles
    are not product data."""
    assert "INSERT INTO voiceos.integration_providers" not in SQL
    assert "INSERT INTO voiceos.integration_provider_capabilities" not in SQL
    seeded = re.findall(r"^\('([a-z_]+\.[a-z_]+)',", SQL, re.MULTILINE)
    assert seeded == ["calendar.list_slots", "calendar.book_slot", "crm.update_contact",
                      "webhook.invoke"]  # fmt: skip
