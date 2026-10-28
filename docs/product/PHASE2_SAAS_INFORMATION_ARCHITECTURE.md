# Phase 2 – SaaS Information Architecture and Customer Journey

**Status: PROPOSED.** No frontend is implemented and no frontend stack is selected (D-18).
The web app is a client of the public API (API-first).

## 1. Customer journey

Target: a non-technical business user reaches a published, working agent without support.

| # | Step | What the user does | What the platform guarantees | Phase |
|---|---|---|---|---|
| 1 | Signup | email + password or SSO, verifies email | no tenant before verified signup; bot/fraud checks | 2A |
| 2 | Organization | name, country, time zone, language, data region | organization = tenant; creator becomes Owner | 2A |
| 3 | Create agent | "New agent" | agent in `development` environment, no phone exposure | 2A |
| 4 | Use case | pick template (blank, appointment booking, lead qualification, support triage, message taking) | template prefills goals, data fields, tools; editable | 2A (blank + 2 templates), 2B |
| 5 | Configure | name, language, voice (preview), opening message, instructions, goals, data fields, hours, escalation | live validation; plain-language guidance; risky settings explained | 2A/2B |
| 6 | Knowledge | paste text/FAQ, upload PDF, add URL | ingestion status, preview of what the agent knows, source list | 2B |
| 7 | Integrations | connect calendar/CRM via OAuth or add a webhook | least-privilege scopes shown; test connection | 2B (1 calendar, 1 CRM, webhook) |
| 8 | Phone number | buy/assign a German number or forward an existing number | regulatory data collected; number bound to deployment | 2B |
| 9 | Test call | browser call (WebRTC) or call the test number | uses the `development` deployment; full transcript, tool results and timings visible | voice worker milestone (browser), 2B (phone); 2A tests run scripted calls through the reference runtime |
| 10 | Review | checklist: goals, data fields, tools, hours, compliance (disclosure, recording), test call passed | publish blocked while checks fail (fail closed) | 2B |
| 11 | Publish | publish → immutable version → production deployment | rollback to earlier version in one click | 2A (API), 2B (UI) |
| 12 | Live calls | real inbound calls | outcomes, contacts, appointments created through the gateway only | 2B |
| 13 | Analytics | dashboard: calls, outcomes, conversion, durations, failures, cost | per agent/version/number | 2B |
| 14 | Optimize | inspect calls, edit draft, test, publish new version; compare versions | version comparison on outcomes and latency | 2B/2C |

## 2. Global navigation

| Section | Purpose | Key roles |
|---|---|---|
| **Dashboard** | today's calls, outcomes, alerts (provider failures, unknown operations, integration errors), usage vs plan | all |
| **Agents** | list, create, templates | Owner, Admin, Developer, Operator (read) |
| **Calls** | call log with filters (agent, number, outcome, date), call detail | Operator, Analyst, Admin |
| **Contacts / Leads** | records created by calls, status, export | Operator, Analyst |
| **Appointments / Tickets** | records with external references and sync state | Operator |
| **Knowledge** | sources, ingestion status, usage by agents | Developer, Admin |
| **Integrations** | connections, health, scopes, re-authorize | Admin, Developer |
| **Workflows** | post-call actions and their runs | Developer, Admin |
| **Phone Numbers** | inventory, bindings, regulatory status, forwarding setup | Admin |
| **Analytics** | outcomes, conversion, durations, latency, failure rates, version comparison | Analyst, Admin |
| **Usage** | minutes, provider units, numbers, by agent/period | Billing, Admin |
| **Billing** | plan, invoices, payment method (provider-hosted) | Billing, Owner |
| **Team** | members, invitations, roles | Owner, Admin |
| **Settings** | organization, data retention, recording policy, compliance texts, region | Owner, Admin |
| **Developer / API** | API keys, service accounts, webhooks, delivery log, OpenAPI docs | Developer, Admin |
| **Audit Log** | who changed what, when; exports | Owner, Admin |

## 3. Agent detail

| Tab | Content |
|---|---|
| **Overview** | status per environment, active version, bound numbers, last calls, outcome rate, health |
| **Configure** | name, description, language, goals, success criteria, data collection schema, business hours, escalation, fallback |
| **Voice** | provider-neutral voice picker with previews, speaking rate, pronunciation lexicon, opening/closing message |
| **Prompt** | system instructions, personality, disclosure text; read-only view of the assembled prompt (without secrets) |
| **Knowledge** | attached sources, retrieval settings, test question box |
| **Tools** | allowed tools, bound connections, confirmation policies, test invocation in sandbox mode |
| **Workflow** | post-call actions for this agent |
| **Phone** | numbers bound per environment, forwarding instructions |
| **Testing** | browser test call, scripted test conversations (evaluation set), last test results |
| **Deployments** | environments, active version, publish, rollback, deployment history |
| **Calls** | calls of this agent with version column |
| **Analytics** | agent-level metrics, version comparison |
| **Versions** | immutable versions, diff between versions, who published |

## 4. Call detail

Timeline (turns with timings, interruptions, tool proposals and gateway decisions), collected
data and confirmation status, outcome, operations with states (`CONFIRMED`, `UNKNOWN`
with "reconcile" action for authorized roles), provider failures, cost breakdown, recording
(only if enabled and consented), transcript export (permission-gated, audited).

## 5. UX rules

- No visual workflow builder in 2A/2B: the Workflow section shows declarative post-call
  actions and their runs.

- Plain-language explanations for every setting that affects legal or business risk
  (recording, disclosure, outbound, data retention).
- Publishing is blocked by failed checks; the UI explains the failed check.
- `UNKNOWN` operations are surfaced as alerts, never hidden or auto-resolved.
- Every destructive or externally visible action (publish, delete, number release, data
  export) requires confirmation and is audited.
- No PII in URLs; deep links use opaque ids.
- Role-aware UI, but authorization is always enforced by the API.
