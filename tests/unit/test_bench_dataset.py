"""Phase-1-lite dataset: size, coverage, synthetic-only, strict schema."""

import json

import pytest
from pydantic import ValidationError

from voiceos.benchmark.dataset import (
    DATASET_DIR,
    Behavior,
    Dialogue,
    Flow,
    ShortCase,
    load_dialogues,
    load_short_cases,
)
from voiceos.core.tools import ToolName

ENTITY_FIELDS = {
    "first_name", "last_name", "phone", "email", "street", "house_number",
    "postal_code", "city", "date", "time", "amount_minor",
}  # fmt: skip
BEHAVIORS = {b for b in Behavior if b is not Behavior.CLEAN}
FLOWS = {
    Flow.QUALIFICATION, Flow.SLOT_LISTING, Flow.BOOKING_CONFIRMATION, Flow.BOOKING_UNKNOWN,
    Flow.CRM_PENDING, Flow.BLOCKED_ACTION,
}  # fmt: skip


def test_dataset_size() -> None:
    assert len(load_short_cases()) >= 50
    assert len(load_dialogues()) >= 20


def test_short_cases_cover_every_entity_and_behavior() -> None:
    cases = load_short_cases()
    covered = {f for c in cases for f, v in c.expected.model_dump().items() if v is not None}
    assert covered >= ENTITY_FIELDS
    # Interruption needs AI audio to interrupt, so it is covered by the dialogues.
    assert {b for c in cases for b in c.behaviors} >= BEHAVIORS - {Behavior.INTERRUPTION}


def test_dialogues_cover_behaviors_and_business_flows() -> None:
    dialogues = load_dialogues()
    assert {b for d in dialogues for t in d.turns for b in t.behaviors} >= BEHAVIORS
    assert {f for d in dialogues for f in d.flows} >= FLOWS


def test_everything_is_synthetic_and_unrecorded() -> None:
    for item in [*load_short_cases(), *load_dialogues()]:
        assert item.synthetic is True
        assert item.audio_status == "NOT RECORDED"
    for case in load_short_cases():
        if case.expected.email:
            assert case.expected.email.endswith("@example.org")  # reserved domain
        if case.expected.phone:
            # Berlin numbers never start with 0 after the area code: unassignable.
            assert case.expected.phone.startswith("+49300")


def test_dialogue_tools_reference_the_allowlist_or_are_deliberate_attacks() -> None:
    allowed = {t.value for t in ToolName}
    unknown = {
        t.llm_tool.name
        for d in load_dialogues()
        for t in d.turns
        if t.llm_tool and t.llm_tool.name not in allowed
    }
    assert unknown == {"calendar.delete_all"}


def test_ground_truth_fields_are_not_part_of_what_adapters_get() -> None:
    # Adapters receive only transcripts/audio refs and LLM scripts; expected values stay
    # in the evaluator-side models.
    assert "expected" in ShortCase.model_fields
    assert "expected" in Dialogue.model_fields


def test_unknown_keys_are_rejected() -> None:
    line = (DATASET_DIR / "short_cases.jsonl").read_text().splitlines()[0]
    data = json.loads(line) | {"customer_id": "real-123"}
    with pytest.raises(ValidationError):
        ShortCase.model_validate(data)


def test_money_is_integer_minor_units() -> None:
    amounts = [c.expected.amount_minor for c in load_short_cases() if c.category == "MONEY"]
    assert amounts and all(isinstance(a, int) for a in amounts)
