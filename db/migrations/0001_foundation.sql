-- VoiceOS Phase 0 foundation schema. Applied by voiceos_migrator, never by voiceos_app.
--
-- Every table is tenant-owned and carries tenant_id. RLS is enabled AND forced on every
-- table, so even the owning migrator role is subject to policies. The application role
-- only ever sees rows of the tenant bound to the current transaction via
-- set_config('app.tenant_id', ..., true) (transaction-local).

CREATE SCHEMA voiceos;
REVOKE ALL ON SCHEMA voiceos FROM PUBLIC;
GRANT USAGE ON SCHEMA voiceos TO voiceos_app;

-- Tenant bound to the current transaction. Missing or empty setting yields NULL, and
-- NULL never equals a tenant_id, so an unbound transaction sees and writes nothing.
CREATE FUNCTION voiceos.current_tenant_id() RETURNS uuid
    LANGUAGE sql STABLE
    SET search_path = pg_catalog
    AS $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;
REVOKE ALL ON FUNCTION voiceos.current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.current_tenant_id() TO voiceos_app;

-- Tenant registry. Rows are created by admin/migration responsibility only.
CREATE TABLE voiceos.tenants (
    tenant_id   uuid PRIMARY KEY,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Authoritative booking ledger: one row per semantic booking operation.
-- (tenant_id, operation_id) is the idempotency key; a second claim of the same
-- operation cannot create a second row.
CREATE TABLE voiceos.booking_operations (
    tenant_id            uuid NOT NULL REFERENCES voiceos.tenants (tenant_id),
    operation_id         text NOT NULL,
    call_id              uuid NOT NULL,
    calendar_ref         text NOT NULL,
    slot_id              text NOT NULL,
    payload_hash         text NOT NULL,
    state                text NOT NULL
        CHECK (state IN ('SUBMITTED', 'CONFIRMED', 'UNKNOWN', 'REJECTED')),
    calendar_booking_id  text,
    crm_state            text NOT NULL DEFAULT 'NOT_STARTED'
        CHECK (crm_state IN ('NOT_STARTED', 'SYNCED', 'PENDING')),
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, operation_id)
);

GRANT SELECT ON voiceos.tenants TO voiceos_app;
GRANT SELECT, INSERT, UPDATE ON voiceos.booking_operations TO voiceos_app;

ALTER TABLE voiceos.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.booking_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.booking_operations FORCE ROW LEVEL SECURITY;

-- Application role: strictly the tenant bound to the current transaction, for reads
-- (USING) and writes (WITH CHECK).
CREATE POLICY tenant_isolation ON voiceos.tenants
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());

CREATE POLICY tenant_isolation ON voiceos.booking_operations
    FOR ALL TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id())
    WITH CHECK (tenant_id = voiceos.current_tenant_id());

-- Migration/admin role: explicit administrative policy instead of BYPASSRLS, so FORCE RLS
-- stays meaningful and no login role in the system carries BYPASSRLS.
CREATE POLICY migrator_admin ON voiceos.tenants
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);

CREATE POLICY migrator_admin ON voiceos.booking_operations
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
