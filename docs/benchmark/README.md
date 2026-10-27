# VoiceOS Voice Benchmark (Phase 1)

**Status:** harness implemented. Single-provider gates (STT, LLM, TTS) and the local
transport gate ran live. One local LiveKit Agents end-to-end voice pipeline
(Deepgram → OpenAI → Tool Gateway → Cartesia/Nico) is `LIVEKIT_E2E_VERIFIED` for one
synthetic German booking dialog plus one tenant-injection test; the same pipeline on
Pipecat's `LiveKitTransport` is `PIPECAT_E2E_VERIFIED` (integration-test run; one earlier
run failed on an LLM dialog decision). The turn-taking gate (native VAD, endpointing and
barge-in of both runtimes) has one counted series: LiveKit Agents `INCONCLUSIVE`, Pipecat
`TURN_TAKING_VERIFIED`; see [RUNTIME_COMPARISON.md](RUNTIME_COMPARISON.md). No runtime or
provider is ranked or selected. Nothing in this directory is an architecture decision.

| Document | Content |
|---|---|
| [PHASE1_DECISION_GATE.md](PHASE1_DECISION_GATE.md) | Phase 1 evidence review, provisional paths, next gate (`HOLD_FOR_EVIDENCE` for final ADRs) |
| [PHASE1_SCOPE.md](PHASE1_SCOPE.md) | what Phase 1 covers, what it does not, blockers |
| [BENCHMARK_METHOD.md](BENCHMARK_METHOD.md) | layers, fairness rules, dataset, metric definitions |
| [RESULT_SCHEMA.md](RESULT_SCHEMA.md) | result and event format |
| [RUNTIME_COMPARISON.md](RUNTIME_COMPARISON.md) | LiveKit Agents vs. Pipecat: setup and evidence incl. turn-taking and the TT13 diagnostic |

## Run it

```bash
uv run python -m voiceos.benchmark.cli --runtime reference   # offline harness, all 20 dialogues
uv run python -m voiceos.benchmark.cli --runtime livekit     # writes NOT TESTED results + reasons
uv run python -m voiceos.benchmark.cli --runtime pipecat     # writes NOT TESTED results + reasons
uv sync --group voice-sdk                                     # optional: pinned runtime SDKs
uv run python -m voiceos.benchmark.cli --sdk-status          # local SDK import/capability check

# Local transport gate (loopback LiveKit dev server, no providers):
docker compose -f docker-compose.livekit.yml up -d
uv run --env-file .env python -m voiceos.benchmark.cli --local-session-gate
uv run --no-sync --env-file .env pytest tests/integration -m livekit_local

# Deepgram STT baseline gate (live; key only in the git-ignored .env; macOS speech synthesis):
uv sync --group stt-deepgram
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --stt-gate --stt-model nova-3 --stt-language de
uv run --no-sync --env-file .env pytest tests/integration -m deepgram_live

# OpenAI text LLM baseline gate (live; key only in the git-ignored .env; needs account credit):
uv sync --group llm-openai
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --llm-gate --llm-model gpt-6-luna --llm-reasoning low
uv run --no-sync --env-file .env pytest tests/integration -m openai_live

# ElevenLabs TTS baseline gate (live; key only in the git-ignored .env):
uv sync --group tts-elevenlabs
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --tts-gate --tts-model eleven_flash_v2_5 --tts-voice-id CwhRBWXzGAHq8TQ4Fs17 --tts-voice-name Roger --tts-language de
uv run --no-sync --env-file .env pytest tests/integration -m elevenlabs_live

# Cartesia TTS challenger gate (live; key only in the git-ignored .env):
uv sync --group tts-cartesia
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --tts-gate --tts-provider cartesia --tts-model sonic-3.5-2026-05-04 --tts-voice-id <id> --tts-voice-name <name> --tts-language de --tts-audio-dir benchmarks/audio/cartesia_voice_gate/<id>
uv run --no-sync --env-file .env pytest tests/integration -m cartesia_live

# LiveKit end-to-end voice pipeline gate (local dev server + live STT/LLM/TTS; keys in .env):
uv sync --group voice-sdk --group stt-deepgram --group llm-openai --group tts-cartesia
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --e2e-gate --stt-model nova-3 --stt-language de --llm-model gpt-6-luna --llm-reasoning low --tts-model sonic-3.5-2026-05-04 --tts-voice-id afa425cf-5489-4a09-8a3f-d3cb1f82150d --tts-language de
uv run --no-sync --env-file .env pytest tests/integration -m livekit_e2e

# Pipecat end-to-end voice pipeline gate (same harness, dialog and providers; runtime differs):
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --e2e-gate --e2e-runtime pipecat --stt-model nova-3 --stt-language de --llm-model gpt-6-luna --llm-reasoning low --tts-model sonic-3.5-2026-05-04 --tts-voice-id afa425cf-5489-4a09-8a3f-d3cb1f82150d --tts-language de
uv run --no-sync --env-file .env pytest tests/integration -m pipecat_e2e

# Turn-taking gate (both runtimes, native VAD/endpointing/barge-in; local dev server + live providers):
uv run --no-sync --env-file .env python -m voiceos.benchmark.cli --turn-taking-gate --turn-repetitions-critical 5 --turn-repetitions-other 3 --stt-model nova-3 --stt-language de --llm-model gpt-6-luna --llm-reasoning low --tts-model sonic-3.5-2026-05-04 --tts-voice-id afa425cf-5489-4a09-8a3f-d3cb1f82150d --tts-language de
uv run --no-sync --env-file .env pytest tests/integration -m turn_taking_live   # written, not yet executed
```

`tests/integration` is not part of the default test run (`testpaths` = `tests/unit`,
`tests/postgres`). Each integration marker needs the local LiveKit dev server and/or the
live provider keys named in its comment above; none of them runs in CI.

Results go to `benchmarks/results/<run_id>/<runtime>/` (git-ignored): one `<scenario>.json`
per dialogue, one `<scenario>.events.jsonl`, and `summary.json`. Exit code 0 = all scenarios
ran and held their oracles, 1 = a scenario failed or hit a hard failure, 2 = not runnable.
The turn-taking gate writes `benchmarks/results/<run_id>/turn-taking/summary.json` plus per
session `<runtime>/<case>-r<n>/` (`events.jsonl`, `caller_frames.json`,
`transcript.json`, `assistant_output.wav`); exit code 0 only if every runtime is
`TURN_TAKING_VERIFIED`. Rendered input audio goes to `benchmarks/audio/` (git-ignored).

If the checkout lives in a cloud-synced folder, macOS can mark `.venv/*.pth` files as
hidden, which Python then skips. If `voiceos` cannot be imported, prefix the command with
`PYTHONPATH=src` (pytest already sets this).

## Code

`src/voiceos/benchmark/`: `ports.py` (contracts), `binding.py` (server-side gateway
binding), `providers.py` (STT/LLM/TTS adapters, the only place provider SDKs are
imported), `runtimes.py` (runtime adapters), `livekit_local.py` (local transport gate),
`voice_loop.py` (agent turn loop), `e2e_gate.py` (E2E harness: synthetic caller, gateway
audit, invariants), `turn_taking.py` (turn-taking cases, shared `TurnTakingAgent`, metric
definitions, session validity and the fail-closed gate rule; no SDK imports),
`turn_runtimes.py` (native LiveKit `AgentSession` and Pipecat pipeline arms),
`turn_gate.py` (turn-taking harness: caller, rooms, artifacts, series), `stt_gate.py`,
`llm_gate.py`, `tts_gate.py`, `synthetic_audio.py` (macOS `say` rendering), `dataset.py`,
`metrics.py`, `results.py`, `runner.py`, `cli.py`. Runtime and provider SDKs are imported
lazily, only in `runtimes.py`, `turn_runtimes.py`, `livekit_local.py`, `e2e_gate.py`,
`turn_gate.py` (LiveKit/Pipecat) and `providers.py` (Deepgram, OpenAI, ElevenLabs,
Cartesia); `tests/unit/test_repo_hygiene.py` enforces this. Dataset:
`benchmarks/datasets/phase1/`.
