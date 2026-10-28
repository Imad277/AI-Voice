# Phase 2 – Decision Register

**Status vocabulary:** `PROPOSED` (a default is suggested for review), `HOLD_FOR_EVIDENCE`
(a default may be used provisionally, but the decision needs named evidence),
`NOT DECIDED` (no default yet). **No entry is `ACCEPTED`.** Accepted decisions are recorded
only as ADRs in `docs/architecture/decisions/` after review and owner approval.
ADR numbers refer to the Manus ADR index (`docs/research/manus/validation/11_ADR_Templates.md`).
Evidence references E-numbers from `docs/benchmark/PHASE1_DECISION_GATE.md`.

| ID | Decision | Options | Evidence so far | Risk | Proposed default | Status | Evidence needed |
|---|---|---|---|---|---|---|---|
| D-01 | Voice runtime (ADR-001) | Pipecat with LiveKit transport; LiveKit Agents; both behind the runtime adapter | E11–E13, E17, E20–E23: equal function/security; Pipecat leads startup, memory, detection/stop latency, room-scoped token; LiveKit leads false endpoints; turn-taking Pipecat `VERIFIED`, LiveKit `INCONCLUSIVE` (test design) | lock-in to a framework's turn model; endpointing quality | no runtime selected; 2A builds only against the runtime adapter contract with a reference runtime; Pipecat and LiveKit Agents stay exchangeable implementations (Phase 1 provisional path Pipecat is input, not a default for 2A) | HOLD_FOR_EVIDENCE; blocks only the voice worker PR | real phone audio (8 kHz), endpointing tuning per arm on digits/pauses, load 10/25/50, crash/drain lifecycle |
| D-02 | Voice architecture (ADR-002) | cascade STT→LLM→TTS; native speech-to-speech; hybrid | only cascade tested; ~3 s caller latency (E14/E15) | latency vs. control of business statements | cascade (speech guard and gateway control proven) | PROPOSED | latency reduction results in cascade; S2S output control evaluation |
| D-03 | STT provider (ADR-003) | Deepgram nova-3; Speechmatics; others | E1–E3, E24: German works, Finalize on VAD end gives ~0.6 s; entity misses on synthetic speech | phone/email entity accuracy on real 8 kHz audio | Deepgram nova-3 as reference implementation of the STT port | HOLD_FOR_EVIDENCE; needed for the voice worker PR | 8 kHz G.711 entity accuracy, consented human speech set, EU data path, cost |
| D-04 | TTS provider (ADR-004) | Cartesia sonic-3.5 (Nico); ElevenLabs flash v2.5; others | E7–E10, E25: Cartesia faster TTFA, preferred voice; quota outage 402 | single-provider outage, voice consistency | Cartesia as reference implementation of the TTS port, ElevenLabs as fallback candidate | HOLD_FOR_EVIDENCE; needed for the voice worker PR | telephony-codec listening test, quota/limits contract, EU data path, cost |
| D-05 | LLM (ADR-005) | OpenAI gpt-6-luna (alias, reasoning low); challenger models; realtime models | E4–E6: 16/17 tool accuracy, injection blocked, nondeterminism after readback fixed by server note in harness | alias drift, latency, data path | gpt-6-luna as reference implementation of the LLM port with the model recorded per call; second model evaluated on the offline suite | HOLD_FOR_EVIDENCE; needed for the voice worker PR | frozen snapshot or per-call model record, EU processing options, latency with streaming, evaluation suite results |
| D-06 | Telephony / carrier (ADR-006) | carrier SIP → media layer (T0); CPaaS media streams (T1); German SIP trunks; BYOC later | none (no PSTN authorized); research comparison only | regulatory (German numbers), reselling terms, emergency obligations, fraud | none; 2A/2B build against the telephony adapter contract; terminating carrier calls in the media layer (T0 shape) is an evaluation hypothesis, not a default | NOT DECIDED | decision-scoped spike per telephony requirements doc §3; legal/contract review |
| D-07 | Workflow / job processing (ADR-007) | domain state machines + Postgres outbox/job queue; dedicated broker; Temporal (excluded by rule 28); n8n only as untrusted webhook consumer | Phase 0 state machines proven | lost or duplicated side effects in async steps | state machines + transactional outbox + Postgres `SKIP LOCKED` jobs | PROPOSED | throughput test of the job table at 2B volume; failure/retry tests |
| D-08 | Tenant architecture (ADR-008) | shared PostgreSQL + RLS; database per tenant for large customers | Phase 0 RLS tests (E19), 26/26 in CI | noisy neighbor, enterprise isolation demands | shared PostgreSQL + RLS (Phase 0 baseline) | PROPOSED – confirm before 2A | enterprise requirements; performance at 2B/2C scale (a later database-per-tenant option stays possible) |
| D-09 | Hosting (ADR-009) | managed EU cloud; EU hosting provider with own operations; hybrid | none | lock-in, operational load, data residency | EU region, containers without Kubernetes (rule 27), managed PostgreSQL and object storage | NOT DECIDED | cost and ops comparison for 2B footprint, provider DPAs, latency to STT/LLM/TTS endpoints |
| D-10 | Observability (ADR-010) | OpenTelemetry + EU-hostable backend; vendor APM | Phase 1 event vocabulary | PII leakage into telemetry, cost | OpenTelemetry instrumentation, backend open | PROPOSED | backend selection by cost/EU hosting; redaction tests |
| D-11 | Knowledge vector store | PostgreSQL vector extension under RLS; dedicated vector database | none | retrieval quality/scale | PostgreSQL vector extension (tenant isolation inherits RLS) | PROPOSED | retrieval quality and latency on pilot knowledge sizes |
| D-12 | Auth provider | hosted identity provider (EU); self-hosted identity server; framework-native auth | none | security of account management, SSO path, EU residency | external OIDC-capable provider with EU hosting option | NOT DECIDED | comparison: MFA, SSO/SAML, EU data residency, cost, lock-in |
| D-13 | Object storage | S3-compatible EU storage (managed or self-hosted) | none | data residency, encryption | S3-compatible API in the EU, server-side encryption, tenant-prefixed keys | PROPOSED | hosting decision D-09 |
| D-14 | Media layer | LiveKit self-hosted; LiveKit managed; CPaaS-only | Phase 1 local LiveKit v1.13.8 for both runtimes (E11, E20) | ops complexity (self-host needs Redis for multi-node), data residency of managed offer | none; 2A builds against the media session contract; LiveKit is the Phase 1 test setup and the first candidate | HOLD_FOR_EVIDENCE; blocks only the voice worker PR | SIP ingress test (D-06), managed EU options, multi-node ops |
| D-15 | Queue / event bus | Postgres outbox/jobs; NATS; RabbitMQ; Redis streams | none | throughput, ops | Postgres outbox/jobs until measured need (see D-07) | PROPOSED | load at 2B volume |
| D-16 | Secret management | cloud KMS/secret manager; Vault-compatible; envelope encryption in DB | none (Phase 0: `.env` only) | secret leakage, rotation | managed secret store in the EU region, envelope encryption for tenant credentials | NOT DECIDED | hosting decision, rotation and audit capabilities |
| D-17 | API style and backend framework | REST + OpenAPI; GraphQL; Python web framework choice | Phase 0/1 are Python 3.12, pydantic | consistency, typing | REST + OpenAPI in Python with pydantic models | PROPOSED | framework comparison limited to typing, async, OpenAPI generation |
| D-18 | Frontend stack | Next.js + React + TypeScript; other web stacks only if the spike below finds a product blocker | VoiceOS is first a browser-based multi-tenant B2B SaaS; CLAUDE.md UI governance orients the web app towards React/Next.js/TypeScript. Apple HIG and the installed `apple-design` skill define design and UX principles, not the rendering technology; SwiftUI/UIKit/AppKit are not implementation technologies for the current web app; a later native Apple app would be a separate architecture decision. No separate frontend-framework benchmark unless a concrete product blocker appears | hosting fit of the Next.js runtime (D-09), server/client boundary for tenant authority | **Next.js + React + TypeScript** | PROPOSED (not ACCEPTED); may stay PROPOSED during the backend/domain part of 2A; must be decided before the first productive Web App Shell PR or VoiceOS Design System PR | one product-foundation / design-system spike: app shell, routing, server/client boundary, auth integration (D-12), design tokens, accessibility, responsive behavior, table/dashboard suitability, build/test/TypeScript tooling – no comparative study of several frameworks |
| D-19 | Billing provider | Stripe; Paddle (merchant of record); other | none | tax/VAT handling, EU invoicing | billing provider with EU invoicing and usage-based billing | NOT DECIDED | usage billing support, VAT/invoice requirements, legal review |
| D-20 | Migration tooling | SQL-first migration tool; ORM-based migrations | Phase 0: hand-written SQL applied by `migrate.py` | RLS policies must stay explicit SQL | SQL-first versioned migrations (keeps RLS/grants explicit) | PROPOSED | fit with RLS policies, CI support |
| D-21 | Caller confirmation policy | exact-phrase classifier (Phase 0 placeholder); LLM-assisted classification with server rules; DTMF confirmation | Phase 0 placeholder; E5/E6 | false confirmation → wrong booking | server-side classifier with conservative rules, ambiguous = not confirmed; DTMF option | NOT DECIDED | evaluation on real speech variants, false-accept rate |
| D-22 | Server confirmation note in product | adopt; replace by structured state message; drop | E5/E6 (harness only) | model nondeterminism after readback | adopt as trusted-state message, rendered from server state | HOLD_FOR_EVIDENCE | evaluation suite across models |
| D-23 | Turn-taking / endpointing profiles | framework defaults; tuned profiles per field type (digits, dates); Finalize-on-VAD-end policy | E21–E24 | premature or late turn ends on digits and pauses | per-agent profiles + digit collection mode, Finalize on VAD end | HOLD_FOR_EVIDENCE | tuned runs on the Phase 1 set + 8 kHz audio; speech-relative barge-in trigger in evaluations |
| D-24 | Recording policy and storage | off; opt-in with consent; dual-channel | none (recording disabled by rule 22) | legal exposure, storage cost | off by default, tenant opt-in with consent prompt and retention | NOT DECIDED | legal review, storage/encryption design |
| D-25 | Email / SMS providers | various EU-capable providers | none | deliverability, data path | not proposed yet | NOT DECIDED | needed only for 2B/2C workflows |
| D-26 | Embedding model | provider embeddings; self-hosted embeddings | none | data path, quality for German | provider-agnostic embedding port | NOT DECIDED | German retrieval quality on pilot data, EU data path |
| D-27 | First integrations | calendar: Google Calendar / Microsoft 365 / Cal.com; CRM: HubSpot / Salesforce / Pipedrive | none | building connectors nobody needs | decide from pilot customer demand; webhook tool covers the rest | NOT DECIDED | pilot customer requirements |

## Decision timing

### MUST DECIDE BEFORE 2A

Only what blocks the first Product Foundation PRs (module layout, migrations, identity
schema, agent schema, `CallContext` v2 / tool registry):

| ID | Why it blocks |
|---|---|
| D-20 Migration tooling | every schema PR needs it (PR-2 is the tool itself) |
| D-08 Tenant architecture – confirm the shared PostgreSQL + RLS baseline | every new table is designed on it |

### CAN DEFER DURING 2A (decide before the named PR)

| ID | Needed before |
|---|---|
| D-12 Auth provider | auth/RBAC PR (build step 4); schema PRs do not need it |
| D-17 API style / backend framework | first API PR (build step 4) |
| D-15 Queue / event bus | outbox/jobs PR (build step 8); default Postgres outbox needs no new infrastructure |
| D-07 Workflow / job processing | outbox/jobs PR (build step 8) |
| D-10 Observability backend | instrumentation uses OpenTelemetry APIs; exporter/backend before staging |
| D-16 Secret management | `credential_ref` format and broker interface in 2A; a real store before the first real credential is stored (build step 15) |
| D-01 Runtime, D-14 Media layer | voice worker PR (build step 11) only |
| D-03 STT, D-04 TTS, D-05 LLM | voice worker PR (reference implementations of the ports) |
| D-02 Voice architecture | voice worker PR (cascade assumed by the contracts) |
| D-21 Confirmation policy, D-22 Server confirmation note, D-23 Turn-taking profiles | voice worker PR / first live speech tests; 2A uses the Phase 0 deterministic placeholder in tests |
| D-13 Object storage | first upload/recording/export feature (2B) |
| D-18 Frontend stack (PROPOSED: Next.js + React + TypeScript) | first productive Web App Shell PR or VoiceOS Design System PR, whichever comes first |

### MUST DECIDE BEFORE 2B

D-06 Telephony; D-09 Hosting; D-18 Frontend stack (at the latest here, if not already decided before the first Web App Shell / Design System PR); D-16 Secret management; D-12 Auth
provider (if not already decided in 2A); D-01, D-14, D-03, D-04, D-05 (the voice worker
must exist before pilots; providers stay exchangeable); D-02 cascade confirmed; D-10
Observability backend; D-13 Object storage; D-11 Vector store and D-26 Embeddings; D-07
job processing confirmed at 2B volume; D-21, D-23 for live calls; D-24 Recording policy;
D-27 First integrations; legal review items for pilots.

### Later (2C)

D-19 Billing provider; D-25 Email/SMS providers; D-08 database-per-tenant option for
enterprise customers.

## Constraints that are rules, not decisions (CLAUDE.md)

No microservices without an ADR; no Kubernetes; no Temporal; n8n never controls realtime
voice and never becomes an authority layer; tenant authority server-side only; Tool
Gateway as the only business path; RLS for tenant data; recording disabled until
authorized; no PSTN or production deployment without explicit authorization. Changing any
of these requires an explicit owner decision, not a register entry.
