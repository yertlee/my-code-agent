from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]
SOURCE_ROOT = ROOT / "src" / "coding_agent"
AGENT_LOOP = SOURCE_ROOT / "agent" / "loop.py"
MAX_PRODUCT_LINES = 8_000
MAX_KERNEL_LINES = 2_000
MAX_AGENT_LOOP_LINES = 500
MAX_REGULAR_MODULE_LINES = 300
APPROVED_RUNTIME_DEPENDENCIES = {"openai", "prompt-toolkit", "pydantic", "rich"}

KERNEL_PATHS = (
    SOURCE_ROOT / "agent",
    SOURCE_ROOT / "protocol",
    SOURCE_ROOT / "runtime",
    SOURCE_ROOT / "tools" / "base.py",
    SOURCE_ROOT / "tools" / "registry.py",
    SOURCE_ROOT / "app" / "application.py",
    SOURCE_ROOT / "app" / "factory.py",
)

BANNED_AGENT_IMPORTS = (
    "coding_agent.app",
    "coding_agent.cli",
    "coding_agent.providers.fake",
    "coding_agent.providers.openai_compatible",
    "coding_agent.tools.edit",
    "coding_agent.tools.readonly",
    "coding_agent.tools.shell",
    "coding_agent.tools.todo",
)

EXTENSION_ROOTS = (
    SOURCE_ROOT / "providers",
    SOURCE_ROOT / "tools",
    SOURCE_ROOT / "permissions",
    SOURCE_ROOT / "session",
    SOURCE_ROOT / "context",
    SOURCE_ROOT / "memory",
    SOURCE_ROOT / "workspace",
)


def test_source_and_kernel_line_budgets() -> None:
    source_files = tuple(SOURCE_ROOT.rglob("*.py"))
    assert sum(_line_count(path) for path in source_files) <= MAX_PRODUCT_LINES
    assert _line_count(AGENT_LOOP) <= MAX_AGENT_LOOP_LINES
    assert sum(_line_count(path) for path in _kernel_files()) <= MAX_KERNEL_LINES

    oversized = {
        path.relative_to(ROOT): _line_count(path)
        for path in source_files
        if path != AGENT_LOOP and _line_count(path) > MAX_REGULAR_MODULE_LINES
    }
    assert oversized == {}


def test_runtime_dependencies_are_explicitly_approved() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = {
        re.split(r"[<>=!~\[]", item, maxsplit=1)[0].strip().lower()
        for item in project["project"]["dependencies"]
    }
    assert dependencies == APPROVED_RUNTIME_DEPENDENCIES


def test_agent_loop_does_not_import_concrete_extensions() -> None:
    imports = _imports_from(AGENT_LOOP)
    violations = {
        name
        for name in imports
        if any(name == banned or name.startswith(f"{banned}.") for banned in BANNED_AGENT_IMPORTS)
    }
    assert violations == set()


def test_extensions_do_not_import_agent_loop() -> None:
    violations: set[Path] = set()
    for root in EXTENSION_ROOTS:
        for path in root.rglob("*.py"):
            if any(name.startswith("coding_agent.agent") for name in _imports_from(path)):
                violations.add(path.relative_to(ROOT))
    assert violations == set()


def test_there_is_one_agent_loop_and_protocols_stay_narrow() -> None:
    loop_classes = 0
    wide_protocols: dict[str, int] = {}
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name == "AgentLoop":
                loop_classes += 1
            if any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases):
                method_count = sum(
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) for item in node.body
                )
                if method_count > 5:
                    wide_protocols[f"{path.relative_to(ROOT)}:{node.name}"] = method_count
    assert loop_classes == 1
    assert wide_protocols == {}


def _kernel_files() -> set[Path]:
    files: set[Path] = set()
    for path in KERNEL_PATHS:
        if path.is_dir():
            files.update(path.rglob("*.py"))
        else:
            files.add(path)
    return files


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    return imports
