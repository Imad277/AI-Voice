"""Local LiveKit transport gate (Phase 1).

Trusted harness side: talks to a loopback-only LiveKit dev server, creates a throwaway
room, mints room-scoped join tokens, plays a synthetic caller (sine tone, no microphone),
lets one runtime adapter join and leave, and verifies the result against the server's
own participant list. No providers, no business tools, no cloud.

The dev server's API key/secret are the public ``--dev`` placeholders and are read from
the environment (``LIVEKIT_URL``, ``LIVEKIT_API_KEY``, ``LIVEKIT_API_SECRET``).
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from voiceos.benchmark.ports import LocalSessionSpec
from voiceos.benchmark.runtimes import _SdkRuntimeCandidate

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class LocalSessionStatus(StrEnum):
    VERIFIED = "LOCAL_SESSION_VERIFIED"
    FAILED = "LOCAL_SESSION_FAILED"
    NOT_TESTED = "NOT_TESTED"


class LocalServerRefused(Exception):
    """Configuration does not point at a loopback dev server."""


@dataclass(frozen=True, slots=True)
class LocalServer:
    url: str
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> LocalServer:
        url = env.get("LIVEKIT_URL", "")
        parsed = urlparse(url)
        if parsed.scheme != "ws" or parsed.hostname not in LOOPBACK_HOSTS:
            raise LocalServerRefused("LIVEKIT_URL must be ws:// on a loopback host")
        key, secret = env.get("LIVEKIT_API_KEY", ""), env.get("LIVEKIT_API_SECRET", "")
        if not key or not secret:
            raise LocalServerRefused("LIVEKIT_API_KEY / LIVEKIT_API_SECRET not set")
        return cls(url, key, secret)

    @property
    def http_url(self) -> str:
        return "http" + self.url.removeprefix("ws")


@dataclass(frozen=True, slots=True)
class LocalSessionReport:
    runtime: str
    runtime_version: str | None
    status: LocalSessionStatus
    room: str | None
    joined_identity: str | None
    server_saw_runtime: bool | None  # authoritative: server participant list while joined
    server_room_empty_of_runtime_after_leave: bool | None
    media_frame_received: bool | None
    room_deleted: bool | None
    error: str | None
    notes: tuple[str, ...] = ()


class SyntheticCaller:
    """A plain livekit.rtc participant publishing a 440 Hz tone. No microphone."""

    def __init__(self, rtc: Any) -> None:
        self._rtc = rtc
        self._room = rtc.Room()
        self._feeder: asyncio.Task[None] | None = None

    async def join(self, url: str, token: str) -> None:
        rtc = self._rtc
        await self._room.connect(url, token)
        source = rtc.AudioSource(48_000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("synthetic-tone", source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await self._room.local_participant.publish_track(track, options)
        self._feeder = asyncio.ensure_future(self._feed(source))

    async def _feed(self, source: Any) -> None:
        samples, n = 480, 0  # 10 ms frames
        while True:
            frame = self._rtc.AudioFrame.create(48_000, 1, samples)
            for i in range(samples):
                frame.data[i] = int(3000 * math.sin(2 * math.pi * 440 * (n * samples + i) / 48_000))
            await source.capture_frame(frame)
            n += 1

    async def leave(self) -> None:
        if self._feeder is not None:
            self._feeder.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._feeder
        await self._room.disconnect()


async def run_local_session_gate(
    adapter: _SdkRuntimeCandidate,
    server: LocalServer,
    *,
    timeout_s: float = 15.0,
    settle_s: float = 1.5,
) -> LocalSessionReport:
    def report(status: LocalSessionStatus, **kwargs: Any) -> LocalSessionReport:
        values: dict[str, Any] = {
            "room": None,
            "joined_identity": None,
            "server_saw_runtime": None,
            "server_room_empty_of_runtime_after_leave": None,
            "media_frame_received": None,
            "room_deleted": None,
            "error": None,
        } | kwargs
        return LocalSessionReport(adapter.provider, adapter.info.version, status, **values)

    if not adapter.sdk_status().importable:
        return report(LocalSessionStatus.NOT_TESTED, notes=("SDK not installed or importable",))

    from livekit import api, rtc

    room = f"voiceos-gate-{adapter.provider}-{uuid.uuid4().hex[:8]}"
    identity = f"{adapter.provider}-runtime"

    def token(who: str) -> str:
        grants = api.VideoGrants(room_join=True, room=room)  # this room only
        return str(
            api.AccessToken(server.api_key, server.api_secret)
            .with_identity(who)
            .with_grants(grants)
            .to_jwt()
        )

    lk = api.LiveKitAPI(server.http_url, server.api_key, server.api_secret)
    caller = SyntheticCaller(rtc)
    during: list[str] = []
    try:
        try:
            await lk.room.create_room(api.CreateRoomRequest(name=room, empty_timeout=30))
            await caller.join(server.url, token("synthetic-caller"))
        except Exception as exc:
            return report(LocalSessionStatus.FAILED, room=room, error=type(exc).__name__)

        async def on_joined() -> None:
            listing = await lk.room.list_participants(api.ListParticipantsRequest(room=room))
            during.extend(p.identity for p in listing.participants)

        async def dispatch(agent_name: str) -> None:
            await lk.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
            )

        spec = LocalSessionSpec(
            url=server.url,
            room=room,
            identity=identity,
            join_token=token(identity),
            worker_api_key=server.api_key if adapter.needs_worker_credentials else None,
            worker_api_secret=server.api_secret if adapter.needs_worker_credentials else None,
            dispatch=dispatch,
            on_joined=on_joined,
            timeout_s=timeout_s,
        )
        observed = await adapter.check_local_session(spec)
        await asyncio.sleep(settle_s)  # let the server process the leave
        listing = await lk.room.list_participants(api.ListParticipantsRequest(room=room))
        after = [p.identity for p in listing.participants]
    finally:
        with contextlib.suppress(Exception):
            await caller.leave()
    deleted: bool | None = None
    with contextlib.suppress(Exception):
        await lk.room.delete_room(api.DeleteRoomRequest(room=room))
        rooms = await lk.room.list_rooms(api.ListRoomsRequest(names=[room]))
        deleted = not rooms.rooms
    await lk.aclose()

    joined = observed.joined_identity
    saw = joined is not None and joined in during
    left = joined is not None and joined not in after
    ok = observed.error is None and saw and left and observed.media_frame_received is True
    return report(
        LocalSessionStatus.VERIFIED if ok else LocalSessionStatus.FAILED,
        room=room,
        joined_identity=joined,
        server_saw_runtime=saw,
        server_room_empty_of_runtime_after_leave=left,
        media_frame_received=observed.media_frame_received,
        room_deleted=deleted,
        error=observed.error,
    )


async def list_gate_rooms(server: LocalServer) -> list[str]:
    """Observer helper: rooms created by this gate that still exist on the server."""
    from livekit import api

    lk = api.LiveKitAPI(server.http_url, server.api_key, server.api_secret)
    try:
        rooms = await lk.room.list_rooms(api.ListRoomsRequest())
    finally:
        await lk.aclose()
    return [r.name for r in rooms.rooms if r.name.startswith("voiceos-gate-")]
