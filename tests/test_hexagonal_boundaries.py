"""Test hexagonal architecture boundaries.

Enforces four boundaries:
1. Domain layer must not import from application or infrastructure.
2. Application layer must not import from infrastructure.
3. Core (domain + application + infrastructure) must not import from any interface.
4. Per-interface tests for Discord and MCP (catch library imports too).
"""

from __future__ import annotations

import re
from pathlib import Path


def _scan_layer_for_forbidden_imports(
    layer_path: Path,
    forbidden_patterns: list[str],
    *,
    src_root: Path,
) -> list[str]:
    """Scan all .py files in *layer_path* for forbidden import strings.

    Returns a list of human-readable violation descriptions.
    """
    violations: list[str] = []

    for py_file in layer_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(src_root)

        for pattern in forbidden_patterns:
            # Match actual import statements, not docstrings / comments
            if re.search(rf"^(?:from|import)\s+{re.escape(pattern)}", content, re.MULTILINE):
                violations.append(f"{rel}: imports {pattern}")

    return violations


def test_domain_layer_has_no_application_infrastructure_imports() -> None:
    """
    Domain layer must not import from application or infrastructure layers.

    This enforces hexagonal architecture where:
    - domain: pure business logic (models, ports, exceptions, domain services)
    - application: orchestration and use cases
    - infrastructure: adapters and implementations
    """
    src_root = Path(__file__).parent.parent / "src"
    domain_path = src_root / "openchronicle" / "core" / "domain"

    violations = _scan_layer_for_forbidden_imports(
        domain_path,
        [
            "openchronicle.core.application",
            "openchronicle.core.infrastructure",
        ],
        src_root=src_root,
    )

    if violations:
        msg = "Domain layer has forbidden imports:\n" + "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(msg)


def test_application_layer_has_no_infrastructure_imports() -> None:
    """
    Application layer must not import from infrastructure layer.

    The composition root (wiring) lives in infrastructure. Application
    use-cases, services, and policies depend only on domain ports and
    application-level config, never on concrete infrastructure.
    """
    src_root = Path(__file__).parent.parent / "src"
    application_path = src_root / "openchronicle" / "core" / "application"

    violations = _scan_layer_for_forbidden_imports(
        application_path,
        [
            "openchronicle.core.infrastructure",
        ],
        src_root=src_root,
    )

    if violations:
        msg = "Application layer has forbidden infrastructure imports:\n" + "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(msg)


def test_core_has_no_interfaces_imports() -> None:
    """
    Core layers must not import from any interfaces module.

    Interfaces (CLI, Discord, MCP, RPC) are driving adapters that depend
    on core, not the reverse. This catches any current or future interface
    leaking into core.
    """
    src_root = Path(__file__).parent.parent / "src"
    core_path = src_root / "openchronicle" / "core"

    violations = _scan_layer_for_forbidden_imports(
        core_path,
        [
            "openchronicle.interfaces",
        ],
        src_root=src_root,
    )

    if violations:
        msg = "Core has forbidden interfaces imports:\n" + "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(msg)


def test_core_has_no_interfaces_discord_imports() -> None:
    """
    Core layers must not import from interfaces.discord.

    Discord is a driving adapter that depends on core, not the reverse.
    Core must remain runnable without Discord installed.
    """
    src_root = Path(__file__).parent.parent / "src"
    core_path = src_root / "openchronicle" / "core"

    violations = _scan_layer_for_forbidden_imports(
        core_path,
        [
            "openchronicle.interfaces.discord",
            "discord",
        ],
        src_root=src_root,
    )

    if violations:
        msg = "Core has forbidden Discord imports:\n" + "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(msg)


def test_core_has_no_interfaces_mcp_imports() -> None:
    """
    Core layers must not import from interfaces.mcp.

    MCP is a driving adapter that depends on core, not the reverse.
    Core must remain runnable without MCP SDK installed.
    """
    src_root = Path(__file__).parent.parent / "src"
    core_path = src_root / "openchronicle" / "core"

    violations = _scan_layer_for_forbidden_imports(
        core_path,
        [
            "openchronicle.interfaces.mcp",
            "mcp",
        ],
        src_root=src_root,
    )

    if violations:
        msg = "Core has forbidden MCP imports:\n" + "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(msg)
