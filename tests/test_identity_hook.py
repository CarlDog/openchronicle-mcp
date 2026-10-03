"""The commit hook's identity check: an allowlist, on author AND committer.

Runs the real `.githooks/check-identity-and-pii.sh` in a throwaway repository
with nothing staged, so only the identity step decides the exit code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".githooks" / "check-identity-and-pii.sh"
NOREPLY = "12345+someone@users.noreply.github.com"


def _bash() -> str | None:
    """The bash that runs git hooks: Git for Windows' own on Windows.

    `bash` on a Windows PATH is often WSL's, which cannot see Windows paths
    or the Windows git; Git for Windows ships its bash beside `cmd/git.exe`.
    """
    git = shutil.which("git")
    if git is None:
        return None
    if os.name == "nt":
        candidate = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        return str(candidate) if candidate.is_file() else None
    return shutil.which("bash")


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="needs git and the bash that runs its hooks")


def _run(
    tmp_path: Path, author: str, committer: str, *, override: str | None = None
) -> subprocess.CompletedProcess[str]:
    assert HOOK.is_file(), "premise: the hook exists"
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    global_config = tmp_path / "gitconfig"
    global_config.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": str(global_config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "A",
        "GIT_AUTHOR_EMAIL": author,
        "GIT_COMMITTER_NAME": "C",
        "GIT_COMMITTER_EMAIL": committer,
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    if override is not None:
        subprocess.run(["git", "config", "fleet.allowedIdentityPattern", override], cwd=repo, env=env, check=True)
    assert BASH is not None
    return subprocess.run([BASH, str(HOOK)], cwd=repo, env=env, capture_output=True, text=True, timeout=60)


def test_noreply_author_and_committer_pass(tmp_path: Path) -> None:
    r = _run(tmp_path, NOREPLY, NOREPLY)
    assert r.returncode == 0, r.stderr


def test_a_personal_domain_author_is_blocked(tmp_path: Path) -> None:
    r = _run(tmp_path, "someone" + "@" + "gmail.com", NOREPLY)
    assert r.returncode == 1
    assert "Commit blocked: author identity is not an allowed email" in r.stderr


def test_a_corporate_committer_is_blocked(tmp_path: Path) -> None:
    """The old check was an author-only consumer-domain denylist: a corporate
    committer matched nothing and passed."""
    r = _run(tmp_path, NOREPLY, "someone" + "@" + "corp.example")
    assert r.returncode == 1
    assert "Commit blocked: committer identity is not an allowed email" in r.stderr


def test_a_per_clone_override_admits_another_domain(tmp_path: Path) -> None:
    corp = "someone" + "@" + "corp.example"
    r = _run(tmp_path, corp, corp, override=r"^[A-Za-z0-9._%+-]+@corp\.example$")
    assert r.returncode == 0, r.stderr
