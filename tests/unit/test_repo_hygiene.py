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


def test_no_provider_or_network_client_imports() -> None:
    for path in [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py")]:
        bad = _imported_roots(path) & FORBIDDEN
        assert not bad, f"{path.relative_to(ROOT)} imports {sorted(bad)}"


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
