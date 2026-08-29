"""End-to-end smoke pass over the `oc` CLI surface.

2026-08-15 review finding: ~80% of the CLI had no ``main([...])``-level
test — only version/config/db were invoked — and a real compatibility
break (3.14-only syntax) had just landed inside an untested subcommand.
These tests drive a real CoreContainer against a tmp DB through the
same ``_build_container`` patch pattern test_cli_db established.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.main import main


@pytest.fixture(autouse=True)
def _scrub_git_hook_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the git-hook environment for this module.

    When the suite runs under the repo's pre-commit hook, git exports
    repo-pinning variables (GIT_DIR, GIT_INDEX_FILE, ...) that override
    ``git -C <path>`` discovery in every child process — observed from
    a linked worktree's hook run as ``fatal: this operation must be
    run in a work tree`` inside ``_make_git_repo``. The temp-repo
    helpers here (and the CLI's own local-path git calls, which
    inherit ``os.environ``) must operate on THEIR repo, never the one
    being committed.
    """
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
        "GIT_OBJECT_DIRECTORY",
    ):
        monkeypatch.delenv(name, raising=False)


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


def _make_git_repo(path: Path) -> None:
    env_flags = ["-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid"]
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "a.py").write_text("print('one')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), *env_flags, "commit", "-q", "-m", "feat: first"], check=True)
    (path / "b.py").write_text("print('two')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), *env_flags, "commit", "-q", "-m", "feat: second"], check=True)


class TestOnboardGitCli:
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
