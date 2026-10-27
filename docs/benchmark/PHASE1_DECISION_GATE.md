# Phase 1 – Architecture Decision Gate

**Date:** 2026-10-26, evidence updated 2026-10-28 (turn-taking gate, regression) · **Branch:** `phase-1-voice-benchmark` · **Prepared by:** Claude Code
(implementation engineer) · **Review:** ChatGPT (architecture/QA) · **Approval:** human
project owner (pending)

**Gate status (template 12 vocabulary): `HOLD_FOR_EVIDENCE`** for every final ADR.
Phase 1 delivers *provisional* reference paths for the next gate, not final decisions.
No ADR in `docs/architecture/decisions/` is created or accepted by this document.

Evidence classes used below: `MEASURED` (counted/timed by the harness), `OBSERVED`
(seen in runs or code, not quantified), `HUMAN_REVIEW` (owner listening), `INCONCLUSIVE`
(measured, but not distinguishable), `NOT_TESTED`. Decision categories: `ACCEPT`,
`PROVISIONAL ACCEPT`, `CONTINUE EVALUATION`, `REJECT`, `NOT DECIDED`.

## 1. Scope and validity of the Phase 1 evidence

- Topology: **local loopback only** (livekit-server v1.13.8 `--dev` on 127.0.0.1,
  livekit.rtc 1.1.18). Manus defines the primary runtime comparison as **T0** (carrier
  SIP → LiveKit SIP/media → rooms); T0 is `NOT_TESTED`. Per the Manus acceptance policy
  this evidence is an offline/loopback population and must not be read as `sip_virtual`
  or `pstn_real` evidence.
- Audio: synthetic German speech (macOS `say`, voice Anna, 16 kHz), deterministic SHA.
  No real speakers, no noise, no 8 kHz/G.711.
- G0 (Manus template 12, section 2) is **open**: no carrier/DID, no legal/data approval
  for real audio, no budget/allowlist, no frozen model snapshots (the LLM is an alias).
- Acceptance criteria AC-PERF-01/02, AC-INT-01, AC-FIELD-01 etc. (Manus doc 09) are still
  `PROPOSED`; no owner has accepted them. Comparisons against them below are informative.
- Sample sizes: provider gates 10–17 cases; runtime comparison n = 5 sessions per arm
  (35 turns), single machine, one day. p95 at n = 5 is a rough indication only.
  Turn-taking gate: one counted series with 54 sessions per arm (14 cases), plus a
  separate TT13 diagnostic with 5 sessions per arm.

## 2. Evidence summary

| # | Evidence | Class | Source |
|---|---|---|---|
| E1 | Deepgram `nova-3`/`de` streaming: 10/10 synthetic cases connected, final transcript, no provider error; identical transcripts in 2 runs | MEASURED | STT gate 2026-10-22 |
| E2 | Deepgram entity misses on synthetic speech: phone (G02), email (G03), date with ordinal (G06); names, address, time, money, correction correct | MEASURED | STT gate |
| E3 | Deepgram holds the final transcript of a spoken phone number ~5.8 s after speech end; other turns 0.7–0.9 s (incl. 500 ms endpointing) | MEASURED (every E2E run, both arms) | E2E gates |
| E4 | OpenAI `gpt-6-luna` (alias, no dated snapshot), reasoning `low`: 16/17 expected tool decisions, 0 hard failures, 6/6 safety/injection cases blocked; first output p50 1617 ms, total p50 1830 ms | MEASURED | LLM gate 2026-10-23 |
| E5 | Model nondeterminism after server slot readback: 15/20 identical text replays re-proposed `book_slot` | MEASURED | confirmation determinism gate |
| E6 | Harness fix (server confirmation note from trusted state): 40/40 `book_slot`, 40/40 one write, `BOOKING_CONFIRMED`, 0 hard failures | MEASURED | harness fix replay |
| E7 | ElevenLabs `eleven_flash_v2_5`: Roger, Susi, Ben, Mark each 10/10 technically valid; TTFA p50 270–356 ms | MEASURED | TTS gates |
| E8 | Cartesia `sonic-3.5-2026-05-04` (dated snapshot): Alina, Lukas, Nico each 10/10 valid; Nico TTFA p50 186 ms, p95 342 ms (gate); in E2E pooled TTFA p50 262/281 ms | MEASURED | Cartesia gate, E2E comparison |
| E9 | Roger rejected (non-native German, clearly AI) | HUMAN_REVIEW | 2026-10-23 |
| E10 | Cartesia voices: naturalness better than the tested ElevenLabs voices, good German accent, very good intelligibility, AI recognizable to a trained ear; suitability 8/10; Nico preferred | HUMAN_REVIEW | 2026-10-26 |
| E11 | Runtime comparison, alternating, identical harness: LiveKit Agents 5/5 happy path, 5/5 injection; Pipecat 5/5, 5/5; 0 hard failures, 0 runtime errors, 0 provider errors, 0 room leaks (20/20 rooms empty and deleted) | MEASURED | controlled comparison |
| E12 | Startup p50: LiveKit 668 ms (happy) / 293 ms (injection), Pipecat 280 / 58 ms; no overlap | MEASURED (lead Pipecat) | controlled comparison |
| E13 | Process RSS peak (harness + caller + runtime): LiveKit 414–428 MB, Pipecat 254–257 MB | MEASURED (lead Pipecat), method coarse | controlled comparison |
| E14 | Caller latency (user audio end → assistant heard), pooled: LiveKit p50 3492 / p95 7799 ms, Pipecat p50 3389 / p95 8030 ms; per-run medians overlap | INCONCLUSIVE between arms | controlled comparison |
| E15 | Non-tool turns only (derived from the same runs): LiveKit p50 3055 / p95 3324 ms (n=9), Pipecat p50 3134 / p95 4452 ms (n=11) | MEASURED; far above PROPOSED AC-PERF-02 (p50 ≤ 800 ms) and AC-PERF-01 (p95 ≤ 1500 ms) for both arms | derived, no new run |
| E16 | Cleanup p50 LiveKit 305 ms, Pipecat 235 ms (overlapping); CPU mean ≈ 21 % both | OBSERVED / INCONCLUSIVE | controlled comparison |
| E17 | LiveKit Agents worker needs the server API key/secret (can mint any room token); Pipecat joins with a room-scoped token only | OBSERVED (structural) | runtime adapters |
| E18 | Turn latency composition: ~0.8 s STT final after speech end, then full LLM response (not first token) before TTS starts, ~0.25 s TTFA; the shared loop waits for the complete LLM response because the speech guard judges whole text | OBSERVED (harness design) | `voice_loop.py` |
| E19 | Phase 0: real PostgreSQL 18.6 RLS (FORCE RLS, non-owner app role without BYPASSRLS), gateway negative tests, BOOKING_UNKNOWN never released by negative lookup, BOOKED_CRM_PENDING | MEASURED (offline + real DB tests) | Phase 0 test suite |
| E20 | Turn-taking gate, counted series `20261027T215843Z-d5b89c30`, native turn-taking of both arms (LiveKit `AgentSession` + `TurnDetector` v1-mini; Pipecat `VADProcessor` + `UserTurnProcessor`/Smart Turn v3): 108/108 sessions `VALID`, 0 hard failures, every gateway execution after a final transcript. Status **LiveKit `INCONCLUSIVE`** (barge-in evidence 12/15 < 90 %), **Pipecat `TURN_TAKING_VERIFIED`** | MEASURED | turn-taking gate 2026-10-27 |
| E21 | False endpoints LiveKit 6/54, Pipecat 34/54; late endpoints (> 1.5 s) LiveKit 26/54, Pipecat 4/54; endpoint latency p50 620 vs 440 ms (not gating, pre-registered) | MEASURED (opposite leads) | turn-taking gate |
| E22 | Barge-in on usable runs: success 12/12 vs 14/14, 0 missed, 0 context loss; interruption detection p50 613 vs 475 ms; TTS stop latency p50 670 vs 541 ms | MEASURED (lead Pipecat on detection/stop) | turn-taking gate |
| E23 | TT13 diagnostic (separate run, speech-relative trigger after 500 ms continuous assistant speech): LiveKit 5/5 and Pipecat 5/5 usable, 0 missed, 0 context loss → the fixed 1,000 ms trigger hit a TTS pause; LiveKit's `INCONCLUSIVE` is a test-design gap, not a measured barge-in defect. Counted series unchanged | MEASURED (diagnostic only) | TT13 diagnostic 2026-10-27 |
| E24 | With Deepgram `Finalize` sent on the runtime's VAD end, STT final after speech end p50 611 / 621 ms (incl. phone numbers ~0.55–0.66 s) – the ~5.8 s of E3 does not occur in this harness; Pipecat splits digit sequences at comma pauses (7/8 phone runs), once seen as number words ("einhundertdreiundzwanzigste") in the diagnostic | MEASURED / OBSERVED | turn-taking gate, TT13 diagnostic |
| E25 | Cartesia refused 108 of 113 syntheses with HTTP 402 `quota_exceeded` ("Model credits limit reached") during a series on 2026-10-27; that series is void. Access restored after the account limit was raised | MEASURED (operational) | provider diagnosis |
| E26 | Harness fail-closed fix: TTS failures are recorded as provider failures with safe codes, sessions classified `VALID` / `INVALID_PROVIDER_FAILURE` / `INVALID_RUNTIME_FAILURE` / `INVALID_HARNESS_FAILURE`, gate needs minimum evidence per group; live smoke 6/6 correct, artificial TTS failure → `INVALID_PROVIDER_FAILURE` | MEASURED | harness fix + smoke 2026-10-27 |
| E27 | Regression: full suite with real PostgreSQL 367/367 passed (26 PostgreSQL/RLS tests run, none skipped); CI parity (`uv sync --locked`, no optional SDK groups) 362 passed / 5 skipped (only the `voice-sdk`-dependent tests) / 0 failed; ruff, mypy strict, `uv lock --check` clean | MEASURED | 2026-10-28 |

## 3. Component assessment

### 3.1 STT – Deepgram `nova-3`, `de`

| Aspect | Class |
|---|---|
| Streaming (v1 websocket) works, German works (E1) | MEASURED |
| Phone/email/ordinal-date entity misses on synthetic speech (E2) | MEASURED |
| Phone-number finalization ~5.8 s in the E2E gates (E3) | MEASURED |
| `Finalize` on the runtime's VAD end (turn-taking harness): STT final p50 ~0.6 s, phone numbers included (E24) | MEASURED (harness policy; product adoption `NOT DECIDED`) |
| Digit sequences split by runtime endpointing can be re-recognized as number words (E24) | OBSERVED |
| Real caller audio, noise, 8 kHz/G.711, accents | NOT_TESTED |
| Alternative STT (Speechmatics trigger per Manus) | NOT_TESTED |
| Cost per minute | NOT_TESTED |

**Decision: `PROVISIONAL ACCEPT` – Deepgram `nova-3` as reference STT for the next gate.**
Not a provider binding (ADR-003 stays `NOT DECIDED`). The digit-finalization delay and the
entity misses are open defects of the current configuration, not accepted behavior.

### 3.2 LLM – OpenAI `gpt-6-luna`, reasoning `low`

| Aspect | Class |
|---|---|
| Strict tool schemas from the gateway, proposals only, gateway decides (E4, E11) | MEASURED |
| 16/17 tool accuracy, 0 hard failures, injection cases blocked (E4) | MEASURED |
| Nondeterministic control flow after readback; fixed in the harness 40/40 (E5, E6) | MEASURED |
| Alias without dated snapshot; reruns may hit a changed model | OBSERVED (reproducibility risk) |
| First output 0.85–2.6 s per turn in E2E; full response awaited before TTS (E18) | MEASURED / OBSERVED |
| Alternative text model, native speech-to-speech (ADR-002) | NOT_TESTED |
| Cost (tokens recorded, no tariff evaluation) | NOT_TESTED |

**Decision: `PROVISIONAL ACCEPT` – `gpt-6-luna` (reasoning `low`) as reference LLM for the
next gate**, with the server confirmation note as part of the harness. ADR-005 stays
`NOT DECIDED`; the alias must be frozen or recorded per run.

### 3.3 TTS – Cartesia and ElevenLabs

| Aspect | Cartesia `sonic-3.5-2026-05-04` | ElevenLabs `eleven_flash_v2_5` |
|---|---|---|
| Technical gate 10/10 valid audio | MEASURED (Alina, Lukas, Nico) | MEASURED (Roger, Susi, Ben, Mark) |
| TTFA p50 (gate) | 186–216 ms; Nico 186 ms | 270–356 ms |
| E2E reference voice in both runtimes (20 sessions) | MEASURED (Nico) | NOT_TESTED in E2E |
| Human listening | HUMAN_REVIEW 8/10, Nico preferred | HUMAN_REVIEW: Roger rejected; Susi/Ben/Mark not formally scored |
| Dated model snapshot | yes | model id without date |
| Telephony codec / PSTN | NOT_TESTED | NOT_TESTED |
| Cost | NOT_TESTED | character cost headers only |
| Account quota outage (402 `quota_exceeded`, E25) | MEASURED operational risk | — |

**Decision: `PROVISIONAL ACCEPT` – Cartesia `sonic-3.5-2026-05-04`, voice Nico
(`afa425cf-5489-4a09-8a3f-d3cb1f82150d`) as reference TTS for the next gate.**
**ElevenLabs: `CONTINUE EVALUATION`** – stays in the project as tested candidate; not the
reference TTS now. ADR-004 stays `NOT DECIDED` (no telephony-codec, cost or larger
listening evidence).

### 3.4 Runtime – LiveKit Agents 1.8.3 vs. Pipecat 1.12.0 (LiveKit transport)

| Criterion | LiveKit Agents | Pipecat | Class |
|---|---|---|---|
| Functional success, injection, hard failures, room leaks | 5/5, 5/5, 0, 0 | 5/5, 5/5, 0, 0 | MEASURED (equal) |
| Caller latency | p50 3492 ms | p50 3389 ms | INCONCLUSIVE |
| Startup | 668 / 293 ms | 280 / 58 ms | MEASURED LEAD Pipecat |
| Process RSS peak | ~428 MB | ~255 MB | MEASURED LEAD Pipecat (whole process, coarse) |
| Cleanup | 305 ms | 235 ms | INCONCLUSIVE (overlap) |
| Credentials held by the runtime | server API key/secret (worker registration) | room-scoped token | OBSERVED: Pipecat closer to least privilege |
| Session model | worker → dispatch → job on its own thread/loop | pipeline in the caller's loop, frame processors | OBSERVED |
| Integration effort in this harness | thin adapter, worker lifecycle, thread hand-off between loops | thin frame processor + audio sink in one loop | OBSERVED (similar size; effort not timed) |
| Turn-taking gate status (E20) | `INCONCLUSIVE` (barge-in evidence 12/15) | `TURN_TAKING_VERIFIED` | MEASURED |
| False / late endpoints (E21) | 6/54 / 26/54 | 34/54 / 4/54 | MEASURED, opposite leads (not gating) |
| Interruption detection / TTS stop p50 (E22) | 613 / 670 ms | 475 / 541 ms | MEASURED LEAD Pipecat |
| Barge-in success, missed, context loss (E22, E23) | 12/12, 0, 0; diagnostic 5/5 | 14/14, 0, 0; diagnostic 5/5 | MEASURED (equal on usable runs) |
| SIP/PSTN (T0), WebSocket transport (T1) | — | — | NOT_TESTED |
| Load 10/25/50/100, crash/drain lifecycle (RT-LC-01…08) | — | — | NOT_TESTED |
| Observability, maintainability over time | — | — | NOT_TESTED |

**A – Is the evidence sufficient for a final runtime decision? No.** Manus ADR-001 requires
T0 (SIP), VAD/barge-in, holdout, lifecycle and load evidence; Phase 1 has local loopback
and synthetic audio. Turn-taking is now measured on both arms (E20–E23) with framework
defaults only, and the results point in opposite directions: Pipecat leads on interruption
detection, TTS stop and late endpoints, LiveKit Agents on false endpoints (premature turn
ends in pauses and digit sequences). SIP integration, real speech, load and operations
remain untested.

**B – Provisional implementation path: `PROVISIONAL ACCEPT – Pipecat` (with LiveKit
transport).** Reasons, in order: equal measured functional and security results (E11);
room-scoped credentials instead of the server API secret (E17), which fits the
least-privilege tenant model; measured lower startup and memory (E12, E13); direct
pipeline lifecycle in one event loop. This is **not** a final runtime selection.
**LiveKit Agents stays the challenger.** The turn-taking gate has since run on both arms
(E20–E23); its mixed result neither confirms nor overturns this provisional path, which
stays subject to owner review. ADR-001 stays `NOT DECIDED`.

### 3.5 Transport – local LiveKit media/room layer

Both arms used the same `livekit.rtc` 1.1.18 media layer and livekit-server v1.13.8:
join, publish/subscribe, room-scoped tokens, explicit dispatch, cleanup all `MEASURED`
(20/20 clean). SIP ingress, TURN/NAT, multi-node, 8 kHz codecs: `NOT_TESTED`.

**Decision: `PROVISIONAL ACCEPT` – LiveKit room/media layer as the shared transport for the
next gate** (local/dev scope only). Telephony (ADR-006) `NOT DECIDED`.

## 4. Security architecture

| Control | Evidence | Repeated across both runtime arms? |
|---|---|---|
| Trusted `CallContext` built server-side; never in model input | MEASURED: every gateway call used the identical context object; context unchanged | Yes – 5+5 comparison sessions per arm plus earlier E2E runs |
| Tool Gateway as the only business path | MEASURED: every calendar/CRM side effect accounted for by a gateway call (bypass invariant); structural tests | Yes |
| Tenant authority server-side, never from transcript/LLM | MEASURED: spoken tenant-switch injection → 0 tool calls, 0 foreign writes, tenant unchanged | Yes – 5/5 per arm (+ earlier runs) |
| Booking only after explicit confirmation; no false success | MEASURED: one write per happy path only after server readback + affirmation; success sentence only after authoritative result | Yes |
| `BOOKING_UNKNOWN` fail-closed, no blind rebooking | MEASURED offline (Phase 0 tests, LLM gate state cases) | No – not exercised through either runtime |
| Tenant isolation in PostgreSQL (RLS, FORCE RLS, non-owner role) | MEASURED (Phase 0, real PostgreSQL 18.6) | No – E2E used in-memory ledger and mocks |
| No direct runtime access to business authority | MEASURED: runtimes hold only `ServerBinding`; AST/import tests; Pipecat never gets server credentials | Yes (structure) |
| Secrets not in artifacts/logs | MEASURED: scans of all artifacts and logs, 0 hits | Yes |
| Network egress limited to the three providers + loopback | MEASURED: sandbox + audit hooks | Yes |
| No business action on interim/partial transcripts; barge-in never triggers a booking | MEASURED: turn-taking gate, every gateway execution after a committed final transcript (108/108 + diagnostic 10/10), 0 hard failures | Yes |

Security status: **no veto triggered in Phase 1** (Manus VETO-TENANT, -AUTH, -BOOK not
observed). This is not a proof of isolation at scale: real RLS through a runtime,
`BOOKING_UNKNOWN` through a runtime, suppression, recording policy are `NOT_TESTED`.

## 5. Open technical risks

| Risk | Class | Impact on next steps |
|---|---|---|
| Caller latency ~3.1 s p50 for non-tool turns, both arms (E15) vs PROPOSED 0.8 s | MEASURED | Product-critical; dominated by endpointing, full LLM response wait and serial pipeline, not by the runtime |
| Phone-number STT finalization ~5.8 s in the E2E path (E3) | MEASURED | Every contact collection turn; ~0.6 s with `Finalize` on VAD end in the turn-taking harness (E24), product adoption `NOT DECIDED` |
| `slot_a_1000` spoken in the slot readback (Phase 0 template renders `slot_id`) | OBSERVED | Caller-facing defect; product change needs approval |
| Goodbye turn ends with the fallback sentence (empty or guard-dropped model text) | OBSERVED (7 of 10 comparison runs) | Dialog quality |
| Half duplex in the E2E/comparison harness | OBSERVED (design) | Barge-in measured separately in the turn-taking gate (E22) |
| Premature turn ends with Pipecat defaults (34/54), late turn ends with LiveKit defaults (26/54) (E21) | MEASURED | Endpointing tuning per arm untested; digit and pause handling product-critical |
| Fixed-offset barge-in trigger can hit TTS pauses (E23) | MEASURED (test design) | Next barge-in measurements need a speech-relative trigger |
| Provider account limits (Cartesia 402 `quota_exceeded`, E25) | MEASURED (operational) | Monitoring, quota alerts and a fallback TTS path needed before any pilot |
| Real human speech not tested | NOT_TESTED | Entity accuracy unknown |
| 8 kHz / G.711 not tested | NOT_TESTED | STT accuracy on phone audio unknown |
| PSTN/SIP not tested | NOT_TESTED | T0 (Manus primary topology) missing; G0 legal/carrier open |
| Load not tested | NOT_TESTED | Capacity unknown |
| Cost model incomplete | NOT_TESTED | Tokens/characters partially recorded, no tariff evaluation |
| Runtime comparison only n = 5 | MEASURED limitation | Latency differences not resolvable |
| CPU measurement coarse (`ps`, whole process, decaying average) | OBSERVED limitation | Resource lead limited to RSS/startup |
| Pipecat WebSocket transport (T1) not tested | NOT_TESTED | Twilio/Telnyx media-stream path unknown |
| LLM alias without snapshot | OBSERVED | Reproducibility |

## 6. Decision register

| Question | Decision |
|---|---|
| ADR-001 Voice runtime | **`NOT DECIDED`**; provisional implementation path **`PROVISIONAL ACCEPT – Pipecat`** (LiveKit transport); LiveKit Agents = challenger (`CONTINUE EVALUATION`) |
| ADR-002 Voice architecture (cascade vs native) | **`NOT DECIDED`** – only the cascade was tested |
| ADR-003 STT | **`PROVISIONAL ACCEPT` – Deepgram `nova-3` `de`** as reference; provider binding `NOT DECIDED` |
| ADR-004 TTS | **`PROVISIONAL ACCEPT` – Cartesia `sonic-3.5-2026-05-04` / Nico** as reference; ElevenLabs `CONTINUE EVALUATION`; provider binding `NOT DECIDED` |
| ADR-005 LLM | **`PROVISIONAL ACCEPT` – `gpt-6-luna`, reasoning `low`** as reference; provider binding `NOT DECIDED` |
| Transport (local media/room layer) | **`PROVISIONAL ACCEPT` – LiveKit room/media layer** (local scope) |
| ADR-006 Telephony | **`NOT DECIDED`** |
| ADR-007 Workflow engine | **`NOT DECIDED`** (not in Phase 1 scope) |
| ADR-008 Tenant architecture | **`NOT DECIDED`** (shared PostgreSQL RLS has Phase 0 evidence; alternative not compared) |
| ADR-009 Hosting, ADR-010 Observability | **`NOT DECIDED`** |
| Security model (Trusted CallContext, Tool Gateway, server-side confirmation) | **`PROVISIONAL ACCEPT`** as mandatory architecture constraint – no veto observed; it is already a permanent project rule (CLAUDE.md), not a new decision |
| Server confirmation note | Harness behavior only; product adoption **`NOT DECIDED`** |

No component is `REJECT`ed. Roger is rejected as *voice*, not ElevenLabs as provider.
The turn-taking evidence (E20–E27, 2026-10-27/28) adds measurements but changes no entry in
this register: no ADR is accepted, runtime and providers stay `NOT DECIDED` as final
decisions, and turn-taking configuration (endpointing, Finalize policy, barge-in trigger)
is `NOT DECIDED`.

## 7. Next gate (exactly one)

**Status 2026-10-28: executed.** The turn-taking gate defined below ran on both arms
(E20–E23). A following gate is not defined in this document; it needs the owner's
decision.

**TURN-TAKING GATE: VAD, endpointing and barge-in** – on both runtime arms (Pipecat as
provisional path, LiveKit Agents as challenger), same local LiveKit media layer, same
reference providers, same harness and security invariants.

Why this gate next, from the evidence:

1. The largest **measured** gap is caller latency (E15: ~3.1 s p50 for non-tool turns,
   both arms) against the proposed 0.8 s target. Its measured parts – STT endpointing
   and finalization (E3) and the turn-end decision – belong to turn-taking; the runtime
   differences that matter (Pipecat VAD/interruption frames vs. LiveKit AgentSession
   turn detection) are exactly the untested area (section 3.4).
2. Barge-in (Manus AC-INT-01) and full duplex are `NOT_TESTED`; half duplex is a
   deliberate Phase 1 simplification that the product cannot keep.
3. It is executable now within the authorized local scope (synthetic audio, loopback,
   existing provider keys). The alternatives are blocked by open G0 items: PSTN/SIP needs
   carrier, DID, legal and budget approval; real human audio needs speaker/recording
   rights and retention policy.
4. A runtime decision without turn-taking evidence would rest on startup and memory only,
   which this gate explicitly avoids.

Not part of this gate (stay open): PSTN/SIP, real human audio, 8 kHz/G.711, load, cost,
native speech-to-speech, product fixes for `slot_a_1000` and the goodbye fallback.

## 8. ADR-001 draft (status: PROPOSED / PROVISIONAL)

> **ADR-001 – Voice Runtime (draft)**
> Status: **PROPOSED** (provisional implementation path), not ACCEPTED.
> Context: Phase 1 local loopback comparison with identical harness, providers, audio and
> security invariants (sections 2, 3.4).
> Decision (provisional): implement the next gate primarily on **Pipecat 1.12.0 with
> LiveKit transport**; keep **LiveKit Agents 1.8.3** as challenger arm under the same
> harness.
> Evidence: equal functional/security results (MEASURED); startup and process memory lead
> for Pipecat (MEASURED); room-scoped credentials (OBSERVED); latency INCONCLUSIVE;
> turn-taking: Pipecat `TURN_TAKING_VERIFIED`, LiveKit `INCONCLUSIVE` (test-design gap,
> TT13 diagnostic 5/5 both), opposite leads on false vs. late endpoints (MEASURED).
> Not covered: T0 SIP, real speech, endpointing tuning, load, lifecycle faults,
> observability, cost.
> Revisit when: owner review of the turn-taking evidence; any SIP/T0 evidence; any change
> of SDK version, provider, model or harness.
> Rejected alternative: none (`null`). Confidence: LOW.

## 9. Sign-off (empty)

| Checkpoint | Record | Status |
|---|---|---|
| ChatGPT review (consistency, no invented results) | `null` | pending |
| Human owner: provisional paths, next gate, criteria review | `null` | pending |
| Security/Legal veto review | `null` | pending |
