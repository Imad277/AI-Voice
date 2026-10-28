# Phase 2 – Target Architecture

**Status: PROPOSED.** No runtime, provider, carrier, workflow engine, hosting or framework
is selected here. Decisions: [PHASE2_DECISION_REGISTER.md](PHASE2_DECISION_REGISTER.md).
Project rules that constrain this design (CLAUDE.md): no microservices without an ADR, no
Kubernetes, no Temporal, n8n never in the realtime path and never an authority layer.

## 1. Repository assessment (state of `main` at 3126830)

### 1.1 Reusable product core (Phase 0) – keep, generalize, do not weaken

| Component | Location | Reuse | Generalization needed |
|---|---|---|---|
| Trusted `CallContext` | `core/context.py` | the authority object of every call | `calendar_ref`/`crm_ref` become a map of authorized integration bindings; `scopes` derived from the published agent version; add environment, deployment id |
| Tool request/result contracts, `Decision`/`Reason` | `core/tools.py` | as is | `ToolName` enum becomes a registry of platform tool types; reasons extended per tool family |
| Tool Gateway pipeline | `gateway/gateway.py` | the only path to side effects | data-driven tool registry instead of six hardcoded handlers; durable sessions (today an in-process dict) and durable audit (today an in-memory list); handlers call integration adapters instead of mocks |
| Strict schemas + authority-key screen | `gateway/schemas.py` | as is | schemas generated from tool type definitions; the qualification demo rule (`service_type`, `budget_eur >= 500`) is use-case specific and must become tenant configuration |
| Booking ledger, `BOOKING_UNKNOWN`, reconciliation, `BOOKED_CRM_PENDING` | `booking/`, `tenancy/ledger.py`, `db/migrations/0001` | the idempotent side-effect pattern | generalize to an **operation ledger** for every non-idempotent external write (booking, ticket, CRM upsert, SMS); keep "one semantic operation id per call + intent" and "negative lookup is never authoritative" |
| Per-call confirmation state | `booking/session.py` | readback revision + affirmation | confirmation policy configurable per data field/tool; `classify_reply` is a placeholder (decision D-21) |
| Speech guard | `booking/speech.py` | business statements only from templates keyed by gateway results | templates per language and tool family, tenant-overridable wording without overriding facts |
| RLS tenancy | `tenancy/db.py`, `preflight.py`, `db/` | transaction-local tenant binding, forced RLS, non-owner app role, preflight | extend to all new tables; add a narrow routing function for number→tenant resolution (see security doc) |
| Fail-closed config | `config.py` | pattern | live/recording switches become per-environment, per-tenant policies with explicit authorization |
| Negative security tests | `tests/unit`, `tests/postgres` | regression baseline | every new table and tool gets the same class of tests |

### 1.2 Reusable from Phase 1 (promote through hardening PRs, not by import)

**Boundary rule:** production code must never import `voiceos.benchmark.*`. A Phase 1
pattern enters the product only by a deliberate promotion PR that re-implements or copies
it into a product module with its own contract, tests and hardening; the benchmark code
itself stays unchanged evidence infrastructure. The table lists candidates, not decisions.

| Component | Location | Value | Before product use |
|---|---|---|---|
| Adapter ports (STT/LLM/TTS/runtime) | `benchmark/ports.py` | provider-agnostic seams | move to a product `ports` module; add metering, cancellation, health |
| Provider adapters Deepgram, OpenAI, Cartesia, ElevenLabs | `benchmark/providers.py` | working streaming integrations, lazy SDK import, safe errors | timeouts/retry budgets, credential broker instead of env keys, usage reporting, circuit breaker |
| `safe_provider_error`, `ProviderFailure`, session validity vocabulary | `benchmark/providers.py`, `turn_taking.py` | safe error capture | reuse as provider-error model in call telemetry |
| `GatewayBinding` (runtime holds only a binding, never the context) | `benchmark/binding.py` | least-privilege runtime boundary | becomes the data-plane gateway client |
| `VoiceAgentLoop.respond` (proposal → gateway → speech guard) | `benchmark/voice_loop.py` | proven turn orchestration | generalize tool rounds, streaming LLM, knowledge retrieval |
| Commit-only-from-final-transcript rule, cancel/rollback/carry of interrupted replies | `benchmark/turn_taking.py` (`TurnTakingAgent`) | barge-in safety | product turn manager |
| Runtime arms: Pipecat pipeline, LiveKit `AgentSession` bridges, room-scoped tokens | `benchmark/runtimes.py`, `turn_runtimes.py` | reference wiring for runtime adapter implementations | nothing promoted before D-01; both stay exchangeable implementations of the runtime adapter contract (section 2.2) |
| Server confirmation note (trusted state → model) | `benchmark/binding.py` | determinism after readback | product adoption NOT DECIDED (D-22) |
| Synthetic German datasets | `benchmarks/datasets/phase1/` | regression/eval suite | keep as offline evaluation set |
| SDK import boundary tests | `tests/unit/test_repo_hygiene.py` | dependency isolation | extend to product modules |

### 1.3 Benchmark-only infrastructure (stays in `voiceos.benchmark`)

STT/LLM/TTS/E2E/turn-taking gates, CLI, `ReferenceRuntime`/scenario runner, benchmark
result schemas and metrics, `synthetic_audio` (macOS `say`), `livekit_local` transport gate,
synthetic caller, `AuditedGateway`, evaluation code. Rule: product modules never import
`voiceos.benchmark`; the benchmark may import product modules (enforced by a hygiene test
in the first Phase 2 PR).

### 1.4 Missing SaaS components (new)

Identity and authentication, organizations/users/memberships/RBAC, API keys and service
accounts, control-plane API, web app, agent configuration and versioning, deployments and
environments, phone number inventory and routing, telephony adapter, call/turn/transcript
persistence, integration connections with OAuth and secret storage, tool registry, custom
webhook/HTTP tools with egress control, knowledge ingestion and retrieval, post-call
workflows and job processing, outbound webhooks, usage metering and rating, billing,
analytics, durable audit log, retention/export/deletion jobs, observability stack,
deployment pipeline and environments.

## 2. Architecture overview

A **modular monolith** (one codebase, one schema, module boundaries enforced by import
tests) deployed as a few **process roles**. This is not a microservice split; scaling
happens per role.

```text
                       ┌───────────────────────── Control Plane ─────────────────────────┐
 Browser / API client  │  Web App ── Public API (REST, OpenAPI) ── AuthN/AuthZ (RBAC)     │
 ─────────────────────▶│  Orgs · Users · Agents · Versions · Deployments · Numbers ·      │
                       │  Integrations · Tools · Knowledge · Workflows · Usage · Billing  │
                       │  Audit · Webhook subscriptions                                    │
                       └──────────────┬──────────────────────────────▲────────────────────┘
                                      │ publish: immutable agent     │ call records, events,
                                      │ version + deployment         │ usage, outcomes
                                      ▼                              │
 PSTN / SIP ─▶ Telephony adapter ─▶ ┌──────────────────── Data Plane (Voice) ──────────────┐
 Browser test call (WebRTC) ──────▶ │ Call Router (number → tenant/deployment, server-side) │
                                    │ Session Manager: builds trusted CallContext,          │
                                    │   issues call-scoped runtime token                    │
                                    │ Voice Runtime (runtime adapter; impl. not selected)   │
                                    │   STT ─ turn manager ─ LLM orchestration ─ TTS        │
                                    │   holds only a GatewayBinding                         │
                                    │ Tool Gateway (allowlist·schema·authz·policy·ledger)   │
                                    │   ─▶ Integration adapters (credential broker)         │
                                    └──────────────┬────────────────────────────────────────┘
                                                   │ durable events (outbox)
                                                   ▼
                       ┌────────────────────── Async / Job Workers ──────────────────────┐
                       │ post-call workflows · reconciliation · CRM sync · webhooks ·     │
                       │ knowledge ingestion · usage rating · retention/deletion · export │
                       └─────────────────────────────────────────────────────────────────┘
 Shared: PostgreSQL (RLS) · object storage · secret store · metrics/logs/traces
```

### 2.1 Process roles (same codebase)

| Role | Responsibility | Scales by |
|---|---|---|
| `api` | control-plane API, web app backend, auth, configuration, read models | requests |
| `voice` | call routing, session manager, runtime, Tool Gateway, provider adapters | concurrent calls |
| `worker` | jobs from the outbox/queue: workflows, reconciliation, webhooks, ingestion, rating, retention | queue depth |
| `media` (external component) | WebRTC/SIP media server behind the media session contract (not selected, D-14; LiveKit was the Phase 1 test setup) | concurrent calls |

### 2.2 Stable contracts (runtime-, media- and carrier-agnostic)

Phase 2A builds against these contracts. LiveKit Agents, Pipecat, any media server and any
carrier/CPaaS are exchangeable implementations; none is selected by this document.

| Contract | Responsibility | Guarantees |
|---|---|---|
| **Session Manager** | turns an authenticated call request (inbound route, test call, later outbound) into a call: resolves deployment and agent version, builds the trusted `CallContext`, opens the gateway session, creates the call record, issues the call-scoped runtime token, closes and finalizes the call | the only producer of `CallContext`; tenant from server-side routing/auth only |
| **Runtime Adapter** | runs one call session: audio in/out, turn handling, STT/LLM/TTS orchestration, barge-in; emits timed events | receives a `GatewayBinding` and published config, never the `CallContext`, DB credentials or other tenants' data; commits turns only from final transcripts |
| **Media Session** | joins/leaves the media transport for one call (WebRTC room, SIP bridge, media stream), provides audio frames, hangup, transfer hooks | call-scoped credentials only; no business logic |
| **Telephony Adapter** | carrier/SIP/CPaaS events normalized to platform events (incoming call with verified dialed number, DTMF, hangup, transfer result, CDR), number provisioning operations | dialed number is the routing key; caller data untrusted; signatures verified |
| **Provider ports** (STT, LLM, TTS, later embeddings) | streaming recognition, model responses with tool proposals, synthesis | timeouts, cancellation, safe errors, usage reporting; credentials via broker |
| **GatewayBinding** | the runtime's only path to business actions: submit proposals, record caller replies, read authoritative results | bound to one call; cannot change tenant, scopes or bindings |
| **Credential Broker** | resolves `credential_ref` → secret for one adapter execution | secret never returned to runtime or model, never logged |

### 2.3 Ownership: control plane vs. data plane

| Control plane owns | Data plane owns |
|---|---|
| configuration (agents, drafts, versions, deployments, tools, knowledge, workflows) | call sessions and their lifecycle |
| user authority (authentication, memberships, RBAC, API keys) | audio transport and media sessions |
| agent publishing and rollback | STT / LLM / TTS execution |
| integration setup and credential **references** | turn handling and barge-in |
| phone number inventory and routing configuration | tool proposals and Tool Gateway execution |
| billing and usage views, audit views | runtime events, call records, usage events |

The data plane reads only published, immutable configuration and never edits it. The voice
runtime never takes tenant authority from the model, the caller, the client (browser or
API payload) or webhook content.

## 3. Control plane

Owns configuration and administration. Never in the realtime audio loop.

| Area | Objects |
|---|---|
| Identity | organizations (tenants), users, memberships, roles/permissions, API keys, service accounts |
| Agents | agents (draft), agent_versions (immutable, published), deployments (environment → version), test runs |
| Telephony | phone_numbers, agent_phone_bindings, routing rules, business hours, caller-ID settings |
| Providers | provider configurations per agent version (references to platform-managed or tenant-supplied credentials) |
| Integrations | integration connections, credential references, tool instances, egress allowlists |
| Knowledge | sources, versions, ingestion jobs |
| Workflows | post-call workflow definitions and versions |
| Environments | `development` / `production` per agent (staging later); deployment states |
| Commercial | usage, plans/subscriptions, billing references |
| Governance | audit events, retention policies, data export/deletion requests |

**Publish flow:** draft config → validation (schema, tools authorized, credentials present,
knowledge indexed) → immutable `agent_version` with content hash → `deployment` binds a
version to an environment → phone binding points at the deployment. Calls always run a
specific version; rollback = rebind to an older version.

## 4. Data plane (voice)

Owns realtime execution. Reads published, immutable configuration; writes call records and
events. It never edits configuration.

| Step | Responsibility | Trust rule |
|---|---|---|
| Ingress | carrier/SIP or WebRTC test call arrives | caller ID and SIP headers are untrusted data |
| Routing | dialed number (carrier-verified) → `phone_number` → deployment → tenant | tenant comes from routing table lookup, never from caller input |
| Session setup | build trusted `CallContext` (tenant, call, agent version, scopes, integration bindings, policies); open gateway session; issue call-scoped runtime token | only server code builds the context |
| Runtime | audio transport, VAD/turn detection, STT, LLM, TTS, barge-in | runtime receives a `GatewayBinding`, not the context, no DB or provider-admin credentials |
| Turn manager | commit turns only from final STT; cancel/rollback interrupted replies | no tool proposal from partial text |
| LLM orchestration | prompt assembly from version config + knowledge snippets; tool schemas exposed | knowledge and caller text are untrusted content |
| Tool execution | proposal → Tool Gateway → integration adapter via credential broker → authoritative result | operation ledger for non-idempotent writes |
| Speech | business statements via templates; model text guarded | no success claim before authoritative result |
| Lifecycle | hangup, transfer, timeout, failover, recording policy | recording off unless tenant policy + consent allow it |
| Telemetry | timed events (Phase 1 vocabulary), usage events, provider failures | no transcript text in technical logs |

Failover (PROPOSED): provider failure classified as in Phase 1 (`INVALID_PROVIDER_FAILURE`
becomes a call event); per agent a configured fallback (second TTS/STT provider or a
graceful "transfer/voicemail/callback" path). Never silent continuation with a broken
component.

## 5. Agent configuration layer

See [PHASE2_DOMAIN_MODEL.md](PHASE2_DOMAIN_MODEL.md#agent-configuration). An agent version
is a validated, immutable document: identity (name, description), language, voice
(provider + voice id), system instructions, personality, opening message, conversation
goals, allowed tools (each bound to an integration connection), knowledge sources, data
collection schema (typed fields with confirmation policy), escalation and fallback rules,
business hours, success criteria, compliance settings (recording, disclosure text,
retention), provider configuration, version and environment. Templates ("blank",
"appointment booking", "lead qualification", "support triage") prefill this document; they
are data, not code.

## 6. Tool and integration platform

### 6.1 Operation ledger (safety boundary for external side effects)

Every irreversible or external side effect (booking, ticket, CRM write, message, custom
webhook with `non_idempotent_write`) goes through the gateway **and** the operation ledger,
generalized from the Phase 0 booking ledger:

| Property | Rule |
|---|---|
| Idempotency | one operation id per semantic operation (tenant, call or workflow run, tool instance, intent); a second claim never creates a second side effect; payload hash detects a changed intent |
| States | `PENDING` (claimed, nothing sent) → `SUBMITTED` (sent, outcome not yet known) → `CONFIRMED` (authoritative success) / `FAILED` (authoritative refusal, proven no side effect) / `UNKNOWN` (timeout, lost response, ambiguous result) |
| Retry policy | automatic retry only from `PENDING`, or where the external API guarantees idempotency by our key; never from `UNKNOWN`; `FAILED` allows a new attempt only as a new, explicitly confirmed intent |
| Reconciliation | `UNKNOWN` resolves only by an authoritative lookup finding the operation with the same payload, or by an audited manual resolution; a negative lookup is not proof (Phase 0 rule) |
| Audit trail | every transition is an append-only row with cause and actor |
| Speech/outcome | success is stated only after `CONFIRMED`; dependent sync failures after confirmation are separate states (Phase 0 `BOOKED_CRM_PENDING` pattern) |

Workflows and jobs are clients of the gateway and the ledger like the runtime: a job retry
re-enters the ledger with the same operation id. No workflow engine, worker or automation
tool may call an integration adapter directly.

### 6.2 Tools and integrations

| Layer | Purpose |
|---|---|
| **Tool type** (platform-defined, global) | stable capability with typed input/output schema, side-effect class (`read`, `idempotent_write`, `non_idempotent_write`), confirmation policy, speech templates. Examples: `calendar.list_slots`, `calendar.book_slot`, `crm.upsert_contact`, `crm.log_call`, `helpdesk.create_ticket`, `message.send_sms`, `message.send_email`, `knowledge.search`, `call.transfer`, `call.end`, `webhook.invoke` |
| **Integration provider** (adapter) | implementation of one or more tool types for one external system (Google Calendar, Microsoft 365, Cal.com; HubSpot, Salesforce, Pipedrive; Zendesk, Freshdesk; SMTP/email API; SMS provider). Provider choice NOT DECIDED; none implemented in Phase 2A |
| **Integration connection** (tenant) | OAuth grant or API credential reference + configuration (which calendar, pipeline, mailbox) |
| **Tool instance** (tenant, per agent version) | tool type bound to a connection with tenant parameters (e.g. slot length, default owner) |

Custom tools: `webhook.invoke` / `http.request` with a tenant-defined JSON schema, signed
requests, HTTPS only, egress allowlist per tenant, SSRF protection (no private/link-local
ranges, DNS rebinding check), response size/time limits, no authority fields in model
arguments, side-effect class declared by the tenant (non-idempotent requires confirmation
policy + idempotency key header). Database-safe internal tools (contacts, notes, callbacks)
write only to VoiceOS tables through the gateway.

## 7. Workflow layer (PROPOSED, D-07)

No visual workflow builder in 2A or 2B. 2B needs only typed domain events, the outbox, jobs,
declarative post-call actions and defined state machines.

| Option | Fit | Status |
|---|---|---|
| Domain state machines in code (call, operation ledger, booking, ticket) | already proven in Phase 0; deterministic, testable | keep – always |
| **Transactional outbox + PostgreSQL-backed job queue** (`SELECT … FOR UPDATE SKIP LOCKED`, retries with backoff, idempotency keys, dead-letter) | durable post-call steps without new infrastructure; EU-hostable; fits RLS | **proposed default for 2A/2B** |
| Dedicated broker (e.g. NATS, RabbitMQ, Redis streams) | higher throughput, fan-out | only on measured need |
| Temporal | durable orchestration | excluded by project rule 28 unless the owner changes the rule |
| n8n / external automation | customer-side automation via our outbound webhooks | allowed only as an untrusted **consumer** of signed webhooks; never authority, never realtime |

Tenant-facing "workflows" in 2B are a small set of typed post-call actions (send summary
email, push to CRM, create ticket, call webhook) with conditions on outcome fields – not a
general node editor.

## 8. Knowledge platform (PROPOSED, D-11, D-26)

| Capability | 2A | 2B | 2C |
|---|---|---|---|
| Sources | – | text, FAQ, PDF upload, single URL | website crawl (bounded), API source, connectors (e.g. Google Drive / Notion / Confluence) only on customer demand |
| Ingestion | – | parse → normalize → chunk → embed, as worker jobs; manual refresh (re-ingest as new version) | scheduled refresh, change detection |
| Storage | – | source versions in object storage; chunks + embeddings in PostgreSQL (vector extension) under RLS | dedicated vector store only on measured need |
| Retrieval | – | `knowledge.search` as a read tool through the gateway, filtered by tenant and the agent version's sources; top-k with score threshold | hybrid search, re-ranking |
| Provenance | – | every chunk → source version → source; call turns record which chunks were used | citations in the call detail UI |
| Versioning | – | agent versions pin source versions or "latest" explicitly | |
| Delete / GDPR | – | deleting a source deletes versions, chunks, embeddings and objects | |
| Safety | – | knowledge content is untrusted data: never instructions with authority, never tool arguments without schema validation | injection detection |

Needed for the first sellable version: text/FAQ/PDF/URL with provenance and deletion.
Everything else waits for customer evidence.

## 9. Cross-cutting

- **API:** REST + OpenAPI (D-17), versioned (`/v1`), idempotency keys on mutating
  endpoints, cursor pagination, the web app uses the same API.
- **Events:** domain events (`call.started`, `call.completed`, `tool.executed`,
  `outcome.recorded`, `agent.published`, …) written to an outbox in the same transaction as
  the state change; consumed by workers and the outbound webhook dispatcher.
- **Storage:** PostgreSQL for all state (RLS); object storage for recordings, uploads and
  exports (tenant-prefixed keys, server-side encryption, signed URLs); vector index in
  PostgreSQL first (D-11).
- **Security, tenancy, metering, observability, telephony:** see the dedicated documents.

## 10. Deployment and infrastructure (PROPOSED, D-09)

| Environment | Purpose | Rules |
|---|---|---|
| `local` | developer machine, docker compose (PostgreSQL, a local media server when the voice worker exists, object storage emulator) | no real PSTN, recording off, synthetic data |
| `staging` | integration with real providers on test tenants, test numbers | explicit authorization, synthetic data, separate credentials |
| `production` | customers | EU region, separate accounts/keys, change control |

Components: container images for `api`, `voice`, `worker`; managed PostgreSQL (EU) with
PITR; S3-compatible object storage (EU); secret manager/KMS (D-16); media server behind the
media session contract (D-14; if LiveKit is self-hosted multi-node it needs Redis, which is
then a media-layer dependency, not an application queue); metrics/logs/traces via OpenTelemetry
(D-10). Orchestration without Kubernetes (rule 27): a managed container platform or VMs
with a simple scheduler; voice nodes scale horizontally on concurrent calls with drain on
deploy. Region strategy: single EU region first (data residency), provider data paths
checked per provider (EU endpoints where available), multi-region later.

## 11. Architecture risks

| Risk | Mitigation |
|---|---|
| Benchmark code leaks into product | promotion only via hardening PRs; hygiene test product ↛ `voiceos.benchmark.*` |
| Early runtime/media/carrier lock-in | 2A builds only against the contracts in 2.2; implementations selected per D-01/D-06/D-14 when the voice worker and telephony PRs need them |
| Latency (~3 s p50 measured, E15) far above a conversational target | streaming LLM to TTS, sentence-level TTS, endpointing tuning, prompt size discipline; measure per release |
| Endpointing trade-off (Pipecat false endpoints vs. LiveKit late endpoints, E21) | per-agent turn settings, digit/phone collection mode, evaluation suite before release |
| Provider outage/quota (Cartesia 402, E25) | provider health checks, quota alerts, fallback provider or graceful degradation |
| RLS gaps in new tables | preflight extended; table-level tests mandatory per migration |
| Custom HTTP tools as SSRF/exfiltration path | egress policy, allowlists, response limits, no secrets in model context |
