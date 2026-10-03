"""Test helper: build real git repositories that nothing else can reach.

Shared by the CLI smoke tests and the git-onboard tests.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

IDENTITY = ["-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid"]


def hermetic_git_env(scratch: Path) -> dict[str, str]:
    """An environment in which git sees only the fixture repository.

    Two leaks broke the CLI smoke tests on 2026-09-23:

    - Under a git hook (the pre-commit framework runs this suite), git exports
      ``GIT_DIR`` and ``GIT_INDEX_FILE``. In a linked worktree ``GIT_DIR`` is
      absolute, so an inherited ``git init <tmp>`` reinitialized the REAL
      repository and flipped its ``core.bare`` to true.
    - The developer's global ``init.templateDir`` copied a real pre-commit
      hook (the fleet identity allowlist) into the fixture, and that hook
      rejected the fixture's commits.

    So drop every inherited ``GIT_*`` variable and read no global or system
    config.
    """
    empty_config = scratch / "empty.gitconfig"
    empty_config.write_text("", encoding="utf-8")
    env = {name: value for name, value in os.environ.items() if not name.upper().startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = str(empty_config)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def make_git_repo(path: Path, subjects: list[str]) -> None:
    """Create a repository at ``path`` with one commit per subject."""
    env = hermetic_git_env(path.parent)
    subprocess.run(["git", "init", "-q", "--template=", str(path)], check=True, env=env)
    for n, subject in enumerate(subjects):
        (path / f"file{n}.py").write_text(f"print({n})\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
        subprocess.run(["git", "-C", str(path), *IDENTITY, "commit", "-q", "-m", subject], check=True, env=env)
