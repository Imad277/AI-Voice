"""Data plane contracts: session lifecycle, authority-free session spec, safe provider errors."""

from __future__ import annotations

import dataclasses

import pytest

from voiceos.gateway.schemas import contains_authority_key
from voiceos.runtime.contracts import (
    CallSessionSpec,
    CallSessionState,
    InvalidSessionTransition,
    RuntimeEvent,
    transition,
)
from voiceos.runtime.providers import ProviderError, ProviderFailure

CANARY = "sk-canary-0123456789abcdef"
S = CallSessionState


def test_session_lifecycle_allows_only_forward_transitions() -> None:
    assert transition(S.CREATED, S.ACTIVE) is S.ACTIVE
    assert transition(S.ACTIVE, S.ENDING) is S.ENDING
    assert transition(S.ENDING, S.ENDED) is S.ENDED
    assert transition(S.CREATED, S.ENDED) is S.ENDED  # failed before media started
    assert transition(S.ACTIVE, S.ENDED) is S.ENDED  # hangup / failure


@pytest.mark.parametrize(
    ("current", "target"),
    [(S.ENDED, S.ACTIVE), (S.ENDED, S.CREATED), (S.ENDED, S.ENDED), (S.ENDING, S.ACTIVE),
     (S.ACTIVE, S.CREATED), (S.CREATED, S.ENDING), (S.ACTIVE, S.ACTIVE)],
)  # fmt: skip
def test_session_lifecycle_rejects_everything_else(
    current: CallSessionState, target: CallSessionState
) -> None:
    with pytest.raises(InvalidSessionTransition):
        transition(current, target)


def test_session_spec_carries_no_authority() -> None:
    fields = {f.name: None for f in dataclasses.fields(CallSessionSpec)}
    assert not contains_authority_key(fields)
    assert not {"call_id", "tenant_id", "principal", "scopes", "calendar_ref"} & set(fields)
    spec = CallSessionSpec("agv_1", "de", 16_000, 24_000, 600.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.agent_version_id = "other"  # type: ignore[misc]


def test_runtime_event_is_immutable() -> None:
    event = RuntimeEvent("VAD_END", 1.0, turn=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.name = "OTHER"  # type: ignore[misc]


def test_provider_failure_keeps_only_safe_fields() -> None:
    failure = ProviderFailure("tts", "cartesia", "APIStatusError", 402, "quota_exceeded")
    assert str(failure) == "tts:cartesia:APIStatusError:402:quota_exceeded"
    error = ProviderError(failure)
    assert str(error) == str(failure) and error.failure is failure
    for bad in (
        {"provider": f"evil {CANARY}"},
        {"error_class": f"Bad {CANARY}"},
        {"provider_code": f"Quota! {CANARY}"},
        {"http_status": 42},
    ):
        values: dict[str, object] = {
            "component": "tts", "provider": "cartesia", "error_class": "APIStatusError",
        } | bad  # fmt: skip
        with pytest.raises(ValueError):
            ProviderFailure(**values)  # type: ignore[arg-type]
