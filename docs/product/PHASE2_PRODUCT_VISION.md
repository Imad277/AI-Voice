# Phase 2 – Product Vision

**Status: PROPOSED** (Phase 2 blueprint, 2026-10-28). Not an accepted architecture
document and not an ADR. Open decisions live in
[PHASE2_DECISION_REGISTER.md](PHASE2_DECISION_REGISTER.md).

## 1. What we build

VoiceOS is a **horizontal, multi-tenant B2B AI voice platform**: companies of any industry
configure, test, publish and operate production phone agents themselves, connect them to
their business systems, and see outcomes, usage and cost.

Direction (not a commitment of order): **AI voice infrastructure + agent platform +
business automation SaaS** – not a single phone bot.

It is explicitly **not** built for one customer or industry. No architecture, schema,
default, prompt or tool may encode a specific customer, vertical or use case (for example
vehicle appraisal, accident handling, insurance, or any named customer). A customer such as
an appraisal company is at most one tenant using a generic agent template.

## 2. Target customers and jobs to be done

| Customer type (examples, not a target-market decision) | Job |
|---|---|
| Service businesses (trades, clinics, agencies, salons, field service) | answer every inbound call, qualify, book appointments, capture leads |
| B2B sales and customer service teams | qualify inbound leads, route, create tickets, hand off to humans |
| Multi-location companies | one agent per location/brand, shared knowledge, central analytics |
| Developers / integrators (later) | API- and webhook-driven voice agents inside their own products |

The product must let a **non-technical business user** configure a working agent, while a
developer can automate the same through an API.

## 3. Core capabilities (end state)

Workspace and team management with roles; multiple agents per organization with versioned
releases and environments; phone numbers (inbound first, outbound later with consent and
suppression); language, voice and personality; conversation goals and a typed data
collection schema; business hours, routing, escalation and human handoff; knowledge
sources with provenance; tools and integrations (calendar, CRM, helpdesk, email, SMS,
webhook, HTTP API); workflows after the call; test calls; live calls with transcripts and
outcomes; contacts, leads, appointments and tickets; analytics, usage, cost and billing;
public API and webhooks; audit log.

## 4. What makes the platform trustworthy (non-negotiable)

These Phase 0 guarantees are product features, not implementation details:

- **Tenant authority is server-side only.** It comes from authenticated control-plane
  sessions or from carrier-verified call routing, never from caller speech, model output,
  knowledge content or webhook payloads.
- **The model proposes, the platform decides.** Every business side effect passes the
  Tool Gateway (allowlist, strict schema, authorization, policy, idempotency).
- **No claimed success without authoritative confirmation.** Uncertain writes enter an
  `UNKNOWN` state and are reconciled, never blindly retried.
- **No business action on partial transcripts.**
- **Fail closed** on missing context, configuration, credentials or evidence.
- **Secrets never enter the agent context**, logs or telemetry.
- **Tenant data isolation** in PostgreSQL with Row Level Security.

## 5. Product principles

| Principle | Meaning for design |
|---|---|
| Horizontal B2B | generic objects (agent, tool, integration, workflow, outcome); verticals are templates, not code |
| Provider-agnostic | STT, TTS, LLM, telephony, runtime behind adapter ports; per-agent provider choice later |
| Multi-tenant | every tenant-owned row carries `tenant_id` and is RLS-protected |
| API-first | the web app uses the same public API as customers |
| Event-driven where useful | durable events for post-call work, usage, webhooks; not for the realtime audio loop |
| Fail-closed | unknown → reject; uncertain → `UNKNOWN` + reconciliation |
| Observable | every call, turn, tool execution and provider call is measurable without leaking PII |
| GDPR-aware | data minimization, retention, export, deletion, recording off by default |
| EU-hosting capable | every component has an EU-hostable option; no hard cloud lock-in |
| Modular and testable | modular monolith with clear module boundaries; negative tests first |
| Not customer-specific | no customer names, verticals or hardcoded flows in the core |

## 6. What the first sellable version must be

Not a fake MVP. The first version external pilot customers use (end of Phase 2B, see
[PHASE2_ROADMAP.md](PHASE2_ROADMAP.md)) must let a business user, without our help:
create an organization and agent, configure it (prompt, voice, goals, data fields,
business hours, escalation), add basic knowledge, connect one calendar and one CRM or a
webhook, connect a German phone number, run a test call, publish, receive real inbound
calls, and see transcripts, outcomes, contacts/appointments, usage and cost – with the
security guarantees above.

## 7. Explicitly not in scope for Phase 2

Marketplace, complex white label, many CRM connectors, international carriers, mobile
app, AI coaching suite, own foundation/STT/TTS models, full contact-center features, a
large workflow node library, outbound campaigns before consent/suppression is built.

## 8. How we work from here

Product first. New spikes or benchmarks only when they block a concrete product or
architecture decision listed in the decision register, with the decision named up front.
Phase 1 benchmark code stays evidence infrastructure; product code is promoted from it only
through reviewed, hardened PRs (see [PHASE2_BUILD_PLAN.md](PHASE2_BUILD_PLAN.md)).
