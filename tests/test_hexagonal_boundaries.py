"""Test hexagonal architecture boundaries.

This test ensures the domain layer remains pure and doesn't import
from application or infrastructure layers.
"""

from __future__ import annotations

from pathlib import Path


def test_domain_layer_has_no_application_infrastructure_imports() -> None:
    """
    Domain layer must not import from application or infrastructure layers.

    This enforces hexagonal architecture where:
    - domain: pure business logic (models, ports, exceptions, domain services)
    - application: orchestration and use cases
    - infrastructure: adapters and implementations
    """
    domain_path = Path(__file__).parent.parent / "src" / "openchronicle" / "core" / "domain"
    violations = []

    for py_file in domain_path.rglob("*.py"):
        # Skip __pycache__ and other non-source files
        if "__pycache__" in str(py_file):
            continue

        content = py_file.read_text(encoding="utf-8")

        # Check for absolute imports
        if "from openchronicle.core.application" in content:
            violations.append(
                f"{py_file.relative_to(domain_path.parent.parent.parent)}: imports from application layer"
            )
        if "from openchronicle.core.infrastructure" in content:
            violations.append(
                f"{py_file.relative_to(domain_path.parent.parent.parent)}: imports from infrastructure layer"
            )

        # Check for relative imports
        if "from ..application" in content or "from ...application" in content:
            violations.append(
                f"{py_file.relative_to(domain_path.parent.parent.parent)}: relative import from application layer"
            )
        if "from ..infrastructure" in content or "from ...infrastructure" in content:
            violations.append(
                f"{py_file.relative_to(domain_path.parent.parent.parent)}: relative import from infrastructure layer"
            )

    if violations:
        msg = "Domain layer has forbidden imports:\n" + "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(msg)
