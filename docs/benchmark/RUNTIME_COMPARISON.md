# Runtime Comparison: LiveKit Agents vs. Pipecat

**Status: compared locally (loopback, synthetic German speech) on transport, end-to-end
pipeline, controlled repetition and turn-taking. Measured leads exist on single criteria
for each arm; no winner. ADR-001 (voice runtime) stays `NOT DECIDED`.**

## Setup

| Arm | Adapter | Transport | STT / LLM / TTS |
|---|---|---|---|
| A | LiveKit Agents 1.8.3 (`livekit-agents`) | shared LiveKit server v1.13.8 | same adapter instances as arm B |
| B | Pipecat 1.12.0 (`pipecat-ai[livekit]`, `LiveKitTransport`) | same LiveKit server | same adapter instances as arm A |

Both arms use the same `livekit.rtc` media layer (livekit 1.1.18), the same provider
adapters (Deepgram `nova-3`/`de`, OpenAI `gpt-6-luna` reasoning `low`, Cartesia
`sonic-3.5-2026-05-04` voice Nico), the same synthetic audio, the Phase 0 Tool Gateway
behind `GatewayBinding` and the same security invariants. Neither runtime receives a
`CallContext`; business actions go through the server-side binding only. The SDKs are an
optional, exactly pinned dependency group (`voice-sdk`) and are imported lazily inside
the benchmark adapter modules only.

## Evidence overview

| Measurement | Arm A (LiveKit Agents) | Arm B (Pipecat) | Class |
|---|---|---|---|
| Local transport join/media/leave | `LOCAL_SESSION_VERIFIED` | `LOCAL_SESSION_VERIFIED` | OBSERVED |
| E2E booking pipeline (single gate) | `LIVEKIT_E2E_VERIFIED` | `PIPECAT_E2E_VERIFIED` (integration run) | MEASURED |
| Controlled comparison, 5 + 5 sessions each | 5/5 happy, 5/5 injection, 0 hard failures | 5/5, 5/5, 0 | MEASURED (equal) |
| Startup p50 (happy / injection) | 668 / 293 ms | 280 / 58 ms | MEASURED LEAD Pipecat |
| Process RSS peak (whole process, coarse) | ~428 MB | ~255 MB | MEASURED LEAD Pipecat |
| Caller latency (user audio end → assistant heard) | p50 3492 ms | p50 3389 ms | INCONCLUSIVE |
| Turn-taking gate (counted series) | `INCONCLUSIVE` | `TURN_TAKING_VERIFIED` | MEASURED (see below) |
| False endpoints (turn-taking) | 6/54 | 34/54 | MEASURED LEAD LiveKit |
| Late endpoints > 1.5 s (turn-taking) | 26/54 | 4/54 | MEASURED LEAD Pipecat |
| Interruption detection p50 (turn-taking) | 613 ms | 475 ms | MEASURED LEAD Pipecat |
| TTS stop latency p50 (turn-taking) | 670 ms | 541 ms | MEASURED LEAD Pipecat |
| Credentials the runtime holds | server API key/secret (worker registration) | room-scoped token | OBSERVED |
| Load 1/5/10/25 sessions, SIP/PSTN, crash/drain lifecycle | NOT TESTED | NOT TESTED | — |

`MEASURED LEAD` names the arm with the better measured value on one criterion only. It is
not a ranking and not a selection.

## Local transport gate (join / media / leave)

Setup, identical for both arms: livekit-server **v1.13.8** (`docker-compose.livekit.yml`,
`--dev`, ports and node IP on 127.0.0.1), one throwaway room per run, the same
`livekit.rtc` (livekit 1.1.18), the same machine, Python 3.12.15 and `voice-sdk` group.
A synthetic caller (plain `livekit.rtc` participant) publishes a 440 Hz tone; no
microphone, no providers, no business tools. External network was blocked during the runs
(macOS sandbox: loopback only).

| Check | Arm A: LiveKit Agents 1.8.3 | Arm B: Pipecat 1.12.0 `LiveKitTransport` |
|---|---|---|
| Orchestration path | worker registers → explicit dispatch (`agent_name`) → `JobContext.connect()` → `ctx.shutdown()` | `PipelineWorker([transport.input(), probe])` → `on_connected` → `cancel()` |
| Credentials the runtime holds | room join via worker; **worker registration needs API key/secret** | room-scoped join token only |
| Server saw the runtime participant | OBSERVED | OBSERVED |
| Synthetic audio frame reached the runtime | OBSERVED | OBSERVED |
| Runtime gone from the room after leave | OBSERVED | OBSERVED |
| Room deleted, no gate rooms left | OBSERVED | OBSERVED |
| Unreachable server | fails fast (`RuntimeError`, `max_retry=0`) | fails within timeout (`TimeoutError`) |
| Status | `LOCAL_SESSION_VERIFIED` | `LOCAL_SESSION_VERIFIED` |

Observations for later review (not rankings): the LiveKit Agents worker protocol needs
the server API secret, which can mint tokens for any room, while Pipecat joins with a
room-scoped token; after `AgentServer.aclose()` the `worker_cpu_load_monitor` thread
stays alive; after Pipecat's disconnect the FFI logs `Attempted to drop unknown FFI
handle`. Timings of this gate are not latency measurements.

## End-to-end voice pipeline gate

Both arms carried the same local voice pipeline end to end (details and timings in
[BENCHMARK_METHOD.md](BENCHMARK_METHOD.md#livekit-end-to-end-voice-pipeline-gate)):
`LIVEKIT_E2E_VERIFIED` (arm A) and `PIPECAT_E2E_VERIFIED` (arm B, integration-test run;
the CLI run before it failed on an LLM dialog decision that the later deterministic
confirmation fix addressed in the harness). Single runs side by side, for orientation
only; different measurement points for "published" (see BENCHMARK_METHOD.md):

| Happy path, p50 over 7 turns | Arm A (LiveKit, run 3) | Arm B (Pipecat, run 3) |
|---|---|---|
| user audio end → STT final | 761 ms | 842 ms |
| LLM request → first output | 1574 ms | 1628 ms |
| TTS request → first audio | 356 ms | 243 ms |
| STT final → first assistant audio published | 2573 ms | 2085 ms |
| user audio end → assistant heard by caller | 3980 ms | 3343 ms |
| session startup / cleanup | NOT MEASURED (added later) | 261 ms / 231 ms |

The controlled comparison (5 happy-path + 5 injection sessions per arm, alternating,
identical harness) is summarized in [PHASE1_DECISION_GATE.md](PHASE1_DECISION_GATE.md)
(E11–E17). Most of each latency is provider time (STT endpointing, LLM, TTS), identical by
design.

## Turn-taking gate (VAD, endpointing, barge-in)

Method, case set, runtime-native settings, metric definitions and the pre-registered,
fail-closed gate rule: [BENCHMARK_METHOD.md](BENCHMARK_METHOD.md#turn-taking-gate-vad-endpointing-barge-in).
Each arm uses its native mechanics: LiveKit `AgentSession` (Silero VAD, local
`TurnDetector` v1-mini, VAD interruption) and Pipecat `VADProcessor` + `UserTurnProcessor`
(Smart Turn v3 local, `InterruptionFrame`). Providers and business layer are shared.

**Counted series: `20261027T215843Z-d5b89c30`** – 14 cases, critical cases 5×, others 3×,
runtimes alternating, 54 sessions per arm. All 108 sessions `VALID`; 0 provider, runtime
or harness failures; 0 hard failures; every gateway execution backed by a final
transcript (108/108); all rooms cleaned; secret scan clean; network only the three
provider hosts plus loopback. Earlier full series are invalid and not evaluated (listed in
BENCHMARK_METHOD.md).

| Gate status | Arm A (LiveKit Agents) | Arm B (Pipecat) |
|---|---|---|
| **Status** | **`INCONCLUSIVE`** | **`TURN_TAKING_VERIFIED`** |
| Evidence groups (usable / runs, minimum) | normal 6/6, endpointing 28/28, phone 5/5, **barge-in 12/15** (< 90 %) | normal 6/6, endpointing 28/28, phone 5/5, barge-in 14/15 |

| Metric (valid runs; latencies over runs without false endpoint) | Arm A (LiveKit) | Arm B (Pipecat) |
|---|---|---|
| End of user speech → runtime VAD end, p50 | 381 ms | 361 ms |
| Endpoint latency p50 / p95 (n) | 620 / 2652 ms (48) | 440 / 3360 ms (20) |
| Deepgram finalize delay p50 / p95 | 208 / 306 ms | 234 / 371 ms |
| STT-final latency p50 / p95 | 611 / 685 ms | 621 / 1076 ms |
| User audio end → assistant heard p50 / p95 (n) | 3633 / 6976 ms (48) | 3241 / 7365 ms (20) – INCONCLUSIVE, unequal n, LLM/TTS dominated |
| False endpoints | **6/54** (5 at 700 ms pause, 1 long thinking pause) | **34/54** (400/700 ms pauses 10/10, barge-in cases 15/15, self-correction 3/3, phone 4/5, date 2/3) |
| Late endpoints (> 1.5 s) | **26/54** (bimodal: ~0.4–0.7 s or ~2.6 s) | **4/54** (~3.4 s) |
| Usable barge-in runs | 12/15 | 14/15 |
| Barge-in success / missed / context loss (usable runs) | 12/12 / 0 / 0 | 14/14 / 0 / 0 |
| Interruption detection p50 / p95 (n = 15) | 613 / 654 ms | 475 / 941 ms |
| TTS stop latency p50 / p95 | 670 / 752 ms (n = 12) | 541 / 926 ms (n = 14) |
| End of barge-in speech → barge-in transcript ready, p50 | 601 ms | 553 ms (min −1691 ms: accepted before the caller finished, due to false endpoints) |
| Phone number digits in the final committed transcript | 8/8 (TT09, TT14) | 8/8; in 7/8 split across 2–3 turns at comma pauses |

False and late endpoints are measured but not gating (pre-registered). Pipecat's
`TURN_TAKING_VERIFIED` therefore does not mean its default endpointing suits digit
sequences or thinking pauses; LiveKit's `INCONCLUSIVE` is missing evidence, not a measured
barge-in defect.

**Why LiveKit is `INCONCLUSIVE`:** 3 of its 5 TT13 runs (barge-in 1,000 ms after the
caller first hears the assistant) were not usable as barge-in evidence, leaving 12/15
(80 %) usable against the pre-registered 90 %. In every TT13 run of both arms the fixed
1,000 ms trigger (measured 1022–1037 ms) fell into the natural pause after the first
assistant phrase ("Ich habe notiert:", phrase end 840–1000 ms, pause 360–640 ms). A run
counted as usable only when that pause was shorter than the pre-registered 0.5 s merge
gap (LiveKit 2/5, Pipecat 4/5). The pause comes from the shared TTS output, not from
either runtime; both arms detected the interruption in these runs as well.

### TT13 diagnostic (separate, not part of the counted series)

Run `20261027T224431Z-d5b89c30-tt13-speech-relative-diagnostic`, TT13 only, 5 sessions per
arm. The only change: the caller barges in after **500 ms of continuous audible assistant
speech** (voiced frames at the pre-registered `VOICED_PEAK`, gaps ≤ 100 ms) instead of
1,000 ms after the first voiced frame. Evaluation unchanged (`evaluate_run`).

| TT13, speech-relative trigger | Arm A (LiveKit) | Arm B (Pipecat) |
|---|---|---|
| Assistant audible at barge-in start | 5/5 | 5/5 |
| Usable barge-in evidence | **5/5** | **5/5** |
| Missed interruptions / context loss | 0 / 0 | 0 / 0 |
| Interruption detection p50 (range) | 615 ms (583–692) | 487 ms (475–566) |
| TTS stop latency p50 (range) | 442 ms (424–482) | 392 ms (322–485) |
| False endpoints | 0/5 | 4/5 |
| Provider / runtime / harness failures | 0 | 0 |
| Diagnostic status | `LIVEKIT_TT13_EVIDENCE_CONFIRMED` | `PIPECAT_TT13_EVIDENCE_CONFIRMED` |

This confirms that the missing TT13 evidence was a property of the fixed-offset test
design. It is diagnostic evidence only: it is not inserted into the counted series, does
not change its gate status and does not turn LiveKit's `INCONCLUSIVE` into `VERIFIED`.
Side observation (Pipecat arm, 3/5): Deepgram transcribed the split digits "1 2 3" as
"einhundertdreiundzwanzigste"; the assistant asked for the number digit by digit and no
tool ran with a wrong number.

## Reference runtime (not a candidate)

The deterministic `ReferenceRuntime` ran all 20 dialogues offline with scripted adapters.
All scenario oracles held and no hard failure occurred (OBSERVED). This validates the
harness and the safety boundary that both candidates are measured against. Its timings are
in-process harness overhead and say nothing about either candidate.

## Not covered (no runtime decision possible yet)

SIP/PSTN (Manus topology T0), WebSocket media streams (T1), real human speech, noise,
8 kHz / G.711, load (1/5/10/25 sessions and above), crash/drain lifecycle, observability,
cost, endpointing tuning per arm (all runs used framework defaults except the settings
listed in BENCHMARK_METHOD.md). Only `MEASURED`, `OBSERVED`, `INCONCLUSIVE` or
`NOT TESTED` statements are made; **no runtime is declared the winner and ADR-001 stays
`NOT DECIDED`.**
