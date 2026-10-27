"""Phase 1 benchmark CLI (offline only).

    uv run python -m voiceos.benchmark.cli --runtime reference
    uv run python -m voiceos.benchmark.cli --runtime livekit   # reports NOT TESTED + reasons
    uv run python -m voiceos.benchmark.cli --sdk-status        # local SDK check, no network
    uv run --env-file .env python -m voiceos.benchmark.cli --local-session-gate
                                    # join/leave both runtimes on the local LiveKit dev server
    uv run --env-file .env python -m voiceos.benchmark.cli --stt-gate \\
        --stt-model nova-3 --stt-language de         # live Deepgram STT baseline gate
    uv run --env-file .env python -m voiceos.benchmark.cli --llm-gate \\
        --llm-model gpt-6-luna --llm-reasoning low   # live OpenAI text LLM baseline gate
    uv run --env-file .env python -m voiceos.benchmark.cli --tts-gate \\
        --tts-model eleven_flash_v2_5 --tts-voice-id CwhRBWXzGAHq8TQ4Fs17 \\
        --tts-voice-name Roger --tts-language de     # live ElevenLabs TTS baseline gate
    uv run --env-file .env python -m voiceos.benchmark.cli --tts-gate --tts-provider cartesia \\
        --tts-model sonic-3.5-2026-05-04 --tts-voice-id <id> --tts-language de
                                                     # live Cartesia TTS challenger gate
    uv run --env-file .env python -m voiceos.benchmark.cli --e2e-gate [--e2e-runtime pipecat] \
        --stt-model nova-3 --stt-language de --llm-model gpt-6-luna --llm-reasoning low \
        --tts-model sonic-3.5-2026-05-04 --tts-voice-id <id> --tts-language de
                                    # end-to-end voice pipeline gate (local server)

Writes one JSON result and one JSONL event log per scenario plus a summary to
``benchmarks/results/<run_id>/<runtime>/`` (git-ignored). Exit codes: 0 all scenarios ran
and held their oracles, 1 a scenario failed or hit a hard failure, 2 not runnable.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import datetime as dt
import json
import os
import subprocess  # fixed git commands for result provenance only
import sys
from pathlib import Path
from typing import Literal

from voiceos.benchmark.dataset import (
    load_dialogues,
    load_llm_gate_cases,
    load_stt_gate_cases,
    load_tts_gate_cases,
)
from voiceos.benchmark.e2e_gate import E2EStatus, run_e2e_gate
from voiceos.benchmark.livekit_local import (
    LocalServer,
    LocalSessionReport,
    LocalSessionStatus,
    run_local_session_gate,
)
from voiceos.benchmark.llm_gate import INSTRUCTIONS, LlmGateStatus, run_llm_gate
from voiceos.benchmark.ports import RuntimeAdapter
from voiceos.benchmark.providers import CartesiaTTS, ConfiguredTextLLM, DeepgramSTT, ElevenLabsTTS
from voiceos.benchmark.results import Status, write_events, write_result
from voiceos.benchmark.runner import RunInfo, run_dialogue
from voiceos.benchmark.runtimes import (
    LiveKitRuntimeAdapter,
    PipecatRuntimeAdapter,
    ReferenceRuntime,
)
from voiceos.benchmark.stt_gate import HostAudit, SttGateStatus, run_stt_gate
from voiceos.benchmark.tts_gate import TtsGateStatus, run_tts_gate, write_manifest
from voiceos.config import load_settings

RUNTIMES: dict[str, type[RuntimeAdapter]] = {
    "reference": ReferenceRuntime,
    "livekit": LiveKitRuntimeAdapter,
    "pipecat": PipecatRuntimeAdapter,
}
RESULTS_DIR = Path("benchmarks/results")
AUDIO_DIR = Path("benchmarks/audio/stt_gate")  # locally synthesized, git-ignored
TTS_AUDIO_DIR = Path("benchmarks/audio/tts_gate")  # provider audio evidence, git-ignored


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="voiceos-bench")
    parser.add_argument("--runtime", choices=sorted(RUNTIMES))
    parser.add_argument("--sdk-status", action="store_true", help="print local SDK status")
    parser.add_argument(
        "--local-session-gate",
        action="store_true",
        help="join/leave both runtime candidates on the loopback LiveKit dev server",
    )
    parser.add_argument("--stt-gate", action="store_true", help="live Deepgram STT gate")
    parser.add_argument("--stt-model", help="exact STT model id for --stt-gate (no default)")
    parser.add_argument("--stt-language", help="STT language for --stt-gate (no default)")
    parser.add_argument("--llm-gate", action="store_true", help="live OpenAI LLM gate")
    parser.add_argument("--llm-model", help="exact LLM model id for --llm-gate (no default)")
    parser.add_argument("--llm-reasoning", help="reasoning effort for --llm-gate (no default)")
    parser.add_argument("--tts-gate", action="store_true", help="live TTS gate")
    parser.add_argument(
        "--tts-provider",
        choices=["elevenlabs", "cartesia"],
        default="elevenlabs",
        help="elevenlabs = baseline, cartesia = challenger",
    )
    parser.add_argument("--tts-model", help="exact TTS model id for --tts-gate (no default)")
    parser.add_argument("--tts-voice-id", help="exact voice id for --tts-gate (no default)")
    parser.add_argument("--tts-voice-name", help="voice name, documentation only")
    parser.add_argument("--tts-language", help="language code for --tts-gate (no default)")
    parser.add_argument(
        "--tts-audio-dir", type=Path, help="WAV + manifest folder (default: per run)"
    )
    parser.add_argument(
        "--e2e-gate",
        action="store_true",
        help="end-to-end gate: Deepgram -> OpenAI -> gateway -> Cartesia (local)",
    )
    parser.add_argument(
        "--e2e-runtime",
        choices=["livekit", "pipecat"],
        default="livekit",
        help="runtime under test for --e2e-gate",
    )
    parser.add_argument(
        "--turn-taking-gate",
        action="store_true",
        help="turn-taking gate (VAD, endpointing, barge-in) on both runtimes (local)",
    )
    parser.add_argument("--turn-cases", help="comma-separated case ids (default: all)")
    parser.add_argument("--turn-runtimes", default="livekit,pipecat")
    parser.add_argument("--turn-repetitions-critical", type=int, default=5)
    parser.add_argument("--turn-repetitions-other", type=int, default=3)
    parser.add_argument("--scenario", action="append", help="dialogue id(s); default all")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    if args.sdk_status:
        statuses = [a.sdk_status() for a in (LiveKitRuntimeAdapter(), PipecatRuntimeAdapter())]
        print(json.dumps([dataclasses.asdict(s) for s in statuses], indent=2, default=dict))
        return 0
    if args.local_session_gate:
        return _local_session_gate()
    if args.turn_taking_gate:
        needed = (
            args.stt_model, args.stt_language, args.llm_model, args.llm_reasoning,
            args.tts_model, args.tts_voice_id, args.tts_language,
        )  # fmt: skip
        if not all(needed):
            parser.error("--turn-taking-gate needs every --stt-*, --llm-* and --tts-* setting")
        return _turn_gate(args, args.out)
    if args.e2e_gate:
        needed = (
            args.stt_model, args.stt_language, args.llm_model, args.llm_reasoning,
            args.tts_model, args.tts_voice_id, args.tts_language,
        )  # fmt: skip
        if not all(needed):
            parser.error("--e2e-gate needs every --stt-*, --llm-* and --tts-* model setting")
        return _e2e_gate(args, args.out)
    if args.tts_gate:
        if not (args.tts_model and args.tts_voice_id and args.tts_language):
            parser.error("--tts-gate needs --tts-model, --tts-voice-id and --tts-language")
        return _tts_gate(args, args.out)
    if args.llm_gate:
        if not (args.llm_model and args.llm_reasoning):
            parser.error("--llm-gate needs --llm-model and --llm-reasoning")
        return _llm_gate(args.llm_model, args.llm_reasoning, args.out)
    if args.stt_gate:
        if not (args.stt_model and args.stt_language):
            parser.error("--stt-gate needs --stt-model and --stt-language")
        return _stt_gate(args.stt_model, args.stt_language, args.out)
    if args.runtime is None:
        parser.error("--runtime is required unless --sdk-status or --local-session-gate")

    load_settings()  # fail closed: refuses live/recording configuration
    now = dt.datetime.now(dt.UTC)
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    run = RunInfo(
        run_id=f"{now:%Y%m%dT%H%M%SZ}-{(commit or 'nogit')[:8]}",
        git_commit=commit,
        git_dirty=None if status is None else bool(status),
        timestamp=now.isoformat(timespec="seconds"),
    )
    runtime = RUNTIMES[args.runtime]()
    out_dir = args.out / run.run_id / args.runtime

    dialogues = [d for d in load_dialogues() if not args.scenario or d.dialogue_id in args.scenario]
    summary: dict[str, object] = {"run_id": run.run_id, "runtime": args.runtime, "scenarios": {}}
    scenarios: dict[str, object] = {}
    for dialogue in dialogues:
        result, events = run_dialogue(dialogue, runtime, run)
        write_result(out_dir, result)
        if events:
            write_events(out_dir, dialogue.dialogue_id, events)
        scenarios[dialogue.dialogue_id] = {
            "status": result.status.value,
            "success": result.success,
            "hard_failures": result.hard_failures,
        }
    summary["scenarios"] = scenarios
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"results: {out_dir}")

    values = [v for v in scenarios.values() if isinstance(v, dict)]
    if not values or all(v["status"] == Status.NOT_TESTED.value for v in values):
        return 2
    return 0 if all(v["success"] and not v["hard_failures"] for v in values) else 1


def _run_info() -> RunInfo:
    now = dt.datetime.now(dt.UTC)
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return RunInfo(
        run_id=f"{now:%Y%m%dT%H%M%SZ}-{(commit or 'nogit')[:8]}",
        git_commit=commit,
        git_dirty=None if status is None else bool(status),
        timestamp=now.isoformat(timespec="seconds"),
    )


def _stt_gate(model: str, language: str, out: Path) -> int:
    load_settings()  # Phase 0 config stays fail-closed; live STT is opted in per adapter
    audit = HostAudit()
    run = _run_info()
    env = {**os.environ, DeepgramSTT.model_env: model, DeepgramSTT.language_env: language}
    stt = DeepgramSTT(env, allow_live=True)
    result, events = asyncio.run(
        run_stt_gate(
            load_stt_gate_cases(),
            stt,
            AUDIO_DIR,
            run_id=run.run_id,
            timestamp=run.timestamp,
            git_commit=run.git_commit,
            git_dirty=run.git_dirty,
            audit=audit,
        )
    )
    out_dir = out / run.run_id / "stt-deepgram"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(result.model_dump_json(indent=2) + "\n")
    for case_id, case_events in events.items():
        lines = [json.dumps(dataclasses.asdict(e), sort_keys=True) for e in case_events]
        (out_dir / f"{case_id}.events.jsonl").write_text("\n".join(lines) + "\n")
    print(f"status: {result.status.value}\nresults: {out_dir}")
    return {SttGateStatus.VERIFIED: 0, SttGateStatus.FAILED: 1}.get(result.status, 2)


def _tts_gate(args: argparse.Namespace, out: Path) -> int:
    load_settings()  # Phase 0 config stays fail-closed; live TTS is opted in per adapter
    audit = HostAudit()
    run = _run_info()
    audio_dir = args.tts_audio_dir or TTS_AUDIO_DIR / run.run_id
    adapter_type = CartesiaTTS if args.tts_provider == "cartesia" else ElevenLabsTTS
    env = {
        **os.environ,
        adapter_type.model_env: args.tts_model,
        adapter_type.voice_env: args.tts_voice_id,
        adapter_type.language_env: args.tts_language,
    }
    result = asyncio.run(
        run_tts_gate(
            load_tts_gate_cases(),
            adapter_type(env, allow_live=True),
            audio_dir,
            voice_name=args.tts_voice_name,
            challenger=args.tts_provider == "cartesia",
            run_id=run.run_id,
            timestamp=run.timestamp,
            git_commit=run.git_commit,
            git_dirty=run.git_dirty,
            audit=audit,
        )
    )
    out_dir = out / run.run_id / f"tts-{args.tts_provider}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(result.model_dump_json(indent=2) + "\n")
    write_manifest(audio_dir, result)
    print(f"status: {result.status.value}\nresults: {out_dir}\naudio: {audio_dir}")
    exit_codes = {
        TtsGateStatus.VERIFIED: 0,
        TtsGateStatus.CHALLENGER_VERIFIED: 0,
        TtsGateStatus.FAILED: 1,
        TtsGateStatus.CHALLENGER_FAILED: 1,
    }
    return exit_codes.get(result.status, 2)


def _llm_gate(model: str, reasoning: str, out: Path) -> int:
    load_settings()  # Phase 0 config stays fail-closed; live LLM is opted in per adapter
    audit = HostAudit()
    run = _run_info()
    env = {
        **os.environ,
        "VOICEOS_BENCH_LLM_PROVIDER": "openai",
        ConfiguredTextLLM.model_env: model,
        ConfiguredTextLLM.reasoning_env: reasoning,
    }
    llm = ConfiguredTextLLM(env, allow_live=True, instructions=INSTRUCTIONS)
    result = asyncio.run(
        run_llm_gate(
            load_llm_gate_cases(),
            llm,
            run_id=run.run_id,
            timestamp=run.timestamp,
            git_commit=run.git_commit,
            git_dirty=run.git_dirty,
            audit=audit,
        )
    )
    out_dir = out / run.run_id / "llm-openai"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(result.model_dump_json(indent=2) + "\n")
    print(f"status: {result.status.value}\nresults: {out_dir}")
    return {LlmGateStatus.VERIFIED: 0, LlmGateStatus.FAILED: 1}.get(result.status, 2)


def _e2e_gate(args: argparse.Namespace, out: Path) -> int:
    load_settings()  # Phase 0 config stays fail-closed; live providers are opted in per adapter
    server = LocalServer.from_env(os.environ)  # refuses anything but a loopback ws:// URL
    audit = HostAudit()
    run = _run_info()
    env = {
        **os.environ,
        DeepgramSTT.model_env: args.stt_model,
        DeepgramSTT.language_env: args.stt_language,
        "VOICEOS_BENCH_LLM_PROVIDER": "openai",
        ConfiguredTextLLM.model_env: args.llm_model,
        ConfiguredTextLLM.reasoning_env: args.llm_reasoning,
        CartesiaTTS.model_env: args.tts_model,
        CartesiaTTS.voice_env: args.tts_voice_id,
        CartesiaTTS.language_env: args.tts_language,
    }
    runtime = (
        LiveKitRuntimeAdapter(env) if args.e2e_runtime == "livekit" else PipecatRuntimeAdapter(env)
    )
    out_dir = out / run.run_id / f"{args.e2e_runtime}-e2e"
    result = asyncio.run(
        run_e2e_gate(
            server,
            env,
            out_dir,
            run_id=run.run_id,
            timestamp=run.timestamp,
            git_commit=run.git_commit,
            git_dirty=run.git_dirty,
            audit=audit,
            runtime=runtime,
        )
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(result.model_dump_json(indent=2) + "\n")
    print(f"status: {result.status.value}\nresults: {out_dir}")
    return 0 if result.status in (E2EStatus.VERIFIED, E2EStatus.PIPECAT_VERIFIED) else 1


def _turn_gate(args: argparse.Namespace, out: Path) -> int:
    from voiceos.benchmark.turn_gate import run_turn_gate
    from voiceos.benchmark.turn_taking import TurnTakingStatus, load_turn_taking_cases

    load_settings()  # Phase 0 config stays fail-closed; live providers are opted in per adapter
    server = LocalServer.from_env(os.environ)  # refuses anything but a loopback ws:// URL
    audit = HostAudit()
    run = _run_info()
    env = {
        **os.environ,
        DeepgramSTT.model_env: args.stt_model,
        DeepgramSTT.language_env: args.stt_language,
        "VOICEOS_BENCH_LLM_PROVIDER": "openai",
        ConfiguredTextLLM.model_env: args.llm_model,
        ConfiguredTextLLM.reasoning_env: args.llm_reasoning,
        CartesiaTTS.model_env: args.tts_model,
        CartesiaTTS.voice_env: args.tts_voice_id,
        CartesiaTTS.language_env: args.tts_language,
    }
    wanted = set(args.turn_cases.split(",")) if args.turn_cases else None
    cases = [c for c in load_turn_taking_cases() if wanted is None or c.case_id in wanted]
    runtimes: list[Literal["livekit", "pipecat"]] = [
        r for r in ("livekit", "pipecat") if r in args.turn_runtimes.split(",")
    ]
    out_dir = out / run.run_id / "turn-taking"
    result = asyncio.run(
        run_turn_gate(
            server, env, cases, out_dir,
            runtimes=runtimes,
            repetitions_critical=args.turn_repetitions_critical,
            repetitions_other=args.turn_repetitions_other,
            run_id=run.run_id, timestamp=run.timestamp,
            git_commit=run.git_commit, git_dirty=run.git_dirty, audit=audit,
        )
    )  # fmt: skip
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(result.model_dump_json(indent=2) + "\n")
    print(f"status: {json.dumps({k: v.value for k, v in result.status.items()})}")
    print(f"results: {out_dir}")
    return 0 if all(s is TurnTakingStatus.VERIFIED for s in result.status.values()) else 1


def _local_session_gate() -> int:
    load_settings()  # fail closed: refuses live/recording configuration
    server = LocalServer.from_env(os.environ)  # refuses anything but a loopback ws:// URL

    async def gate() -> list[LocalSessionReport]:
        return [
            await run_local_session_gate(adapter, server)
            for adapter in (LiveKitRuntimeAdapter(), PipecatRuntimeAdapter())
        ]

    reports = asyncio.run(gate())
    print(json.dumps([dataclasses.asdict(r) for r in reports], indent=2))
    statuses = {r.status for r in reports}
    if statuses == {LocalSessionStatus.VERIFIED}:
        return 0
    return 1 if LocalSessionStatus.FAILED in statuses else 2


if __name__ == "__main__":
    sys.exit(main())
