"""Phase 0 boundary checks on the code base itself."""

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Providers, runtimes and infrastructure that must not enter the code base in Phase 0.
FORBIDDEN = {
    "livekit", "pipecat", "deepgram", "speechmatics", "elevenlabs", "cartesia", "openai",
    "anthropic", "google", "gemini", "twilio", "telnyx", "vonage", "temporalio", "n8n",
    "kubernetes", "redis", "requests", "httpx", "aiohttp", "urllib3", "boto3", "terraform",
}  # fmt: skip


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


# Phase 1: the runtime candidate SDKs may be imported only inside the runtime adapter
# boundary. Everything else (core, gateway, booking, tenancy, config, providers) stays clean.
RUNTIME_SDK_BOUNDARY = {
    Path("src/voiceos/benchmark/runtimes.py"): {"livekit", "pipecat"},
    # Local transport gate harness: livekit.api/livekit.rtc against the loopback dev server.
    Path("src/voiceos/benchmark/livekit_local.py"): {"livekit"},
    # End-to-end gate harness: synthetic caller and room setup on the loopback dev server.
    Path("src/voiceos/benchmark/e2e_gate.py"): {"livekit"},
    # Turn-taking gate: native runtime arms and the harness (caller, room setup).
    Path("src/voiceos/benchmark/turn_runtimes.py"): {"livekit", "pipecat"},
    Path("src/voiceos/benchmark/turn_gate.py"): {"livekit"},
    # Offline Pipecat orchestration test: real pipeline, fake transport (no network).
    Path("tests/unit/test_bench_pipecat_e2e.py"): {"pipecat"},
    # STT/LLM/TTS baseline gates: provider SDKs live only in the provider adapter module.
    Path("src/voiceos/benchmark/providers.py"): {"deepgram", "openai", "elevenlabs", "cartesia"},
}


def test_no_provider_or_network_client_imports() -> None:
    for path in [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py")]:
        allowed = RUNTIME_SDK_BOUNDARY.get(path.relative_to(ROOT), set())
        bad = (_imported_roots(path) & FORBIDDEN) - allowed
        assert not bad, f"{path.relative_to(ROOT)} imports {sorted(bad)}"


def test_runtime_sdks_are_an_exactly_pinned_optional_group() -> None:
    from voiceos.benchmark.runtimes import LiveKitRuntimeAdapter, PipecatRuntimeAdapter

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    group = project["dependency-groups"]["voice-sdk"]
    # Exact pins only; the single extra is Pipecat's LiveKit transport (transport parity).
    assert sorted(group) == [
        f"{LiveKitRuntimeAdapter.distribution}=={LiveKitRuntimeAdapter.pinned}",
        f"{PipecatRuntimeAdapter.distribution}[livekit]=={PipecatRuntimeAdapter.pinned}",
    ]
    assert project["tool"]["uv"]["default-groups"] == ["dev"]


def test_dependencies_stay_minimal() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    names = {
        d.split(">")[0].split("[")[0].split("=")[0].strip()
        for d in project["project"]["dependencies"]
    }
    assert names == {"pydantic", "psycopg"}
    dev = {d.split(">")[0].strip() for d in project["dependency-groups"]["dev"]}
    assert dev == {"pytest", "ruff", "mypy"}


def test_compose_runs_only_postgres_on_localhost() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    images = [line.split(":", 1)[1].strip() for line in compose.splitlines() if "image:" in line]
    assert images == ["postgres:18.6"]
    assert '"127.0.0.1:' in compose


def test_local_livekit_compose_is_pinned_dev_mode_and_loopback_only() -> None:
    compose = (ROOT / "docker-compose.livekit.yml").read_text()
    images = [line.split(":", 1)[1].strip() for line in compose.splitlines() if "image:" in line]
    assert images == ["livekit/livekit-server:v1.13.8"]
    assert '"--dev"' in compose and '"--node-ip", "127.0.0.1"' in compose
    ports = [line.strip() for line in compose.splitlines() if line.strip().startswith('- "')]
    assert ports and all(p.startswith('- "127.0.0.1:') for p in ports)
