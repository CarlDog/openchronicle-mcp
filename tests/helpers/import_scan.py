"""AST-based forbidden-import scanner for architecture boundary tests.

Replaces the regex scanner (2026-08-15 review finding): a pattern
anchored at column 0 could not see imports inside ``if TYPE_CHECKING:``
blocks or function bodies, and never resolved relative imports — two
real type-level boundary leaks rode through that hole for months. The
AST walk sees every ``import``/``from`` node wherever it sits.

TYPE_CHECKING imports ARE violations by default. The narrow, enumerated
exception is ``type_checking_allowed``: (file, forbidden-prefix) pairs
for the documented container-as-opaque-token pragmatism, so every
exemption is greppable here rather than invisible in the scanner.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _package_parts(py_file: Path, src_root: Path) -> list[str]:
    """The package a file's relative imports resolve against."""
    parts = list(py_file.relative_to(src_root).with_suffix("").parts)
    # Both a/b/c.py and a/b/__init__.py resolve level-1 imports against
    # package a.b — dropping the final component covers both.
    return parts[:-1]


def _type_checking_spans(tree: ast.Module) -> list[tuple[int, int]]:
    """Line ranges of ``if TYPE_CHECKING:`` bodies."""
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not node.body:
            continue
        test = node.test
        is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if is_tc:
            end = max(getattr(n, "end_lineno", None) or n.lineno for n in node.body)
            spans.append((node.body[0].lineno, end))
    return spans


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def find_forbidden_imports(
    layer_path: Path,
    forbidden_prefixes: list[str],
    *,
    src_root: Path,
    type_checking_allowed: frozenset[tuple[str, str]] = frozenset(),
) -> list[str]:
    """Return violation descriptions for imports of forbidden modules.

    Sees module-level, function-body, and TYPE_CHECKING imports, and
    resolves relative imports (``from ..infrastructure import x``)
    against the importing file's package.
    """
    violations: list[str] = []

    for py_file in sorted(layer_path.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(src_root).as_posix()
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        tc_spans = _type_checking_spans(tree)
        package = _package_parts(py_file, src_root)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    modules = [node.module or ""]
                else:
                    base = package[: len(package) - (node.level - 1)]
                    modules = [".".join([*base, node.module]) if node.module else ".".join(base)]
            else:
                continue

            in_type_checking = any(start <= node.lineno <= end for start, end in tc_spans)
            for module in modules:
                for prefix in forbidden_prefixes:
                    if not _matches(module, prefix):
                        continue
                    if in_type_checking and (rel, prefix) in type_checking_allowed:
                        continue
                    marker = " (TYPE_CHECKING)" if in_type_checking else ""
                    violations.append(f"{rel}:{node.lineno}: imports {module}{marker}")

    return violations
