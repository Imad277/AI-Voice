"""Versioned, forward-only SQL migrations (decision register D-20: SQL-first).

Migrations are plain SQL files ``db/migrations/NNNN_name.sql`` applied by the migrator
role in version order. Each migration runs in its own transaction together with its
history row, so a failing migration leaves no partial state. History lives in the
``voiceos_migrations`` schema (owned by the migrator, no grants to the application role)
with version, name, SHA-256 checksum, applied timestamp, applying role and method
(``applied`` by this runner, or ``baseline`` for a verified Phase 0 database adopted with
``adopt_phase0_foundation``).

Fail closed, never best effort: the runner refuses to start on a malformed or duplicate
file name, a gap in the version sequence, an applied migration whose file is missing or
whose checksum changed, or a database whose ``voiceos`` schema exists without migration
history (unknown state). There are no automatic rollbacks of applied migrations.

    uv run --env-file .env python -m voiceos.infrastructure.postgres.migrations
    uv run --env-file .env python -m voiceos.infrastructure.postgres.migrations \
        adopt-phase0-foundation   # one-time: verify a pre-runner Phase 0 database as 0001
"""

from __future__ import annotations

import argparse
import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from voiceos.config import load_settings
from voiceos.tenancy.db import Conn, connect_migrator

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations"
HISTORY_SCHEMA = "voiceos_migrations"
GUARDED_SCHEMA = "voiceos"
_FILE_NAME = re.compile(r"(\d{4})_([a-z0-9]+(?:_[a-z0-9]+)*)\.sql")


class MigrationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str

    @property
    def filename(self) -> str:
        return self.path.name


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """All migrations in version order; any irregularity is an error, not a warning."""
    migrations: dict[int, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_NAME.fullmatch(path.name)
        if match is None:
            raise MigrationError(f"invalid migration file name: {path.name}")
        version = int(match.group(1))
        if version in migrations:
            raise MigrationError(f"duplicate migration version {version}: {path.name}")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        migrations[version] = Migration(version, match.group(2), path, checksum)
    ordered = [migrations[v] for v in sorted(migrations)]
    expected = list(range(1, len(ordered) + 1))
    if [m.version for m in ordered] != expected:
        raise MigrationError(f"migration versions must be 1..n without gaps: {sorted(migrations)}")
    return ordered


def _ident(name: str) -> sql.Identifier:
    return sql.Identifier(name)


def ensure_history(conn: Conn, history_schema: str) -> None:
    with conn.transaction():
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(_ident(history_schema)))
        conn.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(_ident(history_schema)))
        conn.execute(
            sql.SQL(
                """CREATE TABLE IF NOT EXISTS {}.schema_migrations (
                       version     integer PRIMARY KEY CHECK (version > 0),
                       name        text NOT NULL,
                       checksum    text NOT NULL CHECK (checksum ~ '^[0-9a-f]{{64}}$'),
                       applied_at  timestamptz NOT NULL DEFAULT now(),
                       applied_by  text NOT NULL DEFAULT current_user,
                       method      text NOT NULL DEFAULT 'applied'
                           CHECK (method IN ('applied', 'baseline'))
                   )"""
            ).format(_ident(history_schema))
        )


def schema_exists(conn: Conn, schema: str) -> bool:
    row = conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,)).fetchone()
    return row is not None


def _applied(conn: Conn, history_schema: str) -> dict[int, tuple[str, str]]:
    rows = conn.execute(
        sql.SQL("SELECT version, name, checksum FROM {}.schema_migrations ORDER BY version").format(
            _ident(history_schema)
        )
    ).fetchall()
    return {version: (name, checksum) for version, name, checksum in rows}


def verify(migrations: list[Migration], applied: dict[int, tuple[str, str]]) -> list[Migration]:
    """Pending migrations, after checking that the history is an unchanged prefix."""
    by_version = {m.version: m for m in migrations}
    for version, (name, checksum) in sorted(applied.items()):
        known = by_version.get(version)
        if known is None:
            raise MigrationError(f"applied migration {version} ({name}) has no file")
        if known.name != name or known.checksum != checksum:
            raise MigrationError(f"applied migration {version} ({name}) was modified")
    if sorted(applied) != list(range(1, len(applied) + 1)):
        raise MigrationError(f"migration history has gaps: {sorted(applied)}")
    return [m for m in migrations if m.version not in applied]


def apply_migrations(
    conn: Conn,
    directory: Path = MIGRATIONS_DIR,
    *,
    history_schema: str = HISTORY_SCHEMA,
    guarded_schema: str = GUARDED_SCHEMA,
) -> list[str]:
    """Apply pending migrations in order; returns the file names applied by this call."""
    migrations = discover(directory)
    with advisory_lock(conn, history_schema):
        if not schema_exists(conn, history_schema) and schema_exists(conn, guarded_schema):
            raise MigrationError(
                f"schema {guarded_schema} exists without migration history; refusing to guess"
                " (a pre-runner Phase 0 database can be adopted with adopt-phase0-foundation)"
            )
        ensure_history(conn, history_schema)
        pending = verify(migrations, _applied(conn, history_schema))
        done: list[str] = []
        for migration in pending:
            with conn.transaction():
                conn.execute(migration.path.read_text())  # trusted repository file
                conn.execute(
                    sql.SQL(
                        "INSERT INTO {}.schema_migrations (version, name, checksum) "
                        "VALUES (%s, %s, %s)"
                    ).format(_ident(history_schema)),
                    (migration.version, migration.name, migration.checksum),
                )
            done.append(migration.filename)
        return done


# -- one-time adoption of a pre-runner Phase 0 database ------------------------------------

PHASE0_MIGRATION = "0001_foundation.sql"
PHASE0_ROLES = ("voiceos_migrator", "voiceos_app")
_PROBE_SCHEMA = "voiceos_adoption_probe"
_PLACEHOLDER = "<schema>"

_SNAPSHOT_QUERIES: dict[str, str] = {
    "schema": """SELECT pg_get_userbyid(nspowner), nspacl::text
                 FROM pg_namespace WHERE nspname = %(s)s""",
    "relation": """SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner), c.relrowsecurity,
                          c.relforcerowsecurity, c.relacl::text
                   FROM pg_class c WHERE c.relnamespace = %(s)s::regnamespace""",
    "column": """SELECT c.relname, a.attnum, a.attname, format_type(a.atttypid, a.atttypmod),
                        a.attnotnull, pg_get_expr(d.adbin, d.adrelid), a.attidentity,
                        a.attgenerated
                 FROM pg_attribute a
                 JOIN pg_class c ON c.oid = a.attrelid
                 LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                 WHERE c.relnamespace = %(s)s::regnamespace AND a.attnum > 0
                   AND NOT a.attisdropped""",
    "constraint": """SELECT c.relname, k.conname, k.contype, pg_get_constraintdef(k.oid)
                     FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
                     WHERE k.connamespace = %(s)s::regnamespace""",
    "index": """SELECT pg_get_indexdef(i.indexrelid) FROM pg_index i
                JOIN pg_class c ON c.oid = i.indrelid
                WHERE c.relnamespace = %(s)s::regnamespace""",
    "policy": """SELECT tablename, policyname, permissive, roles::text, cmd, qual, with_check
                 FROM pg_policies WHERE schemaname = %(s)s""",
    "function": """SELECT p.proname, pg_get_function_identity_arguments(p.oid),
                          pg_get_functiondef(p.oid), pg_get_userbyid(p.proowner), p.proacl::text
                   FROM pg_proc p WHERE p.pronamespace = %(s)s::regnamespace""",
    "trigger": """SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid)
                  FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
                  WHERE c.relnamespace = %(s)s::regnamespace AND NOT t.tgisinternal""",
    "type": """SELECT typname, typtype FROM pg_type
               WHERE typnamespace = %(s)s::regnamespace AND typrelid = 0 AND typelem = 0""",
}


def catalog_snapshot(conn: Conn, schema: str) -> list[str]:
    """Security-relevant catalog state of a schema with the schema name normalized: owners,
    ACLs, RLS flags, columns, constraints, indexes, policies, functions, triggers, types."""
    rows: list[str] = []
    for section, query in _SNAPSHOT_QUERIES.items():
        for row in conn.execute(query, {"s": schema}).fetchall():
            text = " | ".join("NULL" if value is None else str(value) for value in row)
            rows.append(f"{section}: " + text.replace(f"{schema}.", f"{_PLACEHOLDER}."))
    return sorted(rows)


def _check_phase0_roles(conn: Conn) -> None:
    current = conn.execute("SELECT current_user").fetchone()
    if current is None or current[0] != "voiceos_migrator":
        raise MigrationError("baseline must run as voiceos_migrator")
    roles = conn.execute(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = ANY(%s)",
        (list(PHASE0_ROLES),),
    ).fetchall()
    found = {name: (superuser, bypass) for name, superuser, bypass in roles}
    if set(found) != set(PHASE0_ROLES):
        raise MigrationError(f"expected roles {PHASE0_ROLES}, found {sorted(found)}")
    unsafe = sorted(name for name, (superuser, bypass) in found.items() if superuser or bypass)
    if unsafe:
        raise MigrationError(f"roles must not be superuser or BYPASSRLS: {unsafe}")
    member = conn.execute(
        "SELECT pg_has_role('voiceos_app', 'voiceos_migrator', 'MEMBER')"
    ).fetchone()
    if member is None or member[0]:
        raise MigrationError("voiceos_app must not be a member of voiceos_migrator")


def _phase0_mismatch(conn: Conn, migration: Migration) -> list[str]:
    """Compare the existing schema with a fresh application of the repository 0001 file.

    Runs in a savepoint that is always rolled back: the existing schema is renamed aside,
    0001 is applied to a new ``voiceos`` schema, both catalogs are snapshotted, and nothing
    of it survives. Returns the differing snapshot rows (empty = identical).
    """
    existing: list[str] = []
    reference: list[str] = []
    with conn.transaction():
        conn.execute(
            sql.SQL("ALTER SCHEMA {} RENAME TO {}").format(
                _ident(GUARDED_SCHEMA), _ident(_PROBE_SCHEMA)
            )
        )
        existing = catalog_snapshot(conn, _PROBE_SCHEMA)
        conn.execute(migration.path.read_text())  # trusted repository file
        reference = catalog_snapshot(conn, GUARDED_SCHEMA)
        raise psycopg.Rollback()
    missing = [f"missing  {row}" for row in reference if row not in existing]
    extra = [f"extra    {row}" for row in existing if row not in reference]
    return missing + extra


def adopt_phase0_foundation(
    conn: Conn, directory: Path = MIGRATIONS_DIR, *, history_schema: str = HISTORY_SCHEMA
) -> None:
    """Record an existing pre-runner Phase 0 schema as migration 0001, only if verified.

    Preconditions (all fail closed): no migration history at all; a ``voiceos`` schema
    exists; the first repository migration is ``0001_foundation.sql``; both Phase 0 roles
    exist without superuser/BYPASSRLS and the app role is not a migrator member; and the
    existing schema's catalog is identical to a fresh application of that file. Then only
    the history row for version 1 (method ``baseline``) is written; nothing is repaired.
    Later migrations are applied by the regular ``apply_migrations``.
    """
    first = discover(directory)[0]
    if first.filename != PHASE0_MIGRATION:
        raise MigrationError(f"first migration must be {PHASE0_MIGRATION}, not {first.filename}")
    with advisory_lock(conn, history_schema):
        if schema_exists(conn, history_schema):
            raise MigrationError("migration history already exists; baseline is not applicable")
        if not schema_exists(conn, GUARDED_SCHEMA):
            raise MigrationError(
                f"schema {GUARDED_SCHEMA} does not exist; nothing to adopt, run apply instead"
            )
        if schema_exists(conn, _PROBE_SCHEMA):
            raise MigrationError(f"schema {_PROBE_SCHEMA} exists; refusing to continue")
        _check_phase0_roles(conn)
        with conn.transaction():
            mismatch = _phase0_mismatch(conn, first)
            if mismatch:
                shown = "; ".join(mismatch[:5])
                raise MigrationError(
                    f"existing schema does not match {PHASE0_MIGRATION} ({len(mismatch)} "
                    f"differences): {shown}"
                )
            ensure_history(conn, history_schema)
            conn.execute(
                sql.SQL(
                    "INSERT INTO {}.schema_migrations (version, name, checksum, method) "
                    "VALUES (%s, %s, %s, 'baseline')"
                ).format(_ident(history_schema)),
                (first.version, first.name, first.checksum),
            )


@contextmanager
def advisory_lock(conn: Conn, history_schema: str) -> Iterator[None]:
    """Session-level lock so two runners never work on the same history concurrently."""
    lock = int.from_bytes(hashlib.sha256(history_schema.encode()).digest()[:8], "big", signed=True)
    conn.execute("SELECT pg_advisory_lock(%s)", (lock,))
    try:
        yield
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (lock,))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m voiceos.infrastructure.postgres.migrations")
    parser.add_argument("command", nargs="?", choices=["apply", "adopt-phase0-foundation"])
    command = parser.parse_args(argv).command or "apply"
    with connect_migrator(load_settings()) as conn:
        if command == "adopt-phase0-foundation":
            adopt_phase0_foundation(conn)
            print("adopted existing Phase 0 schema as 0001_foundation.sql (verified)")
        applied = apply_migrations(conn)
    print("applied: " + ", ".join(applied) if applied else "up to date; nothing applied")


if __name__ == "__main__":
    main()
