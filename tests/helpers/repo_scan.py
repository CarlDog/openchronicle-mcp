"""Repository file scanner for test helpers.

Scans the codebase for text files, respecting exclusions.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_repo_root() -> Path:
    """Get repository root relative to this file."""
    # This file is at tests/helpers/repo_scan.py
    # So repo root is 2 levels up
    return Path(__file__).parent.parent.parent.resolve()


_MIN_PLAUSIBLE_FILES = 50
"""Floor below which the scan is assumed broken rather than thorough."""


def scan_repository() -> list[tuple[Path, str]]:
    """
    Scan repository for text files.

    Scans src/, tests/, docs/ directories, excluding v1.reference/ and other artifacts.

    Returns:
        List of (path, text_content) tuples for text files.
        Paths are relative to repository root.
    """
    repo_root = get_repo_root()

    # Directories to scan
    scan_dirs = ["src", "tests", "docs"]

    # Binary/artifact file extensions to skip
    binary_extensions = {".zip", ".db", ".sqlite", ".png", ".jpg", ".pdf", ".pyc"}

    # Text file extensions to include
    text_extensions = {
        ".py",
        ".md",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".json",
        ".ini",
        ".cfg",
        ".sh",
        ".ps1",
    }

    # Directories to exclude
    exclude_dirs = {
        "v1.reference",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        ".git",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "*.egg-info",
    }

    results: list[tuple[Path, str]] = []

    for scan_dir_name in scan_dirs:
        scan_dir = repo_root / scan_dir_name

        if not scan_dir.exists():
            continue

        for root, dirs, files in os.walk(scan_dir):
            root_path = Path(root)

            # Remove excluded directories from dirs in-place
            # This prevents os.walk from descending into them
            dirs_to_remove = []
            for dir_name in dirs:
                # Check if directory should be excluded
                if dir_name in exclude_dirs:
                    dirs_to_remove.append(dir_name)
                    continue

                # Check if full path contains v1.reference segment
                dir_path = root_path / dir_name
                if "v1.reference" in dir_path.parts:
                    dirs_to_remove.append(dir_name)

            for dir_name in dirs_to_remove:
                dirs.remove(dir_name)

            # Process files
            for file_name in files:
                file_path = root_path / file_name

                # Skip binary files
                if file_path.suffix in binary_extensions:
                    continue

                # Only process text files with recognized extensions
                if file_path.suffix not in text_extensions:
                    # But include Dockerfile if no extension
                    if file_name != "Dockerfile":
                        continue

                # Double-check v1.reference is not in path
                if "v1.reference" in file_path.parts:
                    continue

                # Read file content
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # Store relative path
                    rel_path = file_path.relative_to(repo_root)
                    results.append((rel_path, content))
                except OSError, PermissionError:
                    # Skip files we can't read
                    continue

    # An empty (or implausibly small) corpus must FAIL, not pass quietly.
    # Eight zero-tolerance tests iterate this list and assert nothing
    # matches their forbidden pattern — so a scan that returns nothing
    # turns all eight green while checking nothing at all. The realistic
    # trigger is get_repo_root() resolving somewhere unexpected, which is
    # silent by construction. The floor is deliberately far below the real
    # count (several hundred) so it only ever catches a broken scan, never
    # a legitimately shrinking repo.
    if len(results) < _MIN_PLAUSIBLE_FILES:
        raise RuntimeError(
            f"scan_repository() found only {len(results)} file(s) under {repo_root} — "
            f"expected at least {_MIN_PLAUSIBLE_FILES}. Every guard built on this scan "
            f"would pass vacuously. Check that the repo root resolved correctly."
        )

    return results
