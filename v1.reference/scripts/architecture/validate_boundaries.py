#!/usr/bin/env python3
"""
Architecture Boundary Validator

Enforces hexagonal architecture separation by validating that:
1. Core modules never import from plugins
2. Domain layer remains dependency-free
3. Infrastructure layer only imports from domain ports
4. Plugins can import from core but not other plugins

Usage:
    python scripts/architecture/validate_boundaries.py
    python scripts/architecture/validate_boundaries.py --fix-violations
"""

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple


class ArchitectureBoundaryValidator:
    """Validates hexagonal architecture boundaries."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_path = project_root / "src" / "openchronicle"
        self.violations = []

    def validate_all(self) -> bool:
        """Validate all architecture boundaries. Returns True if valid."""
        print("Validating hexagonal architecture boundaries...")

        # Rule 1: Core must never import from plugins
        self._validate_core_plugin_separation()

        # Rule 2: Domain layer must remain dependency-free
        self._validate_domain_purity()

        # Rule 3: Infrastructure can only import domain ports
        self._validate_infrastructure_dependencies()

        # Rule 4: Plugins can import core but not other plugins
        self._validate_plugin_isolation()

        return len(self.violations) == 0

    def _validate_core_plugin_separation(self):
        """Ensure core never imports from plugins."""
        print("  Checking core-plugin separation...")

        core_paths = [
            self.src_path / "domain",
            self.src_path / "infrastructure",
            self.src_path / "application",
            self.src_path / "bootstrap",
        ]

        for core_path in core_paths:
            if core_path.exists():
                self._check_directory_for_plugin_imports(core_path, "core")

    def _validate_domain_purity(self):
        """Ensure domain layer has minimal dependencies."""
        print("  Checking domain layer purity...")

        domain_path = self.src_path / "domain"
        if not domain_path.exists():
            return

        allowed_imports = {
            "abc",
            "typing",
            "enum",
            "dataclasses",
            "datetime",
            "uuid",
            "json",
            "pathlib",
            "openchronicle.shared",
        }

        for py_file in domain_path.rglob("*.py"):
            imports = self._extract_imports(py_file)
            for imp in imports:
                # Check if import is outside allowed list and not internal domain
                if not imp.startswith("openchronicle.domain") and not any(
                    imp.startswith(allowed) for allowed in allowed_imports
                ):
                    self.violations.append(
                        {
                            "type": "domain_dependency",
                            "file": str(py_file.relative_to(self.project_root)),
                            "import": imp,
                            "message": f"Domain layer should not import '{imp}'",
                        }
                    )

    def _validate_infrastructure_dependencies(self):
        """Ensure infrastructure only imports domain ports."""
        print("  Checking infrastructure dependencies...")

        infra_path = self.src_path / "infrastructure"
        if not infra_path.exists():
            return

        # Infrastructure can import domain ports and shared utilities
        allowed_patterns = [
            "openchronicle.domain.ports",
            "openchronicle.shared",
            "abc",
            "typing",
            "enum",
            "dataclasses",
            "datetime",
            "sqlite3",
            "json",
            "pathlib",
            "os",
            "sys",
            "warnings",
        ]

        for py_file in infra_path.rglob("*.py"):
            imports = self._extract_imports(py_file)
            for imp in imports:
                # Allow internal infrastructure imports
                if imp.startswith("openchronicle.infrastructure"):
                    continue

                # Check against allowed patterns
                if not any(imp.startswith(pattern) for pattern in allowed_patterns):
                    # Special exception for backwards compatibility imports from plugins
                    if "plugins.storytelling" in imp and "DEPRECATED" in py_file.read_text():
                        continue  # Allow deprecated compatibility imports

                    self.violations.append(
                        {
                            "type": "infrastructure_dependency",
                            "file": str(py_file.relative_to(self.project_root)),
                            "import": imp,
                            "message": f"Infrastructure should only import domain ports and allowed utilities, not '{imp}'",
                        }
                    )

    def _validate_plugin_isolation(self):
        """Ensure plugins don't import from other plugins."""
        print("  Checking plugin isolation...")

        plugins_path = self.src_path / "plugins"
        if not plugins_path.exists():
            return

        # Get all plugin directories
        plugin_dirs = [d for d in plugins_path.iterdir() if d.is_dir() and d.name != "__pycache__"]

        for plugin_dir in plugin_dirs:
            plugin_name = plugin_dir.name
            self._check_plugin_directory(plugin_dir, plugin_name, [p.name for p in plugin_dirs if p != plugin_dir])

    def _check_directory_for_plugin_imports(self, directory: Path, context: str):
        """Check a directory for any plugin imports."""
        for py_file in directory.rglob("*.py"):
            imports = self._extract_imports(py_file)
            for imp in imports:
                if "plugins" in imp and imp.startswith("openchronicle.plugins"):
                    # Check if this is a deprecated compatibility import
                    file_content = py_file.read_text()
                    if "DEPRECATED" in file_content and "backward compatibility" in file_content:
                        continue  # Allow deprecated compatibility imports

                    self.violations.append(
                        {
                            "type": "core_plugin_import",
                            "file": str(py_file.relative_to(self.project_root)),
                            "import": imp,
                            "message": f"{context.title()} module should not import from plugins: '{imp}'",
                        }
                    )

    def _check_plugin_directory(self, plugin_dir: Path, plugin_name: str, other_plugins: List[str]):
        """Check a plugin directory for cross-plugin imports."""
        for py_file in plugin_dir.rglob("*.py"):
            imports = self._extract_imports(py_file)
            for imp in imports:
                # Check for imports from other plugins
                for other_plugin in other_plugins:
                    if f"openchronicle.plugins.{other_plugin}" in imp:
                        self.violations.append(
                            {
                                "type": "cross_plugin_import",
                                "file": str(py_file.relative_to(self.project_root)),
                                "import": imp,
                                "message": f"Plugin '{plugin_name}' should not import from plugin '{other_plugin}': '{imp}'",
                            }
                        )

    def _extract_imports(self, py_file: Path) -> Set[str]:
        """Extract all import statements from a Python file."""
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            imports = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
                        # Also add full paths for specific imports
                        for alias in node.names:
                            imports.add(f"{node.module}.{alias.name}")

            return imports
        except (SyntaxError, UnicodeDecodeError, Exception):
            # Skip files that can't be parsed
            return set()

    def print_violations(self):
        """Print all architecture violations."""
        if not self.violations:
            print("No architecture boundary violations found!")
            return

        print(f"\nFound {len(self.violations)} architecture boundary violations:\n")

        violations_by_type = {}
        for violation in self.violations:
            vtype = violation["type"]
            if vtype not in violations_by_type:
                violations_by_type[vtype] = []
            violations_by_type[vtype].append(violation)

        for vtype, viols in violations_by_type.items():
            print(f"{vtype.replace('_', ' ').title()} ({len(viols)} violations):")
            for v in viols:
                print(f"   {v['file']}: {v['message']}")
            print()

    def get_violation_summary(self) -> Dict[str, int]:
        """Get summary of violations by type."""
        summary = {}
        for violation in self.violations:
            vtype = violation["type"]
            summary[vtype] = summary.get(vtype, 0) + 1
        return summary


def main():
    parser = argparse.ArgumentParser(description="Validate hexagonal architecture boundaries")
    parser.add_argument("--fix-violations", action="store_true", help="Attempt to fix common violations automatically")
    parser.add_argument("--project-root", type=Path, default=".", help="Path to project root directory")

    args = parser.parse_args()

    validator = ArchitectureBoundaryValidator(args.project_root)
    is_valid = validator.validate_all()

    validator.print_violations()

    if args.fix_violations and validator.violations:
        print("Auto-fix functionality not implemented yet.")
        print("   Please manually resolve violations or create issue for auto-fix feature.")

    # Exit with error code if violations found (for CI/CD)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
