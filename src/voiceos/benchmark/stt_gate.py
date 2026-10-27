"""Deepgram STT baseline gate (Phase 1).

Streams locally synthesized German test speech through ``DeepgramSTT`` and records, per
case: connection, first transcript event, interim/final counts, final transcript,
close, provider error and timings. Evaluation: normalized transcript match (only where
formatting is unambiguous), critical entities, final present/empty, error state.

Gate status: STT_BASELINE_VERIFIED when every case connected, produced a non-empty final
transcript and closed without provider error. Accuracy is reported, not gated.
Transcripts in the result files come from synthetic speech of synthetic data only.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from voiceos.benchmark.dataset import SttGateCase
from voiceos.benchmark.metrics import last_number, score_entities, word_error_rate
from voiceos.benchmark.ports import AudioSegment
from voiceos.benchmark.providers import DeepgramSTT, SttStreamEvent
from voiceos.benchmark.synthetic_audio import SAMPLE_RATE_HZ, read_pcm, render


class SttGateStatus(StrEnum):
    VERIFIED = "STT_BASELINE_VERIFIED"
    FAILED = "STT_BASELINE_FAILED"
    NOT_TESTED = "NOT_TESTED"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SttCaseResult(_Strict):
    case_id: str
    category: str
    audio_sha256: str
    audio_ms: float
    connected: bool
    final_transcript: str  # synthetic speech of synthetic data only
    final_present: bool
    empty_transcript: bool
    interim_count: int
    final_count: int
    connect_ms: float | None
    first_transcript_ms: float | None
    last_final_ms: float | None
    audio_sent_ms: float | None
    close_ms: float | None
    wall_ms: float | None
    request_id: str | None
    error: str | None
    match_policy: str
    normalized_match: bool | None  # None when formatting is ambiguous (entity_only)
    wer_errors: int | None
    wer_words: int | None
    entities: dict[str, bool]
    correction_final_ok: bool | None


class SttGateResult(_Strict):
    schema_version: Literal["voiceos.benchmark.stt_gate/1"] = "voiceos.benchmark.stt_gate/1"
    run_id: str
    timestamp: str
    git_commit: str | None
    git_dirty: bool | None
    provider: str
    model: str | None
    language: str | None
    sdk_version: str | None
    audio_source: str
    streaming: str  # how audio was sent
    status: SttGateStatus
    cases: list[SttCaseResult]
    network_hosts: list[str]  # hostnames resolved by this process during the gate
    network_peers: list[str]  # ip:port of every socket connect during the gate
    notes: list[str]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s@.:+-]|(?<!\d)[.:](?!\d)|[.:]$", " ", text)
    return " ".join(text.split())


class HostAudit:
    """Records hostnames resolved and socket peers connected by this process (audit hooks)."""

    def __init__(self) -> None:
        self.hosts: set[str] = set()
        self.peers: set[str] = set()
        self.active = False
        sys.addaudithook(self._hook)

    def _hook(self, event: str, args: tuple[object, ...]) -> None:
        if not self.active:
            return
        if event == "socket.getaddrinfo" and args and isinstance(args[0], str | bytes):
            host = args[0]
            self.hosts.add(host.decode("idna") if isinstance(host, bytes) else host)
        elif event == "socket.connect" and len(args) > 1 and isinstance(args[1], tuple):
            self.peers.add(f"{args[1][0]}:{args[1][1]}")


async def run_stt_gate(
    cases: Sequence[SttGateCase],
    stt: DeepgramSTT,
    audio_dir: Path,
    *,
    run_id: str,
    timestamp: str,
    git_commit: str | None,
    git_dirty: bool | None,
    audit: HostAudit | None = None,
) -> tuple[SttGateResult, dict[str, tuple[SttStreamEvent, ...]]]:
    from voiceos.benchmark.synthetic_audio import source_description

    header = {
        "run_id": run_id,
        "timestamp": timestamp,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "provider": stt.info.provider,
        "model": stt.info.model,
        "language": stt.language,
        "sdk_version": stt.info.version,
        "audio_source": source_description(),
        "streaming": "linear16 16 kHz mono, 20 ms chunks paced in real time, interim results on",
    }
    probe = stt.probe()
    if not probe.available:
        result = SttGateResult(
            **header, status=SttGateStatus.NOT_TESTED, cases=[], network_hosts=[],
            network_peers=[], notes=list(probe.missing),
        )  # fmt: skip
        return result, {}

    results: list[SttCaseResult] = []
    events: dict[str, tuple[SttStreamEvent, ...]] = {}
    if audit is not None:
        audit.active = True
    try:
        for case in cases:
            wav = audio_dir / f"{case.case_id}.wav"
            sha = render(case.speak, wav)
            pcm = read_pcm(wav)
            stream = await stt.stream(AudioSegment(case.case_id, pcm, SAMPLE_RATE_HZ))
            events[case.case_id] = stream.events
            results.append(_evaluate(case, sha, len(pcm) / (SAMPLE_RATE_HZ * 2) * 1000, stream))
    finally:
        if audit is not None:
            audit.active = False

    ok = all(r.connected and r.final_present and r.error is None for r in results)
    status = SttGateStatus.VERIFIED if ok and results else SttGateStatus.FAILED
    return (
        SttGateResult(
            **header,
            status=status,
            cases=results,
            network_hosts=sorted(audit.hosts) if audit is not None else [],
            network_peers=sorted(audit.peers) if audit is not None else [],
            notes=[
                "synthetic speech (local macOS voice), not real callers: functional baseline",
                "latencies are STT stream timings, not voice-agent latency",
                "accuracy is reported, not gated; entity policies in BENCHMARK_METHOD.md",
            ],
        ),
        events,
    )


def _evaluate(case: SttGateCase, sha: str, audio_ms: float, stream: object) -> SttCaseResult:
    from voiceos.benchmark.providers import SttStreamResult

    assert isinstance(stream, SttStreamResult)  # noqa: S101 - internal invariant
    text = stream.final_transcript
    exact = case.match_policy == "exact_normalized"
    errors, words = word_error_rate(case.reference, text) if exact else (None, None)
    correction = None
    if case.correction_final is not None:
        correction = last_number(text) == case.correction_final
    return SttCaseResult(
        case_id=case.case_id,
        category=case.category,
        audio_sha256=sha,
        audio_ms=round(audio_ms, 1),
        connected=stream.connected,
        final_transcript=text,
        final_present=bool(text),
        empty_transcript=not text,
        interim_count=stream.interim_count,
        final_count=stream.final_count,
        connect_ms=stream.connect_ms,
        first_transcript_ms=stream.first_transcript_ms,
        last_final_ms=stream.last_final_ms,
        audio_sent_ms=stream.audio_sent_ms,
        close_ms=stream.close_ms,
        wall_ms=stream.wall_ms,
        request_id=stream.request_id,
        error=stream.error,
        match_policy=case.match_policy,
        normalized_match=normalize(case.reference) == normalize(text) if exact else None,
        wer_errors=errors,
        wer_words=words,
        entities=score_entities(case.expected, text),
        correction_final_ok=correction,
    )
