"""Test hexagonal architecture boundaries.

Enforces the layering with an AST scanner (see
``tests/helpers/import_scan.py``) since 2026-08-17 — the previous regex
scanner was anchored at column 0, so TYPE_CHECKING and function-body
imports bypassed it entirely (2026-08-15 review finding; two real
type-level leaks rode through the hole).

1. Domain must not import from application or infrastructure.
2. Application must not import from infrastructure — with two
   enumerated TYPE_CHECKING exemptions (below).
3. Core (domain + application + infrastructure) must not import from
   any interface.
4. Core must not import the MCP SDK.
"""

from __future__ import annotations

from pathlib import Path

from tests.helpers.import_scan import find_forbidden_imports

_SRC_ROOT = Path(__file__).parent.parent / "src"

# The container-as-opaque-token pragmatism, enumerated: these two
# application modules name CoreContainer in type annotations only —
# maintenance job handlers receive it as an opaque context token, and
# build_health_payload assembles the container-backed health payload
# shared by both surfaces. Neither imports infrastructure at runtime.
# Anything beyond these two pairs is a violation; extend this set only
# with the same documented deliberateness.
_TYPE_CHECKING_ALLOWED = frozenset(
    {
        (
            "openchronicle/core/application/services/maintenance_loop.py",
            "openchronicle.core.infrastructure",
        ),
        (
            "openchronicle/core/application/use_cases/diagnose_runtime.py",
            "openchronicle.core.infrastructure",
        ),
    }
)


def _assert_clean(violations: list[str], label: str) -> None:
    if violations:
        raise AssertionError(f"{label}:\n" + "\n".join(f"  - {v}" for v in violations))


def test_domain_layer_has_no_application_infrastructure_imports() -> None:
    violations = find_forbidden_imports(
        _SRC_ROOT / "openchronicle" / "core" / "domain",
        ["openchronicle.core.application", "openchronicle.core.infrastructure"],
        src_root=_SRC_ROOT,
    )
    _assert_clean(violations, "Domain layer has forbidden imports")


def test_application_layer_has_no_infrastructure_imports() -> None:
    violations = find_forbidden_imports(
        _SRC_ROOT / "openchronicle" / "core" / "application",
        ["openchronicle.core.infrastructure"],
        src_root=_SRC_ROOT,
        type_checking_allowed=_TYPE_CHECKING_ALLOWED,
    )
    _assert_clean(violations, "Application layer has forbidden infrastructure imports")


def test_core_has_no_interfaces_imports() -> None:
    violations = find_forbidden_imports(
        _SRC_ROOT / "openchronicle" / "core",
        ["openchronicle.interfaces"],
        src_root=_SRC_ROOT,
    )
    _assert_clean(violations, "Core has forbidden interfaces imports")


def test_core_has_no_interfaces_mcp_imports() -> None:
    """Core must remain runnable without the MCP SDK installed."""
    violations = find_forbidden_imports(
        _SRC_ROOT / "openchronicle" / "core",
        ["openchronicle.interfaces.mcp", "mcp"],
        src_root=_SRC_ROOT,
    )
    _assert_clean(violations, "Core has forbidden MCP imports")


class TestScannerSeesWhatTheRegexMissed:
    """Self-test pinning the exact holes the 2026-08-15 review found."""

    @staticmethod
    def _scan(tmp_path: Path, source: str) -> list[str]:
        pkg = tmp_path / "app" / "core" / "sub"
        pkg.mkdir(parents=True)
        (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "app" / "core" / "__init__.py").write_text("", encoding="utf-8")
        pkg.joinpath("__init__.py").write_text("", encoding="utf-8")
        pkg.joinpath("mod.py").write_text(source, encoding="utf-8")
        return find_forbidden_imports(tmp_path / "app", ["app.forbidden"], src_root=tmp_path)

    def test_detects_type_checking_import(self, tmp_path: Path) -> None:
        source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.forbidden import x\n"
        violations = self._scan(tmp_path, source)
        assert len(violations) == 1
        assert "(TYPE_CHECKING)" in violations[0]

    def test_detects_function_body_import(self, tmp_path: Path) -> None:
        source = "def f():\n    import app.forbidden\n    return app.forbidden\n"
        assert len(self._scan(tmp_path, source)) == 1

    def test_resolves_relative_imports(self, tmp_path: Path) -> None:
        # From app/core/sub/mod.py, `from ...forbidden import x` is
        # app.forbidden — invisible to any absolute-name regex.
        source = "from ...forbidden import x\n"
        assert len(self._scan(tmp_path, source)) == 1

    def test_clean_module_and_prefix_confusion(self, tmp_path: Path) -> None:
        # 'app.forbidden' must not match 'app.forbidden_not' (prefix
        # match is segment-aware), and stdlib imports never match.
        source = "import os\nfrom app.forbidden_not import x\n"
        assert self._scan(tmp_path, source) == []
