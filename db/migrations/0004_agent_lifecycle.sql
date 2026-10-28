-- VoiceOS Phase 2A agent lifecycle: editable drafts with optimistic concurrency, deployment
-- history support, and database-side write authorization for agents, versions and
-- deployments. Additive; 0001-0003 are untouched.
--
-- Draft storage: the editable draft lives on the agent row (draft_configuration +
-- draft_revision). One draft per agent, no extra table: an UPDATE ... WHERE
-- draft_revision = <expected> detects lost updates, and the row lock it takes serializes
-- writers. Versions remain snapshots in agent_versions; published versions stay immutable
-- (0002 trigger).

ALTER TABLE voiceos.agents
    ADD COLUMN draft_configuration jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(draft_configuration) = 'object'
               AND octet_length(draft_configuration::text) <= 262144),
    ADD COLUMN draft_revision integer NOT NULL DEFAULT 0 CHECK (draft_revision >= 0);

-- Every draft change advances the revision by exactly one; the revision never moves on
-- its own; agent identity is immutable. Applies to every role.
CREATE FUNCTION voiceos.guard_agent_draft() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
BEGIN
    IF NEW.agent_id <> OLD.agent_id OR NEW.tenant_id <> OLD.tenant_id
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'agent identity is immutable' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.draft_configuration IS DISTINCT FROM OLD.draft_configuration THEN
        IF NEW.draft_revision <> OLD.draft_revision + 1 THEN
            RAISE EXCEPTION 'a draft change must advance the revision by one'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.draft_revision <> OLD.draft_revision THEN
        RAISE EXCEPTION 'the draft revision changes only with the draft'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_agent_draft() FROM PUBLIC;

CREATE TRIGGER agents_draft_guard BEFORE UPDATE ON voiceos.agents
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_agent_draft();

-- A version that an active deployment serves cannot be archived (roll back first).
CREATE FUNCTION voiceos.guard_version_archive() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
BEGIN
    IF OLD.status = 'PUBLISHED' AND NEW.status = 'ARCHIVED' AND EXISTS (
        SELECT 1 FROM voiceos.deployments d
        WHERE d.agent_version_id = OLD.agent_version_id AND d.status = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'version % is actively deployed', OLD.agent_version_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_version_archive() FROM PUBLIC;

CREATE TRIGGER agent_versions_archive_guard BEFORE UPDATE ON voiceos.agent_versions
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_version_archive();

-- Deployment history is ordered by created_at. now() is the transaction start, so a deploy
-- that waited for the agent lock could be stamped before the binding it replaced; the
-- statement clock at insert time (taken while the lock is held) keeps history order equal
-- to activation order.
CREATE FUNCTION voiceos.stamp_deployment() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
BEGIN
    NEW.created_at := clock_timestamp();
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION voiceos.stamp_deployment() FROM PUBLIC;

CREATE TRIGGER deployments_stamp BEFORE INSERT ON voiceos.deployments
    FOR EACH ROW EXECUTE FUNCTION voiceos.stamp_deployment();

CREATE INDEX deployments_history_idx
    ON voiceos.deployments (tenant_id, agent_id, environment, created_at);

-- Write authorization re-checked in the database: the acting user (current_user_id) must
-- hold an active membership in the bound organization with a role that has the
-- permission. The role lists must equal voiceos.domain.identity.rbac roles_with(...)
-- (asserted by a test). Reads stay tenant-scoped (the data plane reads published
-- configuration with a call context and no acting user).
CREATE FUNCTION voiceos.caller_can_manage_agents() RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$ SELECT coalesce(voiceos.caller_membership_role() IN ('OWNER', 'ADMIN', 'DEVELOPER'),
                          false) $$;
REVOKE ALL ON FUNCTION voiceos.caller_can_manage_agents() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.caller_can_manage_agents() TO voiceos_app;

CREATE FUNCTION voiceos.caller_can_manage_deployments() RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$ SELECT coalesce(voiceos.caller_membership_role() IN ('OWNER', 'ADMIN', 'DEVELOPER'),
                          false) $$;
REVOKE ALL ON FUNCTION voiceos.caller_can_manage_deployments() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.caller_can_manage_deployments() TO voiceos_app;

DROP POLICY tenant_isolation ON voiceos.agents;
CREATE POLICY tenant_read ON voiceos.agents
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());
CREATE POLICY manage_insert ON voiceos.agents
    FOR INSERT TO voiceos_app
    WITH CHECK (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_agents());
CREATE POLICY manage_update ON voiceos.agents
    FOR UPDATE TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_agents())
    WITH CHECK (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_agents());

DROP POLICY tenant_isolation ON voiceos.agent_versions;
CREATE POLICY tenant_read ON voiceos.agent_versions
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());
CREATE POLICY manage_insert ON voiceos.agent_versions
    FOR INSERT TO voiceos_app
    WITH CHECK (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_agents());
CREATE POLICY manage_update ON voiceos.agent_versions
    FOR UPDATE TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_agents())
    WITH CHECK (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_agents());

DROP POLICY tenant_isolation ON voiceos.deployments;
CREATE POLICY tenant_read ON voiceos.deployments
    FOR SELECT TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id());
CREATE POLICY manage_insert ON voiceos.deployments
    FOR INSERT TO voiceos_app
    WITH CHECK (tenant_id = voiceos.current_tenant_id()
                AND voiceos.caller_can_manage_deployments());
CREATE POLICY manage_update ON voiceos.deployments
    FOR UPDATE TO voiceos_app
    USING (tenant_id = voiceos.current_tenant_id() AND voiceos.caller_can_manage_deployments())
    WITH CHECK (tenant_id = voiceos.current_tenant_id()
                AND voiceos.caller_can_manage_deployments());
