"""Typed agent configuration and its pure validation rules.

A draft is stored as a raw JSON object so incomplete work can be autosaved; only a draft
that validates into ``AgentConfiguration`` can become an agent version. Unknown keys are
rejected everywhere, so a configuration can never carry provider credentials, endpoints
or ad-hoc provider parameters.

Providers, voices, tools and knowledge sources are referenced by opaque references only
(``*_ref``); no provider is named or selected here (decision register D-03/04/05).
Until the tool registry and the knowledge platform exist, tool and knowledge references
are validated for syntax and duplicates only; their existence and tenant ownership are
validated by the later PRs that introduce those tables.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from voiceos.domain.agents.model import configuration_hash

SCHEMA_VERSION: Literal[1] = 1
MAX_DRAFT_BYTES = 256 * 1024  # also enforced by the database (0004)

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Reference = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.:-]{0,127}$")]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_TIMEZONE = re.compile(r"^(UTC|[A-Z][A-Za-z_]+(/[A-Z][A-Za-z_+-]+){1,2})$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BusinessHoursWindow(_Strict):
    day: Weekday
    opens: str
    closes: str

    @model_validator(mode="after")
    def _ordered(self) -> BusinessHoursWindow:
        if not (_CLOCK.match(self.opens) and _CLOCK.match(self.closes)):
            raise ValueError("times must be HH:MM (24h)")
        if self.opens >= self.closes:
            raise ValueError("a window must open before it closes")
        return self


class BusinessHours(_Strict):
    timezone: str
    windows: tuple[BusinessHoursWindow, ...] = Field(min_length=1, max_length=28)

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        if not _TIMEZONE.match(value):
            raise ValueError("timezone must be an IANA name such as Europe/Berlin or UTC")
        return value

    @model_validator(mode="after")
    def _no_overlap(self) -> BusinessHours:
        by_day: dict[str, list[BusinessHoursWindow]] = {}
        for window in self.windows:
            by_day.setdefault(window.day, []).append(window)
        for windows in by_day.values():
            ordered = sorted(windows, key=lambda w: w.opens)
            for first, second in pairwise(ordered):
                if second.opens < first.closes:
                    raise ValueError("business hours windows of one day must not overlap")
        return self


FieldType = Literal[
    "text", "name", "phone", "email", "date", "datetime", "number", "enum", "address", "boolean"
]


class DataField(_Strict):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
    label: Annotated[Text, StringConstraints(min_length=1, max_length=80)]
    type: FieldType
    required: bool = False
    confirmation: Literal["none", "readback", "readback_and_affirm"] = "none"
    options: tuple[Annotated[Text, StringConstraints(min_length=1, max_length=80)], ...] = ()
    pii: bool = False

    @model_validator(mode="after")
    def _options(self) -> DataField:
        if self.type == "enum" and not self.options:
            raise ValueError("an enum field needs options")
        if self.type != "enum" and self.options:
            raise ValueError("only enum fields have options")
        if len(set(self.options)) != len(self.options):
            raise ValueError("enum options must be unique")
        return self


class DataCollectionSchema(_Strict):
    fields: tuple[DataField, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def _unique_keys(self) -> DataCollectionSchema:
        keys = [f.key for f in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("data field keys must be unique")
        return self


class EscalationRule(_Strict):
    condition: Annotated[Text, StringConstraints(min_length=1, max_length=300)]
    action: Literal["transfer", "callback", "end_call"]
    target_ref: Reference | None = None

    @model_validator(mode="after")
    def _target(self) -> EscalationRule:
        if (self.action == "transfer") != (self.target_ref is not None):
            raise ValueError("a transfer needs a target_ref; other actions must not have one")
        return self


class FallbackRules(_Strict):
    on_no_understanding: Literal["repeat", "escalate", "end_call"] = "repeat"
    max_retries: Annotated[int, Field(ge=0, le=5)] = 2
    on_provider_failure: Literal["apologize_and_end", "escalate", "callback"] = "apologize_and_end"


class ComplianceSettings(_Strict):
    ai_disclosure: bool = True
    disclosure_text: Annotated[Text, StringConstraints(max_length=500)] = ""
    recording: Literal["off", "with_consent"] = "off"  # off by default (CLAUDE.md rule 22)
    consent_prompt: Annotated[Text, StringConstraints(min_length=1, max_length=500)] | None = None
    retention_days: Annotated[int, Field(ge=1, le=3650)] = 30

    @model_validator(mode="after")
    def _consistent(self) -> ComplianceSettings:
        if self.ai_disclosure and not self.disclosure_text:
            raise ValueError("AI disclosure needs a disclosure_text")
        if (self.recording == "with_consent") != (self.consent_prompt is not None):
            raise ValueError("recording with consent needs a consent_prompt (and only then)")
        return self


class ModelReferences(_Strict):
    """All five references are required: there is no unbound provider configuration."""

    stt_profile_ref: Reference
    llm_profile_ref: Reference
    tts_profile_ref: Reference
    voice_ref: Reference
    turn_taking_profile_ref: Reference


Goal = Annotated[Text, StringConstraints(min_length=1, max_length=500)]


class AgentConfiguration(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    name: Annotated[Text, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[Text, StringConstraints(max_length=2000)] = ""
    language: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")]
    system_instructions: Annotated[Text, StringConstraints(min_length=1, max_length=20000)]
    opening_message: Annotated[Text, StringConstraints(min_length=1, max_length=1000)]
    personality: Annotated[Text, StringConstraints(max_length=2000)] = ""
    conversation_goals: tuple[Goal, ...] = Field(min_length=1, max_length=20)
    success_criteria: tuple[Goal, ...] = Field(default=(), max_length=20)
    escalation_rules: tuple[EscalationRule, ...] = Field(default=(), max_length=20)
    fallback_rules: FallbackRules = FallbackRules()
    business_hours: BusinessHours | None = None
    data_collection: DataCollectionSchema = DataCollectionSchema()
    compliance: ComplianceSettings
    models: ModelReferences
    tool_refs: tuple[Reference, ...] = Field(default=(), max_length=50)
    knowledge_refs: tuple[Reference, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def _no_duplicates(self) -> AgentConfiguration:
        for name, values in (
            ("conversation_goals", self.conversation_goals),
            ("tool_refs", self.tool_refs),
            ("knowledge_refs", self.knowledge_refs),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        return self

    def canonical(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def hash(self) -> str:
        return configuration_hash(self.canonical())


@dataclass(frozen=True, slots=True)
class ConfigurationCheck:
    configuration: AgentConfiguration | None
    issues: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.configuration is not None


def validate_configuration(raw: Mapping[str, object]) -> ConfigurationCheck:
    """Validate a raw draft. Issues name the location and the rule, never echo values.

    Validated in strict JSON mode: JSON arrays for tuples, but no type coercion (a number
    is never accepted for a string, a string never for a boolean)."""
    try:
        document = json.dumps(dict(raw), allow_nan=False)
    except (TypeError, ValueError):
        return ConfigurationCheck(None, ("<root>: not_json",))
    try:
        return ConfigurationCheck(AgentConfiguration.model_validate_json(document), ())
    except ValidationError as exc:
        issues = tuple(
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['type']}"
            for err in exc.errors(include_input=False, include_url=False)
        )
        return ConfigurationCheck(None, issues)
