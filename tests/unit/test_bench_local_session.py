"""Local transport gate: configuration safety and contracts (offline, no server needed)."""

import asyncio
import dataclasses

import pytest

from voiceos.benchmark.livekit_local import (
    LocalServer,
    LocalServerRefused,
    LocalSessionStatus,
    run_local_session_gate,
)
from voiceos.benchmark.ports import AdapterUnavailable, LocalSessionSpec
from voiceos.benchmark.runtimes import (
    LiveKitRuntimeAdapter,
    PipecatRuntimeAdapter,
    SdkStatus,
    _SdkRuntimeCandidate,
)

DEV = {"LIVEKIT_URL": "ws://127.0.0.1:7880", "LIVEKIT_API_KEY": "devkey", "LIVEKIT_API_SECRET": "x"}


def test_loopback_dev_server_is_accepted() -> None:
    server = LocalServer.from_env(DEV)
    assert server.http_url == "http://127.0.0.1:7880"
    assert "devkey" not in repr(server) and "'x'" not in repr(server)


@pytest.mark.parametrize(
    "url",
    [
        "wss://example.livekit.cloud",
        "ws://10.0.0.5:7880",
        "ws://livekit.example.org:7880",
        "http://127.0.0.1:7880",
        "",
    ],
)
def test_anything_but_a_loopback_ws_url_is_refused(url: str) -> None:
    with pytest.raises(LocalServerRefused):
        LocalServer.from_env(DEV | {"LIVEKIT_URL": url})


def test_missing_dev_credentials_are_refused() -> None:
    with pytest.raises(LocalServerRefused):
        LocalServer.from_env({"LIVEKIT_URL": "ws://127.0.0.1:7880"})


def test_session_spec_carries_transport_access_only() -> None:
    names = {f.name for f in dataclasses.fields(LocalSessionSpec)}
    assert not names & {"context", "call_context", "tenant_id", "scopes", "principal"}
    spec = LocalSessionSpec("ws://127.0.0.1:7880", "r", "id", "jwt-canary", "k-canary", "s-canary")
    assert "canary" not in repr(spec)


def test_only_the_livekit_agents_worker_needs_api_credentials() -> None:
    assert LiveKitRuntimeAdapter.needs_worker_credentials is True
    assert PipecatRuntimeAdapter.needs_worker_credentials is False


@pytest.mark.parametrize("adapter", [LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({})])
def test_gate_is_not_tested_without_sdk(
    adapter: _SdkRuntimeCandidate, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = SdkStatus(adapter.distribution, adapter.pinned, None, False, None, {})
    monkeypatch.setattr(type(adapter), "sdk_status", lambda self: missing)
    report = asyncio.run(run_local_session_gate(adapter, LocalServer.from_env(DEV)))
    assert report.status is LocalSessionStatus.NOT_TESTED
    with pytest.raises(AdapterUnavailable):
        asyncio.run(
            adapter.check_local_session(LocalSessionSpec("ws://127.0.0.1:1", "r", "i", "t"))
        )
