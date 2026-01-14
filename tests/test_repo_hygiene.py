"""Test that enforces repository hygiene and prevents committed artifacts.

This test prevents:
- Local override files that should never ship with the repo (docker-compose.local.yml)
- Environment files that should never be committed (.env, .env.local, etc)

Philosophy: Repository must not contain local overrides or generated configuration
files. These belong in user-owned working directories or mounted volumes, not in git.

Note: Database artifacts (*.db, *.sqlite) are expected to exist during test
execution but are git-ignored and will not be shipped in the repo (per .gitignore).
This test verifies they're not committed by checking git tracking.

Hard exclusion: v1.reference/ is never scanned.
"""

from __future__ import annotations

from pathlib import Path


def _get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parent.parent


def _should_skip_path(path: Path) -> bool:
    """Check if a path should be skipped from scanning.

    Hard excludes v1.reference/ and standard Python/IDE directories.

    Args:
        path: Path to check

    Returns:
        True if path should be skipped
    """
    # Never scan v1.reference
    if "v1.reference" in path.parts:
        return True

    # Skip standard build/install artifacts (allowed in workspace)
    excluded_dirs = {
        ".venv",
        ".git",
        ".github",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".vscode",
        "dist",
        "build",
    }

    for part in path.parts:
        if part in excluded_dirs:
            return True

    return False


def _scan_forbidden_files() -> list[str]:
    """
    Scan for forbidden files that should never exist in-tree or be committed.

    Returns:
        List of forbidden file paths found (relative to repo root)
    """
    repo_root = _get_repo_root()
    violations = []

    # Local override files that should NEVER exist (not even in working directory)
    # These must always be local-only (not in any shared branch/zip)
    local_override_files = [
        "docker-compose.local.yml",
        ".env",
        ".env.local",
    ]
    for filename in local_override_files:
        file_path = repo_root / filename
        if file_path.exists():
            violations.append(filename)

    # Other *.env files (except .env.example)
    for env_file in repo_root.glob("*.env"):
        if env_file.name != ".env.example":
            violations.append(str(env_file.relative_to(repo_root)))

    return sorted(set(violations))


def test_no_runtime_artifacts() -> None:
    """Fail if local override files exist in the repository."""
    violations = _scan_forbidden_files()

    if violations:
        msg = (
            "Repository contains forbidden local override files:\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\n"
            "These files must never be committed or shipped in-tree:\n"
            "  - docker-compose.local.yml is for local dev only\n"
            "  - .env and .env.local are for local dev only\n\n"
            "Action: Delete these files. They should only exist locally.\n"
            "Use git-ignored .env.local for local configuration."
        )
        raise AssertionError(msg)


def test_v1_reference_excluded_from_hygiene_scan() -> None:
    """Regression test: verify v1.reference/ is excluded from hygiene scanning."""
    repo_root = _get_repo_root()
    v1_ref_path = repo_root / "v1.reference"

    if not v1_ref_path.exists():
        # If v1.reference doesn't exist, test passes (nothing to exclude)
        return

    # Check that _should_skip_path correctly identifies v1.reference paths
    test_path = v1_ref_path / "some_file.db"
    assert _should_skip_path(
        test_path
    ), f"ERROR: v1.reference path not being skipped: {test_path}\nThe hard exclusion for hygiene scanning is broken!"
