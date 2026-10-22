# Tool Gateway

**Status:** Phase 0 foundation, pending Architecture/QA review and human approval.

The Tool Gateway (`voiceos/gateway/gateway.py`) is the only path from a model proposal to
a business side effect. The model never calls an adapter or mock directly.

## Pipeline (implemented)

```text
untrusted ToolRequest
  1. allowlist lookup              unknown tool              -> REJECTED UNKNOWN_TOOL
  2. authority-key screen          tenant/credential/...     -> REJECTED AUTHORITY_FIELD_IN_ARGUMENTS
  3. strict schema validation      extra/malformed args      -> REJECTED INVALID_ARGUMENTS
  4. trusted CallContext binding   no session for context    -> ContextMismatch (server error)
  5. authorization                 tool not in scopes        -> REJECTED NOT_AUTHORIZED
  6. policy                        call ended / blocked      -> REJECTED CALL_ENDED / EXECUTION_BLOCKED
  7. handler: confirmation, idempotency, mock execution
  -> authoritative ToolResult (decision, outcome, reason, gateway-issued operation_id)
```

Every decision is appended to an in-memory audit trail without argument payloads.

## Allowlist

| Tool | Arguments | Behavior |
|---|---|---|
| `contact.collect_candidate` | `name`, `phone` | stores a candidate revision; returns readback |
| `qualification.submit_candidate` | `service_type`, `budget_eur` | deterministic demo rule; independent of booking |
| `calendar.list_slots` | `date` | free slots of the context's calendar only |
| `calendar.book_slot` | `slot_id` | see below |
| `booking.get_status` | none | reconciles an uncertain booking |
| `crm.update_contact` | none | syncs the confirmed contact and booking to the CRM mock |

No argument can carry tenant, principal, scopes, credentials, calendar/CRM references,
operation/idempotency ids, URLs, SQL or shell commands. Human handover is not included.

## Booking semantics

1. An existing ledger entry for this call wins: `CONFIRMED` + same slot returns the same
   result (idempotent); `CONFIRMED` + other slot is rejected; `SUBMITTED`/`UNKNOWN` is
   rejected with `RECONCILIATION_REQUIRED` – never resubmitted.
2. Contact must be confirmed (current readback revision affirmed by the caller).
3. Slot must be read back and affirmed; a different slot needs a new confirmation.
4. The gateway builds a `BookingIntent` from the context and confirmed state, claims the
   operation in the ledger (`SUBMITTED`) and only then calls the calendar.
5. Calendar timeout or lost response -> `UNKNOWN` / outcome `BOOKING_UNKNOWN`. Slot taken
   (synchronous, authoritative refusal: no booking created) -> `REJECTED`, which is the
   only state that allows a new attempt. Success -> `CONFIRMED`.
6. `booking.get_status` / `ToolGateway.reconcile`: calendar has the operation with the same
   payload -> `CONFIRMED`. Everything else stays `UNKNOWN`: lookup timeout/error, a
   different payload, and also "not found". A negative lookup is not proof that no booking
   exists, so it never moves `UNKNOWN` to `REJECTED`/`NO_BOOKING` and never releases the
   call for rebooking. There are no blind retries.
7. CRM failure after confirmation -> `BOOKED_CRM_PENDING`; the booking is untouched.

Outcome precedence: ledger state first (`BOOKING_CONFIRMED`, `BOOKED_CRM_PENDING`,
`BOOKING_UNKNOWN`), then server flags (`BLOCKED`, `CALL_DROPPED`), else `NO_BOOKING`.

## Speech guard

`voiceos/booking/speech.py` renders booking statements only from fixed templates keyed by
the gateway result. Model text mentioning bookings is dropped. Readbacks are rendered from
server-held data.

## Assumptions

- One booking per call. Caller affirmation is detected by an exact-phrase classifier
  (placeholder; the production confirmation policy is NOT DECIDED).

## NOT DECIDED

How an uncertain booking is finally resolved when it is not found: a provider adapter
that can deliver an explicitly authoritative, final negative proof, or a manual
resolution path. Until then `BOOKING_UNKNOWN` without a found booking stays unresolved.

Production confirmation detection, retry/timeout budgets for real adapters, durable audit
log, handover tool, multi-booking calls, adapter interfaces for real providers.
