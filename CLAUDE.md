# VoiceOS – Project Rules for Claude Code

VoiceOS is a planned multi-tenant AI voice SaaS platform. The repository is currently in
**Phase 0 – Foundation**: an offline, deterministic, tenant-isolated foundation for a later
validation harness. It is not the product and not a voice agent.

## Roles and authority

- Claude Code is the implementation engineer for the scoped phase only.
- Architecture / QA review: ChatGPT. Final approvals: the human project owner.
- Do not choose the product architecture, providers or runtimes on your own. Do not start
  another phase, merge, push or deploy without explicit instruction from the human owner.

## Source-of-truth hierarchy

1. Accepted ADRs in `docs/architecture/decisions/`
2. Approved architecture documents in `docs/architecture/`
3. Explicit scoped implementation instructions
4. Manus research in `docs/research/manus/` – evidence/specification input only

`PROPOSED`, `PRIMARY CANDIDATE`, `RECOMMENDED`, `SHORTLIST`, `NOT TESTED` are **not**
decisions. If an accepted ADR contradicts a research document, the ADR wins.

## Permanent rules

### Security / authority
1. LLM output is never business authority.
2. `tenant_id` must originate from trusted server-side context.
3. Never accept `tenant_id`, credentials, authorization scopes or permissions from
   model-generated tool arguments.
4. All business-critical external actions must pass through the validated Tool Gateway.
5. Tool execution requires server-side authentication, authorization, tenant validation,
   schema validation, policy validation, and idempotency where applicable.
6. The LLM may propose an action. It may never authorize that action.
7. No arbitrary URL access, SQL execution, shell execution or credential access through
   model-generated tool requests.

### Multi-tenancy
8. Every tenant-owned persistent entity contains `tenant_id`, unless an explicit documented
   architectural exception exists.
9. PostgreSQL Row Level Security is mandatory for tenant-owned data.
10. Application roles must not be database owners, superusers or `BYPASSRLS`.
11. Cross-tenant data access is a HARD FAILURE.
12. Tenant context never originates from untrusted request fields, LLM output, prompt
    content, knowledge documents or arbitrary webhook payloads.

### Business state
13. Never claim a business action succeeded before authoritative backend confirmation.
14. Booking writes must be idempotent.
15. An uncertain booking result enters `BOOKING_UNKNOWN`.
16. `BOOKING_UNKNOWN` requires reconciliation and never triggers blind rebooking.
17. CRM failure after authoritative booking confirmation does not invalidate the booking;
    it is represented independently as `BOOKED_CRM_PENDING`.

### Security / privacy
18. No secrets in source code.
19. No secrets in fixtures.
20. No secrets in logs or telemetry.
21. No real customer data in the benchmark environment.
22. Recording defaults to disabled unless explicitly authorized later.
23. No real PSTN calls without explicit authorization.
24. No production deployment without explicit authorization.
25. No outbound campaign execution in Phase 0.

### Architecture governance
26. No microservices unless an approved ADR requires them.
27. No Kubernetes.
28. No Temporal.
29. No n8n in Phase 0.
30. n8n must never control realtime voice execution.
31. Do not select LiveKit, Pipecat or another runtime as architecture winner in Phase 0.
32. Do not select STT/TTS/LLM/Telephony providers as architecture winners in Phase 0.
33. Provider integrations later use explicit adapter boundaries.
34. Manus research is evidence/specification input, not implementation authority.
35. Security-critical functionality requires automated negative tests.
36. Decisions that require evidence stay `NOT DECIDED` until their validation gate passes.

## Working conventions

- Python 3.12, managed with `uv`. Minimal dependencies (`pydantic`, `psycopg`); dev tools
  `pytest`, `ruff`, `mypy` (strict). Adding a dependency needs a stated reason.
- Small modules, explicit typed contracts, deterministic behavior, negative tests first.
  No speculative abstractions, queues, event buses, factories or provider layers.
- Report test results only as actually observed; use `NOT TESTED` when there is no evidence.

## Commands

```bash
cp .env.example .env            # then fill in local-only passwords
docker compose up -d --wait     # local PostgreSQL 18.6 on 127.0.0.1:55432
uv sync
uv run --env-file .env pytest   # all tests, including real PostgreSQL RLS tests
uv run pytest -m "not postgres" # offline unit tests only
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

The PostgreSQL test session drops and recreates the `voiceos` schema in the local
development database.
