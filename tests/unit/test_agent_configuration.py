"""Typed agent configuration: validation rules, strictness, canonical form and hashing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from support import agent_configuration

from voiceos.domain.agents.configuration import AgentConfiguration, validate_configuration
from voiceos.domain.agents.model import configuration_hash

ROOT = Path(__file__).resolve().parents[2]


def _issues(**overrides: object) -> tuple[str, ...]:
    check = validate_configuration(agent_configuration(**overrides))
    assert not check.valid
    return check.issues


def test_valid_configuration_has_safe_defaults() -> None:
    check = validate_configuration(agent_configuration())
    assert check.valid and check.issues == ()
    configuration = check.configuration
    assert isinstance(configuration, AgentConfiguration)
    assert configuration.schema_version == 1
    assert configuration.compliance.recording == "off"  # recording disabled by default
    assert configuration.compliance.ai_disclosure is True
    assert configuration.business_hours is None
    assert configuration.tool_refs == () and configuration.knowledge_refs == ()


def test_canonical_form_and_hash_are_stable() -> None:
    first = validate_configuration(agent_configuration()).configuration
    reordered = dict(reversed(list(agent_configuration().items())))
    second = validate_configuration(reordered).configuration
    assert first is not None and second is not None
    assert first.canonical() == second.canonical()
    assert first.hash() == second.hash() == configuration_hash(first.canonical())
    again = validate_configuration(first.canonical()).configuration  # canonical round trip
    assert again is not None and again.hash() == first.hash()
    changed = validate_configuration(agent_configuration(opening_message="Hallo")).configuration
    assert changed is not None and changed.hash() != first.hash()


def test_whitespace_is_normalized_before_hashing() -> None:
    padded = validate_configuration(agent_configuration(name="  Reception  ")).configuration
    plain = validate_configuration(agent_configuration()).configuration
    assert padded is not None and plain is not None
    assert padded.name == "Reception" and padded.hash() == plain.hash()


@pytest.mark.parametrize(
    "overrides",
    [
        {"api_key": "placeholder"},
        {"models": {**agent_configuration()["models"], "endpoint": "https://example.org"}},  # type: ignore[dict-item]
        {"compliance": {"ai_disclosure": True, "disclosure_text": "KI", "token": "x"}},
    ],
)
def test_unknown_keys_are_rejected_everywhere(overrides: dict[str, object]) -> None:
    issues = _issues(**overrides)
    assert any(i.endswith("extra_forbidden") for i in issues)


def test_issues_never_echo_values() -> None:
    marker = "marker-value-7f3a"  # synthetic, recognizable value
    issues = _issues(api_key=marker, language=marker)
    assert all(marker not in issue for issue in issues)
    assert "api_key: extra_forbidden" in issues
    assert any(issue.startswith("language:") for issue in issues)


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": 7},
        {"language": "german"},
        {"language": "DE"},
        {"conversation_goals": []},
        {"conversation_goals": ["Same", "Same"]},
        {"compliance": {"ai_disclosure": "true", "disclosure_text": "KI"}},  # no coercion
        {"compliance": {"ai_disclosure": True, "disclosure_text": ""}},
        {"compliance": {"ai_disclosure": False, "recording": "with_consent"}},
        {"compliance": {"ai_disclosure": False, "consent_prompt": "Darf ich aufnehmen?"}},
        {"compliance": {"ai_disclosure": False, "recording": "always"}},
        {"compliance": {"ai_disclosure": False, "retention_days": 0}},
        {"schema_version": 2},
        {"fallback_rules": {"max_retries": 9}},
        {"tool_refs": ["calendar.book", "calendar.book"]},
        {"knowledge_refs": ["Upper.Case"]},
        {"tool_refs": ["https://example.org/hook"]},
        {"escalation_rules": [{"condition": "Caller asks for a human", "action": "transfer"}]},
        {"escalation_rules": [{"condition": "x", "action": "end_call", "target_ref": "team.a"}]},
    ],
)
def test_invalid_values_are_rejected(overrides: dict[str, object]) -> None:
    assert _issues(**overrides)


@pytest.mark.parametrize("missing", ["name", "language", "models", "compliance"])
def test_required_sections_are_required(missing: str) -> None:
    raw = agent_configuration()
    del raw[missing]
    check = validate_configuration(raw)
    assert not check.valid and f"{missing}: missing" in check.issues


def test_every_model_reference_is_required_and_generic() -> None:
    models = dict(agent_configuration()["models"])  # type: ignore[call-overload]
    del models["voice_ref"]
    assert "models.voice_ref: missing" in _issues(models=models)
    models["voice_ref"] = "Voice With Spaces"
    assert any(i.startswith("models.voice_ref:") for i in _issues(models=models))


def test_business_hours_rules() -> None:
    def hours(*windows: tuple[str, str, str], timezone: str = "Europe/Berlin") -> object:
        return {
            "timezone": timezone,
            "windows": [{"day": d, "opens": o, "closes": c} for d, o, c in windows],
        }

    ok = validate_configuration(
        agent_configuration(
            business_hours=hours(("mon", "08:00", "12:00"), ("mon", "13:00", "17:00"))
        )
    )
    assert ok.valid
    assert _issues(business_hours=hours(("mon", "08:00", "12:00"), ("mon", "11:00", "13:00")))
    assert _issues(business_hours=hours(("mon", "12:00", "08:00")))
    assert _issues(business_hours=hours(("mon", "8:00", "12:00")))
    assert _issues(business_hours=hours(("xyz", "08:00", "12:00")))
    assert _issues(business_hours=hours(("mon", "08:00", "12:00"), timezone="CET+1; DROP"))
    assert _issues(business_hours=hours())


def test_data_collection_rules() -> None:
    def fields(*items: dict[str, object]) -> object:
        return {"fields": list(items)}

    phone = {"key": "phone", "label": "Telefon", "type": "phone", "required": True,
             "confirmation": "readback", "pii": True}  # fmt: skip
    choice = {"key": "topic", "label": "Anliegen", "type": "enum", "options": ["A", "B"]}
    assert validate_configuration(agent_configuration(data_collection=fields(phone, choice))).valid
    assert _issues(data_collection=fields(phone, phone))
    assert _issues(data_collection=fields({**choice, "options": []}))
    assert _issues(data_collection=fields({**phone, "options": ["x"]}))
    assert _issues(data_collection=fields({**choice, "options": ["A", "A"]}))
    assert _issues(data_collection=fields({**phone, "key": "Phone-Number"}))
    assert _issues(data_collection=fields({**phone, "confirmation": "maybe"}))


def test_non_json_drafts_are_rejected_without_raising() -> None:
    assert validate_configuration({"name": float("nan")}).issues == ("<root>: not_json",)
    assert validate_configuration({"name": object()}).issues == ("<root>: not_json",)
    assert validate_configuration({}).valid is False


def test_product_code_names_no_concrete_provider() -> None:
    """Agent configuration references profiles only; no provider is hardcoded (D-03/04/05)."""
    pattern = re.compile(r"deepgram|openai|cartesia|elevenlabs|gpt-|whisper", re.IGNORECASE)
    paths = [
        ROOT / "src/voiceos/domain/agents/configuration.py",
        ROOT / "src/voiceos/application/control_plane/agents.py",
        ROOT / "src/voiceos/infrastructure/postgres/agents.py",
        ROOT / "db/migrations/0004_agent_lifecycle.sql",
    ]
    assert [p.name for p in paths if pattern.search(p.read_text())] == []
