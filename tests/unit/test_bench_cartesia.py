"""Cartesia TTS challenger adapter and gate: offline tests (fake SDK, no network, no key)."""

from __future__ import annotations

import array
import asyncio
import base64
import json
import math
import sys
import types
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

from voiceos.benchmark.dataset import load_tts_gate_cases
from voiceos.benchmark.ports import AdapterUnavailable, Probe, TTSAdapter
from voiceos.benchmark.providers import CartesiaTTS, TtsSynthesisResult
from voiceos.benchmark.tts_gate import (
    TtsGateStatus,
    check_audio,
    gate_status,
    run_tts_gate,
    write_manifest,
)

CANARY = "sk_car_canary_0123456789abcdef"
ENV = {
    "CARTESIA_API_KEY": CANARY,
    "VOICEOS_BENCH_TTS_CHALLENGER_MODEL": "model-x",
    "VOICEOS_BENCH_TTS_CHALLENGER_VOICE_ID": "voice-x",
    "VOICEOS_BENCH_TTS_CHALLENGER_LANGUAGE": "de",
}
TEXT = "Guten Tag, hier."


def tone(seconds: float, rate: int = 24_000) -> bytes:
    samples = (
        int(3000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(int(seconds * rate))
    )
    return array.array("h", samples).tobytes()


def test_contract_and_nothing_defaulted() -> None:
    tts = CartesiaTTS({})
    assert isinstance(tts, TTSAdapter)
    assert tts.info.model is None and tts.voice_id is None and tts.language is None
    missing = " ".join(tts.probe().missing)
    for expected in ("CARTESIA_API_KEY", "MODEL", "VOICE_ID", "LANGUAGE"):
        assert expected in missing
    assert "not authorized" in " ".join(CartesiaTTS(ENV).probe().missing)


def test_missing_key_blocks_before_any_network() -> None:
    env = {k: v for k, v in ENV.items() if k != "CARTESIA_API_KEY"}
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(CartesiaTTS(env, allow_live=True).synthesize(TEXT))
    assert any("CARTESIA_API_KEY" in m for m in exc.value.probe.missing)


def test_key_never_in_probe_info_or_repr() -> None:
    tts = CartesiaTTS(ENV, allow_live=True)
    assert CANARY not in repr(tts.probe()) + repr(tts.info) + repr(tts)


def ev(kind: str, **fields: Any) -> Any:
    return types.SimpleNamespace(type=kind, **fields)


def install_fake_sdk(monkeypatch: pytest.MonkeyPatch, outcome: list[Any] | Exception) -> list[Any]:
    seen: list[Any] = []

    class Tts:
        async def generate_sse(self, **kwargs: Any) -> AsyncIterator[Any]:
            seen.append(kwargs)
            if isinstance(outcome, Exception):
                raise outcome

            async def stream() -> AsyncIterator[Any]:
                for event in outcome:
                    yield event

            return stream()

    class FakeAsyncCartesia:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            seen.append({"api_key": api_key, "max_retries": max_retries})
            self.tts = Tts()

        async def close(self) -> None:
            return None

    module = types.ModuleType("cartesia")
    module.AsyncCartesia = FakeAsyncCartesia  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cartesia", module)
    return seen


class ProbedCartesia(CartesiaTTS):
    def probe(self) -> Probe:
        return Probe(True)


def timestamps(words: list[str], end: list[float]) -> Any:
    return types.SimpleNamespace(words=words, start=[0.0] * len(words), end=end)


def test_synthesize_collects_audio_and_word_timestamps(monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tone(0.6)
    events = [
        ev("chunk", data=base64.b64encode(audio[:10000]).decode()),
        ev("timestamps", word_timestamps=timestamps(["Guten", "Tag,"], [0.2, 0.35])),
        ev("chunk", data=base64.b64encode(audio[10000:]).decode()),
        ev("timestamps", word_timestamps=timestamps(["hier."], [0.55])),
        ev("done"),
    ]
    seen = install_fake_sdk(monkeypatch, events)
    result = asyncio.run(ProbedCartesia(ENV).synthesize(TEXT))
    assert result.ok and result.error is None and result.pcm == audio
    assert result.aligned_text == TEXT and result.last_char_end_s == pytest.approx(0.55)
    assert result.chunk_count == 2 and result.first_audio_ms is not None
    request = seen[1]
    assert request["model_id"] == "model-x" and request["voice"] == {"id": "voice-x"}
    assert request["output_format"] == {
        "container": "raw",
        "encoding": "pcm_s16le",
        "sample_rate": 24000,
    }
    assert request["language"] == "de" and request["add_timestamps"] is True
    assert seen[0]["max_retries"] == 0
    assert check_audio(result.pcm, 24_000, TEXT, result).valid


def test_stream_error_event_and_exceptions_are_recorded_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_sdk(
        monkeypatch, [ev("error", status_code=500, message=f"boom {CANARY}", done=True)]
    )
    result = asyncio.run(ProbedCartesia(ENV).synthesize(TEXT))
    assert result.error == "StreamErrorEvent:500" and not result.ok

    class AuthenticationError(Exception):
        status_code = 401

    install_fake_sdk(monkeypatch, AuthenticationError(f"bad key {CANARY}"))
    result = asyncio.run(ProbedCartesia(ENV).synthesize(TEXT))
    assert result.error == "AuthenticationError:401" and CANARY not in repr(result)


def test_quota_refusal_keeps_status_and_provider_code_but_no_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class APIStatusError(Exception):  # Cartesia SDK: the code lives only in the parsed body
        status_code = 402
        body: ClassVar[dict[str, str]] = {
            "error_code": "quota_exceeded",
            "title": "Model credits limit reached",
            "message": f"Please upgrade {CANARY}",
        }

    install_fake_sdk(monkeypatch, APIStatusError(f"402 {CANARY}"))
    result = asyncio.run(ProbedCartesia(ENV).synthesize(TEXT))
    assert not result.ok and result.error == "APIStatusError:402:quota_exceeded"
    assert CANARY not in repr(result) and "upgrade" not in repr(result)

    install_fake_sdk(
        monkeypatch,
        [ev("error", status_code=402, error_code="quota_exceeded", message=CANARY, done=True)],
    )
    result = asyncio.run(ProbedCartesia(ENV).synthesize(TEXT))
    assert result.error == "StreamErrorEvent:402:quota_exceeded" and CANARY not in repr(result)

    class Unsafe(Exception):  # a "code" that is free text is dropped, never copied
        status_code = 402
        body: ClassVar[dict[str, str]] = {"error_code": f"Quota! {CANARY}"}

    install_fake_sdk(monkeypatch, Unsafe())
    result = asyncio.run(ProbedCartesia(ENV).synthesize(TEXT))
    assert result.error == "Unsafe:402" and CANARY not in repr(result)


def test_missing_words_fail_the_truncation_check() -> None:
    pcm = tone(0.6)
    partial = TtsSynthesisResult(
        True, pcm, 24_000, 1, 1.0, 2.0, "Guten Tag,", 0.35, None, None, None
    )
    check = check_audio(pcm, 24_000, TEXT, partial)
    assert check.alignment_complete is False and check.valid is False


def test_challenger_status_vocabulary(tmp_path: Path) -> None:
    class Fake(ProbedCartesia):
        async def synthesize(self, text: str, *, timeout_s: float = 60.0) -> TtsSynthesisResult:
            return TtsSynthesisResult(
                True, tone(1.0), 24_000, 1, 1.0, 2.0, text, 0.9, None, None, None
            )

    cases = load_tts_gate_cases()[:2]
    result = asyncio.run(
        run_tts_gate(
            cases, Fake(ENV), tmp_path, voice_name="X", challenger=True,
            run_id="r", timestamp="t", git_commit=None, git_dirty=None,
        )
    )  # fmt: skip
    assert result.status is TtsGateStatus.CHALLENGER_VERIFIED
    assert result.output_format == "raw/pcm_s16le/24000" and result.provider == "cartesia"
    manifest = json.loads(write_manifest(tmp_path, result).read_text())
    assert manifest["sample_rate_hz"] == 24000 and manifest["test_case_ids"] == ["T01", "T02"]
    assert CANARY not in result.model_dump_json() + json.dumps(manifest)
    failed = result.cases[0].model_copy(
        update={"request_ok": False, "provider_error": "ReadTimeout"}
    )
    assert gate_status([failed], challenger=True) is TtsGateStatus.CHALLENGER_FAILED
    blocked = failed.model_copy(update={"provider_error": "AuthenticationError:401"})
    assert gate_status([blocked], challenger=True) is TtsGateStatus.NOT_TESTED
