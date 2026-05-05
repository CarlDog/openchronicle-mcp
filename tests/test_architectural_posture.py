"""Architectural posture tests — verify structural invariants.

These tests enforce non-functional guarantees that protect the project's
hexagonal architecture and optional-dependency model. v3 has dropped the
Discord interface and the stdio/RPC layer entirely; the v2-era posture
tests targeting those modules have been removed. Phase 4 will revisit
this file once the v3 layout is final.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from unittest.mock import patch

# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────

_SRC_ROOT = Path(__file__).parent.parent / "src"


def _scan_for_forbidden_imports(
    layer_path: Path,
    forbidden_patterns: list[str],
) -> list[str]:
    violations: list[str] = []
    for py_file in layer_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(_SRC_ROOT)
        for pattern in forbidden_patterns:
            if re.search(rf"^(?:from|import)\s+{re.escape(pattern)}", content, re.MULTILINE):
                violations.append(f"{rel}: imports {pattern}")
    return violations


# ───────────────────────────────────────────────────────────────────
# Core runs without MCP SDK installed
# ───────────────────────────────────────────────────────────────────


class TestCoreAgnosticOfMCP:
    """Core CLI/domain/application must import successfully without mcp SDK."""

    @staticmethod
    def _block_mcp_packages() -> dict[str, types.ModuleType | None]:
        blocked = {}
        for name in list(sys.modules):
            if name == "mcp" or name.startswith("mcp."):
                blocked[name] = sys.modules[name]
        sentinel: dict[str, types.ModuleType | None] = dict.fromkeys(blocked)
        for pkg in ("mcp", "mcp.server", "mcp.server.fastmcp"):
            sentinel[pkg] = None
        return sentinel

    def test_core_domain_imports_without_mcp(self) -> None:
        with patch.dict(sys.modules, self._block_mcp_packages()):
            import openchronicle.core.domain  # noqa: F401

    def test_core_application_imports_without_mcp(self) -> None:
        with patch.dict(sys.modules, self._block_mcp_packages()):
            import openchronicle.core.application  # noqa: F401

    def test_cli_main_imports_without_mcp(self) -> None:
        with patch.dict(sys.modules, self._block_mcp_packages()):
            import openchronicle.interfaces.cli.main  # noqa: F401


# ───────────────────────────────────────────────────────────────────
# No MCP imports leak into core
# ───────────────────────────────────────────────────────────────────


class TestMCPDoesNotLeakIntoCore:
    """Neither core.domain, core.application, nor core.infrastructure
    may import from interfaces.mcp or the mcp library."""

    def test_core_has_no_mcp_library_imports(self) -> None:
        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = _scan_for_forbidden_imports(core_path, ["mcp"])
        if violations:
            msg = "Core imports mcp library:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)

    def test_core_has_no_interfaces_mcp_imports(self) -> None:
        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = _scan_for_forbidden_imports(
            core_path,
            ["openchronicle.interfaces.mcp"],
        )
        if violations:
            msg = "Core imports interfaces.mcp:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)
