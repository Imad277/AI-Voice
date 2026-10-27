"""ElevenLabs TTS adapter and TTS gate: offline tests (fake SDK, no network, no key)."""

from __future__ import annotations

import array
import asyncio
import base64
import math
import sys
import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from voiceos.benchmark.dataset import load_tts_gate_cases
from voiceos.benchmark.ports import AdapterUnavailable, Probe, TTSAdapter
from voiceos.benchmark.providers import ElevenLabsTTS, TtsSynthesisResult
from voiceos.benchmark.tts_gate import (
    TtsCaseResult,
    TtsGateResult,
    TtsGateStatus,
    check_audio,
    gate_status,
    run_tts_gate,
    write_manifest,
    write_wav,
)

CANARY = "el-canary-key-0123456789abcdef"
ENV = {
    "ELEVENLABS_API_KEY": CANARY,
    "VOICEOS_BENCH_TTS_MODEL": "model-x",
    "VOICEOS_BENCH_TTS_VOICE_ID": "voice-x",
    "VOICEOS_BENCH_TTS_LANGUAGE": "de",
}
TEXT = "Guten Tag."


def tone(seconds: float, rate: int = 24_000, amplitude: int = 3000) -> bytes:
    samples = array.array(
        "h",
        (
            int(amplitude * math.sin(2 * math.pi * 440 * i / rate))
            for i in range(int(seconds * rate))
        ),
    )
    return samples.tobytes()


# -- probe / contract -----------------------------------------------------------------------


def test_adapter_satisfies_the_tts_contract_and_defaults_nothing() -> None:
    tts = ElevenLabsTTS({})
    assert isinstance(tts, TTSAdapter)
    assert tts.info.model is None and tts.voice_id is None and tts.language is None
    missing = " ".join(tts.probe().missing)
    for expected in ("ELEVENLABS_API_KEY", "MODEL", "VOICE_ID", "LANGUAGE"):
        assert expected in missing
    assert "not authorized" in " ".join(ElevenLabsTTS(ENV).probe().missing)


def test_missing_key_blocks_before_any_network() -> None:
    env = {k: v for k, v in ENV.items() if k != "ELEVENLABS_API_KEY"}
    with pytest.raises(AdapterUnavailable) as exc:
        asyncio.run(ElevenLabsTTS(env, allow_live=True).synthesize(TEXT))
    assert any("ELEVENLABS_API_KEY" in m for m in exc.value.probe.missing)


def test_key_never_in_probe_info_or_repr() -> None:
    tts = ElevenLabsTTS(ENV, allow_live=True)
    assert CANARY not in repr(tts.probe()) + repr(tts.info) + repr(tts)


# -- fake ElevenLabs API --------------------------------------------------------------------


def chunk(audio: bytes, chars: str = "", start: float = 0.0, end: float = 0.0) -> Any:
    alignment = None
    if chars:
        n = len(chars)
        alignment = types.SimpleNamespace(
            characters=list(chars),
            character_start_times_seconds=[start + (end - start) * i / n for i in range(n)],
            character_end_times_seconds=[start + (end - start) * (i + 1) / n for i in range(n)],
        )
    encoded = base64.b64encode(audio).decode() if audio else None
    return types.SimpleNamespace(audio_base_64=encoded, alignment=alignment)


def install_fake_sdk(
    monkeypatch: pytest.MonkeyPatch,
    outcome: list[Any] | Exception,
    headers: dict[str, str] | None = None,
) -> list[Any]:
    seen: list[Any] = []

    class Raw:
        @asynccontextmanager
        async def stream_with_timestamps(self, voice_id: str, **kwargs: Any) -> AsyncIterator[Any]:
            seen.append((voice_id, kwargs))
            if isinstance(outcome, Exception):
                raise outcome

            async def data() -> AsyncIterator[Any]:
                for item in outcome:
                    yield item

            yield types.SimpleNamespace(headers=headers or {}, data=data())

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            seen.append(api_key)
            self.text_to_speech = types.SimpleNamespace(with_raw_response=Raw())

    module = types.ModuleType("elevenlabs")
    module.AsyncElevenLabs = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "elevenlabs", module)
    return seen


class ProbedTTS(ElevenLabsTTS):
    def probe(self) -> Probe:
        return Probe(True)


def test_synthesize_collects_audio_alignment_and_safe_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = tone(0.6)
    headers = {"character-cost": "5", "request-id": "req-1", "authorization": f"Bearer {CANARY}"}
    seen = install_fake_sdk(
        monkeypatch,
        [chunk(audio[:12000], "Guten", 0.0, 0.25), chunk(audio[12000:], " Tag.", 0.25, 0.55)],
        headers,
    )
    result = asyncio.run(ProbedTTS(ENV).synthesize(TEXT))
    assert result.ok and result.error is None
    assert result.pcm == audio and result.chunk_count == 2
    assert result.aligned_text == TEXT and result.last_char_end_s == pytest.approx(0.55)
    assert (result.character_cost, result.request_id) == (5, "req-1")
    assert result.first_audio_ms is not None and result.total_ms is not None
    voice_id, kwargs = seen[1]
    assert voice_id == "voice-x"
    assert kwargs == {
        "text": TEXT,
        "model_id": "model-x",
        "language_code": "de",
        "output_format": "pcm_24000",
    }
    assert CANARY not in repr(result)


def test_provider_error_is_class_status_code_only(monkeypatch: pytest.MonkeyPatch) -> None:
    class ApiError(Exception):
        status_code = 401
        code = "invalid_api_key"

    install_fake_sdk(monkeypatch, ApiError(f"invalid key {CANARY}"))
    result = asyncio.run(ProbedTTS(ENV).synthesize(TEXT))
    assert result.error == "ApiError:401:invalid_api_key"
    assert not result.ok and result.pcm == b"" and CANARY not in repr(result)


# -- audio validation -------------------------------------------------------------------------


def synthesis(pcm: bytes, aligned: str, end: float | None) -> TtsSynthesisResult:
    return TtsSynthesisResult(True, pcm, 24_000, 1, 1.0, 2.0, aligned, end, None, None, None)


def test_valid_audio_passes_every_check() -> None:
    pcm = tone(0.6)
    check = check_audio(pcm, 24_000, TEXT, synthesis(pcm, TEXT, 0.55))
    assert check.valid and check.duration_ms == 600.0


@pytest.mark.parametrize(
    ("pcm", "aligned", "end", "failed"),
    [
        (b"", "Guten Tag.", 0.5, "non_empty"),
        (tone(0.6) + b"\x01", "Guten Tag.", 0.5, "whole_samples"),
        (b"\x00\x00" * 14_400, "Guten Tag.", 0.5, "not_silent"),
        (tone(0.6), "Guten", 0.3, "alignment_complete"),  # provider stopped mid-text
        (tone(0.2), "Guten Tag.", 0.9, "not_truncated"),  # audio ends before the speech
    ],
)
def test_broken_audio_is_detected(pcm: bytes, aligned: str, end: float, failed: str) -> None:
    check = check_audio(pcm, 24_000, TEXT, synthesis(pcm, aligned, end))
    assert getattr(check, failed) is False and check.valid is False


def test_wav_evidence_contains_no_metadata_or_secret(tmp_path: Path) -> None:
    path = tmp_path / "x.wav"
    write_wav(path, tone(0.1), 24_000)
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and b"LIST" not in data and CANARY.encode() not in data


# -- gate ---------------------------------------------------------------------------------------


def case_result(ok: bool, valid: bool, error: str | None = None) -> TtsCaseResult:
    pcm = tone(0.6) if valid else b""
    check = check_audio(pcm, 24_000, TEXT, synthesis(pcm, TEXT, 0.55))
    return TtsCaseResult(
        case_id="T01", category="GREETING", characters=10, request_ok=ok, provider_error=error,
        first_audio_ms=None, total_ms=None, chunk_count=0, audio_bytes=len(pcm), audio=check,
        character_cost=None, request_id=None, audio_sha256=None,
    )  # fmt: skip


def test_gate_status_rules() -> None:
    assert gate_status([case_result(True, True)]) is TtsGateStatus.VERIFIED
    assert gate_status([case_result(True, False)]) is TtsGateStatus.FAILED
    assert gate_status([case_result(False, False, "ApiError:401")]) is TtsGateStatus.NOT_TESTED
    assert gate_status([case_result(False, False, "ReadTimeout")]) is TtsGateStatus.FAILED
    assert gate_status([]) is TtsGateStatus.NOT_TESTED


def test_gate_is_not_tested_without_configuration(tmp_path: Path) -> None:
    result = asyncio.run(
        run_tts_gate(
            load_tts_gate_cases(), ElevenLabsTTS({}), tmp_path, voice_name=None,
            run_id="r", timestamp="t", git_commit=None, git_dirty=None,
        )
    )  # fmt: skip
    assert result.status is TtsGateStatus.NOT_TESTED and result.cases == []
    assert not list(tmp_path.iterdir())


def test_gate_runs_end_to_end_against_the_fake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = load_tts_gate_cases()[:2]

    class PerCaseTTS(ProbedTTS):
        async def synthesize(self, text: str, *, timeout_s: float = 60.0) -> TtsSynthesisResult:
            return synthesis(tone(1.0), text, 0.9)

    result = asyncio.run(
        run_tts_gate(
            cases, PerCaseTTS(ENV), tmp_path, voice_name="X",
            run_id="r", timestamp="t", git_commit=None, git_dirty=None,
        )
    )  # fmt: skip
    assert result.status is TtsGateStatus.VERIFIED and len(result.cases) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["T01.wav", "T02.wav"]
    assert CANARY not in result.model_dump_json()


def test_result_schema_has_no_credential_fields_and_rejects_extras() -> None:
    names = set(TtsGateResult.model_fields) | set(TtsCaseResult.model_fields)
    credential_like = ("api_key", "authorization", "secret", "password", "credential", "bearer")
    assert not {n for n in names if any(s in n for s in credential_like)}
    with pytest.raises(ValueError):
        TtsCaseResult.model_validate({"case_id": "x", "api_key": "x"})


def test_gate_cases_cover_the_required_texts() -> None:
    cases = load_tts_gate_cases()
    assert len(cases) >= 10
    assert {c.category for c in cases} == {
        "GREETING", "PERSON", "PHONE", "EMAIL", "ADDRESS", "DATE", "TIME", "MONEY", "CONFIRMATION",
    }  # fmt: skip
    assert all(c.synthetic for c in cases)


def test_listening_manifest_has_identifiers_only(tmp_path: Path) -> None:
    import json

    result = TtsGateResult(
        run_id="r", timestamp="t", git_commit=None, git_dirty=None, provider="elevenlabs",
        model_id="model-x", voice_id="voice-x", voice_name="Name", language="de",
        output_format="pcm_24000", sample_rate_hz=24_000, sdk_version="2.71.0", streaming="s",
        status=TtsGateStatus.VERIFIED, cases=[case_result(True, True)], network_hosts=[],
        network_peers=[], notes=[],
    )  # fmt: skip
    manifest = json.loads(write_manifest(tmp_path / "voice-x", result).read_text())
    assert manifest["voice_id"] == "voice-x" and manifest["model"] == "model-x"
    assert manifest["test_case_ids"] == ["T01"] and manifest["files"] == ["T01.wav"]
    assert CANARY not in json.dumps(manifest)
