"""Local LiveKit transport gate. Not part of the default test run.

Needs the optional SDKs and the loopback dev server:

    docker compose -f docker-compose.livekit.yml up -d
    uv sync --group voice-sdk
    uv run --no-sync --env-file .env pytest tests/integration -m livekit_local

Fails (does not skip) when the server or SDKs are missing.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from voiceos.benchmark.livekit_local import (
    LocalServer,
    LocalSessionStatus,
    list_gate_rooms,
    run_local_session_gate,
)
from voiceos.benchmark.ports import LocalSessionSpec
from voiceos.benchmark.runtimes import LiveKitRuntimeAdapter, PipecatRuntimeAdapter

pytestmark = pytest.mark.livekit_local
ADAPTERS = [LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({})]


@pytest.fixture(scope="module")
def server() -> LocalServer:
    for adapter in ADAPTERS:
        if not adapter.sdk_status().importable:
            pytest.fail("voice-sdk group not installed (uv sync --group voice-sdk)")
    try:
        server = LocalServer.from_env(os.environ)
        asyncio.run(list_gate_rooms(server))
    except Exception as exc:
        pytest.fail(f"local LiveKit dev server not usable: {type(exc).__name__}")
    return server


@pytest.mark.parametrize("adapter", ADAPTERS, ids=["livekit-agents", "pipecat"])
def test_runtime_joins_receives_media_and_leaves(adapter, server: LocalServer) -> None:  # type: ignore[no-untyped-def]
    report = asyncio.run(run_local_session_gate(adapter, server))
    assert report.error is None
    assert report.server_saw_runtime is True  # authoritative: server participant list
    assert report.media_frame_received is True  # synthetic tone reached the runtime
    assert report.server_room_empty_of_runtime_after_leave is True
    assert report.room_deleted is True
    assert report.status is LocalSessionStatus.VERIFIED


def test_both_arms_share_server_and_media_layer(server: LocalServer) -> None:
    pipecat = PipecatRuntimeAdapter({}).sdk_status()
    livekit = LiveKitRuntimeAdapter({}).sdk_status()
    assert pipecat.capabilities["SharedLiveKitRtc"] is True
    assert livekit.capabilities["LiveKitRtcRoom"] is True
    reports = [asyncio.run(run_local_session_gate(a, server)) for a in ADAPTERS]
    assert {r.status for r in reports} == {LocalSessionStatus.VERIFIED}


def test_no_gate_rooms_are_left_behind(server: LocalServer) -> None:
    asyncio.run(run_local_session_gate(PipecatRuntimeAdapter({}), server))
    assert asyncio.run(list_gate_rooms(server)) == []


@pytest.mark.parametrize("adapter", ADAPTERS, ids=["livekit-agents", "pipecat"])
def test_unreachable_server_fails_fast_and_reports_error_class(
    adapter, server: LocalServer
) -> None:  # type: ignore[no-untyped-def]
    async def noop(*_: object) -> None:
        return None

    spec = LocalSessionSpec(
        url="ws://127.0.0.1:7999",  # nothing listens here
        room="unreachable",
        identity="runtime",
        join_token="not-a-token",  # noqa: S106 - deliberately invalid placeholder
        worker_api_key=server.api_key,
        worker_api_secret=server.api_secret,
        dispatch=noop,
        timeout_s=5,
    )
    start = time.monotonic()
    observed = asyncio.run(adapter.check_local_session(spec))
    assert observed.joined_identity is None
    assert observed.error is not None
    assert time.monotonic() - start < 15


def test_livekit_worker_without_credentials_does_not_connect(server: LocalServer) -> None:
    spec = LocalSessionSpec(server.url, "no-creds", "runtime", "token")
    observed = asyncio.run(LiveKitRuntimeAdapter({}).check_local_session(spec))
    assert observed.error == "WorkerRegistrationNotConfigured"
