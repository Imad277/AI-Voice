"""Apply db/migrations as the migrator role.

Phase 0 has a single migration and no migration tool (tool choice is NOT DECIDED). The
runner refuses to touch an already migrated database.

    uv run --env-file .env python -m voiceos.tenancy.migrate
"""

from __future__ import annotations

from pathlib import Path

from voiceos.config import load_settings
from voiceos.tenancy.db import Conn, connect_migrator

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "db" / "migrations"


def apply_migrations(conn: Conn) -> list[str]:
    exists = conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'voiceos'").fetchone()
    if exists:
        return []
    applied = []
    with conn.transaction():
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.execute(path.read_text())  # trusted repository file, no parameters
            applied.append(path.name)
    return applied


def main() -> None:
    with connect_migrator(load_settings()) as conn:
        applied = apply_migrations(conn)
    print("applied: " + ", ".join(applied) if applied else "already migrated; nothing applied")


if __name__ == "__main__":
    main()
