from pathlib import Path

import pytest

from voiceos.config import ConfigError, Settings, load_settings

ROOT = Path(__file__).resolve().parents[2]


def test_defaults_are_safe() -> None:
    settings = load_settings({})
    assert settings.live_enabled is False
    assert settings.recording_enabled is False


@pytest.mark.parametrize("name", ["VOICEOS_LIVE_ENABLED", "VOICEOS_RECORDING_ENABLED"])
def test_enabling_live_or_recording_is_refused_in_phase_0(name: str) -> None:
    with pytest.raises(ConfigError):
        load_settings({name: "true"})


@pytest.mark.parametrize("value", ["yes", "1", "on", "", "disabled"])
def test_ambiguous_boolean_values_are_refused(value: str) -> None:
    with pytest.raises(ConfigError):
        load_settings({"VOICEOS_LIVE_ENABLED": value})


def test_passwords_never_appear_in_repr() -> None:
    settings = load_settings(
        {"VOICEOS_APP_PASSWORD": "canary-app-pw", "VOICEOS_MIGRATOR_PASSWORD": "canary-mig-pw"}
    )
    assert "canary" not in repr(settings)


def test_missing_password_fails_closed() -> None:
    with pytest.raises(ConfigError):
        Settings().app_conninfo()


def test_env_example_ships_safe_defaults_and_no_secret_values() -> None:
    values = {}
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key] = value
    assert values["VOICEOS_LIVE_ENABLED"] == "false"
    assert values["VOICEOS_RECORDING_ENABLED"] == "false"
    for key in ("POSTGRES_PASSWORD", "VOICEOS_MIGRATOR_PASSWORD", "VOICEOS_APP_PASSWORD"):
        assert values[key] == "", f"{key} must be empty in .env.example"
    assert load_settings(values).live_enabled is False
