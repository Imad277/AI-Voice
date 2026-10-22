"""Tenant isolation enforced by PostgreSQL RLS itself.

All statements here are raw SQL issued as the non-owner application role, deliberately
WITHOUT tenant filters, so only the database policies stand between tenants.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import errors
from support import TENANT_A, TENANT_B, make_context

from voiceos.tenancy.db import Conn, tenant_transaction

CTX_A = make_context(TENANT_A)
CTX_B = make_context(TENANT_B)


def _seed(migrator: Conn, tenant_id: UUID, operation_id: str) -> None:
    migrator.execute(
        """INSERT INTO voiceos.booking_operations
           (tenant_id, operation_id, call_id, calendar_ref, slot_id, payload_hash, state)
           VALUES (%s, %s, %s, 'cal', 'slot_x', 'h', 'CONFIRMED')""",
        (tenant_id, operation_id, uuid4()),
    )


@pytest.fixture
def seeded(migrator: Conn) -> Conn:
    _seed(migrator, TENANT_A, "op_a")
    _seed(migrator, TENANT_B, "op_b")
    return migrator


def _insert(conn: Conn, tenant_id: UUID, operation_id: str) -> None:
    conn.execute(
        """INSERT INTO voiceos.booking_operations
           (tenant_id, operation_id, call_id, calendar_ref, slot_id, payload_hash, state)
           VALUES (%s, %s, %s, 'cal', 'slot_x', 'h', 'SUBMITTED')""",
        (tenant_id, operation_id, uuid4()),
    )


def test_runtime_role_is_the_non_owner_app_role(app_conn: Conn) -> None:
    row = app_conn.execute(
        "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    assert row == ("voiceos_app", False, False)


def test_tenant_sees_only_its_own_rows(app_conn: Conn, seeded: Conn) -> None:
    with tenant_transaction(app_conn, CTX_A) as tx:
        rows = tx.execute(
            "SELECT tenant_id, operation_id FROM voiceos.booking_operations"
        ).fetchall()
    assert rows == [(TENANT_A, "op_a")]


def test_explicit_filter_for_foreign_tenant_returns_nothing(app_conn: Conn, seeded: Conn) -> None:
    with tenant_transaction(app_conn, CTX_A) as tx:
        rows = tx.execute(
            "SELECT * FROM voiceos.booking_operations WHERE tenant_id = %s", (TENANT_B,)
        ).fetchall()
    assert rows == []


def test_insert_for_foreign_tenant_is_denied(app_conn: Conn, seeded: Conn) -> None:
    with pytest.raises(errors.InsufficientPrivilege), tenant_transaction(app_conn, CTX_A) as tx:
        _insert(tx, TENANT_B, "op_injected")
    count = seeded.execute(
        "SELECT count(*) FROM voiceos.booking_operations WHERE operation_id = 'op_injected'"
    ).fetchone()
    assert count == (0,)


def test_update_of_foreign_rows_affects_nothing(app_conn: Conn, seeded: Conn) -> None:
    with tenant_transaction(app_conn, CTX_A) as tx:
        cur = tx.execute(
            "UPDATE voiceos.booking_operations SET state = 'REJECTED' WHERE tenant_id = %s",
            (TENANT_B,),
        )
        assert cur.rowcount == 0
    state = seeded.execute(
        "SELECT state FROM voiceos.booking_operations WHERE operation_id = 'op_b'"
    ).fetchone()
    assert state == ("CONFIRMED",)


def test_moving_own_row_to_foreign_tenant_is_denied(app_conn: Conn, seeded: Conn) -> None:
    with pytest.raises(errors.InsufficientPrivilege), tenant_transaction(app_conn, CTX_A) as tx:
        tx.execute("UPDATE voiceos.booking_operations SET tenant_id = %s", (TENANT_B,))
    owner = seeded.execute(
        "SELECT tenant_id FROM voiceos.booking_operations WHERE operation_id = 'op_a'"
    ).fetchone()
    assert owner == (TENANT_A,)


def test_delete_is_not_granted(app_conn: Conn, seeded: Conn) -> None:
    with pytest.raises(errors.InsufficientPrivilege), tenant_transaction(app_conn, CTX_A) as tx:
        tx.execute("DELETE FROM voiceos.booking_operations")


def test_without_tenant_binding_nothing_is_visible_or_writable(
    app_conn: Conn, seeded: Conn
) -> None:
    assert app_conn.execute("SELECT * FROM voiceos.booking_operations").fetchall() == []
    assert app_conn.execute("SELECT * FROM voiceos.tenants").fetchall() == []
    with pytest.raises(errors.InsufficientPrivilege):
        _insert(app_conn, TENANT_A, "op_unbound")


def test_tenant_registry_is_isolated_and_read_only(app_conn: Conn) -> None:
    with tenant_transaction(app_conn, CTX_A) as tx:
        assert tx.execute("SELECT tenant_id FROM voiceos.tenants").fetchall() == [(TENANT_A,)]
    with pytest.raises(errors.InsufficientPrivilege):
        app_conn.execute(
            "INSERT INTO voiceos.tenants (tenant_id, name) VALUES (%s, 'x')", (uuid4(),)
        )


def test_reused_connection_does_not_leak_tenant_context(app_conn: Conn, seeded: Conn) -> None:
    pid = app_conn.info.backend_pid
    with tenant_transaction(app_conn, CTX_A) as tx:
        assert len(tx.execute("SELECT * FROM voiceos.booking_operations").fetchall()) == 1

    setting = app_conn.execute("SELECT current_setting('app.tenant_id', true)").fetchone()
    assert setting in ((None,), ("",))

    with tenant_transaction(app_conn, CTX_B) as tx:
        rows = tx.execute("SELECT tenant_id FROM voiceos.booking_operations").fetchall()
    assert rows == [(TENANT_B,)]
    assert app_conn.info.backend_pid == pid  # same physical connection throughout


def test_tenant_context_is_cleared_after_rollback(app_conn: Conn, seeded: Conn) -> None:
    with pytest.raises(RuntimeError), tenant_transaction(app_conn, CTX_A):
        raise RuntimeError("request failed mid-transaction")
    assert app_conn.execute("SELECT * FROM voiceos.booking_operations").fetchall() == []


@pytest.mark.parametrize(
    "statement",
    [
        "SET ROLE voiceos_migrator",
        "ALTER TABLE voiceos.booking_operations DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE voiceos.booking_operations NO FORCE ROW LEVEL SECURITY",
        "DROP POLICY tenant_isolation ON voiceos.booking_operations",
        "CREATE TABLE voiceos.shadow (tenant_id uuid)",
    ],
)
def test_app_role_cannot_weaken_isolation(app_conn: Conn, statement: str) -> None:
    with pytest.raises(psycopg.Error):
        app_conn.execute(statement)  # type: ignore[call-overload]


def test_disabling_row_security_errors_instead_of_bypassing(app_conn: Conn, seeded: Conn) -> None:
    with pytest.raises(errors.InsufficientPrivilege), tenant_transaction(app_conn, CTX_A) as tx:
        tx.execute("SET LOCAL row_security = off")
        tx.execute("SELECT * FROM voiceos.booking_operations")
