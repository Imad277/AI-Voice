-- VoiceOS Phase 2A product foundation: organizations, users, memberships, agents,
-- agent versions, deployments. Additive only: 0001 objects and policies are untouched.
-- Applied by voiceos_migrator through voiceos.infrastructure.postgres.migrations.
--
-- Conventions (CLAUDE.md rule 8, PHASE2_DOMAIN_MODEL.md):
-- * every tenant-owned table carries tenant_id (the organization id) with RLS enabled AND
--   forced; voiceos_app sees only rows of the tenant bound to the transaction;
-- * voiceos.users is the documented global exception (no tenant_id): one identity can
--   belong to several organizations. The app role may only read its own user and the
--   members of the bound organization; it cannot insert or update users;
-- * no DELETE grants: lifecycle is expressed through status values;
-- * published agent versions are immutable (trigger), also for the migrator.

-- User bound to the current transaction (set_config('app.user_id', ..., true)), like
-- current_tenant_id(): missing or empty yields NULL, which never matches.
CREATE FUNCTION voiceos.current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    SET search_path = pg_catalog
    AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;
REVOKE ALL ON FUNCTION voiceos.current_user_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.current_user_id() TO voiceos_app;

CREATE FUNCTION voiceos.touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$ BEGIN NEW.updated_at := now(); RETURN NEW; END $$;
REVOKE ALL ON FUNCTION voiceos.touch_updated_at() FROM PUBLIC;

-- Organizations: the product view of a tenant, 1:1 with the Phase 0 tenant registry.
-- Rows are created by a privileged signup path (not the app role).
CREATE TABLE voiceos.organizations (
    tenant_id   uuid PRIMARY KEY REFERENCES voiceos.tenants (tenant_id),
    name        text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
    slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'),
    status      text NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Users: global identity (documented RLS exception: no tenant_id).
-- external_subject is the identity provider subject; the provider is NOT DECIDED (D-12).
CREATE TABLE voiceos.users (
    user_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_subject  text NOT NULL UNIQUE CHECK (length(external_subject) BETWEEN 1 AND 255),
    email             text NOT NULL CHECK (email ~ '^[^@\s]+@[^@\s]+$' AND length(email) <= 320),
    display_name      text NOT NULL DEFAULT '' CHECK (length(display_name) <= 200),
    status            text NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'DISABLED')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_lower_key ON voiceos.users (lower(email));

CREATE TABLE voiceos.organization_memberships (
    tenant_id   uuid NOT NULL REFERENCES voiceos.organizations (tenant_id),
    user_id     uuid NOT NULL REFERENCES voiceos.users (user_id),
    role        text NOT NULL CHECK (role IN (
        'OWNER', 'ADMIN', 'DEVELOPER', 'OPERATOR', 'ANALYST', 'BILLING', 'READ_ONLY')),
    status      text NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('INVITED', 'ACTIVE', 'SUSPENDED', 'REMOVED')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);
CREATE INDEX organization_memberships_user_idx ON voiceos.organization_memberships (user_id);

CREATE TABLE voiceos.agents (
    agent_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES voiceos.organizations (tenant_id),
    name         text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
    description  text NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
    status       text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, agent_id)  -- target of composite foreign keys (same organization)
);

CREATE TABLE voiceos.agent_versions (
    agent_version_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    agent_id            uuid NOT NULL,
    version_number      integer NOT NULL CHECK (version_number > 0),
    status              text NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')),
    configuration       jsonb NOT NULL CHECK (jsonb_typeof(configuration) = 'object'),
    configuration_hash  text NOT NULL CHECK (configuration_hash ~ '^[0-9a-f]{64}$'),
    created_at          timestamptz NOT NULL DEFAULT now(),
    published_at        timestamptz,
    CHECK ((status = 'DRAFT') = (published_at IS NULL)),
    FOREIGN KEY (tenant_id, agent_id) REFERENCES voiceos.agents (tenant_id, agent_id),
    UNIQUE (agent_id, version_number),
    UNIQUE (tenant_id, agent_id, agent_version_id)  -- target for deployments
);

-- Published versions are evidence: nothing but PUBLISHED -> ARCHIVED may change, and only
-- drafts may be deleted. Applies to every role, including the migrator.
CREATE FUNCTION voiceos.guard_agent_version() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'DRAFT' THEN
            RAISE EXCEPTION 'agent version % is % and immutable', OLD.agent_version_id, OLD.status
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF NEW.tenant_id <> OLD.tenant_id OR NEW.agent_id <> OLD.agent_id
       OR NEW.agent_version_id <> OLD.agent_version_id
       OR NEW.version_number <> OLD.version_number OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'agent version identity is immutable' USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.status = 'DRAFT' THEN
        IF NEW.status = 'ARCHIVED' THEN
            RAISE EXCEPTION 'a draft cannot be archived; publish or delete it'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;  -- drafts may be edited and published
    END IF;
    IF OLD.status = 'PUBLISHED' AND NEW.status = 'ARCHIVED'
       AND NEW.configuration = OLD.configuration
       AND NEW.configuration_hash = OLD.configuration_hash
       AND NEW.published_at = OLD.published_at THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'agent version % is % and immutable', OLD.agent_version_id, OLD.status
        USING ERRCODE = 'check_violation';
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_agent_version() FROM PUBLIC;

CREATE TRIGGER agent_versions_immutable
    BEFORE UPDATE OR DELETE ON voiceos.agent_versions
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_agent_version();

CREATE TABLE voiceos.deployments (
    deployment_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL,
    agent_id          uuid NOT NULL,
    agent_version_id  uuid NOT NULL,
    environment       text NOT NULL CHECK (environment IN ('development', 'production')),
    status            text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, agent_id, agent_version_id)
        REFERENCES voiceos.agent_versions (tenant_id, agent_id, agent_version_id)
);
-- At most one active deployment per agent and environment.
CREATE UNIQUE INDEX deployments_one_active_idx
    ON voiceos.deployments (tenant_id, agent_id, environment) WHERE status = 'ACTIVE';
CREATE INDEX deployments_version_idx
    ON voiceos.deployments (tenant_id, agent_id, agent_version_id);

-- An active deployment must point at a published version of the same organization. Runs
-- with the caller's rights: under RLS the caller can only see its own organization's
-- versions, which is exactly the set a deployment may reference.
CREATE FUNCTION voiceos.guard_deployment() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
DECLARE
    version_status text;
BEGIN
    IF NEW.status = 'ACTIVE' THEN
        SELECT v.status INTO version_status FROM voiceos.agent_versions v
            WHERE v.agent_version_id = NEW.agent_version_id AND v.tenant_id = NEW.tenant_id;
        IF version_status IS DISTINCT FROM 'PUBLISHED' THEN
            RAISE EXCEPTION 'an active deployment requires a published agent version'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.tenant_id <> OLD.tenant_id OR NEW.agent_id <> OLD.agent_id
       OR NEW.environment <> OLD.environment OR NEW.created_at <> OLD.created_at) THEN
        RAISE EXCEPTION 'deployment identity is immutable' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_deployment() FROM PUBLIC;

CREATE TRIGGER deployments_guard
    BEFORE INSERT OR UPDATE ON voiceos.deployments
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_deployment();

CREATE TRIGGER organizations_touch BEFORE UPDATE ON voiceos.organizations
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER users_touch BEFORE UPDATE ON voiceos.users
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER organization_memberships_touch BEFORE UPDATE ON voiceos.organization_memberships
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER agents_touch BEFORE UPDATE ON voiceos.agents
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();
CREATE TRIGGER deployments_touch BEFORE UPDATE ON voiceos.deployments
    FOR EACH ROW EXECUTE FUNCTION voiceos.touch_updated_at();

-- Grants: read/insert/update only; no DELETE anywhere; no direct writes to organizations
-- (privileged signup path) or users (identity provisioning path, D-12). Memberships are
-- read-only for the app role until a privileged membership/invite path exists: a direct
-- INSERT or UPDATE of user_id would reveal through the foreign key whether a global user
-- id exists.
GRANT SELECT, UPDATE ON voiceos.organizations TO voiceos_app;
GRANT SELECT ON voiceos.users TO voiceos_app;
GRANT SELECT ON voiceos.organization_memberships TO voiceos_app;
GRANT SELECT, INSERT, UPDATE ON voiceos.agents TO voiceos_app;
GRANT SELECT, INSERT, UPDATE ON voiceos.agent_versions TO voiceos_app;
GRANT SELECT, INSERT, UPDATE ON voiceos.deployments TO voiceos_app;

ALTER TABLE voiceos.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.users FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.organization_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.organization_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.agents FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.agent_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.agent_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE voiceos.deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE voiceos.deployments FORCE ROW LEVEL SECURITY;

-- Application role: strictly the organization bound to the current transaction.
CREATE POLICY tenant_isolation ON voiceos.organizations
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());
CREATE POLICY tenant_update ON voiceos.organizations
    FOR UPDATE TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id())
    WITH CHECK (tenant_id = voiceos.current_tenant_id());

-- Users: the bound user, or members of the bound organization. Read only.
CREATE POLICY user_visibility ON voiceos.users
    FOR SELECT TO voiceos_app
    USING (
        user_id = voiceos.current_user_id()
        OR EXISTS (
            SELECT 1 FROM voiceos.organization_memberships m
            WHERE m.user_id = users.user_id AND m.tenant_id = voiceos.current_tenant_id()
        )
    );

CREATE POLICY tenant_isolation ON voiceos.organization_memberships
    FOR ALL TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id())
    WITH CHECK (tenant_id = voiceos.current_tenant_id());
CREATE POLICY tenant_isolation ON voiceos.agents
    FOR ALL TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id())
    WITH CHECK (tenant_id = voiceos.current_tenant_id());
CREATE POLICY tenant_isolation ON voiceos.agent_versions
    FOR ALL TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id())
    WITH CHECK (tenant_id = voiceos.current_tenant_id());
CREATE POLICY tenant_isolation ON voiceos.deployments
    FOR ALL TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id())
    WITH CHECK (tenant_id = voiceos.current_tenant_id());

-- Migration/admin role: explicit admin policies instead of BYPASSRLS (as in 0001).
CREATE POLICY migrator_admin ON voiceos.organizations
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.users
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.organization_memberships
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.agents
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.agent_versions
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
CREATE POLICY migrator_admin ON voiceos.deployments
    FOR ALL TO voiceos_migrator USING (true) WITH CHECK (true);
