# Phase 2 – Observability, Metering and Billing

**Status: PROPOSED.** Observability stack (D-10) and billing provider (D-19) are NOT
DECIDED. No pricing plan is defined here; only what must be measured.

## 1. Principles

- One event vocabulary from the realtime path to analytics: the Phase 1 timed events
  (`USER_AUDIO_START/END`, `VAD_START/END`, `STT_INTERIM/FINAL`, `TURN_COMMITTED`,
  `TRANSCRIPT_READY`, `LLM_REQUEST_START`, `LLM_FIRST_OUTPUT`, `LLM_DONE`, `TOOL_PROPOSAL`,
  `TOOL_EXEC_START/END`, `TTS_REQUEST_START`, `TTS_FIRST_AUDIO`, `TTS_DONE`,
  `FIRST_ASSISTANT_AUDIO_PUBLISHED`, `INTERRUPTION_DETECTED`, `AUDIO_STOP_REQUESTED`,
  `REPLY_CANCELLED`, …) become `call_events`.
- **No content in technical telemetry:** logs, metrics and traces carry ids, codes,
  durations and counts – never transcript text, contact data, tool arguments or secrets.
  Content lives only in retention-controlled content tables.
- Every signal carries `tenant_id`, `agent_id`, `agent_version_id`, `environment`,
  `call_id` where applicable (cardinality-aware: tenant/agent as attributes in traces and
  logs, aggregated in metrics).
- Provider failures use the safe model from Phase 1: component, provider, error class,
  HTTP status, provider code.

## 2. Signals

| Signal | Use | Proposal |
|---|---|---|
| Structured logs | debugging, security events | JSON, correlation ids (`trace_id`, `call_id`), redaction filter with tests |
| Traces | per-call and per-request latency breakdown | OpenTelemetry spans: call → turn → STT/LLM/TTS/tool spans |
| Metrics | dashboards, alerts, SLOs | OpenTelemetry metrics exported to an EU-hostable backend |
| Call events | product analytics, call timeline UI | `call_events` table (append-only) |
| Audit log | who did what | `audit_events` (append-only), separate from technical logs |
| Usage events | metering and billing | `usage_events` (append-only, idempotent) |

## 3. Metrics catalog

| Group | Metrics |
|---|---|
| Call | calls started/answered/completed/failed, duration, end reason, concurrent calls, setup time, abandonment, transfer rate |
| Turn / latency | end of user speech → VAD end, → turn commit (endpoint latency), → STT final, → first LLM output, → first TTS audio, → first audio heard (caller latency); p50/p95 per agent version |
| Turn-taking | false endpoint rate, late endpoint rate, barge-in count, interruption detection latency, TTS stop latency, cancelled replies |
| STT | audio seconds, finalize delay, error rate, empty transcripts |
| LLM | requests, input/output tokens, first-token latency, total latency, tool proposals per turn, invalid proposals, refusals |
| TTS | characters, first-audio latency, synthesis failures, truncation |
| Tools | executions by tool type and decision (`EXECUTED`/`REJECTED` + reason), latency, `UNKNOWN` operations open/age, reconciliation outcomes, integration error rates |
| Outcome | outcome codes, success rate vs. success criteria, data fields completed/confirmed, conversion (lead → appointment) |
| Provider health | availability, error rate by provider and error code (e.g. 402 `quota_exceeded`), latency drift, quota usage vs. limits |
| Cost | provider cost per call/minute (rated), margin per call, cost per outcome |
| Platform | API latency/error rate, job queue depth/age, webhook delivery success, DB pool saturation, RLS preflight status |

Alerts (initial): provider error rate or quota errors, open `UNKNOWN` operations older than
a threshold, call setup failures, caller latency regression per version, job queue age,
webhook failure rate, security events (failed logins, permission denials spikes).

## 4. Metering

Everything billable or cost-relevant is written as a **usage event** at the point where it
is authoritative, with an idempotency key so retries never double count.

| Usage type | Unit | Source | Notes |
|---|---|---|---|
| `call.minutes` | seconds (billing rounding later) | call ended event | split by direction, environment (test calls flagged), number type |
| `stt.audio` | seconds | STT adapter | per provider/model |
| `llm.tokens` | input/output/cached tokens | LLM adapter | per provider/model |
| `tts.characters` | characters (and seconds of audio) | TTS adapter | per provider/model/voice |
| `telephony.minutes` | seconds per leg | carrier events/CDR | inbound/outbound/transfer legs, destination class |
| `phone_number.days` | number-days | daily job | per number type/country |
| `recording.storage` | GB-days | daily job | only if recording enabled |
| `knowledge.storage` / `knowledge.embeddings` | bytes / tokens | ingestion | |
| `sms` / `email` | messages | messaging adapter | |
| `api.requests` | requests | API gateway | for fair-use limits |
| `seats` | members | membership changes | |

Rating (PROPOSED): versioned `rate_cards` hold provider cost and platform price per unit;
a worker rates usage events into `usage_rollups` (per tenant/day/agent). Invoices are
produced by the billing provider from rolled-up quantities; VoiceOS stores external
invoice references only.

Billing model building blocks (no plan defined): subscription with included minutes,
metered overage, phone numbers as add-ons, seats, optional add-ons (recording, extra
knowledge, premium voices), API usage limits, provider-cost pass-through vs. bundled
pricing, platform margin = price − rated provider cost.

Requirements: usage visible to the customer near real time; spend caps and alerts per
organization; test-call usage separated; reconciliation of carrier CDRs against call
records; no billing decision based on unconfirmed data.
