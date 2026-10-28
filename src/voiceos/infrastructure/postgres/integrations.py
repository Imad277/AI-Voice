"""PostgreSQL implementation of the tool registry and integration store.

Every operation runs in an organization-scoped transaction built from the principal; the
tenant of new rows is ``voiceos.current_tenant_id()``, never a parameter. Writes first ask
the database whether the acting user may manage integrations (0005) and then rely on RLS
policies, foreign keys and guard triggers as the second line. The global catalog is read
only; this adapter has no statement that writes to it.
"""

# Column lists in the SQL below are module constants; values are always parameters.
# ruff: noqa: S608

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from psycopg import errors
from psycopg.types.json import Jsonb

from voiceos.application.control_plane.integrations import (
    ConnectionNotFound,
    ConnectionView,
    IntegrationConflict,
    ProviderView,
    StaleRevision,
    ToolInstanceNotFound,
    ToolInstanceView,
    ToolRefState,
    ToolTypeView,
)
from voiceos.domain.identity.rbac import Permission, PermissionDenied, Principal
from voiceos.domain.integrations.model import (
    AuthType,
    ConnectionId,
    ConnectionStatus,
    CredentialRef,
    ProviderCategory,
    ProviderKey,
)
from voiceos.domain.tools.model import (
    ConfirmationPolicy,
    SideEffectClass,
    ToolInstanceId,
    ToolInstanceRef,
    ToolInstanceStatus,
    ToolTypeKey,
)
from voiceos.infrastructure.postgres.scope import organization_transaction
from voiceos.tenancy.db import Conn

_CONNECTION_COLUMNS = """connection_id, provider_key, display_name, credential_ref, status,
                         configuration, revision, updated_at"""
_INSTANCE_COLUMNS = """tool_instance_id, ref, tool_type_key, connection_id, display_name,
                       configuration, status, revision, updated_at"""


def _connection(row: tuple[Any, ...]) -> ConnectionView:
    connection_id, provider, name, ref, status, configuration, revision, updated = row
    return ConnectionView(ConnectionId(connection_id), ProviderKey(provider), name,
                          CredentialRef(ref) if ref is not None else None,
                          ConnectionStatus(status), configuration, revision,
                          updated)  # fmt: skip


def _instance(row: tuple[Any, ...]) -> ToolInstanceView:
    instance_id, ref, tool_type, connection_id, name, configuration, status, revision, upd = row
    return ToolInstanceView(ToolInstanceId(instance_id), ToolInstanceRef(ref),
                            ToolTypeKey(tool_type),
                            ConnectionId(connection_id) if connection_id is not None else None,
                            name, configuration, ToolInstanceStatus(status), revision,
                            upd)  # fmt: skip


def _returned(row: tuple[Any, ...] | None) -> tuple[Any, ...]:
    if row is None:  # INSERT/UPDATE ... RETURNING on a checked path always yields a row
        raise RuntimeError("statement returned no row")
    return row


@contextmanager
def _mapped() -> Iterator[None]:
    """Database refusals become application errors; messages never carry input values."""
    try:
        yield
    except errors.InsufficientPrivilege:
        raise PermissionDenied(Permission.INTEGRATIONS_MANAGE) from None
    except errors.UniqueViolation:
        raise IntegrationConflict("reference already in use") from None
    except (errors.CheckViolation, errors.ForeignKeyViolation):
        raise IntegrationConflict("change not allowed") from None


class PostgresIntegrationStore:
    def __init__(self, conn: Conn) -> None:
        self._conn = conn

    @staticmethod
    def _require_manager(tx: Conn) -> None:
        row = tx.execute("SELECT voiceos.caller_can_manage_integrations()").fetchone()
        if row is None or row[0] is not True:
            raise PermissionDenied(Permission.INTEGRATIONS_MANAGE)

    # -- catalog --------------------------------------------------------------------------

    def list_tool_types(self, principal: Principal) -> list[ToolTypeView]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                """SELECT tool_type_key, name, description, schema_version, input_schema,
                          output_schema, schema_hash, side_effect_class, confirmation_policy,
                          requires_connection, enabled
                   FROM voiceos.tool_types ORDER BY tool_type_key"""
            ).fetchall()
        return [
            ToolTypeView(ToolTypeKey(key), name, description, version, inp, out, digest,
                         SideEffectClass(effect), ConfirmationPolicy(policy), needs, enabled)
            for key, name, description, version, inp, out, digest, effect, policy, needs,
            enabled in rows
        ]  # fmt: skip

    def list_providers(self, principal: Principal) -> list[ProviderView]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                """SELECT p.provider_key, p.category, p.display_name, p.auth_type, p.enabled,
                          coalesce(array_agg(c.tool_type_key ORDER BY c.tool_type_key)
                                   FILTER (WHERE c.tool_type_key IS NOT NULL), '{}')
                   FROM voiceos.integration_providers p
                   LEFT JOIN voiceos.integration_provider_capabilities c
                          ON c.provider_key = p.provider_key
                   GROUP BY p.provider_key ORDER BY p.provider_key"""
            ).fetchall()
        return [
            ProviderView(ProviderKey(key), ProviderCategory(category), name, AuthType(auth),
                         enabled, frozenset(ToolTypeKey(k) for k in capabilities))
            for key, category, name, auth, enabled, capabilities in rows
        ]  # fmt: skip

    # -- connections ----------------------------------------------------------------------

    def create_connection(
        self, principal: Principal, provider_key: ProviderKey, display_name: str,
        credential_ref: CredentialRef | None, status: ConnectionStatus,
        configuration: Mapping[str, object],
    ) -> ConnectionView:  # fmt: skip
        with _mapped(), organization_transaction(self._conn, principal.scope) as tx:
            self._require_manager(tx)
            row = tx.execute(
                f"""INSERT INTO voiceos.integration_connections
                        (tenant_id, provider_key, display_name, credential_ref, status,
                         configuration)
                    VALUES (voiceos.current_tenant_id(), %s, %s, %s, %s, %s)
                    RETURNING {_CONNECTION_COLUMNS}""",
                (provider_key, display_name, credential_ref, status.value,
                 Jsonb(dict(configuration))),
            ).fetchone()  # fmt: skip
        return _connection(_returned(row))

    def get_connection(
        self, principal: Principal, connection_id: ConnectionId
    ) -> ConnectionView | None:
        with organization_transaction(self._conn, principal.scope) as tx:
            row = tx.execute(
                f"SELECT {_CONNECTION_COLUMNS} FROM voiceos.integration_connections"
                " WHERE connection_id = %s",
                (connection_id,),
            ).fetchone()
        return _connection(row) if row else None

    def update_connection(
        self, principal: Principal, connection_id: ConnectionId, expected_revision: int,
        display_name: str, configuration: Mapping[str, object], status: ConnectionStatus,
    ) -> ConnectionView:  # fmt: skip
        with _mapped(), organization_transaction(self._conn, principal.scope) as tx:
            self._require_manager(tx)
            row = tx.execute(
                f"""UPDATE voiceos.integration_connections
                    SET display_name = %s, configuration = %s, status = %s,
                        revision = revision + 1
                    WHERE connection_id = %s AND revision = %s
                    RETURNING {_CONNECTION_COLUMNS}""",
                (display_name, Jsonb(dict(configuration)), status.value, connection_id,
                 expected_revision),
            ).fetchone()  # fmt: skip
            if row is None:
                exists = tx.execute(
                    "SELECT 1 FROM voiceos.integration_connections WHERE connection_id = %s",
                    (connection_id,),
                ).fetchone()
                if exists is None:
                    raise ConnectionNotFound("connection not found")
                raise StaleRevision("connection changed")
        return _connection(row)

    # -- tool instances -------------------------------------------------------------------

    def create_tool_instance(
        self, principal: Principal, ref: ToolInstanceRef, tool_type_key: ToolTypeKey,
        connection_id: ConnectionId | None, display_name: str,
        configuration: Mapping[str, object],
    ) -> ToolInstanceView:  # fmt: skip
        with _mapped(), organization_transaction(self._conn, principal.scope) as tx:
            self._require_manager(tx)
            provider_key = None
            if connection_id is not None:
                found = tx.execute(  # only this organization's connections are visible
                    "SELECT provider_key FROM voiceos.integration_connections"
                    " WHERE connection_id = %s",
                    (connection_id,),
                ).fetchone()
                if found is None:
                    raise ConnectionNotFound("connection not found")
                provider_key = found[0]
            row = tx.execute(
                f"""INSERT INTO voiceos.tool_instances
                        (tenant_id, ref, tool_type_key, connection_id, provider_key,
                         display_name, configuration)
                    VALUES (voiceos.current_tenant_id(), %s, %s, %s, %s, %s, %s)
                    RETURNING {_INSTANCE_COLUMNS}""",
                (ref, tool_type_key, connection_id, provider_key, display_name,
                 Jsonb(dict(configuration))),
            ).fetchone()  # fmt: skip
        return _instance(_returned(row))

    def get_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId
    ) -> ToolInstanceView | None:
        with organization_transaction(self._conn, principal.scope) as tx:
            row = tx.execute(
                f"SELECT {_INSTANCE_COLUMNS} FROM voiceos.tool_instances"
                " WHERE tool_instance_id = %s",
                (tool_instance_id,),
            ).fetchone()
        return _instance(row) if row else None

    def list_tool_instances(self, principal: Principal) -> list[ToolInstanceView]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                f"SELECT {_INSTANCE_COLUMNS} FROM voiceos.tool_instances ORDER BY ref"
            ).fetchall()
        return [_instance(r) for r in rows]

    def update_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId, expected_revision: int,
        display_name: str, configuration: Mapping[str, object], status: ToolInstanceStatus,
    ) -> ToolInstanceView:  # fmt: skip
        with _mapped(), organization_transaction(self._conn, principal.scope) as tx:
            self._require_manager(tx)
            row = tx.execute(
                f"""UPDATE voiceos.tool_instances
                    SET display_name = %s, configuration = %s, status = %s,
                        revision = revision + 1
                    WHERE tool_instance_id = %s AND revision = %s
                    RETURNING {_INSTANCE_COLUMNS}""",
                (display_name, Jsonb(dict(configuration)), status.value, tool_instance_id,
                 expected_revision),
            ).fetchone()  # fmt: skip
            if row is None:
                exists = tx.execute(
                    "SELECT 1 FROM voiceos.tool_instances WHERE tool_instance_id = %s",
                    (tool_instance_id,),
                ).fetchone()
                if exists is None:
                    raise ToolInstanceNotFound("tool instance not found")
                raise StaleRevision("tool instance changed")
        return _instance(row)

    # -- agent versions -------------------------------------------------------------------

    def tool_ref_states(self, principal: Principal, refs: Sequence[str]) -> list[ToolRefState]:
        with organization_transaction(self._conn, principal.scope) as tx:
            rows = tx.execute(
                """SELECT r.ref, i.status, t.enabled, i.connection_id IS NOT NULL, c.status,
                          p.enabled
                   FROM unnest(%s::text[]) WITH ORDINALITY AS r(ref, position)
                   LEFT JOIN voiceos.tool_instances i ON i.ref = r.ref
                   LEFT JOIN voiceos.tool_types t ON t.tool_type_key = i.tool_type_key
                   LEFT JOIN voiceos.integration_connections c
                          ON c.connection_id = i.connection_id
                   LEFT JOIN voiceos.integration_providers p ON p.provider_key = c.provider_key
                   ORDER BY r.position""",
                (list(refs),),
            ).fetchall()
        return [
            ToolRefState(ref, ToolInstanceStatus(status) if status else None, type_enabled,
                         bool(uses), ConnectionStatus(c_status) if c_status else None,
                         provider_enabled)
            for ref, status, type_enabled, uses, c_status, provider_enabled in rows
        ]  # fmt: skip
