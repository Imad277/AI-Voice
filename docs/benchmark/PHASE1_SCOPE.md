# Phase 1 Scope

## Question

Which voice runtime and voice pipeline combination is technically most suitable for
VoiceOS? Primary candidates: **LiveKit Agents** and **Pipecat**, compared with identical
STT, LLM and TTS components so that only the runtime differs.

## In scope (done)

- Adapter contracts separating scenario, runtime, STT, LLM, TTS, Tool Gateway and results.
- `LiveKitRuntimeAdapter` and `PipecatRuntimeAdapter` under the same contract; both probe
  their prerequisites and refuse to run while they are missing.
- A deterministic `ReferenceRuntime` that proves the harness, the gateway boundary and the
  result pipeline end to end. It is not a runtime candidate.
- Provider adapter contracts with scripted offline adapters and live candidate adapters
  (Deepgram STT, configurable text LLM, ElevenLabs TTS, Cartesia TTS as later challenger)
  that report what is missing. No model id is defaulted.
- Phase-1-lite German dataset: 50 short cases, 20 dialogues, synthetic only, no audio.
- Result schema, JSONL telemetry, offline CLI, tests.
- One local end-to-end voice pipeline on LiveKit Agents (`LIVEKIT_E2E_VERIFIED`, see
  [BENCHMARK_METHOD.md](BENCHMARK_METHOD.md#livekit-end-to-end-voice-pipeline-gate)) and
  on Pipecat (`PIPECAT_E2E_VERIFIED`), a controlled 5 + 5 session comparison, and the
  turn-taking gate on both runtimes (counted series: LiveKit Agents `INCONCLUSIVE`,
  Pipecat `TURN_TAKING_VERIFIED`; see [RUNTIME_COMPARISON.md](RUNTIME_COMPARISON.md)).

## Out of scope

Dashboard, agent builder, campaigns, billing, RAG, white label, real CRM/calendar,
outbound, production deployment, Kubernetes, Terraform, n8n, Temporal, native
speech-to-speech (later challenger), PSTN, load tests above 25 sessions.

## NOT TESTED in this phase, and why

| Area | Missing prerequisite |
|---|---|
| LiveKit Agents runtime (voice) | one local E2E pipeline `LIVEKIT_E2E_VERIFIED` (1 synthetic booking dialog + 1 injection test, single run); controlled comparison 5 + 5 sessions; `AgentSession` with native VAD, turn detection and barge-in measured in the turn-taking gate (`INCONCLUSIVE`, barge-in evidence 12/15); the 20 dialogues, SIP, load NOT TESTED |
| Pipecat runtime (voice) | same E2E pipeline on `LiveKitTransport` `PIPECAT_E2E_VERIFIED` in the integration-test run; the CLI run before it was `PIPECAT_E2E_FAILED` (LLM did not re-propose the booking after the server readback). Controlled comparison 5 + 5 sessions; native VAD, turn detection and barge-in measured in the turn-taking gate (`TURN_TAKING_VERIFIED`); the 20 dialogues, SIP, load NOT TESTED |
| Deepgram STT | streaming baseline gate `STT_BASELINE_VERIFIED` on 10 synthetic cases; real caller audio, noise, telephony audio NOT TESTED |
| OpenAI text LLM (`gpt-6-luna`, Responses API) | text gate `LLM_BASELINE_VERIFIED` on 17 synthetic cases; used unchanged in the E2E gate |
| ElevenLabs TTS (`eleven_flash_v2_5`) | remains a **tested TTS candidate**. Voice `Roger` rejected by human listening; native German voices Susi / Ben / Mark `TTS_BASELINE_VERIFIED` (after the plan change); telephony codec NOT TESTED |
| Cartesia TTS challenger (`sonic-3.5-2026-05-04`, voices Alina / Lukas / Nico) | `TTS_CHALLENGER_VERIFIED` per voice on the same 10 texts; human listening 8/10; **Nico (`afa425cf-5489-4a09-8a3f-d3cb1f82150d`) = `PHASE1_REFERENCE_VOICE`** for the next Phase 1 end-to-end tests only, not a provider decision |
| Caller-observed voice latency | measured once over loopback WebRTC with synthetic speech (E2E gate); real network, telephony, PSTN NOT TESTED |
| STT entity accuracy | recorded audio (`NOT RECORDED`) and a real STT |
| Turn taking / interruption | measured locally with synthetic speech and framework defaults (turn-taking gate); real speech, telephony audio and endpointing tuning NOT TESTED |
| Load lite (1/5/10/25 sessions) | a real runtime; the reference runtime is not a candidate |
| PSTN | carrier account (not required for Phase 1) |
| Cost | usage evidence |

## Blockers to lift before a real comparison

1. Provider credentials for one shared baseline (STT, LLM, TTS) as local env values, plus
   the exact model/voice ids to freeze at test time.
2. A deliberate decision to allow live benchmark execution: the Phase 0 config refuses
   `VOICEOS_LIVE_ENABLED=true`, by design.
3. Done: `livekit-agents==1.8.3` and `pipecat-ai[livekit]==1.12.0` resolve together under
   Python 3.12 in the optional `voice-sdk` group and import offline. Pipecat's
   `LiveKitTransport` uses the same `livekit.rtc` module (livekit 1.1.18) as livekit-agents.
4. Done locally: `docker-compose.livekit.yml` runs livekit-server v1.13.8 in `--dev` mode on
   127.0.0.1. Both runtimes join, receive a synthetic audio frame and leave (local gate).
