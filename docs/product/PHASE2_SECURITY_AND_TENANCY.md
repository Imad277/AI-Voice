# Phase 2 – Security, Tenancy and Compliance

**Status: PROPOSED.** Extends the Phase 0 security model (`docs/architecture/SECURITY_MODEL.md`,
`TENANCY_MODEL.md`, `TOOL_GATEWAY.md`); nothing here weakens it. Auth provider (D-12),
secret management (D-16) and tenant architecture (D-08) are NOT DECIDED.

## 1. Invariants carried over unchanged

1. Tenant authority originates only server-side: authenticated session → membership, API
   key → service account, or carrier-verified dialed number → number route.
2. `CallContext` is built only by trusted server code and passed to the gateway separately
   from model proposals.
3. Model output, caller speech, DTMF, knowledge content, webhook payloads and integration
   responses are untrusted data. They never carry tenant, principal, scopes, credentials,
   URLs or SQL into execution.
4. The Tool Gateway is the only path to business side effects: allowlist, authority-key
   screen, strict schema, context binding, authorization, policy, idempotency, ledger.
5. No business action on partial transcripts; no success statement before an
   authoritative result; `UNKNOWN` is reconciled, never blindly retried.
6. PostgreSQL RLS enabled and forced on every tenant table; app roles are not owners,
   superusers or `BYPASSRLS`; preflight refuses unsafe roles.
7. Secrets never in source, fixtures, logs, telemetry, prompts or model context.
8. Recording off by default; live provider use and PSTN only with explicit authorization.

## 2. Tenancy model

| Aspect | Proposal |
|---|---|
| Isolation | shared PostgreSQL + RLS (Phase 0 evidence); separate databases for large customers is an option for later (D-08) |
| Binding | transaction-local `app.tenant_id` from a trusted context object only (session principal, API key principal, call context) |
| Global data | catalogs (tool types, providers, roles, templates, rate cards) read-only for the app role |
| Default | every new tenant-owned table is tenant-scoped with RLS enabled and forced; deviations are listed with justification in the domain model §11 |
| Privileged paths | signup, number routing, user self-lookup, "my memberships", invitation acceptance, job claiming/outbox dispatch, retention/deletion jobs: dedicated roles with narrow `SECURITY DEFINER` functions, each with negative tests |
| Object storage | keys prefixed by tenant id; access only via short-lived signed URLs issued after an RLS-checked lookup |
| Vector search | embeddings stored in RLS tables; retrieval always filtered by tenant **and** by the agent version's sources |
| Caches | keys always include tenant id; no cross-tenant shared caches of content |
| Logs/metrics | tenant id as label/attribute; no content |
| Tests | every new table: own-tenant visibility, foreign insert/update denied, unbound transaction sees nothing, preflight assertion |

## 3. Authentication

| Principal | Mechanism (PROPOSED) |
|---|---|
| Human users | external identity provider or self-hosted identity service (D-12); email verification; MFA for Owner/Admin/Billing; SSO (OIDC/SAML) in 2C |
| Web sessions | server-side session or short-lived access token + refresh; tenant chosen per request from memberships, never from a client-supplied tenant id alone |
| API keys | per organization, scoped, prefix + secret shown once, stored as hash, expiry, rotation, last-used tracking, revocation |
| Service accounts | non-interactive principals that own API keys; least-privilege scopes |
| Runtime | never derives tenant authority from the model, the caller, the client or webhook content; **call-scoped, short-lived runtime token** issued by the session manager: valid for one call, only for gateway/binding endpoints and the media room of that call; the runtime never receives DB credentials, provider admin keys or other tenants' data. Media tokens room-scoped (Phase 1 evidence E17 favors room-scoped tokens over server API secrets in the runtime) |
| Outbound webhooks | HMAC-SHA256 signature over timestamp + body, per-subscription secret (ref in secret store), replay window, retries with backoff, delivery log |
| Inbound webhooks (carriers, integrations) | provider signature verification mandatory; unsigned → rejected; payload never establishes tenant authority on its own (looked up from our own references) |
| OAuth integrations | authorization code with PKCE where supported, minimal scopes, `state` bound to session and tenant, tokens only in the secret store, refresh by worker, revocation on disconnect |

## 4. RBAC

Roles are per organization membership. Permissions are checked in the API layer; RLS
guarantees tenant isolation underneath.

| Permission area | Owner | Admin | Developer | Operator | Analyst | Billing | Read Only |
|---|---|---|---|---|---|---|---|
| Organization settings, retention, region | ✔ | ✔ | – | – | – | – | read |
| Delete organization, transfer ownership | ✔ | – | – | – | – | – | – |
| Members and roles | ✔ | ✔ | – | – | – | – | read |
| Agents: create/edit drafts | ✔ | ✔ | ✔ | – | – | – | read |
| Agents: publish/rollback production | ✔ | ✔ | ✔ (if allowed by org setting) | – | – | – | – |
| Test calls | ✔ | ✔ | ✔ | ✔ | – | – | – |
| Integrations and credentials | ✔ | ✔ | ✔ | – | – | – | read (no secrets) |
| Phone numbers (buy/release/bind) | ✔ | ✔ | – | – | – | – | read |
| Calls, transcripts, recordings | ✔ | ✔ | ✔ | ✔ | ✔ (transcripts per setting) | – | metadata only |
| Contacts/leads/appointments | ✔ | ✔ | ✔ | ✔ | read | – | read |
| Reconcile `UNKNOWN` operations | ✔ | ✔ | – | ✔ | – | – | – |
| Analytics, usage | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Billing, plan, invoices | ✔ | – | – | – | – | ✔ | – |
| API keys, service accounts, webhooks | ✔ | ✔ | ✔ | – | – | – | – |
| Data export / deletion requests | ✔ | ✔ | – | – | – | – | – |
| Audit log | ✔ | ✔ | – | – | – | – | – |

Every permission check has a negative test (role without permission → 403, no side effect,
audit entry for denied privileged actions).

## 5. Secret management

| Secret | Storage |
|---|---|
| Platform provider keys (STT/LLM/TTS/carrier) | secret manager/KMS (D-16), injected into `voice`/`worker` processes only, never into the runtime's model context |
| Tenant BYO provider keys, OAuth tokens, SIP credentials, custom tool secrets, webhook signing secrets | secret store, referenced by `credential_ref`; envelope encryption with per-tenant data keys as fallback if no external vault |
| Our API keys, invitation tokens | hashes only |
| Database credentials | per role, rotated, never in application logs |

Credential broker: the gateway asks the broker for a credential **for one execution of one
tool instance**; the credential is used inside the adapter and never returned to the
runtime or the model.

## 6. Threats specific to the SaaS phase

| Threat | Control |
|---|---|
| Prompt injection via caller or knowledge content | gateway authority, closed schemas, knowledge treated as data, tool allowlists per version, no secrets in context |
| SSRF/exfiltration via custom HTTP/webhook tools | HTTPS only, tenant egress allowlist, block private/link-local/metadata ranges, DNS re-resolution check, size/time limits |
| Cross-tenant leakage via inbound routing | number routes resolved only by the router function; tests for unknown/released numbers (reject) |
| Toll fraud / premium destinations | transfer/outbound allowlists, spend caps, anomaly alerts |
| Account takeover | MFA for privileged roles, session revocation, audit of security events |
| Insider/support access | no standing cross-tenant access; break-glass with approval, time limit and audit (design in 2B) |
| Model claims false results | speech guard templates, outcome from gateway only |
| Abuse of the platform for spam/scam calls | KYC before outbound, content policy, rate limits, takedown process |

## 7. GDPR / compliance

### 7.1 Technical requirements (we build these)

| Area | Requirement |
|---|---|
| Data inventory | data classes per table (PII flags in the domain model); processing register maintained with the code |
| Minimization | technical telemetry without content; transcripts/recordings only where needed and configured |
| Retention | per data class and organization; enforced by deletion jobs with audit; defaults conservative |
| Recording | off by default; tenant policy + in-call consent prompt + consent evidence stored; per-call indicator |
| AI disclosure | configurable disclosure text at call start; default on |
| Right to access/export | export per contact (calls, transcripts, outcomes, records) and per organization, machine-readable |
| Right to deletion | delete per contact across tables, object storage, vector chunks and backups policy; propagate deletion requests to connected systems where we created data |
| Tenant isolation | RLS (above) and isolation tests in CI |
| Encryption | TLS in transit everywhere; encryption at rest for DB, object storage and backups; field-level encryption for sensitive fields where justified |
| Access logging | audit events for data access to transcripts/recordings/exports, admin actions, security events |
| Provider processing | provider data paths and retention settings recorded per provider; EU endpoints where available; zero-retention options enabled where offered |
| Secrets | secret store, rotation, no secrets in logs |
| Breach readiness | alerting, audit trail, ability to determine affected tenants/data |

### 7.2 Points for later legal review (no legal statements made here)

Controller/processor roles between VoiceOS, customers and providers; data processing
agreements and sub-processor list; international transfers per provider (STT, LLM, TTS,
carrier, hosting); lawful basis and consent wording for recording and for AI processing of
calls; AI disclosure obligations (including EU AI Act transparency duties); retention
periods per data class; telecom regulation for number provisioning, reselling, caller ID
and emergency calling; outbound calling rules (B2B/B2C, consent, suppression); handling of
special categories of personal data if callers volunteer them; employee data of tenant
users; terms of service and acceptable-use policy.
