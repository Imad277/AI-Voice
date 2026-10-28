"""Architecture boundaries of the modular monolith (Phase 2A, PR 1).

Static (AST) checks over ``src/voiceos`` so that every future product PR keeps:

- product code free of ``voiceos.benchmark`` (benchmark = evidence infrastructure only),
- the layer direction domain <- runtime <- application <- infrastructure,
- Phase 0 packages independent of the new product layers,
- control plane and data plane as separate internal modules,
- no import cycles between modules,
- every product module importable without the optional voice SDK groups.

The checker functions are tested against deliberate violations, so the rules cannot pass
silently.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PACKAGE = SRC / "voiceos"

BENCHMARK = "voiceos.benchmark"
NEW_LAYERS = {"domain", "application", "runtime", "infrastructure"}
PHASE0 = {"core", "gateway", "booking", "tenancy", "mocks", "config"}

# Allowed voiceos layers per importing layer (the layer itself is always allowed).
ALLOWED: dict[str, set[str]] = {
    "domain": {"core"},
    "runtime": {"core", "domain"},
    "application": {"core", "domain", "runtime", "gateway", "booking", "tenancy", "config"},
    "infrastructure": {
        "core", "domain", "runtime", "application", "gateway", "booking", "tenancy", "config",
    },
    **{layer: PHASE0 for layer in PHASE0},  # Phase 0 never depends on the new layers
}  # fmt: skip
# Third-party infrastructure libraries the inner product layers must not use directly.
INFRA_LIBRARIES = {"psycopg"}
INNER_LAYERS = {"domain", "runtime", "application"}
PLANES = ("voiceos.application.control_plane", "voiceos.application.data_plane")
VOICE_SDKS = {"livekit", "pipecat", "deepgram", "openai", "elevenlabs", "cartesia"}


def module_name(path: Path) -> tuple[str, bool]:
    parts = path.relative_to(SRC).with_suffix("").parts
    is_package = parts[-1] == "__init__"
    return ".".join(parts[:-1] if is_package else parts), is_package


def imported_modules(source: str, module: str, is_package: bool) -> set[str]:
    """Absolute names imported by a module, including relative and string-based imports."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = module if is_package else module.rpartition(".")[0]
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - (node.level - 1)])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            found.add(target)
            found.update(f"{target}.{alias.name}" for alias in node.names)
        elif (
            isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                or (isinstance(node.func, ast.Name) and node.func.id == "__import__")
            )
        ):
            found.add(node.args[0].value)
    return found


def layer_of(name: str) -> str | None:
    parts = name.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "voiceos" else None


def violations(module: str, source: str, is_package: bool = False) -> list[str]:
    own = layer_of(module)
    if own is None or own == "benchmark":
        return []  # the benchmark may use product contracts
    problems: list[str] = []
    for name in sorted(imported_modules(source, module, is_package)):
        root, layer = name.split(".")[0], layer_of(name)
        if name == BENCHMARK or name.startswith(BENCHMARK + "."):
            problems.append(f"{module} imports benchmark module {name}")
        elif layer is not None and layer != own and layer not in ALLOWED.get(own, set()):
            problems.append(f"{module} ({own}) must not import {name} ({layer})")
        elif own in INNER_LAYERS and root in INFRA_LIBRARIES:
            problems.append(f"{module} ({own}) must not use infrastructure library {root}")
        for plane, other in (PLANES, PLANES[::-1]):
            if module.startswith(plane) and (name == other or name.startswith(other + ".")):
                problems.append(f"{module} crosses the plane boundary into {name}")
    return problems


def source_modules() -> list[tuple[str, bool, Path]]:
    return [(*module_name(p), p) for p in sorted(PACKAGE.rglob("*.py"))]


# -- the rules hold for the code base ---------------------------------------------------------


def test_new_product_layers_exist() -> None:
    names = {name for name, _, _ in source_modules()}
    for layer in NEW_LAYERS:
        assert f"voiceos.{layer}" in names
    assert set(PLANES) <= names
    assert {"voiceos.runtime.contracts", "voiceos.runtime.providers"} <= names


def test_no_module_outside_the_benchmark_imports_it() -> None:
    offenders = [
        (name, imported)
        for name, is_package, path in source_modules()
        if not name.startswith(BENCHMARK)
        for imported in imported_modules(path.read_text(), name, is_package)
        if imported == BENCHMARK or imported.startswith(BENCHMARK + ".")
    ]
    assert offenders == []


def test_layer_rules_hold_for_every_module() -> None:
    problems = [
        problem
        for name, is_package, path in source_modules()
        for problem in violations(name, path.read_text(), is_package)
    ]
    assert problems == []


def test_no_import_cycles_between_modules() -> None:
    # The benchmark is evidence infrastructure (unchanged Phase 1 code) and is excluded.
    modules = {
        name: (is_package, path)
        for name, is_package, path in source_modules()
        if not name.startswith(BENCHMARK)
    }
    graph: dict[str, set[str]] = {}
    for name, (is_package, path) in modules.items():
        edges: set[str] = set()
        for imported in imported_modules(path.read_text(), name, is_package):
            target = imported
            while target and target not in modules:
                target = target.rpartition(".")[0]
            if target in modules and target != name and not modules[target][0]:
                edges.add(target)  # module-level edges; package __init__ files carry no code
        graph[name] = edges
    state: dict[str, int] = {}
    cycles: list[list[str]] = []

    def visit(node: str, trail: list[str]) -> None:
        state[node] = 1
        for nxt in sorted(graph[node]):
            if state.get(nxt) == 1:
                cycles.append([*trail[trail.index(nxt) :], nxt] if nxt in trail else [node, nxt])
            elif nxt not in state:
                visit(nxt, [*trail, nxt])
        state[node] = 2

    for start in sorted(graph):
        if start not in state:
            visit(start, [start])
    assert cycles == []


def test_product_modules_import_without_voice_sdks() -> None:
    names = [name for name, _, _ in source_modules() if not name.startswith(BENCHMARK)]
    sdks = sorted(VOICE_SDKS)
    script = "\n".join([
        "import importlib, json, sys",
        f"for name in {names!r}:",
        "    importlib.import_module(name)",
        f"print(json.dumps(sorted({{m.split('.')[0] for m in sys.modules}} & set({sdks!r}))))",
    ])  # fmt: skip
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    done = subprocess.run(  # noqa: S603 - fixed interpreter and generated script
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, check=False
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == []


# -- the checker catches violations -----------------------------------------------------------


def test_checker_flags_benchmark_imports_in_every_form() -> None:
    cases = [
        ("voiceos.application.data_plane.calls", "from voiceos.benchmark.providers import X"),
        ("voiceos.runtime.contracts", "import voiceos.benchmark.voice_loop"),
        ("voiceos.domain.calls.model", "from ...benchmark import runner"),
        ("voiceos.infrastructure.stt", "importlib.import_module('voiceos.benchmark.cli')"),
        ("voiceos.infrastructure.stt", "__import__('voiceos.benchmark.cli')"),
        ("voiceos.gateway.gateway", "from voiceos import benchmark"),
    ]  # fmt: skip
    for module, source in cases:
        assert any("benchmark" in p for p in violations(module, source)), (module, source)


def test_checker_flags_wrong_layer_direction() -> None:
    assert violations("voiceos.domain.agents.model", "from voiceos.infrastructure import db")
    assert violations("voiceos.domain.agents.model", "from voiceos.application import x")
    assert violations("voiceos.domain.agents.model", "import psycopg")
    assert violations("voiceos.runtime.contracts", "from voiceos.application.data_plane import y")
    assert violations("voiceos.application.data_plane.s", "from voiceos.infrastructure.x import A")
    assert violations("voiceos.application.data_plane.s", "from voiceos.mocks.voice import F")
    assert violations("voiceos.core.context", "from voiceos.domain.identity import Org")
    assert violations("voiceos.tenancy.db", "from voiceos.runtime.contracts import X")


def test_checker_flags_plane_crossing() -> None:
    assert violations(
        "voiceos.application.control_plane.agents", "from voiceos.application.data_plane import s"
    )
    assert violations(
        "voiceos.application.data_plane.sessions", "from ..control_plane import agents"
    )


def test_checker_allows_the_intended_directions() -> None:
    assert not violations("voiceos.runtime.providers", "from voiceos.core.tools import ToolRequest")
    assert not violations(
        "voiceos.application.data_plane.s", "from voiceos.runtime import contracts"
    )
    assert not violations(
        "voiceos.application.control_plane.a", "from voiceos.domain import agents"
    )
    assert not violations(
        "voiceos.infrastructure.pg", "import psycopg\nfrom voiceos.domain import x"
    )
    assert not violations("voiceos.benchmark.cli", "from voiceos.runtime.contracts import X")
