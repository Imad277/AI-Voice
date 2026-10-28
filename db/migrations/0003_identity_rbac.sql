-- VoiceOS Phase 2A identity and RBAC: narrow privileged paths for identity resolution,
-- organization creation and membership management, a last-owner guard, and tighter
-- visibility of invitations. Additive; 0001 and 0002 are untouched.
--
-- Rules for every SECURITY DEFINER function below:
-- * owned by voiceos_migrator (the migration role), never by voiceos_app;
-- * fixed search_path = pg_catalog, every object schema-qualified, no dynamic SQL;
-- * EXECUTE revoked from PUBLIC and granted to voiceos_app only where the app needs it;
-- * tenant and acting user come only from the transaction binding (current_tenant_id(),
--   current_user_id()) that trusted server code sets - never from a parameter;
-- * the caller's role is re-checked against the stored, active membership. The roles
--   allowed to manage members ('OWNER', 'ADMIN') must equal the roles holding
--   members.manage in voiceos.domain.identity.rbac (asserted by a test).
--
-- Error codes (SQLSTATE class VO): VOA01 last owner, VOA02 member not found,
-- VOA03 not permitted, VOA04 invalid request.

-- Role of the acting user's active membership in the bound, active organization (or NULL).
CREATE FUNCTION voiceos.caller_membership_role() RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
        SELECT m.role
        FROM voiceos.organization_memberships m
        JOIN voiceos.organizations o ON o.tenant_id = m.tenant_id
        JOIN voiceos.users u ON u.user_id = m.user_id
        WHERE m.tenant_id = voiceos.current_tenant_id()
          AND m.user_id = voiceos.current_user_id()
          AND m.status = 'ACTIVE' AND o.status = 'ACTIVE' AND u.status = 'ACTIVE'
    $$;
REVOKE ALL ON FUNCTION voiceos.caller_membership_role() FROM PUBLIC;

-- Identity resolution: an authenticated external subject (from trusted server code) to an
-- active user id, or NULL. Not a client-facing lookup.
CREATE FUNCTION voiceos.resolve_external_subject(p_external_subject text) RETURNS uuid
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
        SELECT u.user_id FROM voiceos.users u
        WHERE u.external_subject = p_external_subject AND u.status = 'ACTIVE'
    $$;
REVOKE ALL ON FUNCTION voiceos.resolve_external_subject(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.resolve_external_subject(text) TO voiceos_app;

-- Memberships of the bound user across organizations (RLS only shows one tenant).
CREATE FUNCTION voiceos.my_memberships()
    RETURNS TABLE (tenant_id uuid, role text, status text, organization_status text)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
        SELECT m.tenant_id, m.role, m.status, o.status
        FROM voiceos.organization_memberships m
        JOIN voiceos.organizations o ON o.tenant_id = m.tenant_id
        JOIN voiceos.users u ON u.user_id = m.user_id
        WHERE m.user_id = voiceos.current_user_id() AND u.status = 'ACTIVE'
        ORDER BY m.tenant_id
    $$;
REVOKE ALL ON FUNCTION voiceos.my_memberships() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.my_memberships() TO voiceos_app;

-- Atomic organization creation: tenant registry row, organization, and the bound user as
-- its active OWNER. Any failure rolls back all three.
CREATE FUNCTION voiceos.create_organization(p_name text, p_slug text) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
DECLARE
    v_user uuid := voiceos.current_user_id();
    v_tenant uuid := gen_random_uuid();
BEGIN
    IF v_user IS NULL OR NOT EXISTS (
        SELECT 1 FROM voiceos.users u WHERE u.user_id = v_user AND u.status = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    INSERT INTO voiceos.tenants (tenant_id, name) VALUES (v_tenant, p_name);
    INSERT INTO voiceos.organizations (tenant_id, name, slug) VALUES (v_tenant, p_name, p_slug);
    INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role, status)
        VALUES (v_tenant, v_user, 'OWNER', 'ACTIVE');
    RETURN v_tenant;
END $$;
REVOKE ALL ON FUNCTION voiceos.create_organization(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.create_organization(text, text) TO voiceos_app;

-- Invite a user (by external subject or email) into the bound organization. Returns
-- nothing either way: an unknown identity, an existing member and a new invitation are
-- indistinguishable to the caller. An invitation becomes authority only when the invited
-- user accepts it (accept_membership).
CREATE FUNCTION voiceos.add_member(p_identifier text, p_role text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
DECLARE
    v_tenant uuid := voiceos.current_tenant_id();
    v_caller text := voiceos.caller_membership_role();
    v_identifier text := btrim(coalesce(p_identifier, ''));
    v_target uuid;
    v_status text;
BEGIN
    IF v_caller IS NULL OR v_caller NOT IN ('OWNER', 'ADMIN') THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    IF p_role IS NULL OR p_role NOT IN
        ('OWNER', 'ADMIN', 'DEVELOPER', 'OPERATOR', 'ANALYST', 'BILLING', 'READ_ONLY')
        OR v_identifier = '' THEN
        RAISE EXCEPTION 'invalid request' USING ERRCODE = 'VOA04';
    END IF;
    IF p_role = 'OWNER' AND v_caller <> 'OWNER' THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    PERFORM 1 FROM voiceos.organizations o WHERE o.tenant_id = v_tenant FOR UPDATE;
    SELECT u.user_id INTO v_target FROM voiceos.users u
        WHERE u.status = 'ACTIVE'
          AND (u.external_subject = v_identifier OR lower(u.email) = lower(v_identifier))
        ORDER BY (u.external_subject = v_identifier) DESC
        LIMIT 1;
    IF v_target IS NULL THEN
        RETURN;
    END IF;
    SELECT m.status INTO v_status FROM voiceos.organization_memberships m
        WHERE m.tenant_id = v_tenant AND m.user_id = v_target FOR UPDATE;
    IF v_status IS NULL THEN
        INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role, status)
            VALUES (v_tenant, v_target, p_role, 'INVITED');
    ELSIF v_status IN ('REMOVED', 'SUSPENDED') THEN
        UPDATE voiceos.organization_memberships SET status = 'INVITED', role = p_role
            WHERE tenant_id = v_tenant AND user_id = v_target;
    ELSIF v_status = 'INVITED' THEN
        UPDATE voiceos.organization_memberships SET role = p_role
            WHERE tenant_id = v_tenant AND user_id = v_target;
    END IF;  -- an ACTIVE membership stays unchanged
END $$;
REVOKE ALL ON FUNCTION voiceos.add_member(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.add_member(text, text) TO voiceos_app;

-- The bound user accepts its own pending invitation to an active organization.
CREATE FUNCTION voiceos.accept_membership(p_tenant_id uuid) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
BEGIN
    UPDATE voiceos.organization_memberships m SET status = 'ACTIVE'
        WHERE m.tenant_id = p_tenant_id AND m.user_id = voiceos.current_user_id()
          AND m.status = 'INVITED'
          AND EXISTS (SELECT 1 FROM voiceos.organizations o
                      WHERE o.tenant_id = m.tenant_id AND o.status = 'ACTIVE')
          AND EXISTS (SELECT 1 FROM voiceos.users u
                      WHERE u.user_id = m.user_id AND u.status = 'ACTIVE');
    RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION voiceos.accept_membership(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.accept_membership(uuid) TO voiceos_app;

-- Change the role of an active or suspended member of the bound organization.
CREATE FUNCTION voiceos.change_member_role(p_user_id uuid, p_role text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
DECLARE
    v_tenant uuid := voiceos.current_tenant_id();
    v_caller text := voiceos.caller_membership_role();
    v_current text;
BEGIN
    IF v_caller IS NULL OR v_caller NOT IN ('OWNER', 'ADMIN') THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    IF p_role IS NULL OR p_role NOT IN
        ('OWNER', 'ADMIN', 'DEVELOPER', 'OPERATOR', 'ANALYST', 'BILLING', 'READ_ONLY') THEN
        RAISE EXCEPTION 'invalid request' USING ERRCODE = 'VOA04';
    END IF;
    PERFORM 1 FROM voiceos.organizations o WHERE o.tenant_id = v_tenant FOR UPDATE;
    SELECT m.role INTO v_current FROM voiceos.organization_memberships m
        WHERE m.tenant_id = v_tenant AND m.user_id = p_user_id
          AND m.status IN ('ACTIVE', 'SUSPENDED')
        FOR UPDATE;
    IF v_current IS NULL THEN
        RAISE EXCEPTION 'member not found' USING ERRCODE = 'VOA02';
    END IF;
    IF (v_current = 'OWNER' OR p_role = 'OWNER') AND v_caller <> 'OWNER' THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    UPDATE voiceos.organization_memberships SET role = p_role
        WHERE tenant_id = v_tenant AND user_id = p_user_id;
END $$;
REVOKE ALL ON FUNCTION voiceos.change_member_role(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.change_member_role(uuid, text) TO voiceos_app;

-- Deactivate (status REMOVED) a member of the bound organization. Idempotent.
CREATE FUNCTION voiceos.deactivate_member(p_user_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog
    AS $$
DECLARE
    v_tenant uuid := voiceos.current_tenant_id();
    v_caller text := voiceos.caller_membership_role();
    v_role text;
    v_status text;
BEGIN
    IF v_caller IS NULL OR v_caller NOT IN ('OWNER', 'ADMIN') THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    PERFORM 1 FROM voiceos.organizations o WHERE o.tenant_id = v_tenant FOR UPDATE;
    SELECT m.role, m.status INTO v_role, v_status FROM voiceos.organization_memberships m
        WHERE m.tenant_id = v_tenant AND m.user_id = p_user_id
          AND m.status IN ('ACTIVE', 'SUSPENDED', 'REMOVED')
        FOR UPDATE;
    IF v_status IS NULL THEN
        RAISE EXCEPTION 'member not found' USING ERRCODE = 'VOA02';
    END IF;
    IF v_status = 'REMOVED' THEN
        RETURN;
    END IF;
    IF v_role = 'OWNER' AND v_caller <> 'OWNER' THEN
        RAISE EXCEPTION 'not permitted' USING ERRCODE = 'VOA03';
    END IF;
    UPDATE voiceos.organization_memberships SET status = 'REMOVED'
        WHERE tenant_id = v_tenant AND user_id = p_user_id;
END $$;
REVOKE ALL ON FUNCTION voiceos.deactivate_member(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION voiceos.deactivate_member(uuid) TO voiceos_app;

-- Last-owner guard for every role (including direct migrator changes): an active
-- organization always keeps at least one active OWNER. The organization row is locked
-- first, so concurrent demotions of different owners are serialized and the second one
-- sees the first one's committed change.
CREATE FUNCTION voiceos.guard_last_owner() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
    AS $$
DECLARE
    v_org_status text;
BEGIN
    IF OLD.role = 'OWNER' AND OLD.status = 'ACTIVE'
       AND (TG_OP = 'DELETE' OR NEW.role <> 'OWNER' OR NEW.status <> 'ACTIVE') THEN
        SELECT o.status INTO v_org_status FROM voiceos.organizations o
            WHERE o.tenant_id = OLD.tenant_id FOR UPDATE;
        IF v_org_status = 'ACTIVE' AND NOT EXISTS (
            SELECT 1 FROM voiceos.organization_memberships m
            WHERE m.tenant_id = OLD.tenant_id AND m.role = 'OWNER' AND m.status = 'ACTIVE'
        ) THEN
            RAISE EXCEPTION 'an active organization needs at least one active owner'
                USING ERRCODE = 'VOA01';
        END IF;
    END IF;
    RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION voiceos.guard_last_owner() FROM PUBLIC;

CREATE TRIGGER organization_memberships_last_owner
    AFTER UPDATE OR DELETE ON voiceos.organization_memberships
    FOR EACH ROW EXECUTE FUNCTION voiceos.guard_last_owner();

-- Visibility: invitations are not visible to the organization until accepted (no
-- user-existence signal through add_member), only to the invited user itself.
DROP POLICY tenant_isolation ON voiceos.organization_memberships;
CREATE POLICY member_visibility ON voiceos.organization_memberships
    FOR SELECT TO voiceos_app
    USING (
        tenant_id = voiceos.current_tenant_id()
        AND (status <> 'INVITED' OR user_id = voiceos.current_user_id())
    );

-- Users: self, or active/suspended members of the bound organization (not invitees).
DROP POLICY user_visibility ON voiceos.users;
CREATE POLICY user_visibility ON voiceos.users
    FOR SELECT TO voiceos_app
    USING (
        user_id = voiceos.current_user_id()
        OR EXISTS (
            SELECT 1 FROM voiceos.organization_memberships m
            WHERE m.user_id = users.user_id AND m.tenant_id = voiceos.current_tenant_id()
              AND m.status IN ('ACTIVE', 'SUSPENDED')
        )
    );
