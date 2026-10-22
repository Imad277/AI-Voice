"""Offline scenario runner and evidence vocabulary.

Only the ``offline`` transport class exists in Phase 0. ``sip_virtual`` and ``pstn_real``
require later human authorization (G0) and are intentionally not representable here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from voiceos.config import ConfigError, Settings
from voiceos.core.booking import BookingOutcome
from voiceos.core.context import CallContext
from voiceos.gateway.gateway import ToolGateway
from voiceos.mocks.voice import FakeLLM, FakeRuntime, FakeSTT, FakeTTS, LLMReply


class EvidenceStatus(StrEnum):
    NOT_TESTED = "NOT TESTED"
    PASS = "PASS"  # noqa: S105 - evidence status, not a password
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"


class TransportClass(StrEnum):
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class ScriptedTurn:
    transcript: str
    reply: LLMReply


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    transport: TransportClass
    outcome: BookingOutcome
    qualified: bool | None
    spoken: tuple[str, ...]


def run_offline_scenario(
    settings: Settings,
    gateway: ToolGateway,
    context: CallContext,
    turns: Sequence[ScriptedTurn],
) -> ScenarioResult:
    if settings.live_enabled or settings.recording_enabled:
        raise ConfigError("offline scenarios refuse live or recording configuration")

    audio = [f"turn-{i}".encode() for i in range(len(turns))]
    runtime = FakeRuntime(
        gateway=gateway,
        context=context,
        stt=FakeSTT({a: t.transcript for a, t in zip(audio, turns, strict=True)}),
        llm=FakeLLM([t.reply for t in turns]),
        tts=FakeTTS(),
    )
    for chunk in audio:
        runtime.handle_user_audio(chunk)
    gateway.end_call(context)

    return ScenarioResult(
        transport=TransportClass.OFFLINE,
        outcome=gateway.outcome(context),
        qualified=gateway.session(context).qualified,
        spoken=tuple(runtime.spoken),
    )
