"""Agent lifecycle use cases against an in-memory store: RBAC, publish rules, rollback
selection. The PostgreSQL store is exercised in tests/postgres/test_agent_lifecycle.py."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from support import agent_configuration

from voiceos.application.control_plane.agents import (
    AgentNotFound,
    AgentService,
    AgentView,
    DeploymentView,
    InvalidAgentConfiguration,
    LifecycleConflict,
    StaleDraftRevision,
    UnusableToolReferences,
    VersionNotFound,
    VersionView,
)
from voiceos.domain.agents.model import (
    AgentId,
    AgentStatus,
    AgentVersionId,
    AgentVersionStatus,
    DeploymentEnvironment,
    DeploymentId,
    DeploymentStatus,
)
from voiceos.domain.identity.model import MembershipRole, OrganizationId, UserId
from voiceos.domain.identity.rbac import Permission, PermissionDenied, Principal, roles_with

R = MembershipRole
PROD = DeploymentEnvironment.PRODUCTION
DEV = DeploymentEnvironment.DEVELOPMENT
ROOT = Path(__file__).resolve().parents[2]
ORG_A, ORG_B = OrganizationId(uuid4()), OrganizationId(uuid4())


def _principal(role: MembershipRole, organization: OrganizationId = ORG_A) -> Principal:
    return Principal(UserId(uuid4()), organization, role)


class FakeStore:
    """Minimal in-memory store; rows are keyed by organization like the RLS policies."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.agents: dict[AgentId, tuple[OrganizationId, AgentView]] = {}
        self.versions: dict[AgentVersionId, tuple[OrganizationId, VersionView]] = {}
        self.deployments: list[tuple[OrganizationId, DeploymentView]] = []
        self._clock = datetime(2026, 1, 1, tzinfo=UTC)

    def _now(self) -> datetime:
        self._clock += timedelta(seconds=1)
        return self._clock

    def create_agent(
        self, principal: Principal, name: str, description: str, draft: Mapping[str, object]
    ) -> AgentView:
        self.calls.append("create_agent")
        agent = AgentView(AgentId(uuid4()), name, description, AgentStatus.ACTIVE, dict(draft),
                          0, self._now())  # fmt: skip
        self.agents[agent.agent_id] = (principal.organization_id, agent)
        return agent

    def get_agent(self, principal: Principal, agent_id: AgentId) -> AgentView | None:
        org, agent = self.agents.get(agent_id, (None, None))
        return agent if org == principal.organization_id else None

    def update_draft(
        self, principal: Principal, agent_id: AgentId, expected_revision: int,
        draft: Mapping[str, object], name: str, description: str,
    ) -> AgentView:  # fmt: skip
        self.calls.append("update_draft")
        agent = self.get_agent(principal, agent_id)
        if agent is None:
            raise AgentNotFound("agent not found")
        if agent.draft_revision != expected_revision:
            raise StaleDraftRevision("draft changed")
        updated = replace(agent, draft=dict(draft), draft_revision=agent.draft_revision + 1,
                          name=name, description=description)  # fmt: skip
        self.agents[agent_id] = (principal.organization_id, updated)
        return updated

    def create_version(
        self, principal: Principal, agent_id: AgentId, draft_revision: int,
        configuration: Mapping[str, object], configuration_hash: str,
    ) -> VersionView:  # fmt: skip
        self.calls.append("create_version")
        number = 1 + sum(1 for _, v in self.versions.values() if v.agent_id == agent_id)
        version = VersionView(AgentVersionId(uuid4()), agent_id, number,
                              AgentVersionStatus.DRAFT, dict(configuration), configuration_hash,
                              self._now(), None)  # fmt: skip
        self.versions[version.agent_version_id] = (principal.organization_id, version)
        return version

    def get_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView | None:
        org, version = self.versions.get(version_id, (None, None))
        return version if org == principal.organization_id else None

    def list_versions(self, principal: Principal, agent_id: AgentId) -> list[VersionView]:
        return sorted(
            (v for o, v in self.versions.values()
             if o == principal.organization_id and v.agent_id == agent_id),
            key=lambda v: v.version_number,
        )  # fmt: skip

    def _set_status(self, principal: Principal, version_id: AgentVersionId,
                    status: AgentVersionStatus) -> VersionView:  # fmt: skip
        version = self.get_version(principal, version_id)
        assert version is not None
        updated = replace(version, status=status, published_at=version.published_at or self._now())
        self.versions[version_id] = (principal.organization_id, updated)
        return updated

    def publish_version(
        self, principal: Principal, version_id: AgentVersionId, configuration_hash: str
    ) -> VersionView:
        self.calls.append("publish_version")
        return self._set_status(principal, version_id, AgentVersionStatus.PUBLISHED)

    def archive_version(self, principal: Principal, version_id: AgentVersionId) -> VersionView:
        self.calls.append("archive_version")
        return self._set_status(principal, version_id, AgentVersionStatus.ARCHIVED)

    def deploy(
        self, principal: Principal, agent_id: AgentId, version_id: AgentVersionId,
        environment: DeploymentEnvironment,
    ) -> DeploymentView:  # fmt: skip
        self.calls.append("deploy")
        version = self.get_version(principal, version_id)
        assert version is not None
        self.deployments = [
            (o, replace(d, status=DeploymentStatus.INACTIVE)
             if d.agent_id == agent_id and d.environment is environment else d)
            for o, d in self.deployments
        ]  # fmt: skip
        deployment = DeploymentView(DeploymentId(uuid4()), agent_id, version_id,
                                    version.version_number, environment, DeploymentStatus.ACTIVE,
                                    self._now())  # fmt: skip
        self.deployments.append((principal.organization_id, deployment))
        return deployment

    def deployment_history(
        self, principal: Principal, agent_id: AgentId, environment: DeploymentEnvironment
    ) -> list[DeploymentView]:
        return sorted(
            (d for o, d in self.deployments if o == principal.organization_id
             and d.agent_id == agent_id and d.environment is environment),
            key=lambda d: d.created_at, reverse=True,
        )  # fmt: skip


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


class FakeTools:
    """Tool reference validator double: refs listed in ``unusable`` are reported."""

    def __init__(self) -> None:
        self.unusable: set[str] = set()
        self.checked: list[tuple[str, ...]] = []

    def validate_agent_tool_references(
        self, principal: Principal, refs: Sequence[str]
    ) -> tuple[str, ...]:
        self.checked.append(tuple(refs))
        return tuple(f"tool_refs.{i}: unusable" for i, r in enumerate(refs) if r in self.unusable)


@pytest.fixture
def tools() -> FakeTools:
    return FakeTools()


@pytest.fixture
def service(store: FakeStore, tools: FakeTools) -> AgentService:
    return AgentService(store, tools)


OWNER = _principal(R.OWNER)


def _ready_agent(service: AgentService) -> AgentView:
    return service.create_agent(OWNER, "Reception", draft=agent_configuration())


def _published(service: AgentService, agent: AgentView) -> VersionView:
    current = service.get_agent(OWNER, agent.agent_id)
    version = service.create_version(OWNER, agent.agent_id, current.draft_revision)
    return service.publish_version(OWNER, version.agent_version_id)


# -- RBAC --------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [R.OPERATOR, R.ANALYST, R.BILLING, R.READ_ONLY])
def test_roles_without_agents_manage_change_nothing(
    service: AgentService, store: FakeStore, role: MembershipRole
) -> None:
    agent = _ready_agent(service)
    version = _published(service, agent)
    store.calls.clear()
    actor = _principal(role)
    attempts = [
        lambda: service.create_agent(actor, "X"),
        lambda: service.update_agent_draft(actor, agent.agent_id, 0, {}),
        lambda: service.create_version(actor, agent.agent_id, 0),
        lambda: service.publish_version(actor, version.agent_version_id),
        lambda: service.archive_version(actor, version.agent_version_id),
        lambda: service.deploy_version(actor, agent.agent_id, version.agent_version_id, PROD),
        lambda: service.rollback_deployment(actor, agent.agent_id, PROD),
    ]
    for attempt in attempts:
        with pytest.raises(PermissionDenied):
            attempt()
    assert store.calls == []  # refused before any store write


def test_read_permissions(service: AgentService) -> None:
    agent = _ready_agent(service)
    analyst = _principal(R.ANALYST)
    assert service.get_agent(analyst, agent.agent_id).agent_id == agent.agent_id
    assert service.list_versions(analyst, agent.agent_id) == []
    assert service.deployment_history(analyst, agent.agent_id, PROD) == []
    billing = _principal(R.BILLING)  # billing has neither agents.read nor deployments.read
    with pytest.raises(PermissionDenied):
        service.get_agent(billing, agent.agent_id)
    with pytest.raises(PermissionDenied):
        service.deployment_history(billing, agent.agent_id, PROD)


def test_developer_manages_agents_and_deployments(service: AgentService) -> None:
    developer = _principal(R.DEVELOPER)
    agent = service.create_agent(developer, "Dev", draft=agent_configuration(name="Dev"))
    version = service.create_version(developer, agent.agent_id, 0)
    service.publish_version(developer, version.agent_version_id)
    deployment = service.deploy_version(developer, agent.agent_id, version.agent_version_id, DEV)
    assert deployment.status is DeploymentStatus.ACTIVE


def test_sql_agent_and_deployment_managers_match_the_matrix() -> None:
    """0004 re-checks agents.manage/deployments.manage with fixed role lists; they must equal
    the roles that hold those permissions here."""
    sql = (ROOT / "db" / "migrations" / "0004_agent_lifecycle.sql").read_text()
    found = dict(re.findall(
        r"FUNCTION voiceos\.(caller_can_manage_\w+)\(\) RETURNS boolean.*?IN \(([^)]*)\)",
        sql, re.DOTALL,
    ))  # fmt: skip
    expected = {
        "caller_can_manage_agents": roles_with(Permission.AGENTS_MANAGE),
        "caller_can_manage_deployments": roles_with(Permission.DEPLOYMENTS_MANAGE),
    }
    assert set(found) == set(expected)
    for function, roles in expected.items():
        listed = {MembershipRole(r.strip().strip("'")) for r in found[function].split(",")}
        assert listed == roles, function


# -- drafts and versions -------------------------------------------------------------------------


def test_other_organization_sees_unknown_ids(service: AgentService) -> None:
    agent = _ready_agent(service)
    version = _published(service, agent)
    stranger = _principal(R.OWNER, ORG_B)
    with pytest.raises(AgentNotFound):
        service.get_agent(stranger, agent.agent_id)
    with pytest.raises(AgentNotFound):
        service.update_agent_draft(stranger, agent.agent_id, 1, {})
    with pytest.raises(VersionNotFound):
        service.get_version(stranger, version.agent_version_id)
    with pytest.raises(VersionNotFound):
        service.deploy_version(stranger, agent.agent_id, version.agent_version_id, PROD)


def test_draft_update_syncs_usable_name_only(service: AgentService) -> None:
    agent = _ready_agent(service)
    renamed = service.update_agent_draft(OWNER, agent.agent_id, 0, agent_configuration(name="New"))
    assert renamed.name == "New" and renamed.draft_revision == 1
    kept = service.update_agent_draft(OWNER, agent.agent_id, 1, {"name": "   ", "language": 5})
    assert kept.name == "New" and kept.draft_revision == 2  # incomplete drafts are autosaved
    with pytest.raises(StaleDraftRevision):
        service.update_agent_draft(OWNER, agent.agent_id, 1, {})


def test_drafts_must_be_json_within_the_size_limit(service: AgentService, store: FakeStore) -> None:
    agent = _ready_agent(service)
    for draft, issue in (({"blob": "x" * (256 * 1024)}, "<root>: too_large"),
                         ({"value": float("nan")}, "<root>: not_json")):  # fmt: skip
        with pytest.raises(InvalidAgentConfiguration) as raised:
            service.update_agent_draft(OWNER, agent.agent_id, 0, draft)
        assert raised.value.issues == (issue,)
    with pytest.raises(InvalidAgentConfiguration):
        service.create_agent(OWNER, "Big", draft={"blob": "x" * (256 * 1024)})
    assert "update_draft" not in store.calls


def test_invalid_draft_cannot_become_a_version(service: AgentService, store: FakeStore) -> None:
    agent = service.create_agent(OWNER, "Incomplete")
    check = service.validate_agent_draft(OWNER, agent.agent_id)
    assert not check.valid and check.issues
    with pytest.raises(InvalidAgentConfiguration) as raised:
        service.create_version(OWNER, agent.agent_id, 0)
    assert raised.value.issues == check.issues
    assert "create_version" not in store.calls


def test_version_requires_the_current_revision(service: AgentService) -> None:
    agent = _ready_agent(service)
    service.update_agent_draft(OWNER, agent.agent_id, 0, agent_configuration(personality="calm"))
    with pytest.raises(StaleDraftRevision):
        service.create_version(OWNER, agent.agent_id, 0)
    version = service.create_version(OWNER, agent.agent_id, 1)
    assert version.configuration["personality"] == "calm"


def test_version_snapshot_is_the_canonical_configuration(service: AgentService) -> None:
    agent = service.create_agent(OWNER, "R", draft=agent_configuration(name="  Reception "))
    version = service.create_version(OWNER, agent.agent_id, 0)
    assert version.configuration["name"] == "Reception"
    assert version.configuration["compliance"]["recording"] == "off"  # type: ignore[index]
    assert version.status is AgentVersionStatus.DRAFT


def test_publish_and_archive_rules(service: AgentService, store: FakeStore) -> None:
    agent = _ready_agent(service)
    version = service.create_version(OWNER, agent.agent_id, 0)
    with pytest.raises(LifecycleConflict):
        service.archive_version(OWNER, version.agent_version_id)  # not published yet
    published = service.publish_version(OWNER, version.agent_version_id)
    assert published.status is AgentVersionStatus.PUBLISHED
    with pytest.raises(LifecycleConflict):
        service.publish_version(OWNER, version.agent_version_id)  # only once
    archived = service.archive_version(OWNER, version.agent_version_id)
    assert archived.status is AgentVersionStatus.ARCHIVED
    with pytest.raises(LifecycleConflict):
        service.deploy_version(OWNER, agent.agent_id, version.agent_version_id, PROD)


def test_publish_refuses_a_tampered_snapshot(service: AgentService, store: FakeStore) -> None:
    agent = _ready_agent(service)
    version = service.create_version(OWNER, agent.agent_id, 0)
    org, view = store.versions[version.agent_version_id]
    tampered = {**view.configuration, "opening_message": "Changed after snapshot"}
    store.versions[version.agent_version_id] = (org, replace(view, configuration=tampered))
    with pytest.raises(LifecycleConflict):
        service.publish_version(OWNER, version.agent_version_id)
    store.versions[version.agent_version_id] = (org, replace(view, configuration={"x": 1}))
    with pytest.raises(InvalidAgentConfiguration):
        service.publish_version(OWNER, version.agent_version_id)
    assert "publish_version" not in store.calls


# -- deployments and rollback ----------------------------------------------------------------------


def test_only_published_versions_of_the_same_agent_deploy(service: AgentService) -> None:
    agent, other = _ready_agent(service), _ready_agent(service)
    draft = service.create_version(OWNER, agent.agent_id, 0)
    with pytest.raises(LifecycleConflict):
        service.deploy_version(OWNER, agent.agent_id, draft.agent_version_id, PROD)
    foreign = _published(service, other)
    with pytest.raises(VersionNotFound):
        service.deploy_version(OWNER, agent.agent_id, foreign.agent_version_id, PROD)


def test_rollback_rebinds_to_the_previous_earlier_version(service: AgentService) -> None:
    agent = _ready_agent(service)
    v1, v2, v3 = (_published(service, agent) for _ in range(3))
    for version in (v1, v2, v3):
        service.deploy_version(OWNER, agent.agent_id, version.agent_version_id, PROD)
    rolled = service.rollback_deployment(OWNER, agent.agent_id, PROD)
    assert rolled.agent_version_id == v2.agent_version_id
    current = service.get_deployment(OWNER, agent.agent_id, PROD)
    assert current is not None and current.agent_version_id == v2.agent_version_id
    rolled = service.rollback_deployment(OWNER, agent.agent_id, PROD, v1.agent_version_id)
    assert rolled.version_number == 1
    with pytest.raises(LifecycleConflict):  # forward is a deployment, not a rollback
        service.rollback_deployment(OWNER, agent.agent_id, PROD, v3.agent_version_id)
    with pytest.raises(LifecycleConflict):  # nothing earlier than v1
        service.rollback_deployment(OWNER, agent.agent_id, PROD)
    history = service.deployment_history(OWNER, agent.agent_id, PROD)
    assert [d.version_number for d in history] == [1, 2, 3, 2, 1]
    assert [d.status for d in history].count(DeploymentStatus.ACTIVE) == 1
    statuses = {v.version_number: v.status for v in service.list_versions(OWNER, agent.agent_id)}
    assert set(statuses.values()) == {AgentVersionStatus.PUBLISHED}  # versions untouched


def test_rollback_needs_a_deployment(service: AgentService) -> None:
    agent = _ready_agent(service)
    with pytest.raises(LifecycleConflict):
        service.rollback_deployment(OWNER, agent.agent_id, PROD)
    assert service.get_deployment(OWNER, agent.agent_id, DEV) is None


def test_publish_requires_usable_tool_references(
    service: AgentService, store: FakeStore, tools: FakeTools
) -> None:
    agent = service.create_agent(
        OWNER, "R", draft=agent_configuration(tool_refs=["calendar-main", "crm-main"])
    )
    version = service.create_version(OWNER, agent.agent_id, 0)
    tools.unusable = {"crm-main"}
    with pytest.raises(UnusableToolReferences) as raised:
        service.publish_version(OWNER, version.agent_version_id)
    assert raised.value.issues == ("tool_refs.1: unusable",)
    assert "publish_version" not in store.calls
    tools.unusable = set()
    assert service.publish_version(OWNER, version.agent_version_id).status is (
        AgentVersionStatus.PUBLISHED
    )
    assert tools.checked[-1] == ("calendar-main", "crm-main")  # the snapshot's refs
