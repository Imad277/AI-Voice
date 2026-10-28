"""Tool registry and integration model (migration 0005) against the real database, through
the application services and the PostgreSQL stores.

Organizations, users and memberships are seeded by the migrator; principals are built
directly so forged principals prove that the database re-checks the stored membership role
for every write. Providers and capabilities exist only as synthetic test rows added by a fixture and
removed again; the production migration seeds none.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from uuid import UUID, uuid4

import pytest
from psycopg import errors
from support import TENANT_A, TENANT_B, agent_configuration, req

from voiceos.application.control_plane.agents import (
    AgentService,
    LifecycleConflict,
    UnusableToolReferences,
    VersionView,
)
from voiceos.application.control_plane.integrations import (
    ConnectionNotFound,
    ConnectionView,
    IntegrationConflict,
    IntegrationService,
    InvalidIntegrationInput,
    StaleRevision,
    ToolInstanceNotFound,
    ToolInstanceView,
)
from voiceos.config import Settings
from voiceos.core.context import CallContext
from voiceos.core.tools import Decision, Reason, ToolName
from voiceos.domain.identity.model import MembershipRole, OrganizationId, UserId
from voiceos.domain.identity.rbac import PermissionDenied, Principal
from voiceos.domain.integrations.model import (
    AuthType,
    ConnectionId,
    ConnectionStatus,
    CredentialRef,
    ProviderKey,
)
from voiceos.domain.tools.model import (
    ToolInstanceId,
    ToolInstanceRef,
    ToolInstanceStatus,
    ToolTypeKey,
    policy_is_sufficient,
    schema_hash,
    schema_issues,
)
from voiceos.gateway.gateway import ToolGateway
from voiceos.gateway.schemas import TOOL_SCHEMAS
from voiceos.infrastructure.postgres.agents import PostgresAgentStore
from voiceos.infrastructure.postgres.integrations import PostgresIntegrationStore
from voiceos.infrastructure.postgres.scope import organization_transaction
from voiceos.tenancy.db import Conn, connect_app

R = MembershipRole
OWNER_A = UUID("00000000-0000-4000-8000-0000000002a0")
VIEWER_A = UUID("00000000-0000-4000-8000-0000000002a1")  # READ_ONLY: integrations.read only
OWNER_B = UUID("00000000-0000-4000-8000-0000000002b0")
A, B = OrganizationId(TENANT_A), OrganizationId(TENANT_B)
ALICE = Principal(UserId(OWNER_A), A, R.OWNER)
VIEWER = Principal(UserId(VIEWER_A), A, R.READ_ONLY)
BOB = Principal(UserId(OWNER_B), B, R.OWNER)
FORGED = Principal(UserId(VIEWER_A), A, R.OWNER)  # claims a role that is not stored
INTRUDER = Principal(UserId(OWNER_B), A, R.OWNER)  # no membership in A
CATALOG_TABLES = ("tool_types", "integration_providers", "integration_provider_capabilities")


@pytest.fixture
def people(migrator: Conn) -> None:
    migrator.execute(
        "INSERT INTO voiceos.organizations (tenant_id, name, slug) VALUES"
        " (%s, 'Org A', 'org-a'), (%s, 'Org B', 'org-b')",
        (TENANT_A, TENANT_B),
    )
    migrator.execute(
        "INSERT INTO voiceos.users (user_id, external_subject, email, display_name) VALUES"
        " (%s, 'sub-ta', 'ta@example.org', 'TA'), (%s, 'sub-tv', 'tv@example.org', 'TV'),"
        " (%s, 'sub-tb', 'tb@example.org', 'TB')",
        (OWNER_A, VIEWER_A, OWNER_B),
    )
    migrator.execute(
        "INSERT INTO voiceos.organization_memberships (tenant_id, user_id, role) VALUES"
        " (%s, %s, 'OWNER'), (%s, %s, 'READ_ONLY'), (%s, %s, 'OWNER')",
        (TENANT_A, OWNER_A, TENANT_A, VIEWER_A, TENANT_B, OWNER_B),
    )


@pytest.fixture
def synthetic_catalog(migrator: Conn) -> Iterator[None]:
    """Synthetic providers, capabilities and a connection-less tool type, for tests only.

    The production migration seeds no providers (D-27 is open); tests add their own through
    the migrator and remove them again.
    """
    migrator.execute(
        "INSERT INTO voiceos.tool_types (tool_type_key, name, schema_version, input_schema,"
        " output_schema, schema_hash, side_effect_class, confirmation_policy,"
        " requires_connection) VALUES ('test.echo', 'Echo', 1, %s, %s, %s, 'READ_ONLY',"
        " 'NONE', false)",
        ('{"type": "object", "properties": {}, "additionalProperties": false}',) * 2 + ("0" * 64,),
    )
    migrator.execute(
        "INSERT INTO voiceos.integration_providers (provider_key, category, display_name,"
        " auth_type, enabled) VALUES"
        " ('test.calendar', 'CALENDAR', 'Test calendar', 'NONE', true),"
        " ('test.crm', 'CRM', 'Test CRM', 'API_KEY', true),"
        " ('test.webhook', 'WEBHOOK', 'Test webhook', 'HMAC_SIGNATURE', false)"
    )
    migrator.execute(
        "INSERT INTO voiceos.integration_provider_capabilities VALUES"
        " ('test.calendar', 'calendar.list_slots'), ('test.calendar', 'calendar.book_slot'),"
        " ('test.crm', 'crm.update_contact'), ('test.webhook', 'webhook.invoke')"
    )
    yield
    migrator.execute("TRUNCATE voiceos.tool_instances, voiceos.integration_connections")
    migrator.execute(
        "DELETE FROM voiceos.integration_provider_capabilities WHERE provider_key LIKE 'test.%'"
    )
    migrator.execute("DELETE FROM voiceos.integration_providers WHERE provider_key LIKE 'test.%'")
    migrator.execute("DELETE FROM voiceos.tool_types WHERE tool_type_key = 'test.echo'")


@pytest.fixture
def store(app_conn: Conn, people: None, synthetic_catalog: None) -> PostgresIntegrationStore:
    return PostgresIntegrationStore(app_conn)


@pytest.fixture
def service(store: PostgresIntegrationStore) -> IntegrationService:
    return IntegrationService(store)


@pytest.fixture
def agents(app_conn: Conn, service: IntegrationService) -> AgentService:
    return AgentService(PostgresAgentStore(app_conn), service)


def _calendar(service: IntegrationService, principal: Principal = ALICE) -> ConnectionView:
    return service.create_connection(principal, "test.calendar", "Calendar")


def _slots(
    service: IntegrationService, connection: ConnectionView, principal: Principal = ALICE,
    ref: str = "calendar-slots",
) -> ToolInstanceView:  # fmt: skip
    return service.create_tool_instance(
        principal, ref, "calendar.list_slots", "Slots", connection.connection_id
    )


def _version(agents: AgentService, *refs: str, principal: Principal = ALICE) -> VersionView:
    agent = agents.create_agent(principal, "R", draft=agent_configuration(tool_refs=list(refs)))
    return agents.create_version(principal, agent.agent_id, 0)


# -- global catalog ------------------------------------------------------------------------------


def test_production_migration_seeds_tool_types_but_no_providers(
    app_conn: Conn, people: None, migrator: Conn
) -> None:
    service = IntegrationService(PostgresIntegrationStore(app_conn))  # no synthetic catalog
    tool_types = {t.key: t for t in service.list_tool_types(VIEWER)}
    assert set(tool_types) == {
        "calendar.list_slots", "calendar.book_slot", "crm.update_contact", "webhook.invoke",
    }  # fmt: skip
    for tool in tool_types.values():
        assert schema_issues(tool.input_schema) == () and schema_issues(tool.output_schema) == ()
        assert tool.schema_hash == schema_hash(
            tool.schema_version, tool.input_schema, tool.output_schema
        )
        assert policy_is_sufficient(tool.side_effect_class, tool.confirmation_policy)
    assert not tool_types["webhook.invoke"].enabled  # metadata only, no egress
    assert service.list_integration_providers(VIEWER) == []  # D-27 open: no provider seeded
    capabilities = migrator.execute(
        "SELECT count(*) FROM voiceos.integration_provider_capabilities"
    ).fetchone()
    assert capabilities == (0,)


def test_catalog_providers_and_capabilities_are_readable(service: IntegrationService) -> None:
    providers = {p.key: p for p in service.list_integration_providers(VIEWER)}
    assert set(providers) == {"test.calendar", "test.crm", "test.webhook"}
    assert providers["test.calendar"].capabilities == {
        "calendar.list_slots", "calendar.book_slot",
    }  # fmt: skip
    assert providers["test.webhook"].auth_type is AuthType.HMAC_SIGNATURE
    assert not providers["test.webhook"].enabled


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO voiceos.tool_types (tool_type_key, name, schema_version, input_schema,"
        " output_schema, schema_hash, side_effect_class, confirmation_policy,"
        " requires_connection) VALUES ('evil.tool', 'x', 1, '{}', '{}', repeat('0', 64),"
        " 'READ_ONLY', 'NONE', false)",
        "UPDATE voiceos.tool_types SET confirmation_policy = 'NONE'",
        "UPDATE voiceos.tool_types SET enabled = true WHERE tool_type_key = 'webhook.invoke'",
        "DELETE FROM voiceos.tool_types",
        "INSERT INTO voiceos.integration_providers (provider_key, category, display_name,"
        " auth_type) VALUES ('evil.crm', 'CRM', 'x', 'NONE')",
        "UPDATE voiceos.integration_providers SET enabled = true",
        "INSERT INTO voiceos.integration_provider_capabilities VALUES"
        " ('test.crm', 'calendar.book_slot')",
        "DELETE FROM voiceos.integration_provider_capabilities",
    ],
)
def test_app_role_cannot_change_the_catalog(
    app_conn: Conn, people: None, synthetic_catalog: None, sql: str
) -> None:
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, ALICE.scope) as tx,  # even an owner
    ):
        tx.execute(sql)


def test_catalog_contract_changes_need_a_new_schema_version(migrator: Conn) -> None:
    with pytest.raises(errors.CheckViolation):
        migrator.execute(
            'UPDATE voiceos.tool_types SET input_schema = \'{"type": "object"}\''
            " WHERE tool_type_key = 'calendar.list_slots'"
        )
    with pytest.raises(errors.CheckViolation):  # policy below the side-effect minimum
        migrator.execute(
            "UPDATE voiceos.tool_types SET confirmation_policy = 'NONE'"
            " WHERE tool_type_key = 'calendar.book_slot'"
        )


def test_registry_keys_map_onto_the_gateway(
    service: IntegrationService, gateway: ToolGateway, ctx: CallContext
) -> None:
    """Future boundary: tool instance -> tool type -> gateway execution. A registry key is
    executable only where the gateway has a handler, with the same argument names."""
    for tool in service.list_tool_types(VIEWER):
        properties = set(tool.input_schema.get("properties", {}))  # type: ignore[call-overload]
        if tool.key in {t.value for t in ToolName}:
            fields = set(TOOL_SCHEMAS[ToolName(tool.key)].model_fields)
            assert properties == fields, tool.key
        else:
            result = gateway.execute(ctx, req(tool.key))
            assert (result.decision, result.reason) == (Decision.REJECTED, Reason.UNKNOWN_TOOL)


# -- connections ---------------------------------------------------------------------------------


def test_connection_create_read_update_disable(service: IntegrationService, migrator: Conn) -> None:
    connection = _calendar(service)
    assert connection.status is ConnectionStatus.ACTIVE and connection.revision == 0
    row = migrator.execute(
        "SELECT tenant_id FROM voiceos.integration_connections WHERE connection_id = %s",
        (connection.connection_id,),
    ).fetchone()
    assert row == (TENANT_A,)  # tenant from the bound organization, never a parameter
    assert service.get_connection(VIEWER, connection.connection_id) == connection
    updated = service.update_connection_configuration(
        ALICE, connection.connection_id, 0, {"calendar_id": "primary"}, "Main"
    )
    assert (updated.revision, updated.display_name) == (1, "Main")
    with pytest.raises(StaleRevision):
        service.update_connection_configuration(ALICE, connection.connection_id, 0, {})
    disabled = service.disable_connection(ALICE, connection.connection_id, 1)
    assert disabled.status is ConnectionStatus.DISCONNECTED and disabled.revision == 2


def test_credentials_are_references_only(
    service: IntegrationService, store: PostgresIntegrationStore, migrator: Conn,
) -> None:  # fmt: skip
    pending = service.create_connection(
        ALICE, "test.crm", "CRM", credential_ref="cred:org-a/test-crm/v1"
    )
    assert pending.status is ConnectionStatus.PENDING
    columns = {r[0] for r in migrator.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'voiceos'"
        " AND table_name IN ('integration_connections', 'tool_instances')"
    ).fetchall()}  # fmt: skip
    assert not {c for c in columns if any(m in c for m in ("secret", "token", "password"))}
    assert "credential_ref" in columns
    marker = "sk-live-0000-marker"  # synthetic secret-shaped value
    with pytest.raises(InvalidIntegrationInput) as raised:
        service.create_connection(ALICE, "test.crm", "CRM", credential_ref=marker)
    assert marker not in str(raised.value) and marker not in repr(raised.value.issues)
    with pytest.raises(IntegrationConflict) as conflict:  # the database refuses it as well
        store.create_connection(ALICE, ProviderKey("test.crm"), "CRM", CredentialRef(marker),
                                ConnectionStatus.PENDING, {})  # fmt: skip
    assert marker not in str(conflict.value)
    with pytest.raises(IntegrationConflict):  # credential-less provider: no reference at all
        store.create_connection(ALICE, ProviderKey("test.calendar"), "C",
                                CredentialRef("cred:x"), ConnectionStatus.ACTIVE, {})  # fmt: skip


def test_connection_rules_in_the_database(app_conn: Conn, service: IntegrationService) -> None:
    connection = _calendar(service)
    for sql in (
        "UPDATE voiceos.integration_connections SET display_name = 'x' WHERE connection_id = %s",
        "UPDATE voiceos.integration_connections SET status = 'PENDING', revision = revision + 1"
        " WHERE connection_id = %s",  # ACTIVE -> PENDING is not a transition
        "UPDATE voiceos.integration_connections SET tenant_id = tenant_id,"
        " provider_key = 'test.crm', revision = revision + 1 WHERE connection_id = %s",
    ):
        with (
            pytest.raises(errors.CheckViolation),
            organization_transaction(app_conn, ALICE.scope) as tx,
        ):
            tx.execute(sql, (connection.connection_id,))
    with (
        pytest.raises(errors.CheckViolation),  # disabled provider
        organization_transaction(app_conn, ALICE.scope) as tx,
    ):
        tx.execute(
            "INSERT INTO voiceos.integration_connections (tenant_id, provider_key,"
            " display_name, credential_ref) VALUES (%s, 'test.webhook', 'W', 'cred:w')",
            (TENANT_A,),
        )


def test_connection_tenant_isolation_and_authorization(
    service: IntegrationService, store: PostgresIntegrationStore, app_conn: Conn
) -> None:
    connection = _calendar(service)
    with pytest.raises(ConnectionNotFound):
        service.get_connection(BOB, connection.connection_id)
    with pytest.raises(ConnectionNotFound):
        service.update_connection_configuration(BOB, connection.connection_id, 0, {})
    assert store.get_connection(BOB, connection.connection_id) is None
    with pytest.raises(ConnectionNotFound):
        store.update_connection(BOB, connection.connection_id, 0, "x", {},
                                ConnectionStatus.ACTIVE)  # fmt: skip
    with pytest.raises(PermissionDenied):
        service.create_connection(VIEWER, "test.calendar", "X")
    for principal in (FORGED, INTRUDER):  # pass Principal.require, refused by the database
        with pytest.raises(PermissionDenied):
            service.create_connection(principal, "test.calendar", "X")
        with pytest.raises(PermissionDenied):
            store.update_connection(principal, connection.connection_id, 0, "x", {},
                                    ConnectionStatus.DISCONNECTED)  # fmt: skip
    with (
        pytest.raises(errors.InsufficientPrivilege),
        organization_transaction(app_conn, BOB.scope) as tx,
    ):
        tx.execute(
            "INSERT INTO voiceos.integration_connections (tenant_id, provider_key,"
            " display_name) VALUES (%s, 'test.calendar', 'x')",
            (TENANT_A,),
        )
    with organization_transaction(app_conn, VIEWER.scope) as tx:
        cursor = tx.execute(
            "UPDATE voiceos.integration_connections SET display_name = 'x',"
            " revision = revision + 1 WHERE connection_id = %s",
            (connection.connection_id,),
        )
        assert cursor.rowcount == 0
    assert service.get_connection(ALICE, connection.connection_id).revision == 0


# -- tool instances ------------------------------------------------------------------------------


def test_tool_instance_create_update_disable(service: IntegrationService) -> None:
    instance = _slots(service, _calendar(service))
    assert instance.status is ToolInstanceStatus.ENABLED and instance.revision == 0
    updated = service.update_tool_instance(ALICE, instance.tool_instance_id, 0, {"days": 7})
    assert updated.configuration == {"days": 7} and updated.revision == 1
    with pytest.raises(StaleRevision):
        service.update_tool_instance(ALICE, instance.tool_instance_id, 0, {})
    disabled = service.disable_tool_instance(ALICE, instance.tool_instance_id, 1)
    assert disabled.status is ToolInstanceStatus.DISABLED
    assert [i.ref for i in service.list_tool_instances(VIEWER)] == ["calendar-slots"]
    with pytest.raises(IntegrationConflict):  # refs are unique per organization
        _slots(service, _calendar(service))


def test_tool_instance_binding_rules(
    service: IntegrationService,
    store: PostgresIntegrationStore,
) -> None:
    calendar = _calendar(service)
    with pytest.raises(IntegrationConflict):  # provider does not serve the tool (FK)
        store.create_tool_instance(ALICE, ToolInstanceRef("x"), ToolTypeKey("crm.update_contact"),
                                   calendar.connection_id, "X", {})  # fmt: skip
    with pytest.raises(IntegrationConflict):  # type needs a connection (trigger)
        store.create_tool_instance(ALICE, ToolInstanceRef("x"),
                                   ToolTypeKey("calendar.list_slots"), None, "X", {})  # fmt: skip
    with pytest.raises(IntegrationConflict):  # unknown tool type (FK)
        store.create_tool_instance(ALICE, ToolInstanceRef("x"), ToolTypeKey("nope.tool"),
                                   calendar.connection_id, "X", {})  # fmt: skip
    echo = service.create_tool_instance(ALICE, "echo", "test.echo", "Echo")
    assert echo.connection_id is None


def test_tool_instance_tenant_isolation(
    service: IntegrationService, store: PostgresIntegrationStore, app_conn: Conn
) -> None:
    calendar = _calendar(service)
    instance = _slots(service, calendar)
    with pytest.raises(ConnectionNotFound):  # B cannot bind A's connection
        _slots(service, calendar, BOB)
    with pytest.raises(ConnectionNotFound):
        store.create_tool_instance(BOB, ToolInstanceRef("x"), ToolTypeKey("calendar.list_slots"),
                                   calendar.connection_id, "X", {})  # fmt: skip
    with (
        pytest.raises((errors.ForeignKeyViolation, errors.InsufficientPrivilege)),
        organization_transaction(app_conn, BOB.scope) as tx,
    ):
        tx.execute(
            "INSERT INTO voiceos.tool_instances (tenant_id, ref, tool_type_key, connection_id,"
            " provider_key, display_name) VALUES (%s, 'x', 'calendar.list_slots', %s,"
            " 'test.calendar', 'X')",
            (TENANT_B, calendar.connection_id),
        )
    with pytest.raises(ToolInstanceNotFound):
        service.get_tool_instance(BOB, instance.tool_instance_id)
    with pytest.raises(ToolInstanceNotFound):
        store.update_tool_instance(BOB, instance.tool_instance_id, 0, "x", {},
                                   ToolInstanceStatus.DISABLED)  # fmt: skip
    assert service.list_tool_instances(BOB) == []
    for principal in (FORGED, INTRUDER):
        with pytest.raises(PermissionDenied):
            store.update_tool_instance(principal, instance.tool_instance_id, 0, "x", {},
                                       ToolInstanceStatus.DISABLED)  # fmt: skip
    assert service.get_tool_instance(ALICE, instance.tool_instance_id).revision == 0


# -- agent version integration -------------------------------------------------------------------


def test_publish_accepts_usable_tool_refs(
    service: IntegrationService, agents: AgentService
) -> None:
    _slots(service, _calendar(service))
    version = _version(agents, "calendar-slots")
    published = agents.publish_version(ALICE, version.agent_version_id)
    assert published.configuration["tool_refs"] == ["calendar-slots"]


def test_publish_blocks_unusable_tool_refs(
    service: IntegrationService, agents: AgentService, migrator: Conn
) -> None:
    calendar = _calendar(service)
    _slots(service, calendar)
    off = _slots(service, calendar, ref="off")
    service.disable_tool_instance(ALICE, off.tool_instance_id, 0)
    _slots(service, _calendar(service, BOB), BOB, ref="b-only")
    cases = {
        "missing": "unknown_tool_instance",
        "off": "tool_instance_disabled",
        "b-only": "unknown_tool_instance",  # another organization's instance
    }
    for ref, problem in cases.items():
        version = _version(agents, "calendar-slots", ref)
        with pytest.raises(UnusableToolReferences) as raised:
            agents.publish_version(ALICE, version.agent_version_id)
        assert raised.value.issues == (f"tool_refs.1: {problem}",)
    version = _version(agents, "calendar-slots")
    service.disable_connection(ALICE, calendar.connection_id, 0)
    with pytest.raises(UnusableToolReferences) as raised:
        agents.publish_version(ALICE, version.agent_version_id)
    assert raised.value.issues == ("tool_refs.0: connection_not_active",)


def test_publish_blocks_a_disabled_tool_type(
    service: IntegrationService, agents: AgentService, migrator: Conn
) -> None:
    _slots(service, _calendar(service))
    version = _version(agents, "calendar-slots")
    migrator.execute(
        "UPDATE voiceos.tool_types SET enabled = false WHERE tool_type_key = 'calendar.list_slots'"
    )
    try:
        with pytest.raises(UnusableToolReferences) as raised:
            agents.publish_version(ALICE, version.agent_version_id)
        assert raised.value.issues == ("tool_refs.0: tool_type_disabled",)
    finally:
        migrator.execute(
            "UPDATE voiceos.tool_types SET enabled = true"
            " WHERE tool_type_key = 'calendar.list_slots'"
        )


def test_database_re_checks_tool_refs_on_publish(
    service: IntegrationService, agents: AgentService, app_conn: Conn
) -> None:
    calendar = _calendar(service)
    _slots(service, calendar)
    version = _version(agents, "calendar-slots", "missing")
    store = PostgresAgentStore(app_conn)  # bypasses the application check
    with pytest.raises(LifecycleConflict):
        store.publish_version(ALICE, version.agent_version_id, version.configuration_hash)
    version = _version(agents, "calendar-slots")
    service.disable_connection(ALICE, calendar.connection_id, 0)
    with pytest.raises(LifecycleConflict):
        store.publish_version(ALICE, version.agent_version_id, version.configuration_hash)
    assert agents.get_version(ALICE, version.agent_version_id).status.value == "DRAFT"


# -- concurrency ---------------------------------------------------------------------------------


def _in_threads(*targets: Callable[[], object]) -> list[object]:
    barrier = threading.Barrier(len(targets))
    results: list[object] = [None] * len(targets)

    def run(index: int, target: Callable[[], object]) -> None:
        barrier.wait(5)
        try:
            results[index] = target()
        except BaseException as exc:  # recorded for the assertion
            results[index] = exc

    threads = [threading.Thread(target=run, args=(i, t)) for i, t in enumerate(targets)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert not any(thread.is_alive() for thread in threads)
    return results


def _workers(settings: Settings, count: int) -> list[tuple[IntegrationService, Conn]]:
    workers = []
    for _ in range(count):
        conn = connect_app(settings)
        workers.append((IntegrationService(PostgresIntegrationStore(conn)), conn))
    return workers


def test_parallel_connection_updates_lose_no_revision(
    service: IntegrationService, settings: Settings
) -> None:
    connection = _calendar(service)
    workers = _workers(settings, 6)
    try:
        results = _in_threads(*(
            (lambda s=s, i=i: s.update_connection_configuration(
                ALICE, connection.connection_id, 0, {"variant": i}))
            for i, (s, _) in enumerate(workers)
        ))  # fmt: skip
    finally:
        for _, conn in workers:
            conn.close()
    winners = [r for r in results if isinstance(r, ConnectionView)]
    assert len(winners) == 1, results
    assert all(isinstance(r, StaleRevision) for r in results if r not in winners)
    final = service.get_connection(ALICE, connection.connection_id)
    assert final.revision == 1 and final.configuration == winners[0].configuration


def test_parallel_tool_instance_updates_lose_no_revision(
    service: IntegrationService, settings: Settings
) -> None:
    instance = _slots(service, _calendar(service))
    workers = _workers(settings, 6)
    try:
        results = _in_threads(*(
            (lambda s=s, i=i: s.update_tool_instance(
                ALICE, instance.tool_instance_id, 0, {"variant": i}))
            for i, (s, _) in enumerate(workers)
        ))  # fmt: skip
    finally:
        for _, conn in workers:
            conn.close()
    winners = [r for r in results if isinstance(r, ToolInstanceView)]
    assert len(winners) == 1, results
    assert all(isinstance(r, StaleRevision) for r in results if r not in winners)
    final = service.get_tool_instance(ALICE, instance.tool_instance_id)
    assert final.revision == 1 and final.configuration == winners[0].configuration


def test_unknown_ids_are_not_found(service: IntegrationService) -> None:
    with pytest.raises(ConnectionNotFound):
        service.get_connection(ALICE, ConnectionId(uuid4()))
    with pytest.raises(ToolInstanceNotFound):
        service.get_tool_instance(ALICE, ToolInstanceId(uuid4()))
