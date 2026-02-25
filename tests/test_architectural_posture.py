"""Architectural posture tests — verify structural invariants.

These tests enforce non-functional guarantees that protect the project's
hexagonal architecture, optional-dependency model, session isolation,
and failure-mode contracts.
"""

from __future__ import annotations

import re
import sys
import types
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────

_SRC_ROOT = Path(__file__).parent.parent / "src"

_EnqueueCheckFn = Callable[[str | None], bool]


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
# A. Core runs without Discord installed
# ───────────────────────────────────────────────────────────────────


class TestCoreAgnosticOfDiscord:
    """Core CLI/RPC modules must import successfully without discord."""

    @staticmethod
    def _block_discord_packages() -> dict[str, types.ModuleType | None]:
        """Return a sys.modules overlay that makes discord un-importable."""
        blocked = {}
        for name in list(sys.modules):
            if name == "discord" or name.startswith("discord."):
                blocked[name] = sys.modules[name]
        # Add sentinel None entries so import machinery raises ImportError
        sentinel: dict[str, types.ModuleType | None] = dict.fromkeys(blocked)
        # Also block fresh imports
        for pkg in ("discord", "discord.ext", "discord.ext.commands"):
            sentinel[pkg] = None
        return sentinel

    def test_core_domain_imports_without_discord(self) -> None:
        blocked = self._block_discord_packages()
        with patch.dict(sys.modules, blocked):
            # Re-importing should not fail
            import openchronicle.core.domain  # noqa: F401

    def test_core_application_imports_without_discord(self) -> None:
        blocked = self._block_discord_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.core.application  # noqa: F401

    def test_cli_main_imports_without_discord(self) -> None:
        blocked = self._block_discord_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.interfaces.cli.main  # noqa: F401

    def test_rpc_handlers_import_without_discord(self) -> None:
        blocked = self._block_discord_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.interfaces.cli.rpc_handlers  # noqa: F401

    def test_stdio_imports_without_discord(self) -> None:
        blocked = self._block_discord_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.interfaces.cli.stdio  # noqa: F401


# ───────────────────────────────────────────────────────────────────
# A+B. No discord imports leak into core
# ───────────────────────────────────────────────────────────────────


class TestDiscordDoesNotLeakIntoCore:
    """Neither core.domain, core.application, nor core.infrastructure
    may import from interfaces.discord or the discord library."""

    def test_core_has_no_discord_library_imports(self) -> None:
        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = _scan_for_forbidden_imports(core_path, ["discord"])
        if violations:
            msg = "Core imports discord library:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)

    def test_core_has_no_interfaces_discord_imports(self) -> None:
        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = _scan_for_forbidden_imports(
            core_path,
            ["openchronicle.interfaces.discord"],
        )
        if violations:
            msg = "Core imports interfaces.discord:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)


# ───────────────────────────────────────────────────────────────────
# A2. Core runs without MCP SDK installed
# ───────────────────────────────────────────────────────────────────


class TestCoreAgnosticOfMCP:
    """Core CLI/RPC modules must import successfully without mcp SDK."""

    @staticmethod
    def _block_mcp_packages() -> dict[str, types.ModuleType | None]:
        """Return a sys.modules overlay that makes mcp un-importable."""
        blocked = {}
        for name in list(sys.modules):
            if name == "mcp" or name.startswith("mcp."):
                blocked[name] = sys.modules[name]
        sentinel: dict[str, types.ModuleType | None] = dict.fromkeys(blocked)
        for pkg in ("mcp", "mcp.server", "mcp.server.fastmcp"):
            sentinel[pkg] = None
        return sentinel

    def test_core_domain_imports_without_mcp(self) -> None:
        blocked = self._block_mcp_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.core.domain  # noqa: F401

    def test_core_application_imports_without_mcp(self) -> None:
        blocked = self._block_mcp_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.core.application  # noqa: F401

    def test_cli_main_imports_without_mcp(self) -> None:
        blocked = self._block_mcp_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.interfaces.cli.main  # noqa: F401

    def test_rpc_handlers_import_without_mcp(self) -> None:
        blocked = self._block_mcp_packages()
        with patch.dict(sys.modules, blocked):
            import openchronicle.interfaces.cli.rpc_handlers  # noqa: F401


# ───────────────────────────────────────────────────────────────────
# A+B2. No MCP imports leak into core
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


# ───────────────────────────────────────────────────────────────────
# C. Multi-session isolation (no global mutable state)
# ───────────────────────────────────────────────────────────────────


class TestDiscordMultiInstanceIsolation:
    """Two Discord session managers with different configs must not collide."""

    def test_separate_session_stores_are_independent(self, tmp_path: Path) -> None:
        from openchronicle.interfaces.discord.session import SessionManager

        sm_a = SessionManager(str(tmp_path / "sessions_a.json"))
        sm_b = SessionManager(str(tmp_path / "sessions_b.json"))

        sm_a.set_conversation_id("user-1", "convo-alpha")
        sm_b.set_conversation_id("user-1", "convo-beta")

        assert sm_a.get_conversation_id("user-1") == "convo-alpha"
        assert sm_b.get_conversation_id("user-1") == "convo-beta"

    def test_two_configs_produce_distinct_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig
        from openchronicle.interfaces.discord.session import SessionManager

        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-key")

        config_a = DiscordConfig.from_env(
            file_config={
                "session_store_path": str(tmp_path / "a.json"),
                "conversation_title": "Server A",
                "history_limit": 3,
                "guild_ids": [111],
            }
        )
        config_b = DiscordConfig.from_env(
            file_config={
                "session_store_path": str(tmp_path / "b.json"),
                "conversation_title": "Server B",
                "history_limit": 10,
                "guild_ids": [222],
            }
        )

        assert config_a.conversation_title != config_b.conversation_title
        assert config_a.history_limit != config_b.history_limit
        assert config_a.guild_ids != config_b.guild_ids

        sm_a = SessionManager(config_a.session_store_path)
        sm_b = SessionManager(config_b.session_store_path)

        sm_a.set_conversation_id("user-1", "convo-A")
        sm_b.set_conversation_id("user-1", "convo-B")

        assert sm_a.get_conversation_id("user-1") == "convo-A"
        assert sm_b.get_conversation_id("user-1") == "convo-B"


# ───────────────────────────────────────────────────────────────────
# E. Enqueue allowlist — only transient errors qualify
# ───────────────────────────────────────────────────────────────────


class TestEnqueueAllowlist:
    """is_enqueueable_provider_failure must accept ONLY transient errors."""

    @pytest.fixture()
    def _fn(self) -> _EnqueueCheckFn:
        from openchronicle.core.application.use_cases.ask_conversation import (
            is_enqueueable_provider_failure,
        )

        return is_enqueueable_provider_failure

    def test_connection_error_is_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("CONNECTION_ERROR") is True

    def test_timeout_is_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("TIMEOUT") is True

    def test_provider_error_is_not_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("PROVIDER_ERROR") is False

    def test_budget_exceeded_is_not_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("BUDGET_EXCEEDED") is False

    def test_auth_error_is_not_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("MISSING_API_KEY") is False

    def test_config_error_is_not_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("CONFIG_ERROR") is False

    def test_none_is_not_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn(None) is False

    def test_empty_is_not_enqueueable(self, _fn: _EnqueueCheckFn) -> None:
        assert _fn("") is False

    def test_allowlist_is_exactly_two_codes(self, _fn: _EnqueueCheckFn) -> None:
        """Guard against allowlist creep — only 2 codes should pass."""
        from openchronicle.core.domain.errors import error_codes

        all_codes = [
            getattr(error_codes, name) for name in error_codes.__all__ if isinstance(getattr(error_codes, name), str)
        ]
        passing = [code for code in all_codes if _fn(code)]
        assert sorted(passing) == [
            "CONNECTION_ERROR",
            "TIMEOUT",
        ], f"Allowlist has drifted — expected exactly connection_error + timeout, got {passing}"
