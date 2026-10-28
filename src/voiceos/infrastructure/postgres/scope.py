"""Organization-scoped transactions for the control plane.

The control plane counterpart of the Phase 0 ``tenant_transaction`` (which binds from a
``CallContext``): the tenant (and optionally the acting user) is bound with
``set_config(..., is_local => true)`` inside a transaction, so it disappears on COMMIT or
ROLLBACK and cannot leak to the next user of a pooled connection. The only accepted input
is a trusted ``OrganizationScope`` - never a raw id from a request.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from voiceos.domain.identity.model import OrganizationScope
from voiceos.tenancy.db import Conn


@contextmanager
def organization_transaction(conn: Conn, scope: OrganizationScope) -> Iterator[Conn]:
    if not isinstance(scope, OrganizationScope):
        raise TypeError("organization_transaction requires a trusted OrganizationScope")
    with conn.transaction():
        conn.execute(
            "SELECT set_config('app.tenant_id', %s, true), set_config('app.user_id', %s, true)",
            (str(scope.organization_id), str(scope.user_id) if scope.user_id else ""),
        )
        yield conn
