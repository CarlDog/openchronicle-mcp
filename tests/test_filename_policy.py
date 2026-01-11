"""Test to enforce filename policy in core/ directory.

Prevents future filename regressions by ensuring filenames follow the
two-word snake_case convention.
"""

from pathlib import Path


def test_core_filenames_max_two_words() -> None:
    """Enforce that core/ filenames have at most two underscore-separated words.

    Policy:
    - Python filenames should contain at most 2 underscore-separated words
    - Exceptions:
      - *_port.py (explicit port naming)
      - __init__.py (package init)
      - conftest.py (pytest configuration)

    This test scans the entire core/ directory and fails if any filenames
    violate this policy, listing all offending files.
    """
    # Locate core directory
    test_dir = Path(__file__).parent
    repo_root = test_dir.parent
    core_dir = repo_root / "src" / "openchronicle" / "core"

    if not core_dir.exists():
        raise AssertionError(f"Core directory not found: {core_dir}")

    offending_files = []

    # Walk all Python files in core/
    for py_file in sorted(core_dir.rglob("*.py")):
        filename = py_file.name

        # Skip exceptions
        if filename == "__init__.py" or filename == "conftest.py":
            continue
        if filename.endswith("_port.py"):
            continue

        # Extract the stem (filename without .py)
        stem = py_file.stem

        # Split on underscore to count words
        parts = stem.split("_")

        # Fail if more than 2 parts
        if len(parts) > 2:
            rel_path = py_file.relative_to(repo_root)
            offending_files.append(str(rel_path))

    if offending_files:
        msg = "Filename policy violation: filenames must have at most 2 underscore-separated words.\nOffending files:\n"
        for f in offending_files:
            msg += f"  - {f}\n"
        msg += "\nExceptions: *_port.py, __init__.py, conftest.py\n"
        raise AssertionError(msg)
