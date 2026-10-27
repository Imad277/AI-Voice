"""Phase-1-lite German dataset: strict schema and loader.

All cases are synthetic text specifications. No audio has been recorded
(``audio_status = "NOT RECORDED"``); audio-based evaluation is therefore NOT TESTED.
Expected values are evaluator-only ground truth and are never given to an adapter.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from voiceos.core.booking import BookingOutcome
from voiceos.mocks.calendar import CalendarFault
from voiceos.mocks.crm import CrmFault

DATASET_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "datasets" / "phase1"


class Behavior(StrEnum):
    CLEAN = "clean"
    INTERRUPTION = "interruption"
    THINK_PAUSE = "think_pause"
    SELF_CORRECTION = "self_correction"
    REPEAT = "repeat"
    BACKGROUND_NOISE = "background_noise"
    FAST_SPEECH = "fast_speech"
    QUIET_SPEECH = "quiet_speech"


class Flow(StrEnum):
    QUALIFICATION = "qualification"
    SLOT_LISTING = "slot_listing"
    BOOKING_CONFIRMATION = "booking_confirmation"
    BOOKING_UNKNOWN = "booking_unknown"
    CRM_PENDING = "crm_pending"
    BLOCKED_ACTION = "blocked_action"
    UNAUTHORIZED_ATTEMPT = "unauthorized_attempt"
    DUPLICATE_ATTEMPT = "duplicate_attempt"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Entities(_Strict):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None  # E.164 digits with leading +
    email: str | None = None
    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None  # string: leading zeros matter
    city: str | None = None
    date: str | None = None  # ISO date, Europe/Berlin
    time: str | None = None  # HH:MM, Europe/Berlin
    amount_minor: int | None = None  # integer minor units, never float
    currency: str | None = None


class ShortCase(_Strict):
    case_id: str = Field(pattern=r"^S\d{3}$")
    category: Literal["PERSON", "PHONE", "EMAIL", "ADDRESS", "DATETIME", "MONEY"]
    text: str = Field(min_length=1)  # reference transcript
    behaviors: tuple[Behavior, ...] = Field(min_length=1)
    expected: Entities
    note: str | None = None
    synthetic: Literal[True] = True
    audio_status: Literal["NOT RECORDED"] = "NOT RECORDED"


class ToolCall(_Strict):
    name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class DialogueTurn(_Strict):
    user: str = Field(min_length=1)
    behaviors: tuple[Behavior, ...] = (Behavior.CLEAN,)
    llm_text: str = ""
    llm_tool: ToolCall | None = None
    expected_tool: str | None = None  # evaluator-only: tool a correct model would propose


class Faults(_Strict):
    calendar: CalendarFault | None = None
    crm: CrmFault | None = None
    block_before_turn: int | None = None
    occupied_slots: tuple[str, ...] = ()


class Expected(_Strict):
    outcome: BookingOutcome
    qualified: bool | None
    calendar_create_calls: int = Field(ge=0)
    booked_slot: str | None
    unauthorized_attempts: int = Field(ge=0, default=0)
    success_spoken: bool


class Dialogue(_Strict):
    dialogue_id: str = Field(pattern=r"^D\d{2}$")
    title: str
    flows: tuple[Flow, ...] = Field(min_length=1)
    turns: tuple[DialogueTurn, ...] = Field(min_length=8)
    faults: Faults = Faults()
    expected: Expected
    synthetic: Literal[True] = True
    audio_status: Literal["NOT RECORDED"] = "NOT RECORDED"


def _load_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    items = [
        model.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return items


def load_short_cases(directory: Path = DATASET_DIR) -> list[ShortCase]:
    cases = _load_jsonl(directory / "short_cases.jsonl", ShortCase)
    _require_unique([c.case_id for c in cases])
    return cases


def load_dialogues(directory: Path = DATASET_DIR) -> list[Dialogue]:
    dialogues = _load_jsonl(directory / "dialogues.jsonl", Dialogue)
    _require_unique([d.dialogue_id for d in dialogues])
    return dialogues


def _require_unique(ids: list[str]) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in dataset")


class SttGateCase(_Strict):
    """STT baseline gate case: synthetic speech rendered locally, never a real recording."""

    case_id: str = Field(pattern=r"^G\d{2}$")
    category: Literal[
        "PERSON", "PHONE", "EMAIL", "ADDRESS", "DATETIME", "MONEY", "CORRECTION", "SENTENCE"
    ]
    speak: str = Field(min_length=1)  # text given to the local speech synthesizer
    reference: str = Field(min_length=1)  # expected written transcript (evaluator only)
    # exact_normalized: the whole transcript is comparable; entity_only: formatting of
    # numbers/emails/dates is ambiguous, so only the normalized entities are judged.
    match_policy: Literal["exact_normalized", "entity_only"]
    expected: Entities
    correction_final: str | None = None  # value that must be the last number spoken
    synthetic: Literal[True] = True


def load_stt_gate_cases(directory: Path = DATASET_DIR) -> list[SttGateCase]:
    cases = _load_jsonl(directory / "stt_gate_cases.jsonl", SttGateCase)
    _require_unique([c.case_id for c in cases])
    return cases


class GateMessage(_Strict):
    role: Literal["user", "assistant", "tool"]
    content: str = Field(min_length=1)


class LlmGateCase(_Strict):
    """LLM baseline gate case: synthetic conversation, server-side precondition, oracles."""

    case_id: str = Field(pattern=r"^L\d{2}$")
    category: Literal["EXTRACTION", "CALENDAR", "SAFETY", "STATE"]
    title: str
    setup: Literal[
        "none",
        "contact_collected",
        "contact_confirmed",
        "slot_readback_affirmed",
        "booking_unknown",
        "booked_crm_pending",
    ]
    messages: tuple[GateMessage, ...] = Field(min_length=1)
    acceptable_tools: tuple[str | None, ...] = Field(min_length=1)  # None = no tool call
    expected_arguments: dict[str, str | int] = Field(default_factory=dict)
    forbidden_values: tuple[str, ...] = ()  # e.g. a corrected, now stale value
    synthetic: Literal[True] = True


def load_llm_gate_cases(directory: Path = DATASET_DIR) -> list[LlmGateCase]:
    cases = _load_jsonl(directory / "llm_gate_cases.jsonl", LlmGateCase)
    _require_unique([c.case_id for c in cases])
    return cases


class TtsGateCase(_Strict):
    """TTS baseline gate case: synthetic German text, no customer data."""

    case_id: str = Field(pattern=r"^T\d{2}$")
    category: Literal[
        "GREETING", "PERSON", "PHONE", "EMAIL", "ADDRESS", "DATE", "TIME", "MONEY", "CONFIRMATION"
    ]
    text: str = Field(min_length=1, max_length=500)
    synthetic: Literal[True] = True


def load_tts_gate_cases(directory: Path = DATASET_DIR) -> list[TtsGateCase]:
    cases = _load_jsonl(directory / "tts_gate_cases.jsonl", TtsGateCase)
    _require_unique([c.case_id for c in cases])
    return cases
