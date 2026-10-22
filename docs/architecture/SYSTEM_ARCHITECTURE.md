# System Architecture

**Status:** Phase 0 foundation, pending Architecture/QA review and human approval.
Nothing here selects a runtime, provider or hosting model.

## Phase 0 foundation (implemented)

A single Python 3.12 package (`src/voiceos`) plus a local PostgreSQL container. No
services, queues or network clients.

| Area | Location | Responsibility |
|---|---|---|
| Core contracts | `voiceos/core/` | `CallContext`, `ToolRequest`, `ToolResult`, `BookingIntent`, `BookingOutcome` |
| Tool Gateway | `voiceos/gateway/` | allowlist, strict schemas, authorization, policy, dispatch |
| Booking domain | `voiceos/booking/` | confirmation state, ledger contract, speech guard |
| Tenant isolation | `voiceos/tenancy/` + `db/` | tenant-bound transactions, RLS preflight, Postgres ledger, migration |
| Deterministic mocks | `voiceos/mocks/` | calendar, CRM, fake STT/LLM/TTS/runtime |
| Benchmark foundation | `voiceos/benchmark/` | offline scenario runner, evidence status vocabulary |
| Configuration | `voiceos/config.py`, `.env.example` | fail-closed settings; live and recording forced off |
| Tests | `tests/unit`, `tests/postgres` | negative security tests, booking safety, real RLS |

Data flow of one tool call:

```text
FakeLLM -> ToolRequest (untrusted) ----------------+
server: CallContext (trusted) ---------------------+--> ToolGateway --> CalendarMock / CrmMock
                                                   |         |
                                                   |         +--> booking ledger (PostgreSQL, RLS)
                                                   +<-- ToolResult (authoritative)
speech guard: ToolResult -> fixed template; model text about bookings is dropped
```

Dependencies point inward: `core` has no dependencies on other packages; `gateway` uses
`core`, `booking` and the mocks; `tenancy` implements the ledger contract from `booking`.

## Assumptions

- One booking operation per call (operation id derived from tenant, call, calendar ref).
- A calendar lookup that finds the booking by operation id is authoritative. A lookup that
  finds nothing is *not* treated as authoritative: the booking stays `BOOKING_UNKNOWN`.
- Per-call confirmation state lives in process memory; only the booking ledger is persisted.

## Proposed future work (not started)

- Persist call/session state and outcomes; add further tenant-owned tables as needed.
- Real adapters behind the existing mock seams, only after the G0 freeze and approval.

## NOT DECIDED

Voice runtime, voice architecture (cascade vs. native vs. hybrid), STT, TTS, LLM,
telephony/carrier, workflow engine, hosting, observability stack, migration tooling,
service decomposition, deployment model. See `VOICE_ARCHITECTURE.md` and the open
ADR-001…010 in `docs/research/manus/validation/11_ADR_Templates.md` (not accepted ADRs).
