"""Fixtures for tests against the real Docker Compose PostgreSQL.

Run with the local .env loaded:  uv run --env-file .env pytest
These tests fail (not skip) when the database is unreachable, so a missing database can
never be mistaken for passing isolation tests. Each test session recreates the voiceos
schema and the migration history in the local development database and applies every
migration through the versioned runner.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from support import TENANT_A, TENANT_B

from voiceos.config import Settings, load_settings
from voiceos.infrastructure.postgres.migrations import HISTORY_SCHEMA, apply_migrations, discover
from voiceos.tenancy.db import Conn, connect_app, connect_migrator

HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if HERE in Path(item.path).parents:
            item.add_marker(pytest.mark.postgres)


@pytest.fixture(scope="session")
def settings() -> Settings:
    settings = load_settings()
    if not (settings.pg_app_password and settings.pg_migrator_password):
        pytest.fail("PostgreSQL credentials missing; run: uv run --env-file .env pytest")
    return settings


@pytest.fixture(scope="session")
def migrator(settings: Settings) -> Iterator[Conn]:
    """Admin/migration role. Also serves as the independent observer of the end state."""
    try:
        conn = connect_migrator(settings)
    except psycopg.OperationalError as exc:
        pytest.fail(f"PostgreSQL not reachable (docker compose up -d --wait): {exc}")
    conn.execute("DROP SCHEMA IF EXISTS voiceos CASCADE")
    conn.execute(f"DROP SCHEMA IF EXISTS {HISTORY_SCHEMA} CASCADE")
    applied = apply_migrations(conn)
    assert applied[0] == "0001_foundation.sql"
    assert applied == [m.filename for m in discover()]
    assert apply_migrations(conn) == []  # a second run applies nothing
    conn.execute(
        "INSERT INTO voiceos.tenants (tenant_id, name) VALUES (%s, 'canary-a'), (%s, 'canary-b')",
        (TENANT_A, TENANT_B),
    )
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _clean_ledger(migrator: Conn) -> None:
    migrator.execute("TRUNCATE voiceos.booking_operations")
    # Product foundation tables (0002). Truncation bypasses the immutability trigger,
    # which guards UPDATE/DELETE of published versions, not test resets.
    migrator.execute(
        "TRUNCATE voiceos.deployments, voiceos.agent_versions, voiceos.agents,"
        " voiceos.organization_memberships, voiceos.organizations, voiceos.users"
    )


@pytest.fixture
def app_conn(settings: Settings, migrator: Conn) -> Iterator[Conn]:
    conn = connect_app(settings)
    yield conn
    conn.close()
