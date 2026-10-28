"""Versioned migration runner against the real database (fail-closed behavior).

Runner behavior is exercised on throwaway migrations in scratch schemas, so the session
schema used by the other PostgreSQL tests is never touched; the last test checks the
history the session itself recorded for the repository migrations.
"""

# Table and schema names in the SQL below are fixed test constants, never input.
# ruff: noqa: S608

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from voiceos.infrastructure.postgres.migrations import (
    HISTORY_SCHEMA,
    MigrationError,
    apply_migrations,
    discover,
)
from voiceos.tenancy.db import Conn

GUARD = "voiceos_rt"
HISTORY = "voiceos_rt_history"


@pytest.fixture
def scratch(migrator: Conn) -> Iterator[Conn]:
    migrator.execute(f"DROP SCHEMA IF EXISTS {GUARD} CASCADE")
    migrator.execute(f"DROP SCHEMA IF EXISTS {HISTORY} CASCADE")
    yield migrator
    migrator.execute(f"DROP SCHEMA IF EXISTS {GUARD} CASCADE")
    migrator.execute(f"DROP SCHEMA IF EXISTS {HISTORY} CASCADE")


def _write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body)
    return path


def _run(conn: Conn, directory: Path) -> list[str]:
    return apply_migrations(conn, directory, history_schema=HISTORY, guarded_schema=GUARD)


def _history(conn: Conn) -> list[tuple[int, str, str]]:
    return [
        (int(v), str(n), str(c))
        for v, n, c in conn.execute(
            f"SELECT version, name, checksum FROM {HISTORY}.schema_migrations ORDER BY version"
        ).fetchall()
    ]


def _two(directory: Path) -> None:
    # Written out of order on purpose: application order comes from the version only.
    _write(directory, "0002_add_note.sql", f"ALTER TABLE {GUARD}.item ADD COLUMN note text;")
    _write(
        directory, "0001_create.sql", f"CREATE SCHEMA {GUARD}; CREATE TABLE {GUARD}.item (id int);"
    )


def test_empty_database_applies_all_in_order_and_records_checksums(
    scratch: Conn, tmp_path: Path
) -> None:
    _two(tmp_path)
    assert _run(scratch, tmp_path) == ["0001_create.sql", "0002_add_note.sql"]
    expected = [
        (1, "create", hashlib.sha256((tmp_path / "0001_create.sql").read_bytes()).hexdigest()),
        (2, "add_note", hashlib.sha256((tmp_path / "0002_add_note.sql").read_bytes()).hexdigest()),
    ]
    assert _history(scratch) == expected
    assert _run(scratch, tmp_path) == []  # second run: nothing re-applied
    assert _history(scratch) == expected


def test_new_migration_is_applied_incrementally(scratch: Conn, tmp_path: Path) -> None:
    _write(
        tmp_path, "0001_create.sql", f"CREATE SCHEMA {GUARD}; CREATE TABLE {GUARD}.item (id int);"
    )
    assert _run(scratch, tmp_path) == ["0001_create.sql"]
    _write(tmp_path, "0002_add_note.sql", f"ALTER TABLE {GUARD}.item ADD COLUMN note text;")
    assert _run(scratch, tmp_path) == ["0002_add_note.sql"]


def test_modified_applied_migration_is_detected(scratch: Conn, tmp_path: Path) -> None:
    _two(tmp_path)
    _run(scratch, tmp_path)
    _write(
        tmp_path, "0001_create.sql", f"CREATE SCHEMA {GUARD}; CREATE TABLE {GUARD}.item (x int);"
    )
    _write(tmp_path, "0003_more.sql", f"CREATE TABLE {GUARD}.more (id int);")
    with pytest.raises(MigrationError, match="modified"):
        _run(scratch, tmp_path)
    assert [v for v, _, _ in _history(scratch)] == [1, 2]  # nothing new applied


def test_applied_migration_without_file_is_detected(scratch: Conn, tmp_path: Path) -> None:
    _two(tmp_path)
    _run(scratch, tmp_path)
    (tmp_path / "0002_add_note.sql").unlink()
    with pytest.raises(MigrationError, match="has no file"):
        _run(scratch, tmp_path)


def test_history_gap_is_detected(scratch: Conn, tmp_path: Path) -> None:
    _two(tmp_path)
    _run(scratch, tmp_path)
    scratch.execute(f"DELETE FROM {HISTORY}.schema_migrations WHERE version = 1")
    with pytest.raises(MigrationError, match="gaps"):
        _run(scratch, tmp_path)


def test_failing_migration_rolls_back_completely(scratch: Conn, tmp_path: Path) -> None:
    _write(
        tmp_path, "0001_create.sql", f"CREATE SCHEMA {GUARD}; CREATE TABLE {GUARD}.item (id int);"
    )
    _write(
        tmp_path,
        "0002_broken.sql",
        f"CREATE TABLE {GUARD}.half (id int); SELECT * FROM {GUARD}.does_not_exist;",
    )
    with pytest.raises(psycopg.errors.UndefinedTable):
        _run(scratch, tmp_path)
    assert [v for v, _, _ in _history(scratch)] == [1]  # 0001 committed, 0002 not recorded
    half = scratch.execute("SELECT to_regclass(%s)", (f"{GUARD}.half",)).fetchone()
    assert half == (None,)  # no partial state of the failed migration
    _write(tmp_path, "0002_broken.sql", f"CREATE TABLE {GUARD}.half (id int);")
    assert _run(scratch, tmp_path) == ["0002_broken.sql"]  # lock released, run resumes


def test_unknown_schema_state_is_refused(scratch: Conn, tmp_path: Path) -> None:
    scratch.execute(f"CREATE SCHEMA {GUARD}")  # exists, but no migration history
    _two(tmp_path)
    with pytest.raises(MigrationError, match="without migration history"):
        _run(scratch, tmp_path)
    exists = scratch.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (HISTORY,)).fetchone()
    assert exists is None


def test_invalid_files_stop_the_run_before_any_change(scratch: Conn, tmp_path: Path) -> None:
    _two(tmp_path)
    _write(tmp_path, "0002_duplicate.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="duplicate"):
        _run(scratch, tmp_path)
    exists = scratch.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (GUARD,)).fetchone()
    assert exists is None


def test_history_is_not_visible_to_the_app_role(app_conn: Conn) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute(f"SELECT * FROM {HISTORY_SCHEMA}.schema_migrations")


def test_session_history_matches_the_repository_migrations(migrator: Conn) -> None:
    rows = migrator.execute(
        f"SELECT version, name, checksum, applied_by FROM {HISTORY_SCHEMA}.schema_migrations"
        " ORDER BY version"
    ).fetchall()
    assert [(v, n, c) for v, n, c, _ in rows] == [
        (m.version, m.name, m.checksum) for m in discover()
    ]
    assert {by for *_, by in rows} == {"voiceos_migrator"}
