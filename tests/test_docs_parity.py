"""Docs-parity gates: the CLI, the MCP tool inventory and `OC_*` settings (ROADMAP QUAL-05).

Each fact here lives twice, once in code and once in an operator document,
and the copies drifted before (design 0004, finding 5: six falsehoods at one
snapshot). These tests read the code's own view (the argparse tree, the
registered MCP tools, the `OC_*` names the source reads) and require the
documents to match, in both directions: an undocumented command or setting
fails, and so does a documented one that no longer exists.

They do not force MCP/REST/CLI parity, and they do not generate documents
(0004's advice): only the inventories are checked, not prose.

Every check first asserts it found something, so a broken parser or a moved
file fails loudly instead of comparing two empty sets.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

import pytest

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.main import build_parser
from openchronicle.interfaces.mcp.config import MCPConfig
from openchronicle.interfaces.mcp.server import create_server

ROOT = Path(__file__).resolve().parents[1]
COMMANDS_MD = ROOT / "docs" / "cli" / "commands.md"
MCP_SPEC_MD = ROOT / "docs" / "integrations" / "mcp_server_spec.md"
ENV_VARS_MD = ROOT / "docs" / "configuration" / "env_vars.md"
ENV_EXAMPLE = ROOT / ".env.example"
SRC = ROOT / "src" / "openchronicle"


def _read(path: Path) -> str:
    assert path.is_file(), f"premise: {path.relative_to(ROOT)} exists"
    return path.read_text(encoding="utf-8")


# --- CLI: docs/cli/commands.md -------------------------------------------------


def _leaf_commands(parser: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> dict[str, set[str]]:
    """Each runnable command path (`memory add`) mapped to its long options."""
    found: dict[str, set[str]] = {}
    has_subcommands = False
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            has_subcommands = True
            for name, sub in action.choices.items():
                found.update(_leaf_commands(sub, (*path, name)))
    if path and not has_subcommands:
        found[" ".join(path)] = {
            opt
            for action in parser._actions
            for opt in action.option_strings
            if opt.startswith("--") and opt != "--help"
        }
    return found


_HEADING = re.compile(r"^### `oc ([^`]*)`", re.M)
_COMMAND_WORD = re.compile(r"[a-z][a-z-]*")


def _documented_commands() -> dict[str, str]:
    """Each `### \\`oc ...\\`` heading's command path, mapped to its section text."""
    text = _read(COMMANDS_MD)
    headings = list(_HEADING.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(headings):
        words = []
        for token in m.group(1).split():
            if not _COMMAND_WORD.fullmatch(token):
                break  # an argument placeholder (NAME, [--flag], --flag) ends the path
            words.append(token)
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        next_h2 = text.find("\n## ", m.end())
        if next_h2 != -1:
            end = min(end, next_h2)
        sections[" ".join(words)] = text[m.start() : end]
    return sections


def test_every_cli_command_is_documented() -> None:
    commands = _leaf_commands(build_parser())
    assert len(commands) >= 20, f"premise: the parser walk found commands ({len(commands)})"
    missing = sorted(set(commands) - set(_documented_commands()))
    assert not missing, f"commands with no `### \\`oc ...\\`` heading in docs/cli/commands.md: {missing}"


def test_every_documented_cli_command_exists() -> None:
    documented = _documented_commands()
    assert len(documented) >= 20, f"premise: the headings parsed ({len(documented)})"
    stale = sorted(set(documented) - set(_leaf_commands(build_parser())))
    assert not stale, f"docs/cli/commands.md documents commands the CLI does not have: {stale}"


def test_every_cli_long_option_is_documented_in_its_section() -> None:
    commands = _leaf_commands(build_parser())
    documented = _documented_commands()
    assert sum(len(opts) for opts in commands.values()) >= 20, "premise: the walk found long options"
    missing = [
        f"oc {path} {opt}"
        for path, opts in sorted(commands.items())
        if path in documented
        for opt in sorted(opts)
        if not re.search(re.escape(opt) + r"(?![a-z-])", documented[path])
    ]
    assert not missing, f"long options not mentioned in their command's section of docs/cli/commands.md: {missing}"


# --- MCP: docs/integrations/mcp_server_spec.md --------------------------------------

_TOOL_ROW = re.compile(r"^\| `([a-z_]+)` \|", re.M)
_GATED_SECTION = "## Optional local backup and restore preparation"
_INVENTORY_END = "## Tool design philosophy"


def _documented_tools() -> tuple[set[str], set[str]]:
    """(default tools, gated backup tools) from the spec's inventory tables."""
    text = _read(MCP_SPEC_MD)
    assert _GATED_SECTION in text and _INVENTORY_END in text, "premise: the spec's section headings moved"
    default_part, rest = text.split(_GATED_SECTION, 1)
    gated_part = rest.split(_INVENTORY_END, 1)[0]
    return set(_TOOL_ROW.findall(default_part)), set(_TOOL_ROW.findall(gated_part))


async def _registered_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, backup: bool) -> set[str]:
    # Building the server constructs the real container: point it at a temp DB.
    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "parity.db"))
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    container = CoreContainer()
    try:
        server = create_server(container, MCPConfig.from_env(), backup_tools_enabled=backup)
        return {tool.name for tool in await server.list_tools()}
    finally:
        container.close()


@pytest.mark.anyio
async def test_mcp_tool_inventory_matches_the_spec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    default = await _registered_tools(monkeypatch, tmp_path, backup=False)
    gated = await _registered_tools(monkeypatch, tmp_path, backup=True) - default
    assert len(default) >= 15 and gated, f"premise: tools registered ({len(default)} default, {len(gated)} gated)"
    documented_default, documented_gated = _documented_tools()

    assert documented_default == default, (
        f"default MCP tools vs docs/integrations/mcp_server_spec.md: "
        f"undocumented {sorted(default - documented_default)}, stale {sorted(documented_default - default)}"
    )
    assert documented_gated == gated, (
        f"gated backup tools vs the spec's '{_GATED_SECTION[3:]}' section: "
        f"undocumented {sorted(gated - documented_gated)}, stale {sorted(documented_gated - gated)}"
    )
    assert f"default {len(default)}-tool inventory" in _read(MCP_SPEC_MD), (
        f"the spec's stated default inventory size is not {len(default)}"
    )


# --- Environment: docs/configuration/env_vars.md and .env.example ----------------

_OC_NAME = re.compile(r"OC_[A-Z0-9_]+")


def _source_env_names() -> set[str]:
    """Every string literal in the source that is exactly an `OC_*` name.

    Names are read through several helpers (`os.getenv`, `os.environ`,
    `env_override`, `parse_bool_env`), so the literal is the one stable signal.
    """
    files = list(SRC.rglob("*.py"))
    assert files, "premise: the source tree resolved"
    names = set()
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _OC_NAME.fullmatch(node.value):
                names.add(node.value)
    return names


def _documented_env_names() -> set[str]:
    return set(re.findall(r"`(OC_[A-Z0-9_]+)`", _read(ENV_VARS_MD)))


def test_every_env_var_the_source_reads_is_documented() -> None:
    source = _source_env_names()
    assert len(source) >= 20, f"premise: the scan found OC_* names ({len(source)})"
    missing = sorted(source - _documented_env_names())
    assert not missing, f"OC_* settings the source reads but docs/configuration/env_vars.md omits: {missing}"


def test_every_documented_env_var_is_read_by_the_source() -> None:
    documented = _documented_env_names()
    assert len(documented) >= 20, f"premise: env_vars.md parsed ({len(documented)})"
    stale = sorted(documented - _source_env_names())
    assert not stale, f"docs/configuration/env_vars.md documents OC_* settings nothing reads: {stale}"


def test_env_example_names_are_real() -> None:
    example = set(re.findall(r"^#?\s*(OC_[A-Z0-9_]+)=", _read(ENV_EXAMPLE), re.M))
    assert example, "premise: .env.example lists OC_* settings"
    stale = sorted(example - _source_env_names())
    assert not stale, f".env.example lists OC_* settings nothing reads: {stale}"
