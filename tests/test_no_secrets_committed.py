"""Test that prevents secrets from being committed to the repository.

This test enforces zero-tolerance for:
- Local env files (.env.local, .env) that should never be in-tree
- Real-looking API keys or tokens in source files

Hard exclusion: v1.reference/ is never scanned.

Philosophy:
- Keys belong in user-owned persistent config files (/config)
- Plaintext config is fine, but keys must not be in git
- .env.example is allowed as a placeholder-only file
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.helpers.repo_scan import scan_repository  # isort:skip


# Forbidden files that must never exist in the repository tree
FORBIDDEN_FILES = [
    ".env.local",
    ".env",
]

# Forbidden patterns (glob-style) - env files except .env.example
FORBIDDEN_PATTERNS = [
    "*.env",
]

# Allowed exceptions to forbidden patterns
ALLOWED_ENV_FILES = {
    ".env.example",
}

# PII patterns. These mirror the pre-commit hook's checks, which are the
# ONLY place they ran until 2026-08-28 - and a local hook is bypassable by
# design: --no-verify skips it, an unset core.hooksPath disables it
# silently, and a commit pushed from another machine never saw it. CI is
# the backstop that cannot be skipped by the person making the mistake.
#
# The patterns are deliberately GENERIC: this file is public, so baking in
# a real name, username, or address would leak the thing it guards.
PII_PATTERNS = [
    (r"[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]", "Mac/Windows user-home path"),
    (r"[/\\]home[/\\][A-Za-z0-9._-]+[/\\]", "Linux user-home path"),
    (
        r"[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud|me|live|aol)\.[a-z]{2,}",
        "personal-domain email address",
    ),
]
# Secret patterns to detect (matched case-insensitively where noted)
SECRET_PATTERNS = [
    # OpenAI-style keys: sk-... format
    (r"\bsk-[A-Za-z0-9_-]{20,}\b", "OpenAI API key format"),
    # Generic api_key in JSON/dict with non-placeholder value (20+ chars)
    (r'"api_key"\s*:\s*"(?!changeme|replace_me|your_key_here|your-key)[^"]{20,}"', "api_key with real value"),
    # Generic token in JSON/dict with non-placeholder value
    (r'"token"\s*:\s*"(?!changeme|replace_me|your_token_here|your-token)[^"]{20,}"', "token with real value"),
    # Generic secret in JSON/dict with non-placeholder value
    (r'"secret"\s*:\s*"(?!changeme|replace_me|your_secret_here|your-secret)[^"]{20,}"', "secret with real value"),
    # OPENAI_API_KEY= with non-placeholder value (env file style)
    (r"OPENAI_API_KEY\s*=\s*(?!changeme|replace_me|your[_-]key|#)[^\s#]{20,}", "OPENAI_API_KEY with real value"),
]

# Placeholders that are explicitly allowed (case-insensitive check)
ALLOWED_PLACEHOLDERS = {
    "changeme",
    "replace_me",
    "your_key_here",
    "your-key",
    "your_token_here",
    "your-token",
    "your_secret_here",
    "your-secret",
    "test-key",
    "fake-key",
    "stub",
}

# Test-specific patterns that are allowed (for test fixtures)
# These patterns indicate obvious test/fake values
TEST_VALUE_PATTERNS = [
    r"sk-super-secret",  # Obvious test pattern
    r"sk-test-",  # Test prefix
    r"sk-fake-",  # Fake prefix
    r"-12345\b",  # Ends with obvious numeric sequence
    r"-67890\b",  # Ends with obvious numeric sequence
    r"svcacct-6-bRj",  # Specific test fixture pattern (short, obvious test value)
]


def _scan_for_forbidden_files() -> list[str]:
    """
    Scan repository root for forbidden files.

    Returns:
        List of forbidden file paths found
    """
    repo_root = Path(__file__).parent.parent
    violations = []

    # Check for exact forbidden files
    for forbidden_file in FORBIDDEN_FILES:
        file_path = repo_root / forbidden_file
        if file_path.exists():
            violations.append(str(file_path.relative_to(repo_root)))

    # Check for forbidden patterns (like *.env)
    for pattern in FORBIDDEN_PATTERNS:
        for file_path in repo_root.glob(pattern):
            relative_path = file_path.relative_to(repo_root)
            # Skip allowed exceptions
            if file_path.name in ALLOWED_ENV_FILES:
                continue
            # Skip if it's a directory
            if file_path.is_dir():
                continue
            violations.append(str(relative_path))

    return sorted(set(violations))


def _scan_for_secrets() -> list[tuple[Path, int, str, str]]:
    """
    Scan repository files for likely secrets.

    Returns:
        List of (file_path, line_number, pattern_name, masked_snippet)
    """
    violations = []

    # Get all text files from repo (excludes v1.reference and binaries)
    scanned_files = scan_repository()

    for file_path, content in scanned_files:
        # Split into lines for line-number tracking
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Check each secret pattern
            for pattern_regex, pattern_name in SECRET_PATTERNS:
                match = re.search(pattern_regex, line, re.IGNORECASE)
                if match:
                    # Extract the matched value
                    matched_value = match.group(0)

                    # Check if it's a known placeholder (case-insensitive)
                    if any(placeholder.lower() in matched_value.lower() for placeholder in ALLOWED_PLACEHOLDERS):
                        continue

                    # Check if it matches obvious test patterns
                    if any(
                        re.search(test_pattern, matched_value, re.IGNORECASE) for test_pattern in TEST_VALUE_PATTERNS
                    ):
                        continue

                    # Mask the matched value for output (never show the actual secret)
                    masked_snippet = _mask_secret(line, match.start(), match.end())

                    violations.append((file_path, line_num, pattern_name, masked_snippet))

    return violations


def _mask_secret(line: str, start: int, end: int) -> str:
    """
    Mask a secret in a line for safe display.

    Args:
        line: Full line containing secret
        start: Start index of secret
        end: End index of secret

    Returns:
        Line with secret replaced by ***
    """
    # Show context before and after, but mask the secret itself
    before = line[:start]
    after = line[end:]

    # Truncate if too long
    if len(before) > 40:
        before = "..." + before[-37:]
    if len(after) > 40:
        after = after[:37] + "..."

    return f"{before}***{after}"


def test_no_forbidden_env_files() -> None:
    """Fail if forbidden environment files exist in repository."""
    violations = _scan_for_forbidden_files()

    if violations:
        msg = (
            "Found forbidden files in repository tree:\n\n" + "\n".join(f"  - {v}" for v in violations) + "\n\n"
            "These files must never be committed:\n"
            "- .env.local contains local secrets\n"
            "- .env may contain secrets\n"
            "- Other *.env files (except .env.example)\n\n"
            "Action: Remove these files and add them to .gitignore if needed.\n"
            "API keys should be stored in /config model JSON files (user-owned volume)."
        )
        raise AssertionError(msg)


def test_no_secrets_in_source_files() -> None:
    """Fail if real-looking secrets are found in source files."""
    violations = _scan_for_secrets()

    if violations:
        msg = "Found likely secrets in repository files:\n\n"

        for file_path, line_num, pattern_name, masked_snippet in violations:
            msg += f"{file_path}:{line_num} - {pattern_name}\n"
            msg += f"  {masked_snippet}\n\n"

        msg += (
            "IMPORTANT: Do not commit real API keys or tokens to the repository.\n\n"
            "API keys should be stored in:\n"
            "  1. /config model JSON files (for persistent configuration)\n"
            "  2. Environment variables (for runtime overrides)\n"
            "  3. User-owned .env.local files (git-ignored, not in repo)\n\n"
            "For placeholder values, use obvious placeholders:\n"
            "  - changeme\n"
            "  - replace_me\n"
            "  - your_key_here\n"
            "  - test-key (for tests only)\n"
        )
        raise AssertionError(msg)


def test_v1_reference_excluded_from_secret_scan() -> None:
    """Regression test: verify v1.reference/ is excluded from secret scanning."""
    scanned_files = scan_repository()

    # Collect all paths that were scanned
    scanned_paths = [str(path).replace("\\", "/") for path, _ in scanned_files]

    # None should contain "v1.reference" as a path segment
    for path in scanned_paths:
        assert "v1.reference" not in path.split("/"), (
            f"ERROR: scan_repository returned path containing v1.reference: {path}\n"
            "The hard exclusion for secret scanning is broken!"
        )


def test_no_pii_in_tracked_files() -> None:
    """User-home paths and personal-domain emails must not reach the repo.

    Until 2026-08-28 this ran only in the pre-commit hook, which is
    bypassable by design (--no-verify, an unset core.hooksPath, a fresh
    clone before the installer runs, a push from another machine). This is
    the CI backstop for the same rule.

    Findings are MASKED in the failure message: a test that prints the PII
    it caught into a public CI log defeats itself.
    """
    offenders: list[str] = []
    for path, content in scan_repository():
        # This file necessarily contains the patterns themselves.
        if path.name == "test_no_secrets_committed.py":
            continue
        for pattern, label in PII_PATTERNS:
            for match in re.finditer(pattern, content):
                text = match.group(0)
                masked = text[:3] + "***" + text[-4:] if len(text) > 8 else "***"
                line_no = content[: match.start()].count(chr(10)) + 1
                offenders.append(f"{path.as_posix()}:{line_no} [{label}] {masked}")

    assert offenders == [], "PII found in tracked files: " + "; ".join(offenders)


# Test vectors are ASSEMBLED, never written as literals.
#
# The pre-commit hook scans staged content textually and cannot tell a
# synthetic fixture from a real leak — it blocked this very file until
# these were split. Concatenating keeps the hook free of exemptions (an
# exemption for "the test file" is one a real leak could later hide
# behind) while the runtime values stay byte-identical to what a genuine
# leak would look like.
_AT = "@"
_SEP = chr(92)  # backslash, kept out of the literal for the same reason

_PII_VECTORS = [
    ("C:" + _SEP + "Users" + _SEP + "someone" + _SEP + "project", True),
    ("/home/" + "someone/project", True),
    ("a.person" + _AT + "gmail.com", True),
    ("someone" + _AT + "outlook.com", True),
    # Negatives that MUST NOT trip. The repo uses noreply emails
    # everywhere and its container paths look superficially like home
    # paths — a pattern flagging either would fail on every commit and be
    # deleted within a day, so these are the load-bearing half.
    ("dev" + _AT + "users.noreply.github.com", False),
    ("/usr/local/bin/python", False),
    ("/data/openchronicle.db", False),
    ("/volume1/docker/openchronicle/config", False),
]


@pytest.mark.parametrize(("text", "should_match"), _PII_VECTORS)
def test_pii_patterns_match_what_they_claim(text: str, should_match: bool) -> None:
    """A guard nobody has seen fire is a guard nobody knows works."""
    hit = any(re.search(pattern, text) for pattern, _ in PII_PATTERNS)
    assert hit is should_match
