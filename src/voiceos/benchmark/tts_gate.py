"""ElevenLabs TTS baseline gate (Phase 1).

Synthesizes 10 synthetic German texts through ``ElevenLabsTTS`` (HTTP streaming with
character timestamps) and validates every result technically: audio present, whole
16-bit samples, decodable as WAV, duration > 0, not silent, and not truncated (the
provider's character alignment covers the whole input text and ends within the audio).
No subjective quality score. Audio is written only to git-ignored evidence files.

Gate status: TTS_BASELINE_VERIFIED when every case returned a complete stream and valid,
untruncated audio. Account-level errors (invalid key, quota) make it NOT_TESTED.
"""

from __future__ import annotations

import array
import hashlib
import io
import json
import wave
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from voiceos.benchmark.dataset import TtsGateCase
from voiceos.benchmark.ports import AdapterInfo, Probe
from voiceos.benchmark.providers import TtsSynthesisResult
from voiceos.benchmark.stt_gate import HostAudit

ACCOUNT_LEVEL_ERRORS = (":401", "quota_exceeded", "invalid_api_key", "payment_required", ":402")
SILENCE_PEAK = 300  # max |sample| below this (of 32767) counts as silent
END_TOLERANCE_S = 0.25  # last aligned character may end this much after the audio


class TtsGateStatus(StrEnum):
    VERIFIED = "TTS_BASELINE_VERIFIED"
    FAILED = "TTS_BASELINE_FAILED"
    CHALLENGER_VERIFIED = "TTS_CHALLENGER_VERIFIED"
    CHALLENGER_FAILED = "TTS_CHALLENGER_FAILED"
    NOT_TESTED = "NOT_TESTED"


class TtsGateAdapter(Protocol):
    """What the gate needs from a TTS adapter (ElevenLabs baseline, Cartesia challenger)."""

    provider: str
    output_format: str
    sample_rate_hz: int

    @property
    def info(self) -> AdapterInfo: ...
    @property
    def voice_id(self) -> str | None: ...
    @property
    def language(self) -> str | None: ...
    def probe(self) -> Probe: ...
    async def synthesize(self, text: str, *, timeout_s: float = ...) -> TtsSynthesisResult: ...


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AudioCheck(_Strict):
    non_empty: bool
    whole_samples: bool
    decodable: bool
    duration_ms: float
    not_silent: bool
    alignment_complete: bool
    not_truncated: bool
    valid: bool


class TtsCaseResult(_Strict):
    case_id: str
    category: str
    characters: int
    request_ok: bool
    provider_error: str | None
    first_audio_ms: float | None
    total_ms: float | None
    chunk_count: int
    audio_bytes: int
    audio: AudioCheck
    character_cost: int | None
    request_id: str | None
    audio_sha256: str | None


class TtsGateResult(_Strict):
    schema_version: Literal["voiceos.benchmark.tts_gate/1"] = "voiceos.benchmark.tts_gate/1"
    run_id: str
    timestamp: str
    git_commit: str | None
    git_dirty: bool | None
    provider: str
    model_id: str | None
    voice_id: str | None
    voice_name: str | None
    language: str | None
    output_format: str
    sample_rate_hz: int
    sdk_version: str | None
    streaming: str
    status: TtsGateStatus
    cases: list[TtsCaseResult]
    network_hosts: list[str]
    network_peers: list[str]
    notes: list[str]


def check_audio(
    pcm: bytes, sample_rate_hz: int, text: str, result: TtsSynthesisResult
) -> AudioCheck:
    whole = len(pcm) % 2 == 0
    frames = 0
    decodable = False
    if pcm and whole:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate_hz)
            wav.writeframes(pcm)
        buffer.seek(0)
        with wave.open(buffer, "rb") as wav:
            frames = wav.getnframes()
            decodable = frames == len(pcm) // 2 and len(wav.readframes(frames)) == len(pcm)
    duration_s = frames / sample_rate_hz
    samples = array.array("h", pcm[: len(pcm) - len(pcm) % 2])
    peak = max((abs(s) for s in samples), default=0)
    aligned = result.aligned_text == text
    ends_inside = (
        result.last_char_end_s is not None
        and result.last_char_end_s <= duration_s + END_TOLERANCE_S
    )
    check = {
        "non_empty": bool(pcm),
        "whole_samples": whole,
        "decodable": decodable,
        "duration_ms": round(duration_s * 1000, 1),
        "not_silent": peak >= SILENCE_PEAK,
        "alignment_complete": aligned,
        "not_truncated": aligned and ends_inside,
    }
    check["valid"] = all(v for k, v in check.items() if k != "duration_ms") and duration_s > 0
    return AudioCheck(**check)


def write_wav(path: Path, pcm: bytes, sample_rate_hz: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(pcm)


def write_manifest(directory: Path, result: TtsGateResult) -> Path:
    """Listening-test manifest next to the WAV files: identifiers only, no secrets."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "voice_name": result.voice_name,
        "voice_id": result.voice_id,
        "model": result.model_id,
        "provider": result.provider,
        "output_format": result.output_format,
        "sample_rate_hz": result.sample_rate_hz,
        "status": result.status.value,
        "run_id": result.run_id,
        "test_case_ids": [c.case_id for c in result.cases],
        "files": [f"{c.case_id}.wav" for c in result.cases if c.audio_bytes],
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def gate_status(cases: Sequence[TtsCaseResult], *, challenger: bool = False) -> TtsGateStatus:
    if not cases:
        return TtsGateStatus.NOT_TESTED
    errors = [c.provider_error or "" for c in cases if not c.request_ok]
    if (
        errors
        and len(errors) == len(cases)
        and all(any(code in e for code in ACCOUNT_LEVEL_ERRORS) for e in errors)
    ):
        return TtsGateStatus.NOT_TESTED
    ok = all(c.request_ok and c.audio.valid for c in cases)
    if challenger:
        return TtsGateStatus.CHALLENGER_VERIFIED if ok else TtsGateStatus.CHALLENGER_FAILED
    return TtsGateStatus.VERIFIED if ok else TtsGateStatus.FAILED


async def run_tts_gate(
    cases: Sequence[TtsGateCase],
    tts: TtsGateAdapter,
    audio_dir: Path,
    *,
    voice_name: str | None,
    challenger: bool = False,
    run_id: str,
    timestamp: str,
    git_commit: str | None,
    git_dirty: bool | None,
    audit: HostAudit | None = None,
) -> TtsGateResult:
    header: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": timestamp,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "provider": tts.provider,
        "model_id": tts.info.model,
        "voice_id": tts.voice_id,
        "voice_name": voice_name,
        "language": tts.language,
        "output_format": tts.output_format,
        "sample_rate_hz": tts.sample_rate_hz,
        "sdk_version": tts.info.version,
        "streaming": "HTTP stream with character timestamps (stream_with_timestamps)",
    }
    probe = tts.probe()
    if not probe.available:
        return TtsGateResult(
            **header, status=TtsGateStatus.NOT_TESTED, cases=[], network_hosts=[],
            network_peers=[], notes=list(probe.missing),
        )  # fmt: skip

    results: list[TtsCaseResult] = []
    if audit is not None:
        audit.active = True
    try:
        for case in cases:
            synthesis = await tts.synthesize(case.text)
            sha = None
            if synthesis.pcm:
                write_wav(
                    audio_dir / f"{case.case_id}.wav", synthesis.pcm, synthesis.sample_rate_hz
                )
                sha = hashlib.sha256(synthesis.pcm).hexdigest()
            results.append(
                TtsCaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    characters=len(case.text),
                    request_ok=synthesis.ok,
                    provider_error=synthesis.error,
                    first_audio_ms=synthesis.first_audio_ms,
                    total_ms=synthesis.total_ms,
                    chunk_count=synthesis.chunk_count,
                    audio_bytes=len(synthesis.pcm),
                    audio=check_audio(
                        synthesis.pcm, synthesis.sample_rate_hz, case.text, synthesis
                    ),
                    character_cost=synthesis.character_cost,
                    request_id=synthesis.request_id,
                    audio_sha256=sha,
                )
            )
    finally:
        if audit is not None:
            audit.active = False

    return TtsGateResult(
        **header,
        status=gate_status(results, challenger=challenger),
        cases=results,
        network_hosts=sorted(audit.hosts) if audit is not None else [],
        network_peers=sorted(audit.peers) if audit is not None else [],
        notes=[
            "synthetic texts; technical validation only, no subjective quality score",
            "timings are TTS request timings, not voice-agent latency",
            "voice and model chosen by a fixed rule from the live listing, not by quality",
        ],
    )
