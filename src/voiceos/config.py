"""Phase 0 configuration.

Fails closed: live provider execution and recording can not be switched on in Phase 0.
Secrets are never part of ``repr`` so settings can not leak them into logs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from psycopg.conninfo import make_conninfo


class ConfigError(Exception):
    pass


def _parse_bool(env: Mapping[str, str], name: str) -> bool:
    raw = env.get(name, "false").strip().lower()
    if raw == "false":
        return False
    if raw == "true":
        return True
    raise ConfigError(f"{name} must be 'true' or 'false'")


@dataclass(frozen=True, slots=True)
class Settings:
    live_enabled: bool = False
    recording_enabled: bool = False
    pg_host: str = "127.0.0.1"
    pg_port: int = 55432
    pg_db: str = "voiceos"
    pg_app_password: str | None = field(default=None, repr=False)
    pg_migrator_password: str | None = field(default=None, repr=False)

    def app_conninfo(self) -> str:
        return self._conninfo("voiceos_app", self.pg_app_password)

    def migrator_conninfo(self) -> str:
        return self._conninfo("voiceos_migrator", self.pg_migrator_password)

    def _conninfo(self, user: str, password: str | None) -> str:
        if not password:
            raise ConfigError(f"no password configured for {user}")
        return make_conninfo(
            host=self.pg_host, port=self.pg_port, dbname=self.pg_db, user=user, password=password
        )


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    live_enabled = _parse_bool(env, "VOICEOS_LIVE_ENABLED")
    recording_enabled = _parse_bool(env, "VOICEOS_RECORDING_ENABLED")
    # Phase 0 boundary: neither may be enabled, regardless of what the environment asks for.
    if live_enabled:
        raise ConfigError("live provider execution is not authorized in Phase 0")
    if recording_enabled:
        raise ConfigError("recording is not authorized in Phase 0")
    return Settings(
        live_enabled=False,
        recording_enabled=False,
        pg_host=env.get("VOICEOS_PG_HOST", "127.0.0.1"),
        pg_port=int(env.get("VOICEOS_PG_PORT", "55432")),
        pg_db=env.get("VOICEOS_PG_DB", "voiceos"),
        pg_app_password=env.get("VOICEOS_APP_PASSWORD") or None,
        pg_migrator_password=env.get("VOICEOS_MIGRATOR_PASSWORD") or None,
    )
