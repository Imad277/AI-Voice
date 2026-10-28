-- VoiceOS Phase 2A tool registry and integration model. Additive; 0001-0004 untouched.
--
-- Global catalog (platform-defined, shipped with migrations, read-only for the app role):
--   tool_types, integration_providers, integration_provider_capabilities
-- Tenant-scoped (RLS, writes re-checked against the stored membership role):
--   integration_connections, tool_instances
--
-- No credential is stored anywhere: a connection holds an opaque credential_ref only
-- (secret store and broker: D-16, later). Nothing here executes a tool or calls a
-- provider; execution stays in the Tool Gateway.

-- -- global catalog ---------------------------------------------------------------------

CREATE TABLE voiceos.tool_types (
    tool_type_key        text PRIMARY KEY
        CHECK (tool_type_key ~ '^[a-z][a-z0-9_]{0,31}\.[a-z][a-z0-9_]{0,63}$'),
    name                 text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    description          text NOT NULL DEFAULT '' CHECK (length(description) <= 1000),
    schema_version       integer NOT NULL CHECK (schema_version >= 1),
    input_schema         jsonb NOT NULL
        CHECK (jsonb_typeof(input_schema) = 'object'
               AND octet_length(input_schema::text) <= 16384),
    output_schema        jsonb NOT NULL
        CHECK (jsonb_typeof(output_schema) = 'object'
               AND octet_length(output_schema::text) <= 16384),
    schema_hash          text NOT NULL CHECK (schema_hash ~ '^[0-9a-f]{64}$'),
    side_effect_class    text NOT NULL CHECK (side_effect_class IN (
        'READ_ONLY', 'REVERSIBLE_WRITE', 'IRREVERSIBLE_WRITE', 'EXTERNAL_COMMUNICATION')),
    confirmation_policy  text NOT NULL CHECK (confirmation_policy IN (
        'NONE', 'EXPLICIT_USER_CONFIRMATION', 'SERVER_VERIFIED_CONFIRMATION')),
    requires_connection  boolean NOT NULL,
    enabled              boolean NOT NULL DEFAULT true,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    -- Weakest allowed policy per side-effect class (= domain MINIMUM_CONFIRMATION).
    CHECK (CASE side_effect_class
        WHEN 'READ_ONLY' THEN true
        WHEN 'REVERSIBLE_WRITE' THEN confirmation_policy <> 'NONE'
        WHEN 'IRREVERSIBLE_WRITE' THEN confirmation_policy = 'SERVER_VERIFIED_CONFIRMATION'
        WHEN 'EXTERNAL_COMMUNICATION' THEN confirmation_policy <> 'NONE'
    END)
);

-- A tool type's contract changes only with a new schema version and a new hash.
CREATE FUNCTION voiceos.guard_tool_type() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
BEGIN
    IF NEW.tool_type_key <> OLD.tool_type_key OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'tool type identity is immutable' USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.input_schema IS DISTINCT FROM OLD.input_schema
        OR NEW.output_schema IS DISTINCT FROM OLD.output_schema)
       AND (NEW.schema_version <= OLD.schema_version OR NEW.schema_hash = OLD.schema_hash) THEN
        RAISE EXCEPTION 'a schema change needs a new schema version and hash'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_tool_type() FROM PUBLIC;

CREATE TRIGGER tool_types_guard BEFORE UPDATE ON voiceos.tool_types
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_tool_type();

CREATE TABLE voiceos.integration_providers (
    provider_key  text PRIMARY KEY
        CHECK (provider_key ~ '^[a-z][a-z0-9_]{0,31}\.[a-z][a-z0-9_]{0,63}$'),
    category      text NOT NULL CHECK (category IN ('CALENDAR', 'CRM', 'WEBHOOK')),
    display_name  text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 120),
    auth_type     text NOT NULL
        CHECK (auth_type IN ('NONE', 'OAUTH2', 'API_KEY', 'HMAC_SIGNATURE')),
    enabled       boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Which tool types a provider can serve (target of the tool instance foreign key).
CREATE TABLE voiceos.integration_provider_capabilities (
    provider_key   text NOT NULL REFERENCES voiceos.integration_providers (provider_key),
    tool_type_key  text NOT NULL REFERENCES voiceos.tool_types (tool_type_key),
    PRIMARY KEY (provider_key, tool_type_key)
);

-- -- tenant-scoped ----------------------------------------------------------------------

CREATE TABLE voiceos.integration_connections (
    connection_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES voiceos.organizations (tenant_id),
    provider_key    text NOT NULL REFERENCES voiceos.integration_providers (provider_key),
    display_name    text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 120),
    credential_ref  text CHECK (credential_ref ~ '^cred:[a-z0-9][a-z0-9._/-]{0,199}$'),
    status          text NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'ACTIVE', 'DISCONNECTED', 'ERROR', 'REVOKED')),
    configuration   jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(configuration) = 'object'
               AND octet_length(configuration::text) <= 16384),
    revision        integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, connection_id, provider_key)  -- target of the tool instance key
);

-- Identity is immutable, every update advances the revision by one, status changes follow
-- the domain transition table (CONNECTION_TRANSITIONS), and the credential reference
-- matches the provider's auth type. Applies to every role.
CREATE FUNCTION voiceos.guard_integration_connection() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
DECLARE
    provider record;
BEGIN
    SELECT p.auth_type, p.enabled INTO provider
        FROM voiceos.integration_providers p WHERE p.provider_key = NEW.provider_key;
    IF TG_OP = 'INSERT' THEN
        IF NOT coalesce(provider.enabled, false) THEN
            RAISE EXCEPTION 'integration provider is not available'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.revision <> 0 THEN
            RAISE EXCEPTION 'a new connection starts at revision 0'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        IF NEW.connection_id <> OLD.connection_id OR NEW.tenant_id <> OLD.tenant_id
           OR NEW.provider_key <> OLD.provider_key OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'connection identity is immutable'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.revision <> OLD.revision + 1 THEN
            RAISE EXCEPTION 'an update must advance the revision by one'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status <> OLD.status AND (OLD.status, NEW.status) NOT IN (VALUES
            ('PENDING', 'ACTIVE'), ('PENDING', 'ERROR'), ('PENDING', 'DISCONNECTED'),
            ('PENDING', 'REVOKED'),
            ('ACTIVE', 'DISCONNECTED'), ('ACTIVE', 'ERROR'), ('ACTIVE', 'REVOKED'),
            ('ERROR', 'ACTIVE'), ('ERROR', 'DISCONNECTED'), ('ERROR', 'REVOKED'),
            ('DISCONNECTED', 'PENDING'), ('DISCONNECTED', 'REVOKED')
        ) THEN
            RAISE EXCEPTION 'connection status transition not allowed'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF (provider.auth_type = 'NONE') <> (NEW.credential_ref IS NULL) THEN
        RAISE EXCEPTION 'credential reference does not match the provider auth type'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_integration_connection() FROM PUBLIC;

CREATE TRIGGER integration_connections_guard
    BEFORE INSERT OR UPDATE ON voiceos.integration_connections
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_integration_connection();

CREATE TABLE voiceos.tool_instances (
    tool_instance_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES voiceos.organizations (tenant_id),
    ref               text NOT NULL CHECK (ref ~ '^[a-z0-9][a-z0-9_.:-]{0,127}$'),
    tool_type_key     text NOT NULL REFERENCES voiceos.tool_types (tool_type_key),
    connection_id     uuid,
    provider_key      text,
    display_name      text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 120),
    configuration     jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(configuration) = 'object'
               AND octet_length(configuration::text) <= 16384),
    status            text NOT NULL DEFAULT 'ENABLED' CHECK (status IN ('ENABLED', 'DISABLED')),
    revision          integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, ref),
    CHECK ((connection_id IS NULL) = (provider_key IS NULL)),
    -- the connection belongs to the same organization ...
    FOREIGN KEY (tenant_id, connection_id, provider_key)
        REFERENCES voiceos.integration_connections (tenant_id, connection_id, provider_key),
    -- ... and its provider serves this tool type
    FOREIGN KEY (provider_key, tool_type_key)
        REFERENCES voiceos.integration_provider_capabilities (provider_key, tool_type_key)
);
CREATE INDEX tool_instances_connection_idx ON voiceos.tool_instances (connection_id);

CREATE FUNCTION voiceos.guard_tool_instance() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
DECLARE
    tool_type record;
BEGIN
    SELECT t.requires_connection, t.enabled INTO tool_type
        FROM voiceos.tool_types t WHERE t.tool_type_key = NEW.tool_type_key;
    IF TG_OP = 'INSERT' THEN
        IF NOT coalesce(tool_type.enabled, false) THEN
            RAISE EXCEPTION 'tool type is not available' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.revision <> 0 THEN
            RAISE EXCEPTION 'a new tool instance starts at revision 0'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        IF NEW.tool_instance_id <> OLD.tool_instance_id OR NEW.tenant_id <> OLD.tenant_id
           OR NEW.ref <> OLD.ref OR NEW.tool_type_key <> OLD.tool_type_key
           OR NEW.connection_id IS DISTINCT FROM OLD.connection_id
           OR NEW.provider_key IS DISTINCT FROM OLD.provider_key
           OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'tool instance identity is immutable'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.revision <> OLD.revision + 1 THEN
            RAISE EXCEPTION 'an update must advance the revision by one'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF tool_type.requires_connection <> (NEW.connection_id IS NOT NULL) THEN
        RAISE EXCEPTION 'tool type and connection do not match' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_tool_instance() FROM PUBLIC;

CREATE TRIGGER tool_instances_guard BEFORE INSERT OR UPDATE ON voiceos.tool_instances
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_tool_instance();

CREATE TRIGGER tool_types_touch BEFORE UPDATE ON voiceos.tool_types
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER integration_providers_touch BEFORE UPDATE ON voiceos.integration_providers
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER integration_connections_touch BEFORE UPDATE ON voiceos.integration_connections
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER tool_instances_touch BEFORE UPDATE ON voiceos.tool_instances
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();

-- -- publish check ----------------------------------------------------------------------

-- An agent version can only be published while every tool instance its configuration
-- names (tool_refs) exists in the same organization, is enabled, has an enabled tool type
-- and, where it uses a connection, an ACTIVE connection of an enabled provider. Runs with
-- the caller's rights, so RLS still applies to the lookups.
CREATE FUNCTION voiceos.guard_version_tool_refs() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
BEGIN
    IF OLD.status = 'DRAFT' AND NEW.status = 'PUBLISHED'
       AND jsonb_typeof(NEW.configuration -> 'tool_refs') = 'array'
       AND EXISTS (
           SELECT 1 FROM jsonb_array_elements_text(NEW.configuration -> 'tool_refs') r(ref)
           WHERE NOT EXISTS (
               SELECT 1
               FROM voiceos.tool_instances i
               JOIN voiceos.tool_types t ON t.tool_type_key = i.tool_type_key
               LEFT JOIN voiceos.integration_connections c
                   ON c.connection_id = i.connection_id AND c.tenant_id = i.tenant_id
               LEFT JOIN voiceos.integration_providers p ON p.provider_key = c.provider_key
               WHERE i.tenant_id = NEW.tenant_id AND i.ref = r.ref
                 AND i.status = 'ENABLED' AND t.enabled
                 AND (i.connection_id IS NULL OR (c.status = 'ACTIVE' AND p.enabled))
           )
       ) THEN
        RAISE EXCEPTION 'agent version references an unusable tool instance'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_version_tool_refs() FROM PUBLIC;

CREATE TRIGGER agent_versions_tool_refs_guard BEFORE UPDATE ON voiceos.agent_versions
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_version_tool_refs();

-- -- authorization ----------------------------------------------------------------------

-- The role list must equal voiceos.domain.identity.rbac roles_with(integrations.manage)
-- (asserted by a test).
CREATE FUNCTION voiceos.caller_can_manage_integrations() RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$ SELECT coalesce(voiceos.caller_membership_role() IN ('OWNER', 'ADMIN', 'DEVELOPER'),
                          false) $$;
REVOKE ALL ON FUNCTION voiceos.caller_can_manage_integrations() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.caller_can_manage_integrations() TO voiceos_app;

-- Catalog: read-only for the app role; written by migrations only.
GRANT SELECT ON voiceos.tool_types, voiceos.integration_providers,
    voiceos.integration_provider_capabilities TO voiceos_app;
-- Tenant tables: no DELETE (connections are disconnected/revoked, instances disabled).
GRANT SELECT, INSERT, UPDATE ON voiceos.integration_connections, voiceos.tool_instances
    TO voiceos_app;

ALTER TABLE voiceos.tool_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.tool_types FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.integration_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.integration_providers FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.integration_provider_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.integration_provider_capabilities FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.integration_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.integration_connections FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.tool_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.tool_instances FORCE ROW LEVEL SECURITY;

CREATE POLICY catalog_read ON voiceos.tool_types FOR SELECT TO voiceos_app USING (true);
CREATE POLICY catalog_read ON voiceos.integration_providers
    FOR SELECT TO voiceos_app USING (true);
CREATE POLICY catalog_read ON voiceos.integration_provider_capabilities
    FOR SELECT TO voiceos_app USING (true);

CREATE POLICY tenant_read ON voiceos.integration_connections
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());
CREATE POLICY manage_insert ON voiceos.integration_connections
    FOR INSERT TO voiceos_app
    WITH CHECK (tenant_id = voiceos.current_tenant_id()
                AND voiceos.caller_can_manage_integrations());
CREATE POLICY manage_update ON voiceos.integration_connections
    FOR UPDATE TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_integrations())
    WITH CHECK (tenant_id = voiceos.current_tenant_id()
                AND voiceos.caller_can_manage_integrations());

CREATE POLICY tenant_read ON voiceos.tool_instances
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());
CREATE POLICY manage_insert ON voiceos.tool_instances
    FOR INSERT TO voiceos_app
    WITH CHECK (tenant_id = voiceos.current_tenant_id()
                AND voiceos.caller_can_manage_integrations());
CREATE POLICY manage_update ON voiceos.tool_instances
    FOR UPDATE TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_integrations())
    WITH CHECK (tenant_id = voiceos.current_tenant_id()
                AND voiceos.caller_can_manage_integrations());

CREATE POLICY migrator_admin ON voiceos.tool_types
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.integration_providers
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.integration_provider_capabilities
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.integration_connections
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.tool_instances
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);

-- -- seed catalog -----------------------------------------------------------------------
-- Tool types are product capabilities, not external vendors. Schema hashes are
-- voiceos.domain.tools.model.schema_hash(1, input, output); a test recomputes them from
-- the stored schemas. Keys mirror the Phase 0 gateway tool names where a gateway handler
-- exists; webhook.invoke is registry metadata only (no egress before egress control) and
-- therefore disabled.
--
-- No integration providers and no capabilities are seeded: the first real integrations
-- are not decided (D-27), and test doubles are not product data. Providers are added by a
-- later migration once a provider has been decided.

INSERT INTO voiceos.tool_types (tool_type_key, name, description, schema_version,
    input_schema, output_schema, schema_hash, side_effect_class, confirmation_policy,
    requires_connection, enabled) VALUES
('calendar.list_slots', 'List calendar slots', 'Free appointment slots for one day.', 1,
 '{"type": "object", "properties": {"date": {"type": "string", "format": "date", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}}, "required": ["date"], "additionalProperties": false}',
 '{"type": "object", "properties": {"slots": {"type": "array", "maxItems": 50, "items": {"type": "object", "properties": {"slot_id": {"type": "string", "pattern": "^slot_[a-z0-9_]{1,40}$"}, "start_local": {"type": "string", "maxLength": 40}}, "required": ["slot_id", "start_local"], "additionalProperties": false}}}, "required": ["slots"], "additionalProperties": false}',
 '0364c8ab0278cfddea8393caeec77690e8125ecde2f33ee4e20006b21007d9d5',
 'READ_ONLY', 'NONE', true, true),
('calendar.book_slot', 'Book a calendar slot',
 'Books one confirmed slot; the outcome comes from the operation ledger.', 1,
 '{"type": "object", "properties": {"slot_id": {"type": "string", "pattern": "^slot_[a-z0-9_]{1,40}$"}}, "required": ["slot_id"], "additionalProperties": false}',
 '{"type": "object", "properties": {}, "additionalProperties": false}',
 'c99938156596b004e294d9f0651cad65a1f2d00b2327d4e3eba63570339d7609',
 'IRREVERSIBLE_WRITE', 'SERVER_VERIFIED_CONFIRMATION', true, true),
('crm.update_contact', 'Update CRM contact',
 'Writes the server-confirmed contact of a confirmed booking to the CRM.', 1,
 '{"type": "object", "properties": {}, "additionalProperties": false}',
 '{"type": "object", "properties": {}, "additionalProperties": false}',
 '3a0f70a6b5fd136225511541d1c9006ac02352888d28b5f5e460ff5668cb469c',
 'REVERSIBLE_WRITE', 'SERVER_VERIFIED_CONFIRMATION', true, true),
('webhook.invoke', 'Invoke webhook',
 'Registry metadata only; no egress until egress control and signing exist.', 1,
 '{"type": "object", "properties": {}, "additionalProperties": false}',
 '{"type": "object", "properties": {}, "additionalProperties": false}',
 '3a0f70a6b5fd136225511541d1c9006ac02352888d28b5f5e460ff5668cb469c',
 'EXTERNAL_COMMUNICATION', 'EXPLICIT_USER_CONFIRMATION', true, false);
