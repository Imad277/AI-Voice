# Phase 2 – Domain Model

**Status: PROPOSED.** Logical model only. No migration is implemented by this document;
table names are working names. Every tenant-owned table carries `tenant_id` and uses the
Phase 0 pattern (RLS enabled **and forced**, `tenant_isolation` policy on
`tenant_id = voiceos.current_tenant_id()`, non-owner app role, no `BYPASSRLS`).

Legend: **T** = tenant-scoped (RLS), **G** = global platform data (no tenant rows, read-only
for the app role or served through a narrow function), **A** = append-only (app role has no
`UPDATE`/`DELETE`; corrections are new rows), **PII** = may contain personal data,
**S** = must never hold secrets (references only).

## 1. Identity and organization

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `organizations` | T (row = tenant) | `tenant_id` PK, name, slug, region, status, plan_ref, data_retention_policy | evolves from Phase 0 `tenants`; created only by the signup service (privileged path) |
| `users` | G (identity) | `user_id`, email (PII), name (PII), auth_subject, status | global identity because one person can belong to several organizations; **documented RLS exception**: readable only as self or via membership join through a security-definer view |
| `organization_memberships` | T | `tenant_id`, `user_id`, role, status, invited_by | tenant authority for web/API sessions is derived from here server-side |
| `roles` | G | role key, description | fixed system roles in 2A (Owner, Admin, Developer, Operator, Analyst, Billing, ReadOnly) |
| `role_permissions` | G | role key, permission key | permission catalog, versioned with the code |
| `invitations` | T, PII | email, role, token_hash, expires_at | token stored hashed only |
| `api_keys` | T, S | key_id, prefix, **hash**, scopes, created_by, expires_at, last_used_at | the secret is shown once; only a hash is stored |
| `service_accounts` | T | principal for integrations/automation | owns API keys; no interactive login |
| `teams` / `locations` (2B/2C) | T | grouping for agents, numbers, analytics | optional scoping of permissions later |

## 2. Agents and releases

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `agents` | T | agent_id, name, description, status, current_draft (JSON, validated) | mutable draft |
| `agent_versions` | T, A | agent_version_id, agent_id, version_no, config (JSON), config_hash, created_by, created_at, validation_report | **immutable** snapshot used by calls; `CallContext.agent_release_id` points here |
| `agent_deployments` | T | deployment_id, agent_id, environment (`development`/`production`), agent_version_id, state (`active`/`paused`/`draining`), activated_at | changing the version = new row + state switch; history kept |
| `agent_templates` | G | template_id, vertical tag, config skeleton, version | data, not code; tenants copy into their draft |
| `provider_configurations` | T, S | per agent version: stt/llm/tts/runtime provider keys, model ids, voice id, credential_ref (platform-managed or tenant BYO) | referenced from the version config |

### Agent configuration

Validated document stored in `agents.current_draft` and frozen in `agent_versions.config`:

| Section | Fields |
|---|---|
| Identity | name, description, internal notes |
| Language & voice | language(s), TTS provider + voice id, speaking rate, pronunciation lexicon |
| Behavior | system instructions, personality, opening message, closing message, disclosure text ("you are speaking with an AI assistant") |
| Goals | conversation goals (ordered), success criteria (which outcome fields must be filled / which tool result counts as success) |
| Data collection schema | typed fields (`text`, `name`, `phone`, `email`, `date`, `datetime`, `number`, `enum`, `address`, `boolean`), required/optional, validation, **confirmation policy** (none / readback / readback + explicit affirmation), PII flag |
| Tools | allowed tool instances (tool type + integration connection + parameters); per tool: confirmation policy, max executions per call |
| Knowledge | knowledge source ids + retrieval settings |
| Routing & hours | business hours (time zone, weekly schedule, holidays), out-of-hours behavior, escalation rules (keywords/intents/outcome conditions → transfer number or callback), fallback rules (provider failure, no answer, repeated misunderstanding) |
| Turn-taking | endpointing profile (default / digit-friendly / patient), barge-in on/off, max silence, max call duration |
| Compliance | recording mode (off by default), consent prompt, retention override (≤ org policy), PII redaction settings |
| Post-call | workflow ids, webhook subscriptions, summary generation on/off |

No field may name a customer or encode vertical logic; vertical behavior is expressed with
goals, data fields, tools and templates.

## 3. Telephony

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `phone_numbers` | T, S | number_id, e164 (globally unique), country, capabilities, carrier_provider, carrier_ref, status, regulatory_bundle_ref | e164 uniqueness is platform-wide |
| `number_routes` | G-function | e164 → tenant_id, deployment_id | resolved by a narrow `SECURITY DEFINER` function owned by a dedicated router role that returns only the route for one dialed number; this is where inbound tenant authority originates |
| `agent_phone_bindings` | T | number_id, agent_id, environment, active_from, active_to | history kept |
| `business_hours` | T | inline in agent config in 2A; separate table when shared across agents (2B) | |
| `routing_rules` | T | escalation/transfer targets, caller-ID policy | transfer targets validated (no premium/international without permission) |
| `sip_trunks` (2C, BYOC) | T, S | trunk config + credential_ref | |

## 4. Integrations and tools

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `tool_types` | G | key (`calendar.book_slot`…), input/output schema, side-effect class, default confirmation policy, template keys | versioned with code |
| `integration_providers` | G | key (`google_calendar`…), supported tool types, auth method | catalog |
| `integrations` (connections) | T | connection_id, provider key, display name, config (non-secret), status, health | |
| `integration_credentials` | T, **S** | connection_id, **credential_ref** (secret-store path/version), scopes granted, expires_at, rotated_at | **never** access/refresh tokens, API keys or passwords in this table |
| `tool_instances` | T | tool type + connection + parameters, agent version usage | |
| `custom_tools` | T | name, JSON schema, endpoint URL (validated against egress allowlist), signing secret **ref**, side-effect class | |
| `egress_allowlists` | T | allowed hosts per tenant | SSRF control |

## 5. Knowledge

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `knowledge_sources` | T | source_id, type (text/faq/pdf/url/website/upload/api), title, status, refresh policy | |
| `knowledge_source_versions` | T, A | version_id, content hash, object storage key, ingested_at, parser version | provenance |
| `knowledge_chunks` | T, PII? | chunk_id, version_id, text, position, embedding (vector), embedding model | deleted with the source version (GDPR) |
| `ingestion_jobs` | T | status, error class, counts | |

## 6. Calls and conversations

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `calls` | T, PII | call_id, direction, number_id, deployment_id, agent_version_id, caller e164 (PII), started/answered/ended_at, end_reason, environment, test flag | one row per call; state machine `ringing → active → ended` |
| `call_events` | T, A | call_id, seq, t_ms, source, name, attrs (no transcript text) | Phase 1 `TimedEvent` vocabulary; technical timeline |
| `call_turns` | T, A, PII | call_id, turn_no, role (caller/agent), committed text, final/interrupted flags, timings | content data, retention-controlled |
| `transcripts` | T, PII | call_id, assembled transcript ref (DB or object storage), redaction state | derived from turns |
| `recordings` (2B, policy) | T, PII | call_id, object key, consent evidence ref, retention_until | only if recording policy + consent allow |
| `tool_executions` | T, A, PII | call_id, proposal_id, tool type, decision, reason, outcome, operation_id, latency, arguments **hash** (+ redacted copy only if policy allows) | durable successor of the in-memory `AuditRecord` |
| `operations` (operation ledger) | T | (tenant_id, operation_id) PK, call_id or workflow_run_id, tool type, connection_id, payload_hash, state (`PENDING`/`SUBMITTED`/`CONFIRMED`/`FAILED`/`UNKNOWN`), retry_policy, attempts, external_ref, dependent sync states | generalization of `booking_operations` (Phase 0 `REJECTED` = `FAILED`: authoritative refusal, no side effect); idempotency key; automatic retry only from `PENDING` or with provider-side idempotency, never from `UNKNOWN`; `UNKNOWN` only resolved by authoritative lookup or audited manual resolution (target architecture §6.1) |
| `operation_transitions` | T, A | operation_id, from, to, cause, at | reconciliation history |
| `call_outcomes` | T, PII | call_id, outcome code, success flag, collected data (typed, per schema), summary, sentiment (later) | the business result of the call |
| `provider_failures` | T, A | call_id, component, provider, error_class, http_status, provider_code | Phase 1 `ProviderFailure` model |

## 7. Business records

| Table | Scope | Key fields | Notes |
|---|---|---|---|
| `contacts` | T, PII | contact_id, name, phones, emails, source call, external CRM refs, consent flags | dedupe per tenant |
| `leads` | T, PII | lead_id, contact_id, status, qualification data, owner | |
| `appointments` | T, PII | appointment_id, contact_id, calendar connection, external event ref, start/end, status, operation_id | mirrors authoritative calendar result |
| `tickets` (2B/2C) | T, PII | ticket_id, helpdesk ref, status, operation_id | |
| `callbacks` / `tasks` | T, PII | follow-ups for humans | |
| `suppression_list` (before outbound) | T, PII | e164, reason, source, created_at | consent/suppression gate for outbound |

## 8. Workflows and events

| Table | Scope | Notes |
|---|---|---|
| `workflows`, `workflow_versions` | T | typed post-call actions with conditions; versions immutable |
| `workflow_runs`, `workflow_steps` | T | state per run, attempts, errors (class only) |
| `outbox_events` | T, A | domain events written in the same transaction as the state change |
| `jobs` | T | queue table (`SKIP LOCKED`), idempotency key, attempts, next_run_at, dead-letter flag |
| `webhook_subscriptions` | T, S | URL (egress-validated), events, signing secret **ref** |
| `webhook_deliveries` | T, A | attempt log, status code, latency; payload not stored or stored redacted |

## 9. Usage, billing, governance

| Table | Scope | Notes |
|---|---|---|
| `usage_events` | T, A | metered quantities with idempotency key (see metering doc) |
| `rate_cards` | G, A | provider cost and platform price versions |
| `usage_rollups` | T | derived daily/monthly aggregates |
| `subscriptions` | T | plan ref, status, period, external billing ref |
| `invoices` | T | external invoice ref, period, totals; documents stay at the billing provider |
| `audit_events` | T, A | actor (user/api key/service/system), action, target, result, ip hash, at; no payloads |
| `data_requests` | T | export/deletion requests and their execution state |
| `retention_policies` | T | per data class retention; enforced by jobs |

## 10. Rules derived from the model

1. **Default: tenant-scoped + RLS.** Every new Phase 2 table is tenant-owned, carries
   `tenant_id`, has RLS enabled and forced, and is covered by the preflight, unless it is
   listed as a deviation below. Global tables (G) are read-only for the app role.
2. **Privileged entry points are narrow functions, not broad roles,** each owned by a
   dedicated role and covered by negative tests: signup (creates an organization), number
   routing (dialed number → route), user self-lookup, **"my memberships"** (list the
   organizations of the authenticated user before a tenant is bound), **invitation
   acceptance** (token hash lookup before membership exists), **job claiming and outbox
   dispatch** (returns one job with its tenant id; processing then runs in a normal
   tenant-bound transaction), retention/deletion jobs.
3. **Append-only** for evidence: `agent_versions`, `call_events`, `call_turns`,
   `tool_executions`, `operation_transitions`, `provider_failures`, `outbox_events`,
   `webhook_deliveries`, `usage_events`, `rate_cards`, `audit_events`. Deletion for GDPR is
   performed by a separate retention role through audited jobs, not by the app role.
4. **Secrets never in normal tables:** OAuth access/refresh tokens, API keys of
   integrations, SIP credentials, webhook signing secrets and provider keys live in the
   secret store; tables hold `credential_ref` only. Our own API keys and invitation tokens
   are stored as hashes.
5. **PII minimization:** technical tables (`call_events`, `provider_failures`, logs) hold
   no transcript text or contact data; content tables are retention-controlled.
6. **Immutability for reproducibility:** a call references exactly one `agent_version`;
   analytics can always explain which configuration produced a result.

## 11. Deviations from the tenant-scoped default

| Table / object | Scope | Justification |
|---|---|---|
| `organizations` | T, row = tenant | the tenant itself; created only through the signup function |
| `users` | G with RLS exception | one identity can belong to several organizations; visible only as self or through the membership view; no tenant data stored on it |
| `roles`, `role_permissions` | G | fixed permission catalog shipped with the code |
| `agent_templates` | G | platform-provided starting points; tenants copy them into tenant-owned drafts |
| `tool_types`, `integration_providers` | G | capability and adapter catalog shipped with the code |
| `number_routes` | G-function | inbound routing must resolve a dialed number before a tenant is known; exposed only through the router function returning one route |
| `rate_cards` | G, A | platform cost/price versions; tenant usage is rated into tenant-owned rollups |

Everything else in this model – including memberships, agents, versions, deployments,
integrations, credentials references, calls, events, turns, operations, usage, audit,
knowledge, workflows, jobs and outbox – is tenant-scoped with RLS.
