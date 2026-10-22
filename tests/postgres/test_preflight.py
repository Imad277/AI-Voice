"""RLS preflight against the real database, including proof that the checker can fail."""

from __future__ import annotations

import pytest

from voiceos.tenancy.db import Conn
from voiceos.tenancy.preflight import PreflightError, assert_preflight, preflight_violations


def test_app_role_passes_preflight(app_conn: Conn) -> None:
    assert preflight_violations(app_conn) == []


def test_owner_role_fails_preflight(migrator: Conn) -> None:
    violations = preflight_violations(migrator)
    assert "role voiceos_migrator owns schema voiceos" in violations
    assert "role voiceos_migrator owns table booking_operations" in violations
    with pytest.raises(PreflightError):
        assert_preflight(migrator)


def test_table_without_forced_rls_or_tenant_id_fails_preflight(
    app_conn: Conn, migrator: Conn
) -> None:
    migrator.execute("CREATE TABLE voiceos.rls_probe (id int)")
    migrator.execute("ALTER TABLE voiceos.rls_probe ENABLE ROW LEVEL SECURITY")
    try:
        violations = preflight_violations(app_conn)
    finally:
        migrator.execute("DROP TABLE voiceos.rls_probe")
    assert "table rls_probe: row level security not forced" in violations
    assert "table rls_probe: no tenant_id column" in violations
