# Phase 2 – Build Plan

**Status: PROPOSED.** Concrete build order for Phase 2A and the start of 2B. Each step is
one reviewable PR (or a small series) with tests first. No PR weakens a Phase 0 invariant;
every PR keeps the full suite (unit + PostgreSQL/RLS) and CI parity green.

## 1. Working rules

1. **Product first.** A spike or benchmark is allowed only when it blocks a named decision
   in the register; the PR description names the decision and the evidence it produces.
2. **Promotion, not import.** Production code never imports `voiceos.benchmark.*`. A useful
   Phase 1 pattern is promoted by a dedicated PR that re-implements or copies it into a
   product module with its own contract, hardening (timeouts, credential broker, metering,
   safe errors) and tests; the benchmark code stays unchanged. A hygiene test (PR-1)
   enforces the direction.
3. **Contracts before implementations.** Runtime, media, telephony and speech providers are
   built against stable contracts; a concrete implementation is a separate PR that is the
   only thing blocked by the corresponding decision.
4. **Migrations with RLS tests.** Every migration that adds a tenant table adds: RLS
   enabled + forced, policies, grants, preflight coverage, and the standard negative tests.
5. **Gateway and ledger first for side effects.** No module – runtime, worker, workflow –
   writes to an external system except through a tool handler behind the gateway and the
   operation ledger.
6. **No customer-specific code.** Templates and configuration only.
7. **Small modules, explicit contracts, deterministic tests,** as in Phase 0/1.

## 2. Build order

| # | PR | Content | Depends on | Acceptance |
|---|---|---|---|---|
| 1 | Product module layout + boundaries | create product packages (empty contracts), import-boundary tests (product ↛ benchmark, core ↛ adapters, SDKs only in adapter modules) | – | hygiene tests green |
| 2 | Migration tooling + schema baseline | adopt migration tool (D-20); port `0001_foundation` unchanged; versioned migrations in CI | D-20 | Phase 0 RLS tests unchanged and green |
| 3 | Identity schema | organizations (from `tenants`), users (documented RLS exception), memberships, roles/permissions catalog, invitations (hashed tokens), API keys (hashed), service accounts; signup function | 2 | RLS + privileged-function negative tests |
| 4 | Auth + RBAC in the API | auth provider integration (D-12), API framework (D-17), session → principal → membership → tenant binding, permission checks, API keys | 3, D-12, D-17 | 403 tests per permission, no tenant from client input |
| 5 | Agents, versions, deployments | draft config schema (validated), publish → immutable version with hash, deployments per environment, rollback, templates as data | 3, 4 | immutability tests, validation tests, no customer-specific fields |
| 6 | `CallContext` v2 + tool registry | integration bindings map, environment, deployment id; tool types as data (schemas, side-effect class, confirmation policy); scopes derived from version | 5 | all Phase 0 gateway negative tests pass unchanged against the registry |
| 7 | Durable gateway state | sessions, audit (`tool_executions`), generalized operations ledger (+ transitions) in PostgreSQL; `booking_operations` migrated or wrapped | 6 | `BOOKING_UNKNOWN` restart/negative-lookup tests generalized to all non-idempotent tools |
| 8 | Calls domain | calls, call events (Phase 1 vocabulary), turns, outcomes, contacts, provider failures; outbox + job table | 7 | append-only grants tested, RLS tests |
| 9 | Voice contracts | provider ports (STT/LLM/TTS), runtime adapter, media session and telephony adapter contracts, credential broker interface, `GatewayBinding`; fake providers and a deterministic reference runtime implementing them | 1, 8 | contract tests; no SDK import anywhere in product code yet |
| 10 | Session manager | test-call/route request → deployment → `CallContext` → gateway session → call record → call-scoped runtime token; turn manager rules (final-only commit, barge-in rollback), speech guard v2; runs with the reference runtime | 7, 8, 9 | security invariants (no context in runtime, no action on partial transcript, no tenant from client) with fakes |
| 11 | **Voice worker (gated)** | one runtime adapter implementation (D-01), one media session implementation (D-14), reference provider adapters promoted from Phase 1 with hardening (D-03/04/05), browser test call for the `development` deployment | 10, D-01, D-14, D-03/04/05, D-21, D-23 | fake-SDK tests as in Phase 1; live smoke on staging only with authorization |
| 12 | Usage + observability baseline | usage events with idempotency, OpenTelemetry instrumentation with redaction tests (exporter/backend later, D-10) | 8, 10 | redaction tests (no transcript/PII in logs) |
| 13 | Internal tools | `contact.capture`, `callback.create`, `note.add`, `call.end` as gateway tools with confirmation policies | 7, 8 | tool negative tests |
| 14 | Control-plane API completion | calls/contacts read APIs, agent test endpoints, OpenAPI published internally | 4, 5, 8 | contract tests |
| — | **2A exit review** | | | exit criteria in the roadmap (steps 1–10, 12–14; step 11 is the separately gated voice worker milestone) |
| 15 | Secret store + OAuth framework | secret store implementation (D-16) behind the credential broker, OAuth flow with PKCE, token refresh worker | 4, 9, D-16 | no secret in DB/logs tests |
| 16 | Webhooks out + `webhook.invoke` tool | signed outbound webhooks, delivery log; custom tool with egress allowlist/SSRF protection | 8, 15 | SSRF negative tests |
| 17 | Telephony inbound | number inventory and routing function (can start earlier, carrier-agnostic); telephony adapter implementation per D-06; transfer, DTMF, voicemail fallback | 9, 10, 11, D-06 | routing negative tests (unknown/released number), authorized staging calls |
| 18 | First calendar + CRM integrations | per D-27, via tool types and operations ledger | 15 | `UNKNOWN`/reconciliation tests per integration |
| 19 | Knowledge v1 | sources, ingestion jobs, chunks/embeddings under RLS, `knowledge.search` tool, deletion | 8, D-11, D-26 | tenant/agent filter tests, deletion tests |
| 20 | Web app v1 | stack per D-18 (PROPOSED: Next.js + React + TypeScript), VoiceOS design system first, journey steps, role-aware UI on the public API | 14, D-18 decided before the first Web App Shell or Design System PR | e2e UI tests on staging |
| 21 | Compliance features | retention jobs, export/deletion per contact, recording opt-in with consent, audit UI | 8, 12 | deletion propagation tests |

## 3. First implementation PRs (proposed to start with)

1. **PR-1 Product module layout and import boundaries** – no behavior change; establishes
   where product code lives and that it cannot depend on benchmark code.
2. **PR-2 Migration tooling** – decision D-20 plus porting the Phase 0 schema unchanged.
3. **PR-3 Identity schema with RLS** – organizations/users/memberships/roles/API keys,
   privileged signup and user-lookup functions, full negative test set.
4. **PR-4 Agent configuration schema, versions and deployments** – the core product object,
   immutable publish, templates as data.
5. **PR-5 `CallContext` v2 and data-driven tool registry** – generalizes the gateway while
   keeping every Phase 0 security test green.

PR-1, PR-2 and PR-4 can be prepared in parallel (PR-4 depends only on the schema conventions
of PR-2/PR-3 at merge time). None of PR-1…PR-5 needs a runtime, media, telephony or
speech-provider decision. Auth/API (step 4) starts as soon as D-12 and D-17 are decided.

## 4. Explicitly deferred

Outbound calling and campaigns, billing provider integration, SSO, porting, BYOC SIP,
helpdesk integrations, website crawling, teams/locations, agency structures, multi-region,
marketplace, white label.
