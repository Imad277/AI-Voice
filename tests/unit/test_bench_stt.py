"""Deepgram STT adapter and STT gate: offline tests (fake SDK, no network, no key)."""

from __future__ import annotations

import asyncio
import dataclasses
import sys
import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from voiceos.benchmark.dataset import Entities, load_stt_gate_cases
from voiceos.benchmark.metrics import last_number, score_entities
from voiceos.benchmark.ports import AdapterUnavailable, AudioSegment, Probe
from voiceos.benchmark.providers import DeepgramSTT, SttStreamResult
from voiceos.benchmark.stt_gate import (
    SttGateResult,
    SttGateStatus,
    _evaluate,
    normalize,
    run_stt_gate,
)

CANARY = "dg-canary-key-0123456789"
ENV = {
    "DEEPGRAM_API_KEY": CANARY,
    "VOICEOS_BENCH_STT_MODEL": "nova-3",
    "VOICEOS_BENCH_STT_LANGUAGE": "de",
}


# -- probe / configuration ---------------------------------------------------------------


def test_nothing_is_defaulted_and_live_needs_explicit_opt_in() -> None:
    adapter = DeepgramSTT({})
    assert adapter.info.model is None and adapter.language is None
    missing = " ".join(adapter.probe().missing)
    for expected in ("DEEPGRAM_API_KEY", "VOICEOS_BENCH_STT_MODEL", "VOICEOS_BENCH_STT_LANGUAGE"):
        assert expected in missing
    assert "not authorized" in " ".join(DeepgramSTT(ENV).probe().missing)


def test_missing_credential_blocks_before_any_network() -> None:
    adapter = DeepgramSTT(
        {k: v for k, v in ENV.items() if k != "DEEPGRAM_API_KEY"}, allow_live=True
    )
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(adapter.stream(AudioSegment("x", b"\0\0", 16_000)))
    assert any("DEEPGRAM_API_KEY" in m for m in exc.value.probe.missing)


def test_key_never_appears_in_probe_or_info() -> None:
    adapter = DeepgramSTT(ENV, allow_live=True)
    assert CANARY not in repr(adapter.probe()) + repr(adapter.info) + repr(adapter)


# -- streaming against a fake SDK ----------------------------------------------------------


def _results(text: str, final: bool) -> Any:
    alt = types.SimpleNamespace(transcript=text)
    return types.SimpleNamespace(
        type="Results", is_final=final, channel=types.SimpleNamespace(alternatives=[alt])
    )


class FakeSocket:
    def __init__(self, messages: list[Any]) -> None:
        self.messages = messages
        self.sent: list[bytes] = []
        self.closed = asyncio.Event()

    async def send_media(self, chunk: bytes) -> None:
        self.sent.append(chunk)

    async def send_close_stream(self) -> None:
        self.closed.set()

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[Any]:
        for message in self.messages:
            yield message
        await self.closed.wait()


def install_fake_sdk(monkeypatch: pytest.MonkeyPatch, socket: FakeSocket | Exception) -> list[Any]:
    seen: list[Any] = []

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            seen.append(api_key)
            listen = types.SimpleNamespace(v1=types.SimpleNamespace(connect=self.connect))
            self.listen = listen

        @asynccontextmanager
        async def connect(self, **options: Any) -> AsyncIterator[FakeSocket]:
            seen.append(options)
            if isinstance(socket, Exception):
                raise socket
            yield socket

    module = types.ModuleType("deepgram")
    module.AsyncDeepgramClient = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", module)
    return seen


class ProbedDeepgram(DeepgramSTT):
    def probe(self) -> Probe:  # SDK presence is irrelevant for the fake
        return Probe(True)


def test_stream_collects_interim_and_final_results(monkeypatch: pytest.MonkeyPatch) -> None:
    meta = types.SimpleNamespace(type="Metadata", request_id="req-1")
    socket = FakeSocket(
        [
            _results("Mein", False),
            _results("Mein Name", False),
            _results("Mein Name ist Erika.", True),
            meta,
        ]
    )
    seen = install_fake_sdk(monkeypatch, socket)
    pcm = b"\x01\x00" * 16_000  # one second
    result = asyncio.run(ProbedDeepgram(ENV).stream(AudioSegment("x", pcm, 16_000), realtime=False))

    assert result.connected and result.error is None
    assert result.final_transcript == "Mein Name ist Erika."
    assert (result.interim_count, result.final_count, result.request_id) == (2, 1, "req-1")
    assert b"".join(socket.sent) == pcm and len(socket.sent) == 50  # 20 ms chunks
    options = seen[1]
    assert options["model"] == "nova-3" and options["language"] == "de"
    assert options["encoding"] == "linear16" and options["sample_rate"] == "16000"
    kinds = [e.kind for e in result.events]
    assert kinds[0] == "open" and kinds[-1] == "close" and "final" in kinds
    assert result.events[0].t_ms <= 0 <= result.events[-1].t_ms  # relative to first audio


def test_provider_error_is_recorded_by_class_and_status_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InvalidStatus(Exception):
        def __init__(self) -> None:
            super().__init__(f"server rejected: Authorization: Token {CANARY}")
            self.response = types.SimpleNamespace(status_code=401)

    install_fake_sdk(monkeypatch, InvalidStatus())
    result = asyncio.run(ProbedDeepgram(ENV).stream(AudioSegment("x", b"\0\0", 16_000)))
    assert result.error == "InvalidStatus:401"
    assert result.connected is False and result.final_transcript == ""
    assert CANARY not in repr(result)


# -- evaluation ------------------------------------------------------------------------------


def _stream(text: str) -> SttStreamResult:
    return SttStreamResult(True, text, 1, 1, (), 1.0, 2.0, 3.0, 3.0, 4.0, 5.0, None, None)


def test_entity_only_cases_never_claim_a_transcript_match() -> None:
    case = next(c for c in load_stt_gate_cases() if c.case_id == "G02")
    result = _evaluate(case, "sha", 1.0, _stream("Meine Telefonnummer ist 030 0001001."))
    assert result.normalized_match is None and result.wer_words is None
    assert result.entities == {"phone": True}


def test_exact_cases_report_match_and_wer() -> None:
    case = next(c for c in load_stt_gate_cases() if c.case_id == "G10")
    good = _evaluate(case, "sha", 1.0, _stream(case.reference.upper()))
    assert good.normalized_match is True and (good.wer_errors, good.wer_words) == (0, 9)
    bad = _evaluate(case, "sha", 1.0, _stream(""))
    assert bad.empty_transcript and not bad.final_present and bad.normalized_match is False


def test_correction_requires_the_corrected_value_last() -> None:
    case = next(c for c in load_stt_gate_cases() if c.case_id == "G09")
    assert _evaluate(case, "s", 1.0, _stream("Hausnummer 15, nein, 17.")).correction_final_ok
    assert not _evaluate(case, "s", 1.0, _stream("Hausnummer 17, nein, 15.")).correction_final_ok


def test_gate_is_not_tested_without_configuration(tmp_path: Path) -> None:
    result, events = asyncio.run(
        run_stt_gate(
            load_stt_gate_cases(), DeepgramSTT({}), tmp_path,
            run_id="r", timestamp="t", git_commit=None, git_dirty=None,
        )
    )  # fmt: skip
    assert result.status is SttGateStatus.NOT_TESTED and result.cases == [] and events == {}
    assert not list(tmp_path.iterdir())  # no audio rendered, nothing sent


def test_gate_result_schema_has_no_credential_fields() -> None:
    names = set(SttGateResult.model_fields)
    assert not {n for n in names if any(s in n for s in ("key", "token", "auth", "secret"))}
    assert {"provider", "model", "language", "status", "cases", "network_hosts"} <= names


def test_gate_cases_cover_required_categories() -> None:
    cases = load_stt_gate_cases()
    assert len(cases) >= 10
    assert {c.category for c in cases} == {
        "PERSON", "PHONE", "EMAIL", "ADDRESS", "DATETIME", "MONEY", "CORRECTION", "SENTENCE",
    }  # fmt: skip
    fields = {f for c in cases for f, v in c.expected.model_dump().items() if v is not None}
    assert {"first_name", "last_name", "phone", "email", "street", "house_number",
            "postal_code", "city", "date", "time", "amount_minor"} <= fields  # fmt: skip


# -- normalization ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hypothesis", "ok"),
    [("am 23.10.2026", True), ("am 23. Oktober 2026", True), ("am 23 Oktober", True),
     ("am 24. Oktober", False), ("am dreiundzwanzigsten Oktober", False)],
)  # fmt: skip
def test_date_normalization(hypothesis: str, ok: bool) -> None:
    assert score_entities(Entities(date="2026-10-23"), hypothesis) == {"date": ok}


@pytest.mark.parametrize(
    ("hypothesis", "ok"),
    [("um 14:30", True), ("14.30 Uhr", True), ("14 Uhr 30", True), ("14 Uhr", False)],
)
def test_time_normalization(hypothesis: str, ok: bool) -> None:
    assert score_entities(Entities(time="14:30"), hypothesis) == {"time": ok}


def test_postal_code_digits_and_house_number_boundaries() -> None:
    assert score_entities(Entities(postal_code="10115"), "PLZ 1 0 1 1 5") == {"postal_code": True}
    assert score_entities(Entities(house_number="12"), "Hausnummer 112") == {"house_number": False}
    assert last_number("15, nein, 17.") == "17" and last_number("keine Zahl") is None


def test_normalize_keeps_digits_and_drops_sentence_punctuation() -> None:
    assert normalize("Ich möchte, bitte!") == "ich möchte bitte"
    assert normalize("Um 14:30 Uhr.") == "um 14:30 uhr"


def test_stream_result_has_no_credential_fields() -> None:
    assert not {f.name for f in dataclasses.fields(SttStreamResult)} & {
        "api_key",
        "token",
        "headers",
    }
