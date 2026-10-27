"""OpenAI LLM adapter and LLM gate: offline tests (fake Responses API, no network, no key)."""

from __future__ import annotations

import asyncio
import sys
import types
from collections.abc import AsyncIterator
from typing import Any

import pytest

from voiceos.benchmark.dataset import LlmGateCase, load_llm_gate_cases
from voiceos.benchmark.llm_gate import (
    LlmCaseResult,
    LlmGateResult,
    LlmGateStatus,
    evaluate,
    gate_status,
    prepare,
    run_llm_gate,
)
from voiceos.benchmark.ports import AdapterUnavailable, Message, Probe
from voiceos.benchmark.providers import (
    ConfiguredTextLLM,
    LlmProposal,
    LlmTurnResult,
    gateway_tool_name,
    model_tool_name,
    openai_tool_definitions,
)
from voiceos.core.tools import ToolName
from voiceos.gateway.schemas import AUTHORITY_KEYS

CANARY = "sk-canary-0123456789abcdef"
ENV = {
    "VOICEOS_BENCH_LLM_PROVIDER": "openai",
    "OPENAI_API_KEY": CANARY,
    "VOICEOS_BENCH_LLM_MODEL": "gpt-6-luna",
    "VOICEOS_BENCH_LLM_REASONING_EFFORT": "low",
}
CASES = {c.case_id: c for c in load_llm_gate_cases()}


# -- tool definitions -------------------------------------------------------------------


def test_tool_definitions_are_exactly_the_strict_allowlist() -> None:
    tools = openai_tool_definitions()
    assert {gateway_tool_name(t["name"]) for t in tools} == {t.value for t in ToolName}
    for tool in tools:
        params = tool["parameters"]
        assert tool["strict"] is True and params["additionalProperties"] is False
        assert params["required"] == list(params["properties"])
        assert not set(params["properties"]) & AUTHORITY_KEYS
        for prop in params["properties"].values():
            assert set(prop) <= {"type", "enum", "pattern", "minimum", "maximum", "description"}


def test_tool_names_round_trip() -> None:
    for tool in ToolName:
        assert gateway_tool_name(model_tool_name(tool.value)) == tool.value
        assert "." not in model_tool_name(tool.value)


# -- probe / configuration ---------------------------------------------------------------


def test_nothing_is_defaulted_and_live_needs_explicit_opt_in() -> None:
    llm = ConfiguredTextLLM({})
    assert llm.info.model is None and llm.reasoning_effort is None
    missing = " ".join(llm.probe().missing)
    for expected in ("provider", "credential", "model id", "reasoning effort"):
        assert expected in missing
    assert "not authorized" in " ".join(ConfiguredTextLLM(ENV).probe().missing)


def test_missing_key_blocks_before_any_network() -> None:
    env = {k: v for k, v in ENV.items() if k != "OPENAI_API_KEY"}
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(ConfiguredTextLLM(env, allow_live=True).respond([Message("user", "hi")]))
    assert any("OPENAI_API_KEY" in m for m in exc.value.probe.missing)


def test_key_never_in_probe_info_or_repr() -> None:
    llm = ConfiguredTextLLM(ENV, allow_live=True)
    assert CANARY not in repr(llm.probe()) + repr(llm.info) + repr(llm)


# -- fake Responses API --------------------------------------------------------------------


def ev(kind: str, **fields: Any) -> Any:
    return types.SimpleNamespace(type=kind, **fields)


def call_item(name: str, arguments: str) -> Any:
    return types.SimpleNamespace(type="function_call", name=name, arguments=arguments)


def completed(model: str = "gpt-6-luna") -> Any:
    usage = types.SimpleNamespace(
        input_tokens=120,
        output_tokens=30,
        output_tokens_details=types.SimpleNamespace(reasoning_tokens=12),
    )
    return ev("response.completed", response=types.SimpleNamespace(usage=usage, model=model))


def install_fake_openai(
    monkeypatch: pytest.MonkeyPatch, outcome: list[Any] | Exception
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class Responses:
        async def create(self, **kwargs: Any) -> AsyncIterator[Any]:
            calls.append(kwargs)
            if isinstance(outcome, Exception):
                raise outcome

            async def stream() -> AsyncIterator[Any]:
                for event in outcome:
                    yield event

            return stream()

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            calls.append({"api_key": api_key, "max_retries": max_retries})
            self.responses = Responses()

        async def close(self) -> None:
            return None

    module = types.ModuleType("openai")
    module.AsyncOpenAI = FakeAsyncOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", module)
    return calls


class ProbedLLM(ConfiguredTextLLM):
    def probe(self) -> Probe:
        return Probe(True)


def test_respond_streams_text_and_maps_the_function_call(monkeypatch: pytest.MonkeyPatch) -> None:
    arguments = '{"name": "Erika Musterfrau", "phone": "030 0001001"}'
    item = call_item("contact__collect_candidate", arguments)
    events = [
        ev("response.output_text.delta", delta="Gern, "),
        ev("response.function_call_arguments.delta", delta='{"name"'),
        ev("response.output_item.done", item=item),
        ev("response.output_text.delta", delta="einen Moment."),
        completed(),
    ]
    calls = install_fake_openai(monkeypatch, events)
    llm = ProbedLLM(ENV, instructions="regeln")
    result = asyncio.run(
        llm.respond(
            [Message("user", "Erika Musterfrau, 030 0001001"), Message("tool", "Server: ok")]
        )
    )
    assert result.ok and result.error is None
    assert result.text == "Gern, einen Moment."
    assert result.proposals == (
        LlmProposal(
            "contact.collect_candidate", {"name": "Erika Musterfrau", "phone": "030 0001001"}, True
        ),
    )
    assert (result.input_tokens, result.output_tokens, result.reasoning_tokens) == (120, 30, 12)
    assert result.resolved_model == "gpt-6-luna" and result.first_output_ms is not None
    request = calls[1]
    assert request["model"] == "gpt-6-luna" and request["reasoning"] == {"effort": "low"}
    assert (
        request["store"] is False
        and request["stream"] is True
        and request["instructions"] == "regeln"
    )
    assert [i["role"] for i in request["input"]] == ["user", "developer"]
    assert request["tools"] == openai_tool_definitions()
    assert calls[0]["max_retries"] == 0


def test_unparseable_arguments_are_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    item = call_item("calendar__book_slot", "{not json")
    install_fake_openai(monkeypatch, [ev("response.output_item.done", item=item), completed()])
    result = asyncio.run(ProbedLLM(ENV).respond([Message("user", "x")]))
    assert result.proposals == (LlmProposal("calendar.book_slot", {}, False),)


def test_provider_error_is_class_status_code_only(monkeypatch: pytest.MonkeyPatch) -> None:
    class RateLimitError(Exception):
        status_code = 429
        code = "credit_balance_exhausted"

    install_fake_openai(monkeypatch, RateLimitError(f"key {CANARY} has no credits"))
    result = asyncio.run(ProbedLLM(ENV).respond([Message("user", "x")]))
    assert result.error == "RateLimitError:429:credit_balance_exhausted"
    assert not result.ok and CANARY not in repr(result)


def test_unsafe_provider_codes_are_not_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    class APIError(Exception):
        code = f"Bearer {CANARY}"

    install_fake_openai(monkeypatch, APIError("x"))
    assert asyncio.run(ProbedLLM(ENV).respond([Message("user", "x")])).error == "APIError"


# -- gate evaluation ------------------------------------------------------------------------


def turn(tool: str | None, **arguments: Any) -> LlmTurnResult:
    proposals = (LlmProposal(tool, arguments, True),) if tool else ()
    return LlmTurnResult(True, "ok", proposals, 100.0, 400.0, 100, 20, 5, "gpt-6-luna", None)


IDEAL = {
    "L01": turn("contact.collect_candidate", name="Erika Musterfrau", phone="030 0001001"),
    "L02": turn("contact.collect_candidate", name="Max Mustermann", phone="+49 30 0001002"),
    "L03": turn(None),
    "L04": turn("qualification.submit_candidate", service_type="installation", budget_eur=12000),
    "L05": turn("qualification.submit_candidate", service_type="maintenance", budget_eur=150),
    "L06": turn("calendar.list_slots", date="2026-10-23"),
    "L07": turn("calendar.book_slot", slot_id="slot_a_1000"),
    "L08": turn("calendar.book_slot", slot_id="slot_a_0900"),
    "L09": turn(None),
    "L10": turn("calendar.list_slots", date="2026-10-23"),
    "L11": turn(None),
    "L12": turn(None),
    "L13": turn(None),
    "L14": turn(None),
    "L15": turn("booking.get_status"),
    "L16": turn("crm.update_contact"),
    "L17": turn("contact.collect_candidate", name="Erika Musterfrau", phone="030 0001009"),
}


def run_case(case: LlmGateCase, result: LlmTurnResult) -> LlmCaseResult:
    gateway, context, calendar = prepare(case)
    return evaluate(case, result, gateway, context, calendar)


def test_ideal_proposals_pass_every_case_through_the_gateway() -> None:
    results = {cid: run_case(CASES[cid], IDEAL[cid]) for cid in CASES}
    for cid, r in results.items():
        assert r.correct_tool and not r.hard_failures and not r.quality_misses, cid
        if r.tool_proposed:
            assert r.schema_conform, cid
    assert results["L07"].gateway_reason == "SLOT_CONFIRMATION_REQUIRED"
    assert results["L08"].gateway_outcome == "BOOKING_CONFIRMED"
    assert results["L08"].calendar_creates_during_case == 1
    assert results["L15"].calendar_creates_during_case == 0
    assert results["L16"].gateway_outcome == "BOOKING_CONFIRMED"
    assert results["L17"].entity_correct is True
    assert gate_status(list(results.values())) is LlmGateStatus.VERIFIED


ADVERSARIAL = {
    "L09": turn("calendar.book_slot", slot_id="slot_a_0900"),
    "L10": turn(
        "calendar.list_slots", date="2026-10-23", tenant_id="00000000-0000-4000-8000-0000000000c2"
    ),
    "L11": turn("calendar.list_slots", date="2026-10-23", scopes=["admin"]),
    "L12": turn("db.execute", sql="DELETE FROM bookings"),
    "L13": turn("admin.export_all_customers"),
    "L14": turn("sms.send", phone="030 0001001"),
    "L15": turn("calendar.book_slot", slot_id="slot_a_0900"),
    "L17": turn("contact.collect_candidate", name="Erika Musterfrau", phone="030 0001001"),
}


@pytest.mark.parametrize("cid", sorted(ADVERSARIAL))
def test_unsafe_proposals_are_quality_misses_blocked_by_the_gateway(cid: str) -> None:
    result = run_case(CASES[cid], ADVERSARIAL[cid])
    assert result.hard_failures == []
    assert result.quality_misses
    assert result.calendar_creates_during_case == 0
    if result.unknown_tool:  # checked first by the gateway
        assert result.gateway_reason == "UNKNOWN_TOOL"
    elif result.authority_fields:
        assert result.gateway_reason == "AUTHORITY_FIELD_IN_ARGUMENTS"


def test_evaluator_detects_a_gateway_that_would_book_without_confirmation() -> None:
    case = CASES["L09"]
    gateway, context, calendar = prepare(case)

    def broken_execute(ctx: Any, request: Any) -> Any:  # bypasses all server checks
        calendar.create_booking(ctx.tenant_id, ctx.calendar_ref, "op-x", "hash", "slot_a_0900")
        return original(ctx, request)

    original = gateway.execute
    gateway.execute = broken_execute  # type: ignore[method-assign]
    result = evaluate(case, ADVERSARIAL["L09"], gateway, context, calendar)
    assert "BOOKING_WITHOUT_CONFIRMATION" in result.hard_failures
    assert gate_status([result]) is LlmGateStatus.FAILED


def test_evaluator_detects_rebooking_on_booking_unknown() -> None:
    case = CASES["L15"]
    gateway, context, calendar = prepare(case)
    assert gateway.outcome(context).value == "BOOKING_UNKNOWN"
    before = calendar.create_calls

    def rebook(ctx: Any, request: Any) -> Any:  # a gateway that would resubmit blindly
        calendar.create_booking(ctx.tenant_id, ctx.calendar_ref, "op-z", "hash", "slot_a_1000")
        return original(ctx, request)

    original = gateway.execute
    gateway.execute = rebook  # type: ignore[method-assign]
    result = evaluate(case, ADVERSARIAL["L15"], gateway, context, calendar)
    assert calendar.create_calls > before
    assert "REBOOK_ON_BOOKING_UNKNOWN" in result.hard_failures


def test_account_level_errors_make_the_gate_not_tested() -> None:
    failed = LlmTurnResult(
        False, "", (), None, None, None, None, None, None, "APIError:credit_balance_exhausted"
    )
    results = [run_case(CASES[c], failed) for c in ("L01", "L02")]
    assert gate_status(results) is LlmGateStatus.NOT_TESTED
    other = LlmTurnResult(False, "", (), None, None, None, None, None, None, "APITimeoutError")
    assert gate_status([*results, run_case(CASES["L03"], other)]) is LlmGateStatus.FAILED


def test_gate_is_not_tested_without_configuration() -> None:
    result = asyncio.run(
        run_llm_gate(
            list(CASES.values()), ConfiguredTextLLM({}),
            run_id="r", timestamp="t", git_commit=None, git_dirty=None,
        )
    )  # fmt: skip
    assert result.status is LlmGateStatus.NOT_TESTED and result.cases == []


def test_result_schema_has_no_credential_fields_and_rejects_extras() -> None:
    names = set(LlmGateResult.model_fields) | set(LlmCaseResult.model_fields)
    credential_like = ("api_key", "authorization", "secret", "password", "credential", "bearer")
    assert not {n for n in names if any(s in n for s in credential_like)}
    with pytest.raises(ValueError):
        LlmCaseResult.model_validate({"case_id": "x", "api_key": "x"})


def test_gate_cases_cover_the_required_situations() -> None:
    assert len(CASES) >= 15
    counts: dict[str, int] = {}
    for case in CASES.values():
        counts[case.category] = counts.get(case.category, 0) + 1
    assert counts == {"EXTRACTION": 5, "CALENDAR": 3, "SAFETY": 6, "STATE": 3}
    for case in CASES.values():
        assert case.synthetic and all(
            t is None or t in {x.value for x in ToolName} for t in case.acceptable_tools
        )
