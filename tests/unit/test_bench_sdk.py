"""Local SDK status of the runtime candidates (offline; no session, no network)."""

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from voiceos.benchmark.runtimes import (
    LiveKitRuntimeAdapter,
    PipecatRuntimeAdapter,
    SdkStatus,
    _SdkRuntimeCandidate,
)

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = [LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({})]


@pytest.mark.parametrize("adapter", CANDIDATES, ids=["livekit", "pipecat"])
def test_missing_sdk_is_reported_not_raised(
    adapter: _SdkRuntimeCandidate, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(type(adapter), "_installed_version", lambda self: None)
    status = adapter.sdk_status()
    assert status == SdkStatus(adapter.distribution, adapter.pinned, None, False, None, {})
    assert any("not installed" in m for m in adapter.probe().missing)
    assert adapter.probe().available is False


@pytest.mark.parametrize("adapter", CANDIDATES, ids=["livekit", "pipecat"])
def test_failing_sdk_import_is_reported_by_class_name(
    adapter: _SdkRuntimeCandidate, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: object) -> dict[str, bool]:
        raise OSError("/private/path/libportaudio.dylib not found")

    monkeypatch.setattr(type(adapter), "_installed_version", lambda self: adapter.pinned)
    monkeypatch.setattr(type(adapter), "_import_capabilities", boom)
    status = adapter.sdk_status()
    assert status.importable is False
    assert status.import_error == "OSError"
    assert any("import failed: OSError" in m for m in adapter.probe().missing)
    assert "/private/path" not in repr(adapter.probe())


@pytest.mark.parametrize("adapter", CANDIDATES, ids=["livekit", "pipecat"])
def test_unpinned_version_is_reported(
    adapter: _SdkRuntimeCandidate, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(type(adapter), "_installed_version", lambda self: "0.0.1")
    monkeypatch.setattr(type(adapter), "_import_capabilities", lambda self: {})
    assert any("is not the pinned" in m for m in adapter.probe().missing)


needs_sdk = pytest.mark.skipif(
    importlib.util.find_spec("livekit") is None or importlib.util.find_spec("pipecat") is None,
    reason="optional voice-sdk group not installed (uv sync --group voice-sdk)",
)


@needs_sdk
def test_installed_sdks_import_with_expected_entry_points() -> None:
    livekit = LiveKitRuntimeAdapter({}).sdk_status()
    pipecat = PipecatRuntimeAdapter({}).sdk_status()
    assert (livekit.installed_version, livekit.importable) == ("1.8.3", True)
    assert (pipecat.installed_version, pipecat.importable) == ("1.12.0", True)
    assert livekit.capabilities == {
        "AgentSession": True,
        "Agent": True,
        "JobContext": True,
        "LiveKitRtcRoom": True,
    }
    assert pipecat.capabilities == {
        "Pipeline": True,
        "PipelineWorker": True,
        "WorkerRunner": True,
        "FrameProcessor": True,
        "LiveKitTransport": True,
        "LiveKitParams": True,
        "SharedLiveKitRtc": True,  # same livekit.rtc media layer as livekit-agents
    }
    for adapter in (LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({})):
        missing = adapter.probe().missing
        assert not any(
            m.startswith(("SDK capability", f"SDK {adapter.distribution}")) for m in missing
        )


@needs_sdk
def test_sdk_probe_opens_no_sockets_and_starts_no_threads() -> None:
    # Fresh interpreter: every socket connect fails loudly, then the SDKs are probed.
    code = textwrap.dedent(
        """
        import json, socket, threading

        def refuse(*args, **kwargs):
            raise AssertionError("network access attempted")

        socket.socket.connect = refuse
        socket.socket.connect_ex = refuse
        socket.create_connection = refuse
        before = threading.active_count()
        from voiceos.benchmark.runtimes import LiveKitRuntimeAdapter, PipecatRuntimeAdapter

        statuses = [a.sdk_status() for a in (LiveKitRuntimeAdapter({}), PipecatRuntimeAdapter({}))]
        print(json.dumps({
            "importable": [s.importable for s in statuses],
            "threads": [before, threading.active_count()],
        }))
        """
    )
    out = subprocess.run(  # noqa: S603 - fixed interpreter and inline script
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert result["importable"] == [True, True]
    assert result["threads"][0] == result["threads"][1]
