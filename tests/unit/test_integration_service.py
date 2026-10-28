"""Integration use cases against an in-memory store: RBAC, connection and tool instance
rules, credential handling and the agent tool-reference check. The PostgreSQL store is
exercised in tests/postgres/test_tool_registry.py."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voiceos.application.control_plane.integrations import (
    ConnectionNotFound,
    ConnectionView,
    IntegrationConflict,
    IntegrationService,
    InvalidIntegrationInput,
    ProviderNotFound,
    ProviderView,
    StaleRevision,
    ToolInstanceNotFound,
    ToolInstanceView,
    ToolRefState,
    ToolTypeNotFound,
    ToolTypeView,
)
from voiceos.domain.identity.model import MembershipRole, OrganizationId, UserId
from voiceos.domain.identity.rbac import PermissionDenied, Principal
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

R = MembershipRole
ORG_A, ORG_B = OrganizationId(uuid4()), OrganizationId(uuid4())
NOW = datetime(2026, 1, 1, tzinfo=UTC)
EMPTY: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}


def _principal(role: MembershipRole, organization: OrganizationId = ORG_A) -> Principal:
    return Principal(UserId(uuid4()), organization, role)


def _type(key: str, *, needs: bool = True, enabled: bool = True) -> ToolTypeView:
    return ToolTypeView(ToolTypeKey(key), key, "", 1, EMPTY, EMPTY, "0" * 64,
                        SideEffectClass.READ_ONLY, ConfirmationPolicy.NONE, needs,
                        enabled)  # fmt: skip


def _provider(key: str, auth: AuthType, *tools: str, enabled: bool = True) -> ProviderView:
    return ProviderView(ProviderKey(key), ProviderCategory.CALENDAR, key, auth, enabled,
                        frozenset(ToolTypeKey(t) for t in tools))  # fmt: skip


class FakeStore:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.types = [
            _type("calendar.list_slots"), _type("calendar.book_slot"),
            _type("internal.echo", needs=False), _type("webhook.invoke", enabled=False),
        ]  # fmt: skip
        self.providers = [
            _provider("test.calendar", AuthType.NONE, "calendar.list_slots",
                      "calendar.book_slot"),
            _provider("test.oauth_calendar", AuthType.OAUTH2, "calendar.list_slots"),
            _provider("test.webhook", AuthType.HMAC_SIGNATURE, "webhook.invoke", enabled=False),
        ]  # fmt: skip
        self.connections: dict[ConnectionId, tuple[OrganizationId, ConnectionView]] = {}
        self.instances: dict[ToolInstanceId, tuple[OrganizationId, ToolInstanceView]] = {}

    def list_tool_types(self, principal: Principal) -> list[ToolTypeView]:
        return list(self.types)

    def list_providers(self, principal: Principal) -> list[ProviderView]:
        return list(self.providers)

    def create_connection(
        self, principal: Principal, provider_key: ProviderKey, display_name: str,
        credential_ref: CredentialRef | None, status: ConnectionStatus,
        configuration: Mapping[str, object],
    ) -> ConnectionView:  # fmt: skip
        self.writes.append("create_connection")
        view = ConnectionView(ConnectionId(uuid4()), provider_key, display_name, credential_ref,
                              status, dict(configuration), 0, NOW)  # fmt: skip
        self.connections[view.connection_id] = (principal.organization_id, view)
        return view

    def get_connection(
        self, principal: Principal, connection_id: ConnectionId
    ) -> ConnectionView | None:
        org, view = self.connections.get(connection_id, (None, None))
        return view if org == principal.organization_id else None

    def update_connection(
        self, principal: Principal, connection_id: ConnectionId, expected_revision: int,
        display_name: str, configuration: Mapping[str, object], status: ConnectionStatus,
    ) -> ConnectionView:  # fmt: skip
        self.writes.append("update_connection")
        view = self.get_connection(principal, connection_id)
        if view is None:
            raise ConnectionNotFound("connection not found")
        if view.revision != expected_revision:
            raise StaleRevision("connection changed")
        view = replace(view, display_name=display_name, configuration=dict(configuration),
                       status=status, revision=view.revision + 1)  # fmt: skip
        self.connections[connection_id] = (principal.organization_id, view)
        return view

    def create_tool_instance(
        self, principal: Principal, ref: ToolInstanceRef, tool_type_key: ToolTypeKey,
        connection_id: ConnectionId | None, display_name: str,
        configuration: Mapping[str, object],
    ) -> ToolInstanceView:  # fmt: skip
        self.writes.append("create_tool_instance")
        view = ToolInstanceView(ToolInstanceId(uuid4()), ref, tool_type_key, connection_id,
                                display_name, dict(configuration), ToolInstanceStatus.ENABLED, 0,
                                NOW)  # fmt: skip
        self.instances[view.tool_instance_id] = (principal.organization_id, view)
        return view

    def get_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId
    ) -> ToolInstanceView | None:
        org, view = self.instances.get(tool_instance_id, (None, None))
        return view if org == principal.organization_id else None

    def list_tool_instances(self, principal: Principal) -> list[ToolInstanceView]:
        return [v for o, v in self.instances.values() if o == principal.organization_id]

    def update_tool_instance(
        self, principal: Principal, tool_instance_id: ToolInstanceId, expected_revision: int,
        display_name: str, configuration: Mapping[str, object], status: ToolInstanceStatus,
    ) -> ToolInstanceView:  # fmt: skip
        self.writes.append("update_tool_instance")
        view = self.get_tool_instance(principal, tool_instance_id)
        if view is None:
            raise ToolInstanceNotFound("tool instance not found")
        if view.revision != expected_revision:
            raise StaleRevision("tool instance changed")
        view = replace(view, display_name=display_name, configuration=dict(configuration),
                       status=status, revision=view.revision + 1)  # fmt: skip
        self.instances[tool_instance_id] = (principal.organization_id, view)
        return view

    def tool_ref_states(self, principal: Principal, refs: Sequence[str]) -> list[ToolRefState]:
        states = []
        for ref in refs:
            found = [v for v in self.list_tool_instances(principal) if v.ref == ref]
            if not found:
                states.append(ToolRefState(ref, None, None, False, None, None))
                continue
            instance = found[0]
            tool = next(t for t in self.types if t.key == instance.tool_type_key)
            connection = (self.get_connection(principal, instance.connection_id)
                          if instance.connection_id else None)  # fmt: skip
            provider = (next(p for p in self.providers if p.key == connection.provider_key)
                        if connection else None)  # fmt: skip
            states.append(ToolRefState(
                ref, instance.status, tool.enabled, connection is not None,
                connection.status if connection else None,
                provider.enabled if provider else None,
            ))  # fmt: skip
        return states


OWNER = _principal(R.OWNER)


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def service(store: FakeStore) -> IntegrationService:
    return IntegrationService(store)


def _calendar(service: IntegrationService) -> ConnectionView:
    return service.create_connection(OWNER, "test.calendar", "Calendar")


# -- RBAC --------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [R.OPERATOR, R.ANALYST, R.BILLING, R.READ_ONLY])
def test_roles_without_integrations_manage_change_nothing(
    service: IntegrationService, store: FakeStore, role: MembershipRole
) -> None:
    connection = _calendar(service)
    instance = service.create_tool_instance(
        OWNER, "calendar-main", "calendar.list_slots", "Slots", connection.connection_id
    )
    store.writes.clear()
    actor = _principal(role)
    attempts: list[Callable[[], object]] = [
        lambda: service.create_connection(actor, "test.calendar", "X"),
        lambda: service.update_connection_configuration(actor, connection.connection_id, 0, {}),
        lambda: service.disable_connection(actor, connection.connection_id, 0),
        lambda: service.create_tool_instance(actor, "x", "calendar.list_slots", "X"),
        lambda: service.update_tool_instance(actor, instance.tool_instance_id, 0, {}),
        lambda: service.disable_tool_instance(actor, instance.tool_instance_id, 0),
    ]
    for attempt in attempts:
        with pytest.raises(PermissionDenied):
            attempt()
    assert store.writes == []


def test_read_permissions(service: IntegrationService) -> None:
    connection = _calendar(service)
    viewer = _principal(R.READ_ONLY)  # integrations.read
    assert {t.key for t in service.list_tool_types(viewer)} >= {"calendar.list_slots"}
    assert {p.key for p in service.list_integration_providers(viewer)} >= {"test.calendar"}
    assert service.get_connection(viewer, connection.connection_id) == connection
    for role in (R.OPERATOR, R.ANALYST, R.BILLING):  # no integrations.read
        with pytest.raises(PermissionDenied):
            service.list_tool_types(_principal(role))
    with pytest.raises(PermissionDenied):  # tool-ref check needs agents.read
        service.validate_agent_tool_references(_principal(R.BILLING), ["x"])


# -- connections ---------------------------------------------------------------------------------


def test_connection_status_follows_the_auth_type(service: IntegrationService) -> None:
    keyless = _calendar(service)
    assert keyless.status is ConnectionStatus.ACTIVE and keyless.credential_ref is None
    vendor = service.create_connection(
        OWNER, "test.oauth_calendar", "Vendor", credential_ref="cred:org-a/vendor/v1"
    )
    assert vendor.status is ConnectionStatus.PENDING  # no verification path yet
    assert "cred:" not in repr(vendor)  # references are not even printed


@pytest.mark.parametrize(
    ("provider", "credential", "issue"),
    [
        ("test.calendar", "cred:x", "credential_ref: not_allowed"),
        ("test.oauth_calendar", None, "credential_ref: missing"),
        ("test.oauth_calendar", "ya29.secret-token-value", "credential_ref: invalid_format"),
    ],
)
def test_credentials_only_as_references(
    service: IntegrationService, store: FakeStore, provider: str, credential: str | None,
    issue: str,
) -> None:  # fmt: skip
    with pytest.raises(InvalidIntegrationInput) as raised:
        service.create_connection(OWNER, provider, "X", credential_ref=credential)
    assert raised.value.issues == (issue,)
    assert credential is None or credential not in str(raised.value)
    assert store.writes == []


def test_secret_configuration_is_rejected_without_echo(
    service: IntegrationService, store: FakeStore
) -> None:
    marker = "sk-live-marker-7f3a"
    with pytest.raises(InvalidIntegrationInput) as raised:
        service.create_connection(OWNER, "test.calendar", "X", {"api_key": marker, "note": marker})
    assert set(raised.value.issues) == {"api_key: forbidden_key", "note: secret_like_value"}
    assert marker not in str(raised.value) and marker not in repr(raised.value.issues)
    connection = _calendar(service)
    with pytest.raises(InvalidIntegrationInput):
        service.update_connection_configuration(
            OWNER, connection.connection_id, 0, {"password": "x"}
        )
    assert store.writes == ["create_connection"]


def test_unknown_or_disabled_provider(service: IntegrationService) -> None:
    with pytest.raises(ProviderNotFound):
        service.create_connection(OWNER, "nope.calendar", "X")
    with pytest.raises(IntegrationConflict):
        service.create_connection(OWNER, "test.webhook", "X", credential_ref="cred:x")


def test_update_disable_and_stale_revision(service: IntegrationService) -> None:
    connection = _calendar(service)
    updated = service.update_connection_configuration(
        OWNER, connection.connection_id, 0, {"calendar_id": "primary"}, "Main calendar"
    )
    assert updated.revision == 1 and updated.display_name == "Main calendar"
    with pytest.raises(StaleRevision):
        service.update_connection_configuration(OWNER, connection.connection_id, 0, {})
    disabled = service.disable_connection(OWNER, connection.connection_id, 1)
    assert disabled.status is ConnectionStatus.DISCONNECTED and disabled.revision == 2
    assert service.disable_connection(OWNER, connection.connection_id, 2) == disabled  # no-op


def test_revoked_connection_is_final(service: IntegrationService, store: FakeStore) -> None:
    connection = _calendar(service)
    org, view = store.connections[connection.connection_id]
    store.connections[connection.connection_id] = (
        org,
        replace(view, status=ConnectionStatus.REVOKED),
    )
    with pytest.raises(IntegrationConflict):
        service.update_connection_configuration(OWNER, connection.connection_id, 0, {})
    with pytest.raises(IntegrationConflict):
        service.disable_connection(OWNER, connection.connection_id, 0)
    with pytest.raises(IntegrationConflict):
        service.create_tool_instance(
            OWNER, "x", "calendar.list_slots", "X", connection.connection_id
        )


def test_other_organization_sees_unknown_ids(service: IntegrationService) -> None:
    connection = _calendar(service)
    instance = service.create_tool_instance(
        OWNER, "slots", "calendar.list_slots", "Slots", connection.connection_id
    )
    stranger = _principal(R.OWNER, ORG_B)
    with pytest.raises(ConnectionNotFound):
        service.get_connection(stranger, connection.connection_id)
    with pytest.raises(ConnectionNotFound):  # cannot bind another organization's connection
        service.create_tool_instance(
            stranger, "slots", "calendar.list_slots", "Slots", connection.connection_id
        )
    with pytest.raises(ToolInstanceNotFound):
        service.disable_tool_instance(stranger, instance.tool_instance_id, 0)
    assert service.list_tool_instances(stranger) == []


# -- tool instances ------------------------------------------------------------------------------


def test_tool_instance_rules(service: IntegrationService) -> None:
    connection = _calendar(service)
    cid = connection.connection_id
    with pytest.raises(ToolTypeNotFound):
        service.create_tool_instance(OWNER, "x", "calendar.delete_everything", "X", cid)
    with pytest.raises(IntegrationConflict):
        service.create_tool_instance(OWNER, "x", "webhook.invoke", "X", cid)  # type disabled
    with pytest.raises(InvalidIntegrationInput) as raised:
        service.create_tool_instance(OWNER, "x", "calendar.list_slots", "X")
    assert raised.value.issues == ("connection_id: required",)
    with pytest.raises(InvalidIntegrationInput) as raised:
        service.create_tool_instance(OWNER, "x", "internal.echo", "X", cid)
    assert raised.value.issues == ("connection_id: not_allowed",)
    with pytest.raises(InvalidIntegrationInput) as raised:
        service.create_tool_instance(OWNER, "Bad Ref", "calendar.list_slots", "X", cid)
    assert raised.value.issues == ("ref: invalid_format",)
    vendor = service.create_connection(OWNER, "test.oauth_calendar", "V", credential_ref="cred:v")
    with pytest.raises(IntegrationConflict):  # test.oauth_calendar does not serve book_slot
        service.create_tool_instance(OWNER, "x", "calendar.book_slot", "X", vendor.connection_id)
    with pytest.raises(ConnectionNotFound):
        service.create_tool_instance(OWNER, "x", "calendar.list_slots", "X", ConnectionId(uuid4()))
    echo = service.create_tool_instance(OWNER, "echo", "internal.echo", "Echo")
    assert echo.connection_id is None and echo.status is ToolInstanceStatus.ENABLED


def test_tool_instance_update_and_disable(service: IntegrationService) -> None:
    connection = _calendar(service)
    instance = service.create_tool_instance(
        OWNER, "slots", "calendar.list_slots", "Slots", connection.connection_id,
        {"slot_minutes": 30},
    )  # fmt: skip
    updated = service.update_tool_instance(
        OWNER, instance.tool_instance_id, 0, {"slot_minutes": 45}
    )
    assert updated.configuration == {"slot_minutes": 45} and updated.revision == 1
    renamed = service.update_tool_instance(OWNER, instance.tool_instance_id, 1, display_name="S")
    assert renamed.configuration == {"slot_minutes": 45} and renamed.display_name == "S"
    with pytest.raises(StaleRevision):
        service.update_tool_instance(OWNER, instance.tool_instance_id, 0, {})
    with pytest.raises(InvalidIntegrationInput):
        service.update_tool_instance(OWNER, instance.tool_instance_id, 2, {"token": "x"})
    disabled = service.disable_tool_instance(OWNER, instance.tool_instance_id, 2)
    assert disabled.status is ToolInstanceStatus.DISABLED


# -- agent tool references -----------------------------------------------------------------------


def test_agent_tool_reference_issues(service: IntegrationService, store: FakeStore) -> None:
    calendar = _calendar(service)
    usable = service.create_tool_instance(
        OWNER, "slots", "calendar.list_slots", "S", calendar.connection_id
    )
    off = service.create_tool_instance(
        OWNER, "off", "calendar.book_slot", "B", calendar.connection_id
    )
    service.disable_tool_instance(OWNER, off.tool_instance_id, 0)
    vendor = service.create_connection(OWNER, "test.oauth_calendar", "V", credential_ref="cred:v")
    service.create_tool_instance(OWNER, "pending", "calendar.list_slots", "P", vendor.connection_id)
    viewer = _principal(R.ANALYST)  # agents.read is enough
    assert service.validate_agent_tool_references(viewer, [usable.ref]) == ()
    assert service.validate_agent_tool_references(viewer, []) == ()
    issues = service.validate_agent_tool_references(viewer, ["slots", "missing", "off", "pending"])
    assert issues == (
        "tool_refs.1: unknown_tool_instance",
        "tool_refs.2: tool_instance_disabled",
        "tool_refs.3: connection_not_active",
    )
    store.types = [replace(t, enabled=False) if t.key == "calendar.list_slots" else t
                   for t in store.types]  # fmt: skip
    assert service.validate_agent_tool_references(viewer, ["slots"]) == (
        "tool_refs.0: tool_type_disabled",
    )
    stranger = _principal(R.OWNER, ORG_B)
    assert service.validate_agent_tool_references(stranger, ["slots"]) == (
        "tool_refs.0: unknown_tool_instance",
    )
    assert service.validate_agent_tool_references(viewer, ["x"] * 51) == ("tool_refs: too_many",)
