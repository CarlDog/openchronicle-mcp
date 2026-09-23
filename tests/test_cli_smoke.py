"""End-to-end smoke pass over the `oc` CLI surface.

2026-08-15 review finding: ~80% of the CLI had no ``main([...])``-level
test — only version/config/db were invoked — and a real compatibility
break (3.14-only syntax) had just landed inside an untested subcommand.
These tests drive a real CoreContainer against a tmp DB through the
same ``_build_container`` patch pattern test_cli_db established.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.main import main


@pytest.fixture()
def container(tmp_path: Path) -> Iterator[CoreContainer]:
    db_path = tmp_path / "smoke.db"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OC_DB_PATH", str(db_path))
    monkeypatch.setenv("OC_CONFIG_DIR", str(config_dir))
    monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
    c = CoreContainer()
    yield c
    monkeypatch.undo()


def _run(container: CoreContainer, argv: list[str]) -> tuple[int, str]:
    with (
        patch("builtins.print") as mock_print,
        patch("openchronicle.interfaces.cli.main._build_container", return_value=container),
    ):
        rc = main(argv)
    out = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
    return rc, out


class TestProjectAndMemoryLifecycle:
    def test_full_lifecycle(self, container: CoreContainer, tmp_path: Path) -> None:
        # Create a project; the bare id on stdout is the scripting contract
        # (README does PROJECT_ID=$(oc init-project ...)).
        rc, out = _run(container, ["init-project", "smoke"])
        assert rc == 0
        project_id = out.strip().splitlines()[-1].strip()
        assert project_id

        rc, out = _run(container, ["list-projects"])
        assert rc == 0
        assert "smoke" in out

        rc, out = _run(container, ["show-project", project_id])
        assert rc == 0

        rc, _ = _run(container, ["update-project", project_id, "--name", "smoke-renamed"])
        assert rc == 0
        rc, out = _run(container, ["show-project", project_id])
        assert "smoke-renamed" in out

        rc, _ = _run(
            container,
            ["memory", "add", "the quick brown fox", "--project-id", project_id, "--tags", "smoke,cli"],
        )
        assert rc == 0
        items = container.storage.list_memory(project_id=project_id)
        assert len(items) == 1
        mem_id = items[0].id

        rc, out = _run(container, ["memory", "list", "--project-id", project_id])
        assert rc == 0
        assert "quick brown fox" in out

        rc, out = _run(container, ["memory", "search", "quick fox", "--project-id", project_id])
        assert rc == 0

        rc, out = _run(container, ["memory", "show", mem_id])
        assert rc == 0
        assert "quick brown fox" in out

        rc, _ = _run(container, ["memory", "pin", mem_id, "--on"])
        assert rc == 0
        pinned_item = container.storage.get_memory(mem_id)
        assert pinned_item is not None
        assert pinned_item.pinned is True

        rc, _ = _run(container, ["memory", "update", mem_id, "--content", "updated smoke content"])
        assert rc == 0
        updated_item = container.storage.get_memory(mem_id)
        assert updated_item is not None
        assert updated_item.content == "updated smoke content"

        # Export before deleting, so import can round-trip it back.
        export_path = tmp_path / "export.json"
        rc, _ = _run(container, ["memory", "export", "--out", str(export_path)])
        assert rc == 0
        assert export_path.exists()

        # Delete preview must not delete (the CLI's never-silent two-step).
        rc, out = _run(container, ["memory", "delete", mem_id])
        assert container.storage.get_memory(mem_id) is not None
        assert "--confirm" in out

        rc, _ = _run(container, ["memory", "delete", mem_id, "--confirm"])
        assert rc == 0
        assert container.storage.get_memory(mem_id) is None

        rc, _ = _run(container, ["memory", "import", str(export_path)])
        assert rc == 0
        assert container.storage.get_memory(mem_id) is not None

        # Project delete: preview leaves it, confirm cascades.
        rc, out = _run(container, ["delete-project", project_id])
        assert container.storage.get_project(project_id) is not None
        rc, _ = _run(container, ["delete-project", project_id, "--confirm"])
        assert rc == 0
        assert container.storage.get_project(project_id) is None
        assert container.storage.list_memory(project_id=project_id) == []


class TestMaintenanceCli:
    def test_list_shows_default_jobs(self, container: CoreContainer) -> None:
        rc, out = _run(container, ["maintenance", "list"])
        assert rc == 0
        assert "db_backup" in out
        assert "db_vacuum" in out


class TestErrorPaths:
    """Missing ids must exit 1 with a printed error, never a traceback."""

    def test_show_project_missing(self, container: CoreContainer) -> None:
        rc, out = _run(container, ["show-project", "nope"])
        assert rc == 1

    def test_memory_show_missing(self, container: CoreContainer) -> None:
        rc, out = _run(container, ["memory", "show", "nope"])
        assert rc == 1

    def test_memory_update_missing(self, container: CoreContainer) -> None:
        rc, out = _run(container, ["memory", "update", "nope", "--content", "x"])
        assert rc == 1

    def test_memory_embed_not_configured_exits_1_with_hint(self, container: CoreContainer) -> None:
        """The CLI treats an unconfigured provider as an error (rc 1) with
        a fix hint — unlike the MCP/REST twins, which return a
        not_configured payload; an operator typing the command is asking
        for something the deployment can't do.
        """
        rc, out = _run(container, ["memory", "embed"])
        assert rc == 1
        assert "OC_EMBEDDING_PROVIDER" in out


def _hermetic_git_env(scratch: Path) -> dict[str, str]:
    """An environment in which git sees only the fixture repository.

    Two leaks broke these tests on 2026-09-23:

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


def _make_git_repo(path: Path) -> None:
    env = _hermetic_git_env(path.parent)
    identity = ["-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid"]
    subprocess.run(["git", "init", "-q", "--template=", str(path)], check=True, env=env)
    (path / "a.py").write_text("print('one')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(path), *identity, "commit", "-q", "-m", "feat: first"], check=True, env=env)
    (path / "b.py").write_text("print('two')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(path), *identity, "commit", "-q", "-m", "feat: second"], check=True, env=env)


@pytest.fixture()
def hermetic_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply ``_hermetic_git_env`` to this process for the CLI's own git calls.

    The onboard CLI runs ``git rev-parse`` and ``git log`` with the inherited
    environment. Under a hook, an inherited ``GIT_DIR`` would make them read
    the real repository instead of the fixture.
    """
    for name in [name for name in os.environ if name.upper().startswith("GIT_")]:
        monkeypatch.delenv(name)
    env = _hermetic_git_env(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", env["GIT_CONFIG_GLOBAL"])
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.mark.usefixtures("hermetic_git")
class TestOnboardGitCli:
    def test_fixture_repo_ignores_a_hostile_git_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins ``_make_git_repo``'s isolation (the 2026-09-23 incident).

        An inherited ``GIT_DIR`` must not reach another repository, and an
        inherited template must not install hooks into the fixture.
        """
        clean = _hermetic_git_env(tmp_path)
        decoy = tmp_path / "decoy"
        subprocess.run(["git", "init", "-q", "--template=", str(decoy)], check=True, env=clean)
        decoy_config = (decoy / ".git" / "config").read_bytes()
        hostile_template = tmp_path / "hostile-template"
        (hostile_template / "hooks").mkdir(parents=True)
        (hostile_template / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (hostile_template / "hooks" / "pre-commit").chmod(0o755)
        monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
        monkeypatch.setenv("GIT_INDEX_FILE", str(decoy / ".git" / "index"))
        monkeypatch.setenv("GIT_TEMPLATE_DIR", str(hostile_template))

        repo = tmp_path / "repo"
        _make_git_repo(repo)

        assert (decoy / ".git" / "config").read_bytes() == decoy_config
        commits = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            env=clean,
        )
        assert commits.stdout.strip() == "2"

    def test_dry_run_previews_without_writing(self, container: CoreContainer, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _make_git_repo(repo)
        rc, out = _run(container, ["init-project", "onboard-smoke"])
        project_id = out.strip().splitlines()[-1].strip()

        rc, out = _run(
            container,
            ["onboard", "git", "--project-id", project_id, "--repo-path", str(repo), "--dry-run"],
        )

        assert rc == 0
        assert "Branch " in out  # the resolved-ref echo
        assert container.storage.list_memory_by_source("git-onboard", project_id) == []
        assert container.storage.list_memory_by_source("git-onboard-watermark", project_id) == []

    def test_full_run_saves_memories_and_watermark_then_goes_incremental(
        self, container: CoreContainer, tmp_path: Path
    ) -> None:
        """The CLI now shares the MCP orchestration: it SAVES a watermark
        (it never did before 2026-08-16) and re-runs are incremental.
        """
        repo = tmp_path / "repo"
        _make_git_repo(repo)
        rc, out = _run(container, ["init-project", "onboard-smoke"])
        project_id = out.strip().splitlines()[-1].strip()

        rc, out = _run(container, ["onboard", "git", "--project-id", project_id, "--repo-path", str(repo)])
        assert rc == 0
        memories = container.storage.list_memory_by_source("git-onboard", project_id)
        assert len(memories) >= 1
        watermarks = container.storage.list_memory_by_source("git-onboard-watermark", project_id)
        assert len(watermarks) == 1

        rc, out = _run(container, ["onboard", "git", "--project-id", project_id, "--repo-path", str(repo)])
        assert rc == 0
        assert "Up to date" in out
