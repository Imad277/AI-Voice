"""RLS preflight: run as the application role before trusting tenant isolation.

Any violation is a hard failure even if no leak has been observed: the application role
must not be superuser, must not have BYPASSRLS, must not own (or be able to assume the
owner of) protected tables, and every table must have RLS enabled and forced and carry
tenant_id.
"""

from __future__ import annotations

from voiceos.tenancy.db import Conn

SCHEMA = "voiceos"
MIGRATOR_ROLE = "voiceos_migrator"


class PreflightError(Exception):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("; ".join(violations))
        self.violations = violations


def preflight_violations(conn: Conn) -> list[str]:
    violations: list[str] = []

    row = conn.execute(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    if row is None:
        return ["current role not found in pg_roles"]
    role, is_super, bypass = row
    if is_super:
        violations.append(f"role {role} is superuser")
    if bypass:
        violations.append(f"role {role} has BYPASSRLS")

    member = conn.execute(
        "SELECT pg_has_role(current_user, %s, 'MEMBER')", (MIGRATOR_ROLE,)
    ).fetchone()
    if member is not None and member[0] and role != MIGRATOR_ROLE:
        violations.append(f"role {role} is a member of {MIGRATOR_ROLE}")

    schema_owner = conn.execute(
        "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s", (SCHEMA,)
    ).fetchone()
    if schema_owner is None:
        return [*violations, f"schema {SCHEMA} does not exist (not migrated)"]
    if schema_owner[0] == role:
        violations.append(f"role {role} owns schema {SCHEMA}")

    tables = conn.execute(
        """
        SELECT c.relname, pg_get_userbyid(c.relowner), c.relrowsecurity, c.relforcerowsecurity,
               EXISTS (SELECT 1 FROM pg_attribute a
                       WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
        ORDER BY c.relname
        """,
        (SCHEMA,),
    ).fetchall()
    if not tables:
        violations.append(f"schema {SCHEMA} has no tables")
    for name, owner, rls, force, has_tenant_id in tables:
        if owner == role:
            violations.append(f"role {role} owns table {name}")
        if not rls:
            violations.append(f"table {name}: row level security not enabled")
        if not force:
            violations.append(f"table {name}: row level security not forced")
        if not has_tenant_id:
            violations.append(f"table {name}: no tenant_id column")
    return violations


def assert_preflight(conn: Conn) -> None:
    violations = preflight_violations(conn)
    if violations:
        raise PreflightError(violations)
