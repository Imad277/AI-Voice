# Tenancy Model

**Status:** Phase 0 foundation, pending Architecture/QA review and human approval.
The long-term tenant architecture (shared DB + RLS vs. separate databases, ADR-008) is
**NOT DECIDED**. Phase 0 implements shared PostgreSQL + RLS because it is what the
foundation must be able to test.

## Database (implemented)

PostgreSQL 18.6 (official Docker image, current supported major line), local only,
bound to `127.0.0.1`. Schema in `db/migrations/0001_foundation.sql`.

| Role | Purpose | Attributes |
|---|---|---|
| `postgres` | container superuser; creates roles once (`db/init/01_roles.sh`) | not used by application or tests |
| `voiceos_migrator` | migration/admin; owns schema and tables; independent test observer | LOGIN, no SUPERUSER, no BYPASSRLS |
| `voiceos_app` | application runtime | LOGIN, no SUPERUSER, no BYPASSRLS, NOINHERIT, owns nothing |

Tables (both tenant-owned, both carry `tenant_id`, RLS **enabled and forced**):

- `voiceos.tenants` – tenant registry; app role may only `SELECT` its own row.
- `voiceos.booking_operations` – authoritative booking ledger; primary key
  `(tenant_id, operation_id)` is the idempotency key; app role has `SELECT/INSERT/UPDATE`,
  no `DELETE`.

Policies:

- `tenant_isolation` (to `voiceos_app`): `USING` and `WITH CHECK`
  `tenant_id = voiceos.current_tenant_id()`.
- `migrator_admin` (to `voiceos_migrator`): explicit admin policy, so no login role needs
  `BYPASSRLS` and `FORCE ROW LEVEL SECURITY` stays meaningful for the owner.

## Tenant binding

`voiceos.tenancy.db.tenant_transaction(conn, context)` opens a transaction and runs
`set_config('app.tenant_id', <context.tenant_id>, true)`. The setting is transaction-local,
so it vanishes on commit or rollback and can not leak into the next use of a pooled
connection. It takes a `CallContext`, never a raw tenant id from a request. Without a
binding, `current_tenant_id()` is `NULL` and the app role sees and writes nothing.

## Preflight

`voiceos.tenancy.preflight.assert_preflight(conn)` refuses to proceed if the connected role
is superuser, has `BYPASSRLS`, is a member of the migrator role, owns the schema or any
table, or if any table lacks enabled/forced RLS or a `tenant_id` column.

## Verified by tests (real PostgreSQL, non-owner app role)

Own-tenant visibility only; foreign-tenant filter returns nothing; foreign insert denied;
foreign update affects nothing; moving a row to another tenant denied; delete not granted;
unbound transaction sees/writes nothing; tenant registry isolated and read-only; reused
physical connection carries no tenant state across transactions or after rollback; app role
cannot `SET ROLE`, disable/unforce RLS, drop policies or create tables; `row_security = off`
errors instead of bypassing; preflight passes for the app role and fails for the owner and
for a table without forced RLS or `tenant_id`.

## Documented exceptions

None. Every table carries `tenant_id`.

## NOT DECIDED

Connection pooling product and settings, migration tool, backup/restore and tenant export,
per-tenant encryption, agency/client hierarchy, separate-database option (ADR-008).
