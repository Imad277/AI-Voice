"""Fixtures for tests against the real Docker Compose PostgreSQL.

Run with the local .env loaded:  uv run --env-file .env pytest
These tests fail (not skip) when the database is unreachable, so a missing database can
never be mistaken for passing isolation tests. Each test session recreates the voiceos
schema in the local development database.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from support import TENANT_A, TENANT_B

from voiceos.config import Settings, load_settings
from voiceos.tenancy.db import Conn, connect_app, connect_migrator
from voiceos.tenancy.migrate import apply_migrations

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
    assert apply_migrations(conn) == ["0001_foundation.sql"]
    conn.execute(
        "INSERT INTO voiceos.tenants (tenant_id, name) VALUES (%s, 'canary-a'), (%s, 'canary-b')",
        (TENANT_A, TENANT_B),
    )
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _clean_ledger(migrator: Conn) -> None:
    migrator.execute("TRUNCATE voiceos.booking_operations")


@pytest.fixture
def app_conn(settings: Settings, migrator: Conn) -> Iterator[Conn]:
    conn = connect_app(settings)
    yield conn
    conn.close()
