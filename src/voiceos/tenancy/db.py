"""Connections and transaction-scoped tenant binding.

The tenant is bound with ``set_config('app.tenant_id', ..., is_local => true)`` inside a
transaction, so it disappears on COMMIT/ROLLBACK and can not leak to the next user of a
pooled connection. The tenant id comes only from a trusted ``CallContext``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import TupleRow

from voiceos.config import Settings
from voiceos.core.context import CallContext

Conn = psycopg.Connection[TupleRow]


def connect_app(settings: Settings) -> Conn:
    # autocommit: no implicit transaction is ever left open; every unit of work is an
    # explicit tenant_transaction().
    return psycopg.connect(settings.app_conninfo(), autocommit=True)


def connect_migrator(settings: Settings) -> Conn:
    return psycopg.connect(settings.migrator_conninfo(), autocommit=True)


@contextmanager
def tenant_transaction(conn: Conn, context: CallContext) -> Iterator[Conn]:
    with conn.transaction():
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(context.tenant_id),))
        yield conn
