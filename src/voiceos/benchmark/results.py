"""Benchmark result schema (one result per run x scenario) and writers.

Every metric group carries an explicit ``status``. A value that was not measured is
``null`` with status NOT TESTED; it is never filled with 0. Results contain no
credentials, transcripts, contact data or tool arguments.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from voiceos.benchmark.ports import Event


class Status(StrEnum):
    MEASURED = "MEASURED"  # numeric value taken from an actual run
    OBSERVED = "OBSERVED"  # qualitative behavior taken from an actual run
    NOT_TESTED = "NOT TESTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Quantiles(_Strict):
    status: Status
    scope: str  # what the clock actually measured
    n: int | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    max_ms: float | None = None


class LatencyMetrics(_Strict):
    caller_voice_latency: Quantiles  # end of user speech -> start of AI audio at the caller
    pipeline_latency: Quantiles  # runtime-internal: user turn end -> first TTS chunk
    endpointing: Quantiles
    stt_final: Quantiles
    llm_ttft: Quantiles
    tts_ttfb: Quantiles


class Ratio(_Strict):
    correct: int
    total: int


class EntityMetrics(_Strict):
    status: Status
    reason: str | None = None
    wer: Ratio | None = None
    per_field: dict[str, Ratio] = Field(default_factory=dict)


class ConversationMetrics(_Strict):
    status: Status
    reason: str | None = None
    interruption_opportunities: int | None = None
    false_endpoint: Ratio | None = None
    late_endpoint: Ratio | None = None
    missed_interruption: Ratio | None = None
    interruption_stop_ms: float | None = None
    context_loss: Ratio | None = None


class ToolMetrics(_Strict):
    status: Status
    proposals: int
    executed: int
    rejected: int
    unknown_tool_attempts: int
    unauthorized_attempts: int
    unauthorized_executions: int
    duplicate_side_effects: int
    correct_tool_selected: Ratio | None  # null when the LLM is a scripted oracle
    selection_status: Status
    timeouts: int | None = None


class BookingMetrics(_Strict):
    status: Status
    expected_outcome: str
    observed_outcome: str
    outcome_correct: bool
    expected_slot: str | None
    observed_slot: str | None
    calendar_create_calls: int
    expected_create_calls: int
    false_success_statements: int
    success_spoken: bool
    unknown_fail_closed: bool | None  # None when the scenario has no UNKNOWN path


class RuntimeMetrics(_Strict):
    status: Status
    startup_ms: float | None
    cpu_s: float | None
    max_rss_kib: int | None
    session_cleanup: bool | None
    crashed: bool
    errors: list[str]


class BenchmarkResult(_Strict):
    schema_version: Literal["voiceos.benchmark.result/1"] = "voiceos.benchmark.result/1"
    run_id: str
    timestamp: str  # UTC ISO 8601
    git_commit: str | None
    git_dirty: bool | None
    transport: Literal["offline"]
    runtime: str
    runtime_version: str | None
    stt_provider: str
    stt_model: str | None
    llm_provider: str
    llm_model: str | None
    tts_provider: str
    tts_model: str | None
    scenario_id: str
    status: Status
    success: bool | None  # all scenario oracles held; None when not run
    hard_failures: list[str]
    latency: LatencyMetrics | None
    tools: ToolMetrics | None
    booking: BookingMetrics | None
    entities: EntityMetrics
    conversation: ConversationMetrics
    runtime_metrics: RuntimeMetrics | None
    errors: list[str]
    cost: None = None  # no usage evidence exists; never estimated
    notes: list[str]


def write_result(directory: Path, result: BenchmarkResult) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.scenario_id}.json"
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


_SAFE_ATTRS = {"tool", "outcome", "reason", "error"}


def write_events(directory: Path, scenario_id: str, events: tuple[Event, ...]) -> Path:
    """Append-only JSONL. Only allowlisted, non-content attributes are written."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{scenario_id}.events.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for seq, event in enumerate(events):
            record = {
                "seq": seq,
                "scenario_id": scenario_id,
                "event": event.name,
                "t_ns": event.t_ns,
                "turn": event.turn,
                "attrs": {k: v for k, v in event.attrs.items() if k in _SAFE_ATTRS},
            }
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    return path
