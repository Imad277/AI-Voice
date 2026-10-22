# Product Scope

**Status:** Phase 0 foundation, pending Architecture/QA review and human approval.

## Long-term goal (direction, not a commitment of scope or order)

VoiceOS is intended to become a multi-tenant AI voice SaaS platform (inbound and outbound
calls, agent builder with versioned releases, German and multilingual agents, qualification,
appointment booking, CRM/calendar integrations, campaign management, human handover,
knowledge base, analytics, agency/client structures, white label, API/webhooks, usage
metering, billing, consent/suppression). It is explicitly not a thin wrapper around a voice
provider: tenancy, agent lifecycle and releases, business rules, tool gateway,
authorization, campaign state, consent/suppression, outcomes and usage ledger stay under
VoiceOS control.

## Phase 0 scope (this repository state)

Foundation only, offline only. It proves one chain:

```text
trusted server context -> Tool Gateway -> deterministic business logic
  -> tenant-isolated PostgreSQL -> authoritative result
```

Reference journey used by tests (from the validation research, used here only as a test
scenario): inbound appointment and qualification – collect and confirm contact, qualify,
list slots, confirm slot, book server-side, speak success only after authoritative
confirmation, update CRM, record outcome.

## Explicitly out of scope in Phase 0

Real STT/TTS/LLM/telephony providers, LiveKit, Pipecat, SIP/PSTN, real CRM or calendar,
n8n, Temporal, Kubernetes, Terraform, Redis, cloud infrastructure, deployment, frontend,
dashboard, campaigns, outbound calling, billing, RAG, human handover, recording.

## NOT DECIDED

- Order and scope of later phases (Phase A onward).
- First production use case and target market details.
