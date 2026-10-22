# Security Model

**Status:** Phase 0 foundation, pending Architecture/QA review and human approval.

## Trust boundaries (implemented)

| Input | Trust | Handling |
|---|---|---|
| `CallContext` (tenant, call, agent/release, principal, calendar/CRM refs, scopes) | trusted, server-issued | passed to the gateway separately from the proposal |
| `ToolRequest` (model output) | untrusted | allowlist, authority-key screen, strict schema, then authorization |
| Model free text | untrusted | never states booking results; booking statements come from templates |
| Caller replies | untrusted | deterministic affirmation classifier; ambiguous replies confirm nothing |
| Calendar/CRM mock responses | authoritative for business state | timeouts become `BOOKING_UNKNOWN` |

## Controls and their tests

| Control | Enforced in | Negative tests |
|---|---|---|
| Unknown tools rejected | `gateway.ToolGateway.execute` | `test_unknown_tools_are_rejected` |
| Authority fields (tenant, credentials, scopes, refs, ids, URL, SQL, shell) rejected, also nested | `gateway.schemas.contains_authority_key` | `test_authority_fields_in_model_arguments_are_rejected` |
| Closed strict schemas, no coercion | `gateway.schemas` | `test_malformed_arguments_are_rejected` |
| Tool must be in trusted scopes | gateway | `test_tools_outside_the_trusted_scopes_are_rejected` |
| Context must match the opened session | gateway | `test_forged_context_is_not_accepted` |
| Blocked / ended calls execute nothing | gateway | `test_blocked_execution_has_no_side_effects`, `test_dropped_call_without_booking` |
| `BOOKING_UNKNOWN` never released by a negative lookup; no rebooking, no blind retry | `gateway.ToolGateway._reconcile`, `_existing_booking` | `test_timeout_before_commit_with_negative_lookup_stays_unknown_and_blocks_rebooking`, `test_repeated_negative_lookups_never_release_rebooking`, `test_negative_lookup_keeps_persisted_unknown_across_restart` |
| No success without authoritative confirmation | `booking.speech` | `test_no_success_statement_without_authoritative_confirmation`, offline scenarios |
| Tenant isolation in the database | PostgreSQL RLS (see `TENANCY_MODEL.md`) | `tests/postgres/test_rls_isolation.py` |
| No secrets in repr/logs; audit has no payloads | `config.Settings`, `AuditRecord` | `test_passwords_never_appear_in_repr`, `test_audit_trail_has_no_argument_payloads` |
| Live execution and recording off | `config.load_settings` (refuses `true`) | `tests/unit/test_config.py` |
| No provider/network client code | dependency and import checks | `tests/unit/test_repo_hygiene.py` |

## Secrets

No secrets in source, fixtures or logs. Local database passwords live only in the
git-ignored `.env`; `.env.example` ships empty values. No provider credentials exist.

## Assumptions

- The process that builds `CallContext` is trusted. How it authenticates callers,
  dispatchers or webhooks is not part of Phase 0.
- The authority-key screen is defense in depth; the closed schemas are the primary control.
- The speech guard's keyword filter is defense in depth; fixed templates are the primary
  control. Output control for native speech-to-speech models is NOT DECIDED.

## NOT DECIDED / not covered

SSRF egress controls (no URL-taking tools exist), webhook signature verification,
suppression/consent gate, encryption/key management, audit log persistence, telemetry
redaction pipeline, legal/compliance assessment.
