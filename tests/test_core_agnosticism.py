from __future__ import annotations

import ast
import importlib
import linecache
from pathlib import Path

DENYLISTED_IMPORTS = {
    "discord",
    "discord.py",
    "slack",
    "slack_sdk",
    "telegram",
    "telebot",
    "fastapi",
    "flask",
    "django",
    "aiohttp",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source_root() -> Path:
    return _repo_root() / "src" / "openchronicle"


def _iter_source_files() -> list[Path]:
    """Iterate core source files (domain + application + infrastructure).

    Excludes ``interfaces/`` — that layer is the driving adapter where
    framework imports (discord.py, Flask, etc.) legitimately belong.
    """
    root = _source_root() / "core"
    if not root.exists():
        raise AssertionError(f"Core source root not found: {root}")

    files: list[Path] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def _scan_file(path: Path) -> list[tuple[Path, int, str]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    violations: list[tuple[Path, int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DENYLISTED_IMPORTS:
                    statement = linecache.getline(str(path), node.lineno).rstrip()
                    violations.append((path, node.lineno, statement))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            root = node.module.split(".")[0]
            if root in DENYLISTED_IMPORTS:
                statement = linecache.getline(str(path), node.lineno).rstrip()
                violations.append((path, node.lineno, statement))

    return violations


def test_core_stays_frontend_agnostic() -> None:
    violations: list[tuple[Path, int, str]] = []
    for path in _iter_source_files():
        violations.extend(_scan_file(path))

    if violations:
        formatted = "\n".join(f"{path}:{lineno}: {statement}" for path, lineno, statement in violations)
        raise AssertionError("Forbidden front-end/framework imports detected:\n" + formatted)


def test_cli_entrypoint_importable() -> None:
    cli_path = _source_root() / "interfaces" / "cli" / "main.py"
    assert cli_path.exists()
    importlib.import_module("openchronicle.interfaces.cli.main")
