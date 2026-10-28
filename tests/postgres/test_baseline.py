"""One-time adoption of a pre-runner Phase 0 database as migration 0001 (fail closed).

These tests need the real schema names, so the session schemas are renamed aside for the
duration of each test and restored afterwards.
"""

# Schema names in the SQL below are fixed test constants, never input.
# ruff: noqa: S608

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from support import TENANT_A

from voiceos.infrastructure.postgres.migrations import (
    HISTORY_SCHEMA,
    MIGRATIONS_DIR,
    MigrationError,
    adopt_phase0_foundation,
    apply_migrations,
    discover,
)
from voiceos.tenancy.db import Conn
from voiceos.tenancy.preflight import preflight_violations

HOLD = ("voiceos_session_hold", "voiceos_migrations_session_hold")
PROBE = "voiceos_adoption_probe"


def _exists(conn: Conn, schema: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,)).fetchone()
        is not None
    )


@pytest.fixture
def bare(migrator: Conn) -> Iterator[Conn]:
    """A database without the session's voiceos schemas (restored afterwards)."""
    migrator.execute(f"ALTER SCHEMA voiceos RENAME TO {HOLD[0]}")
    migrator.execute(f"ALTER SCHEMA {HISTORY_SCHEMA} RENAME TO {HOLD[1]}")
    try:
        yield migrator
    finally:
        for schema in ("voiceos", HISTORY_SCHEMA, PROBE):
            migrator.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        migrator.execute(f"ALTER SCHEMA {HOLD[0]} RENAME TO voiceos")
        migrator.execute(f"ALTER SCHEMA {HOLD[1]} RENAME TO {HISTORY_SCHEMA}")


@pytest.fixture
def phase0(bare: Conn) -> Conn:
    """A Phase 0 database as the pre-runner script left it: 0001 applied, no history, data."""
    with bare.transaction():
        bare.execute((MIGRATIONS_DIR / "0001_foundation.sql").read_text())
    bare.execute("INSERT INTO voiceos.tenants (tenant_id, name) VALUES (%s, 'kept')", (TENANT_A,))
    return bare


def _history(conn: Conn) -> list[tuple[int, str, str]]:
    return [
        (int(v), str(n), str(m))
        for v, n, m in conn.execute(
            f"SELECT version, name, method FROM {HISTORY_SCHEMA}.schema_migrations ORDER BY version"
        ).fetchall()
    ]


def test_verified_phase0_schema_is_adopted_and_then_migrated_regularly(
    phase0: Conn, app_conn: Conn
) -> None:
    with pytest.raises(MigrationError, match="without migration history"):
        apply_migrations(phase0)  # the regular runner still refuses an unknown state
    adopt_phase0_foundation(phase0)
    assert _history(phase0) == [(1, "foundation", "baseline")]
    remaining = [m.filename for m in discover()][1:]
    assert apply_migrations(phase0) == remaining
    assert _history(phase0)[1:] == [(m.version, m.name, "applied") for m in discover()[1:]]
    kept = phase0.execute("SELECT name FROM voiceos.tenants WHERE tenant_id = %s", (TENANT_A,))
    assert kept.fetchone() == ("kept",)  # nothing was rebuilt; data untouched
    assert preflight_violations(app_conn) == []
    assert not _exists(phase0, PROBE)


@pytest.mark.parametrize(
    "manipulation",
    [
        "ALTER TABLE voiceos.booking_operations ADD COLUMN extra text",
        "ALTER TABLE voiceos.booking_operations DROP CONSTRAINT booking_operations_state_check",
        "CREATE TABLE voiceos.extra (tenant_id uuid)",
        "CREATE INDEX extra_idx ON voiceos.booking_operations (slot_id)",
        "ALTER TABLE voiceos.tenants NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE voiceos.booking_operations DISABLE ROW LEVEL SECURITY",
        "DROP POLICY tenant_isolation ON voiceos.tenants;"
        " CREATE POLICY tenant_isolation ON voiceos.tenants FOR SELECT TO voiceos_app USING (true)",
        "DROP POLICY migrator_admin ON voiceos.booking_operations",
        "GRANT DELETE ON voiceos.booking_operations TO voiceos_app",
        "GRANT SELECT ON voiceos.booking_operations TO PUBLIC",
        "GRANT USAGE ON SCHEMA voiceos TO PUBLIC",
        "GRANT EXECUTE ON FUNCTION voiceos.current_tenant_id() TO PUBLIC",
        "CREATE OR REPLACE FUNCTION voiceos.current_tenant_id() RETURNS uuid LANGUAGE sql STABLE"
        " SET search_path = pg_catalog AS $$ SELECT NULL::uuid $$",
    ],
)
def test_manipulated_phase0_schema_is_refused_and_not_repaired(
    phase0: Conn, manipulation: str
) -> None:
    phase0.execute(manipulation)
    before = phase0.execute(
        "SELECT count(*) FROM pg_class WHERE relnamespace = 'voiceos'::regnamespace"
    ).fetchone()
    with pytest.raises(MigrationError, match="does not match"):
        adopt_phase0_foundation(phase0)
    assert not _exists(phase0, HISTORY_SCHEMA)  # nothing marked as applied
    assert not _exists(phase0, PROBE)  # the probe was rolled back
    after = phase0.execute(
        "SELECT count(*) FROM pg_class WHERE relnamespace = 'voiceos'::regnamespace"
    ).fetchone()
    assert before == after  # nothing repaired or rebuilt


def test_partially_migrated_database_without_history_is_refused(phase0: Conn) -> None:
    with phase0.transaction():
        phase0.execute((MIGRATIONS_DIR / "0002_product_foundation.sql").read_text())
    with pytest.raises(MigrationError, match="does not match"):
        adopt_phase0_foundation(phase0)
    assert not _exists(phase0, HISTORY_SCHEMA)


def test_adoption_is_refused_once_history_exists(phase0: Conn) -> None:
    adopt_phase0_foundation(phase0)
    with pytest.raises(MigrationError, match="already exists"):
        adopt_phase0_foundation(phase0)  # not repeatable
    apply_migrations(phase0)
    with pytest.raises(MigrationError, match="already exists"):
        adopt_phase0_foundation(phase0)
    assert [method for *_, method in _history(phase0)].count("baseline") == 1


def test_empty_database_needs_no_baseline_and_migrates_normally(bare: Conn) -> None:
    with pytest.raises(MigrationError, match="nothing to adopt"):
        adopt_phase0_foundation(bare)
    assert not _exists(bare, HISTORY_SCHEMA)
    assert apply_migrations(bare) == [m.filename for m in discover()]
    assert {method for *_, method in _history(bare)} == {"applied"}


def test_adoption_refuses_a_leftover_probe_schema(phase0: Conn) -> None:
    phase0.execute(f"CREATE SCHEMA {PROBE}")
    with pytest.raises(MigrationError, match=PROBE):
        adopt_phase0_foundation(phase0)
    assert not _exists(phase0, HISTORY_SCHEMA)


def test_adoption_only_applies_to_the_phase0_foundation_file(phase0: Conn, tmp_path: Path) -> None:
    (tmp_path / "0001_something_else.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError, match=r"0001_foundation\.sql"):
        adopt_phase0_foundation(phase0, tmp_path)
    assert not _exists(phase0, HISTORY_SCHEMA)
