# Phase 2 – Roadmap

**Status: PROPOSED.** Scope levels, not dates. Each level has exit criteria; a level is
done when its criteria are met and reviewed, not when a date passes. Decisions referenced
as D-xx: [PHASE2_DECISION_REGISTER.md](PHASE2_DECISION_REGISTER.md).

## Phase 2A – Product Foundation (internal, no external customers)

Goal: the horizontal, **runtime-agnostic** core runs end to end for an internal user
through the API, on the Phase 0 security model. 2A does not depend on a runtime, media
layer, telephony or speech-provider decision: everything voice-related is built against the
stable contracts (session manager, runtime adapter, media session, provider ports,
`GatewayBinding`; target architecture §2.2) and exercised with a deterministic reference
runtime, as Phase 0 did with `FakeRuntime`.

Runtime-agnostic by design: organizations/tenants, users/memberships, RBAC, agent drafts,
agent versions, deployments, tool registry, integration registry, `CallContext` v2, durable
Tool Gateway, operation ledger, calls/call events, audit, usage/metering, API,
observability, secret references.

| Area | Scope |
|---|---|
| Codebase | modular monolith layout (`identity`, `agents`, `calls`, `gateway`, `tools`, `integrations`, `providers`, `runtime`, `usage`, `audit`, `jobs`), import-boundary tests; benchmark stays separate |
| Data | migration tooling (D-20); schema for organizations, users, memberships, roles, API keys, agents, agent versions, deployments, calls, call events/turns, tool executions, operations ledger, outcomes, contacts, audit events, usage events, outbox/jobs – all with RLS and negative tests |
| Identity | auth provider integration (D-12), sessions, memberships, RBAC enforcement, API keys, service accounts |
| Control-plane API | REST/OpenAPI (D-17): organizations, members, agents (draft, validate, publish, rollback), versions, deployments, calls (read), contacts (read), API keys |
| Gateway v2 | tool registry, `CallContext` v2 (integration bindings, environment, deployment), durable sessions and audit, generalized operation ledger, all Phase 0 negative tests kept green |
| Tools | internal database-safe tools (`contact.capture`, `callback.create`, `note.add`), `call.end`, `call.transfer` contract (no PSTN), knowledge not yet |
| Data plane contracts | session manager, call-scoped runtime token, runtime adapter / media session / provider port contracts, `GatewayBinding`, turn manager rules (final-only commit, barge-in rollback), speech guard v2; a deterministic reference runtime and fake providers implement the contracts for tests |
| Telemetry | call events, OpenTelemetry instrumentation with redaction (backend D-10 can follow), usage events |
| Quality | contract tests for every port; offline evaluation suite from the Phase 1 datasets prepared for later runtime implementations |

Exit criteria: an internal user creates an organization, invites a member, creates an agent
from the blank template, configures it, publishes version 1; a scripted call through the
session manager and the reference runtime collects and confirms contact data through the
durable gateway; the call appears with turns, events, operations, outcome, contact, audit
and usage; rollback to a previous version works; RLS/RBAC/gateway negative tests green in
CI; no runtime, media, carrier or speech provider selected; no PSTN, recording off.

### Voice worker milestone (end of 2A or start of 2B, gated)

The first production voice worker: one runtime adapter implementation, one media session
implementation, reference provider adapters promoted from Phase 1 with hardening, and a
browser test call. Blocked only by the decisions it actually needs: D-01 (runtime), D-14
(media layer), D-03/D-04/D-05 (reference providers), D-23 (turn-taking profiles), D-21
(confirmation policy for live speech). Exit: browser test call with real STT/LLM/TTS on
staging (explicit authorization), latency and turn-taking measured per agent version,
security invariants unchanged.

## Phase 2B – Usable SaaS (first external B2B pilots, self-service)

Goal: pilot customers configure and run real inbound phone agents themselves.

| Area | Scope |
|---|---|
| Web app | stack per D-18 (PROPOSED: Next.js + React + TypeScript; decided before the first Web App Shell or Design System PR); journey steps 1–14 (templates, configure, voice preview, test, review checklist, publish, calls, analytics) |
| Telephony | inbound German numbers via the selected path (D-06): provisioning or forwarding, business hours, transfer to humans, voicemail/callback fallback, DTMF, emergency-safe behavior, concurrency and spend caps |
| Integrations | OAuth + secret store (D-16); one calendar provider and one CRM provider (D-27); `webhook.invoke` custom tool with egress control; outbound signed webhooks |
| Knowledge | text, FAQ, PDF, URL; chunking, embeddings, retrieval tool, source provenance, manual refresh, deletion, RLS (D-11, D-26); no connectors |
| Workflows | typed events, outbox, jobs, declarative post-call actions (email summary, CRM push, webhook, callback task) and defined state machines (D-07); no visual workflow builder; n8n or similar only as an untrusted consumer of signed webhooks |
| Records | contacts, leads, appointments with sync state; `UNKNOWN` operations surfaced for reconciliation |
| Analytics | call log, call detail timeline, outcome and conversion dashboards, latency and failure panels, usage view |
| Compliance | AI disclosure default on, recording opt-in with consent prompt, retention jobs, export and deletion per contact, audit log UI, legal review of pilot terms and DPA |
| Operations | staging and production in the EU (D-09), provider health checks and fallback, alerting, incident runbook, backups/PITR tested |

Exit criteria: at least one pilot organization, without our hands-on help, publishes an
agent on a German number, receives real calls, gets appointments/leads into its calendar or
CRM, and sees outcomes and usage; measured caller latency and endpointing quality within
agreed pilot targets; no cross-tenant incident; legal review items for pilots closed.

## Phase 2C – Commercial Platform

| Area | Scope |
|---|---|
| Billing | billing provider (D-19), plans, included minutes, overage, numbers and seats, invoices, spend caps, dunning |
| API | public API and webhooks GA with docs, SDK snippets, rate limits, idempotency guarantees |
| Identity | SSO (OIDC/SAML), SCIM later, MFA enforcement policies |
| Telephony | porting, BYOC SIP, outbound calls via API, campaigns only after consent/suppression and legal approval |
| Integrations | helpdesk (one provider), further calendar/CRM providers by demand, email/SMS providers (D-25) |
| Organization | teams/locations, per-location agents and analytics; agency/client structure only on demand |
| Quality | evaluation sets per agent, version comparison, regression gates before publish |
| Scale | load tests (10/25/50/100 concurrent calls), voice node autoscaling and drain, capacity plan, SLOs |
| Knowledge | website crawl, scheduled refresh, connectors (Drive/Notion/Confluence) by demand |

## Not planned in Phase 2

Marketplace, complex white label, many CRM connectors, international carriers, mobile app,
AI coaching suite, own models, full contact center, large workflow node library.

## Decision gates per level

The authoritative timing lists (`MUST DECIDE BEFORE 2A`, `CAN DEFER DURING 2A`,
`MUST DECIDE BEFORE 2B`, later) are in
[PHASE2_DECISION_REGISTER.md](PHASE2_DECISION_REGISTER.md#decision-timing). In short: 2A
starts with the migration tooling and the confirmed shared-PostgreSQL+RLS baseline; runtime,
media layer, speech providers and telephony block only the specific later PRs that
implement them.
