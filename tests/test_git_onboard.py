"""Tests for git onboarding: filter, cluster, synthesize, extract, orchestrate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openchronicle.core.application.services.git_onboard import (
    cluster_commits,
    extract_commits_from_git,
    extract_commits_from_url,
    filter_commits,
    format_cluster_as_raw_memory,
    format_cluster_for_synthesis,
    run_git_onboard,
    synthesize_cluster,
)
from openchronicle.core.domain.models.git_commit import CommitCluster, GitCommit
from openchronicle.core.domain.ports.llm_port import LLMResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_DATE = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _commit(
    subject: str,
    *,
    hours_offset: float = 0,
    files: list[str] | None = None,
    insertions: int = 10,
    deletions: int = 5,
    body: str = "",
) -> GitCommit:
    return GitCommit(
        hash=f"abc{abs(hash(subject)) % 10000:04d}",
        author="dev",
        date=_BASE_DATE + timedelta(hours=hours_offset),
        subject=subject,
        body=body,
        files_changed=files or ["src/main.py"],
        insertions=insertions,
        deletions=deletions,
    )


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


class TestFilterCommits:
    def test_filter_skips_merge_commits(self) -> None:
        commits = [
            _commit("Merge branch 'feature' into main"),
            _commit("Merge pull request #42 from user/branch"),
            _commit("feat: real work"),
        ]
        result = filter_commits(commits)
        assert len(result) == 1
        assert result[0].subject == "feat: real work"

    def test_filter_skips_formatting_only(self) -> None:
        commits = [
            _commit("fmt: fix whitespace"),
            _commit("style: run prettier"),
            _commit("chore: format code"),
            _commit("feat: add feature"),
        ]
        result = filter_commits(commits)
        assert len(result) == 1
        assert result[0].subject == "feat: add feature"

    def test_filter_skips_version_bumps(self) -> None:
        commits = [
            _commit("bump version to 1.2.3"),
            _commit("v1.2.3"),
            _commit("1.2.3"),
            _commit("feat: something real"),
        ]
        result = filter_commits(commits)
        assert len(result) == 1

    def test_filter_skips_empty_diffs(self) -> None:
        commits = [
            _commit("empty commit", insertions=0, deletions=0),
            _commit("real commit", insertions=5, deletions=3),
        ]
        result = filter_commits(commits)
        assert len(result) == 1
        assert result[0].subject == "real commit"

    def test_filter_keeps_real_commits(self) -> None:
        commits = [
            _commit("feat: add auth"),
            _commit("fix: resolve crash"),
            _commit("refactor: split module"),
        ]
        result = filter_commits(commits)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


class TestClusterCommits:
    def test_cluster_by_time_proximity(self) -> None:
        commits = [
            _commit("a", hours_offset=0, files=["f1.py"]),
            _commit("b", hours_offset=1, files=["f1.py"]),
            _commit("c", hours_offset=2, files=["f1.py"]),
        ]
        clusters = cluster_commits(commits, time_window_hours=72)
        assert len(clusters) == 1
        assert len(clusters[0].commits) == 3

    def test_cluster_splits_on_time_gap(self) -> None:
        commits = [
            _commit("a", hours_offset=0, files=["f1.py"]),
            _commit("b", hours_offset=1, files=["f1.py"]),
            _commit("c", hours_offset=100, files=["f2.py"]),
        ]
        clusters = cluster_commits(commits, time_window_hours=72)
        assert len(clusters) == 2

    def test_cluster_merges_by_file_overlap(self) -> None:
        # Two time-separated groups but with overlapping files
        commits = [
            _commit("a", hours_offset=0, files=["src/core.py", "src/utils.py"]),
            _commit("b", hours_offset=1, files=["src/core.py"]),
            _commit("c", hours_offset=100, files=["src/core.py", "src/utils.py"]),
        ]
        clusters = cluster_commits(commits, time_window_hours=72)
        # Jaccard of {src/core.py, src/utils.py} and {src/core.py, src/utils.py} = 1.0 > 0.2
        assert len(clusters) == 1

    def test_cluster_caps_total(self) -> None:
        # Create many well-separated clusters
        commits = [_commit(f"c{i}", hours_offset=i * 200, files=[f"file{i}.py"]) for i in range(20)]
        clusters = cluster_commits(commits, max_clusters=5, time_window_hours=72)
        assert len(clusters) <= 5

    def test_cluster_single_commit(self) -> None:
        commits = [_commit("solo")]
        clusters = cluster_commits(commits)
        assert len(clusters) == 1
        assert len(clusters[0].commits) == 1
        assert clusters[0].time_span_days == 0.0

    def test_cluster_empty_input(self) -> None:
        assert cluster_commits([]) == []

    def test_cluster_label_generation(self) -> None:
        commits = [
            _commit("feat: add thing", files=["src/domain/model.py"]),
            _commit("feat: more stuff", files=["src/domain/port.py"]),
        ]
        clusters = cluster_commits(commits)
        assert len(clusters) == 1
        # Label should contain "src/domain" (common path) and "feat" (common type)
        assert "src/domain" in clusters[0].label
        assert "feat" in clusters[0].label


# ---------------------------------------------------------------------------
# Synthesis / Formatting
# ---------------------------------------------------------------------------


class TestFormatting:
    def test_format_cluster_for_synthesis_truncates(self) -> None:
        long_body = "x" * 1000
        commits = [_commit("big commit", body=long_body)]
        cluster = CommitCluster(commits=commits, label="test")
        result = format_cluster_for_synthesis(cluster)
        # Body should be truncated to 500 chars
        assert len(result) < len(long_body)
        assert "Cluster: test" in result

    def test_format_cluster_as_raw_memory(self) -> None:
        commits = [
            _commit("feat: add auth", hours_offset=0, files=["src/auth.py"]),
            _commit("fix: login bug", hours_offset=1, files=["src/auth.py"]),
        ]
        cluster = CommitCluster(commits=commits, label="auth work")
        result = format_cluster_as_raw_memory(cluster)
        assert "auth work" in result
        assert "feat: add auth" in result
        assert "src/auth.py" in result

    @pytest.mark.asyncio
    async def test_synthesize_cluster_calls_llm(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.complete_async = AsyncMock(
            return_value=LLMResponse(
                content="Synthesized memory about auth changes.",
                provider="stub",
                model="stub-model",
            )
        )
        from openchronicle.core.application.routing.router_policy import RouteDecision

        route = RouteDecision(provider="stub", model="stub-model", mode="fast", reasons=["test"])
        commits = [_commit("feat: add auth")]
        cluster = CommitCluster(commits=commits, label="auth")

        result = await synthesize_cluster(mock_llm, route, cluster)
        assert result == "Synthesized memory about auth changes."
        mock_llm.complete_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_cluster_prompt_content(self) -> None:
        mock_llm = AsyncMock()
        captured_messages: list[Any] = []

        async def capture(*, messages: Any, **kwargs: Any) -> LLMResponse:
            captured_messages.append(messages)
            return LLMResponse(content="ok", provider="stub", model="stub-model")

        mock_llm.complete_async = AsyncMock(side_effect=capture)
        from openchronicle.core.application.routing.router_policy import RouteDecision

        route = RouteDecision(provider="stub", model="stub-model", mode="fast", reasons=["test"])
        commits = [_commit("feat: big change")]
        cluster = CommitCluster(commits=commits, label="big change")

        await synthesize_cluster(mock_llm, route, cluster)
        assert len(captured_messages) == 1
        prompt_text = captured_messages[0][0]["content"]
        assert "WHY" in prompt_text
        assert "big change" in prompt_text


# ---------------------------------------------------------------------------
# Git Extraction
# ---------------------------------------------------------------------------


class TestExtractCommits:
    def test_extract_commits_parses_git_output(self) -> None:
        sep = "---GIT_ONBOARD_SEP---"
        field_sep = "---GIT_ONBOARD_FIELD---"
        git_output = (
            f"{sep}"
            f"abc1234{field_sep}Dev User{field_sep}2026-01-15T12:00:00+00:00{field_sep}feat: add feature{field_sep}Body text\n"
            "10\t5\tsrc/main.py\n"
            "3\t1\tsrc/utils.py\n"
        )
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=git_output, stderr="")
            commits = extract_commits_from_git("/fake/repo")

        assert len(commits) == 1
        assert commits[0].hash == "abc1234"
        assert commits[0].author == "Dev User"
        assert commits[0].subject == "feat: add feature"
        assert commits[0].insertions == 13
        assert commits[0].deletions == 6
        assert commits[0].files_changed == ["src/main.py", "src/utils.py"]

    def test_extract_commits_handles_no_repo(self) -> None:
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository",
            )
            with pytest.raises(RuntimeError, match="Not a git repository"):
                extract_commits_from_git("/fake/path")

    def test_extract_commits_handles_empty_repo(self) -> None:
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            commits = extract_commits_from_git("/fake/repo")
        assert commits == []


class TestExtractCommitsFromUrl:
    """extract_commits_from_url clones into a tmpdir then delegates to the path-based extractor."""

    def test_clone_success_delegates_to_path_extractor(self) -> None:
        # Mock the clone subprocess + the inner extract_commits_from_git that
        # would otherwise re-shell git in the tmpdir.
        with (
            patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
            patch("openchronicle.core.application.services.git_onboard.extract_commits_from_git") as mock_extract,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_extract.return_value = [_commit("feat: x")]

            commits = extract_commits_from_url("https://example.com/repo.git", max_commits=42)

        assert len(commits) == 1
        # Inner extractor got the tmpdir path and the same max/since args
        call_args = mock_extract.call_args
        assert call_args.kwargs.get("max_commits") == 42 or call_args.args[1] == 42
        assert call_args.kwargs.get("since_commit") is None
        # Clone command included --depth (since no since_commit)
        clone_argv = mock_run.call_args[0][0]
        assert "git" in clone_argv[0]
        assert "clone" in clone_argv
        assert "--depth" in clone_argv

    def test_clone_with_since_commit_does_full_clone(self) -> None:
        with (
            patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
            patch("openchronicle.core.application.services.git_onboard.extract_commits_from_git") as mock_extract,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_extract.return_value = []
            extract_commits_from_url("https://example.com/repo.git", max_commits=100, since_commit="abc123")

        clone_argv = mock_run.call_args[0][0]
        # since_commit means the SHA must be reachable, so no --depth
        assert "--depth" not in clone_argv

    def test_clone_failure_raises_runtime_error(self) -> None:
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: repository 'https://example.com/repo.git/' not found",
            )
            with pytest.raises(RuntimeError, match="git clone failed"):
                extract_commits_from_url("https://example.com/repo.git")

    def test_git_not_installed_raises_runtime_error(self) -> None:
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError(2, "No such file or directory: 'git'")
            with pytest.raises(RuntimeError, match="git is not installed"):
                extract_commits_from_url("https://example.com/repo.git")

    def test_token_injects_auth_header_for_github(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OC_GIT_TOKEN set + github.com URL → bearer header in subprocess env."""
        monkeypatch.setenv("OC_GIT_TOKEN", "ghp_test_token_xyz")
        with (
            patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
            patch("openchronicle.core.application.services.git_onboard.extract_commits_from_git") as mock_extract,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_extract.return_value = []
            extract_commits_from_url("https://github.com/CarlDog/private-repo")

        passed_env = mock_run.call_args.kwargs["env"]
        assert "GIT_CONFIG_PARAMETERS" in passed_env
        assert "ghp_test_token_xyz" in passed_env["GIT_CONFIG_PARAMETERS"]
        assert "AUTHORIZATION: bearer" in passed_env["GIT_CONFIG_PARAMETERS"]
        # URL-scoped to github.com, not a global header
        assert "http.https://github.com/.extraheader" in passed_env["GIT_CONFIG_PARAMETERS"]
        # Token must NOT appear in argv (the whole point of using env)
        clone_argv = mock_run.call_args[0][0]
        assert not any("ghp_test_token_xyz" in str(a) for a in clone_argv)

    def test_no_token_no_auth_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No OC_GIT_TOKEN env → no GIT_CONFIG_PARAMETERS injection."""
        monkeypatch.delenv("OC_GIT_TOKEN", raising=False)
        with (
            patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
            patch("openchronicle.core.application.services.git_onboard.extract_commits_from_git") as mock_extract,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_extract.return_value = []
            extract_commits_from_url("https://github.com/CarlDog/repo")

        passed_env = mock_run.call_args.kwargs["env"]
        assert "GIT_CONFIG_PARAMETERS" not in passed_env

    def test_token_only_for_github_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OC_GIT_TOKEN set but non-github URL → no header (token isn't leaked elsewhere)."""
        monkeypatch.setenv("OC_GIT_TOKEN", "ghp_test_token_xyz")
        with (
            patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
            patch("openchronicle.core.application.services.git_onboard.extract_commits_from_git") as mock_extract,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_extract.return_value = []
            extract_commits_from_url("https://gitlab.com/foo/bar")

        passed_env = mock_run.call_args.kwargs["env"]
        assert "GIT_CONFIG_PARAMETERS" not in passed_env


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class TestRunGitOnboard:
    @pytest.mark.asyncio
    async def test_run_git_onboard_saves_memories(self) -> None:
        store = MagicMock()
        emit_event = MagicMock()
        commits = [
            _commit("feat: add auth", hours_offset=0),
            _commit("fix: auth bug", hours_offset=1),
        ]
        memories = await run_git_onboard(
            commits,
            store=store,
            emit_event=emit_event,
            project_id="proj-1",
            max_clusters=5,
        )
        assert len(memories) > 0
        assert store.add_memory.call_count == len(memories)
        for m in memories:
            assert m.source == "git-onboard"
            assert m.project_id == "proj-1"
            assert "git-derived" in m.tags

    @pytest.mark.asyncio
    async def test_run_git_onboard_emits_events(self) -> None:
        store = MagicMock()
        emit_event = MagicMock()
        commits = [_commit("feat: something")]
        await run_git_onboard(
            commits,
            store=store,
            emit_event=emit_event,
            project_id="proj-1",
        )
        event_types = [call.args[0].type for call in emit_event.call_args_list]
        assert "onboard.git.started" in event_types
        assert "onboard.git.completed" in event_types
        assert "memory.written" in event_types

    @pytest.mark.asyncio
    async def test_run_git_onboard_respects_max_memories(self) -> None:
        store = MagicMock()
        emit_event = MagicMock()
        # Create many well-separated commits
        commits = [_commit(f"feat: thing {i}", hours_offset=i * 200, files=[f"file{i}.py"]) for i in range(20)]
        memories = await run_git_onboard(
            commits,
            store=store,
            emit_event=emit_event,
            project_id="proj-1",
            max_clusters=3,
        )
        assert len(memories) <= 3

    @pytest.mark.asyncio
    async def test_run_git_onboard_no_llm_fallback(self) -> None:
        store = MagicMock()
        emit_event = MagicMock()
        commits = [_commit("feat: add thing")]
        memories = await run_git_onboard(
            commits,
            llm=None,
            route_decision=None,
            store=store,
            emit_event=emit_event,
            project_id="proj-1",
        )
        assert len(memories) == 1
        # Raw format should contain the commit subject
        assert "feat: add thing" in memories[0].content


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_list_memory_by_source(self, tmp_path: Path) -> None:
        from openchronicle.core.domain.models.memory_item import MemoryItem
        from openchronicle.core.domain.models.project import Project
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        db_path = tmp_path / "test.db"
        store = SqliteStore(str(db_path))
        store.init_schema()
        store.add_project(Project(id="proj-1", name="test"))

        # Add a git-onboard memory
        item = MemoryItem(
            content="test memory",
            tags=["git-derived"],
            source="git-onboard",
            project_id="proj-1",
        )
        store.add_memory(item)

        # Add a non-git-onboard memory
        other = MemoryItem(content="other", source="manual", project_id="proj-1")
        store.add_memory(other)

        result = store.list_memory_by_source("git-onboard", "proj-1")
        assert len(result) == 1
        assert result[0].source == "git-onboard"

    def test_list_memory_by_source_empty(self, tmp_path: Path) -> None:
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        db_path = tmp_path / "test.db"
        store = SqliteStore(str(db_path))
        store.init_schema()

        result = store.list_memory_by_source("git-onboard", "proj-1")
        assert result == []


# ---------------------------------------------------------------------------
# MCP Tool
# ---------------------------------------------------------------------------


class TestMCPOnboardGit:
    def test_onboard_git_returns_clusters(self) -> None:
        from openchronicle.interfaces.mcp.tools.onboard import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        # Set up container mock
        container = MagicMock()
        container.storage.get_project.return_value = MagicMock()
        # No existing memories, no watermark → fresh run
        container.storage.list_memory_by_source.return_value = []
        container.event_logger.append = MagicMock()

        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        with patch("openchronicle.interfaces.mcp.tools.onboard.extract_commits_from_url") as mock_extract:
            mock_extract.return_value = [
                _commit("feat: add auth", files=["src/auth.py"]),
                _commit("feat: add login", hours_offset=1, files=["src/auth.py"]),
            ]
            result = registered["onboard_git"](
                project_id="proj-1",
                repo_url="https://example.com/test/repo.git",
                ctx=ctx,
            )

        assert "clusters" in result
        assert result["cluster_count"] > 0
        assert result["commit_count"] > 0
        assert "instructions" in result
        # Watermark should have been saved
        container.storage.delete_memory.assert_not_called()  # no old watermark to delete

    def test_onboard_git_idempotency(self) -> None:
        from openchronicle.interfaces.mcp.tools.onboard import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        container = MagicMock()
        container.storage.get_project.return_value = MagicMock()
        # Existing memories but no watermark → pre-incremental state
        container.storage.list_memory_by_source.side_effect = lambda source, pid: (
            [MagicMock()] if source == "git-onboard" else []
        )

        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        result = registered["onboard_git"](
            project_id="proj-1",
            repo_url="https://example.com/test/repo.git",
            ctx=ctx,
        )
        assert "error" in result
        assert result["existing_count"] == 1


class TestIncrementalOnboard:
    """Tests for incremental onboard_git with watermark tracking."""

    def test_extract_with_since_commit(self) -> None:
        """extract_commits_from_git with since_commit uses git range syntax."""
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            extract_commits_from_git("/tmp/repo", max_commits=100, since_commit="abc123")

        cmd = mock_run.call_args[0][0]
        assert "abc123..HEAD" in cmd

    def test_extract_without_since_commit(self) -> None:
        """extract_commits_from_git without since_commit has no range."""
        with patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            extract_commits_from_git("/tmp/repo", max_commits=100)

        cmd = mock_run.call_args[0][0]
        assert not any("..HEAD" in str(arg) for arg in cmd)

    def test_save_watermark(self, tmp_path: Path) -> None:
        """save_watermark creates a memory with the latest commit hash."""
        from openchronicle.core.application.services.git_onboard import save_watermark
        from openchronicle.core.domain.models.project import Project
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        db_path = tmp_path / "test.db"
        store = SqliteStore(str(db_path))
        store.init_schema()
        store.add_project(Project(id="proj-1", name="test"))

        save_watermark(store, "proj-1", "abc123def")

        wms = store.list_memory_by_source("git-onboard-watermark", "proj-1")
        assert len(wms) == 1
        assert wms[0].content == "abc123def"

    def test_save_watermark_replaces_existing(self, tmp_path: Path) -> None:
        """save_watermark replaces old watermark."""
        from openchronicle.core.application.services.git_onboard import save_watermark
        from openchronicle.core.domain.models.project import Project
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        db_path = tmp_path / "test.db"
        store = SqliteStore(str(db_path))
        store.init_schema()
        store.add_project(Project(id="proj-1", name="test"))

        save_watermark(store, "proj-1", "first_hash")
        save_watermark(store, "proj-1", "second_hash")

        wms = store.list_memory_by_source("git-onboard-watermark", "proj-1")
        assert len(wms) == 1
        assert wms[0].content == "second_hash"

    def test_mcp_incremental_uses_watermark(self) -> None:
        """MCP onboard_git passes watermark hash to extract_commits."""
        from openchronicle.interfaces.mcp.tools.onboard import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        wm_item = MagicMock()
        wm_item.content = "abc123"

        container = MagicMock()
        container.storage.get_project.return_value = MagicMock()
        container.storage.list_memory_by_source.side_effect = lambda source, pid: (
            [] if source == "git-onboard" else [wm_item]
        )
        container.event_logger.append = MagicMock()

        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        with patch("openchronicle.interfaces.mcp.tools.onboard.extract_commits_from_url") as mock_extract:
            mock_extract.return_value = [
                _commit("feat: new stuff", files=["src/new.py"]),
            ]
            result = registered["onboard_git"](
                project_id="proj-1",
                repo_url="https://example.com/test/repo.git",
                ctx=ctx,
            )

        mock_extract.assert_called_once_with("https://example.com/test/repo.git", 500, since_commit="abc123")
        assert result["incremental"] is True

    def test_mcp_no_new_commits_returns_up_to_date(self) -> None:
        """When watermark exists but no new commits, return up_to_date."""
        from openchronicle.interfaces.mcp.tools.onboard import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        wm_item = MagicMock()
        wm_item.content = "abc123"

        container = MagicMock()
        container.storage.get_project.return_value = MagicMock()
        container.storage.list_memory_by_source.side_effect = lambda source, pid: (
            [] if source == "git-onboard" else [wm_item]
        )

        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        with patch("openchronicle.interfaces.mcp.tools.onboard.extract_commits_from_url") as mock_extract:
            mock_extract.return_value = []
            result = registered["onboard_git"](
                project_id="proj-1",
                repo_url="https://example.com/test/repo.git",
                ctx=ctx,
            )

        assert result["status"] == "up_to_date"
        assert result["watermark"] == "abc123"

    def test_mcp_force_deletes_watermark_and_memories(self) -> None:
        """force=True deletes existing memories and watermark."""
        from openchronicle.interfaces.mcp.tools.onboard import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        mem_item = MagicMock()
        mem_item.id = "mem-1"
        wm_item = MagicMock()
        wm_item.id = "wm-1"
        wm_item.content = "old_hash"

        container = MagicMock()
        container.storage.get_project.return_value = MagicMock()
        container.storage.list_memory_by_source.side_effect = lambda source, pid: (
            [mem_item] if source == "git-onboard" else [wm_item]
        )
        container.event_logger.append = MagicMock()

        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        with patch("openchronicle.interfaces.mcp.tools.onboard.extract_commits_from_url") as mock_extract:
            mock_extract.return_value = [
                _commit("feat: fresh", files=["src/fresh.py"]),
            ]
            result = registered["onboard_git"](
                project_id="proj-1",
                repo_url="https://example.com/test/repo.git",
                ctx=ctx,
                force=True,
            )

        # Both memory and watermark should have been deleted
        delete_calls = [c[0][0] for c in container.storage.delete_memory.call_args_list]
        assert "mem-1" in delete_calls
        assert "wm-1" in delete_calls
        # Fresh run (no watermark after force)
        mock_extract.assert_called_once_with("https://example.com/test/repo.git", 500, since_commit=None)
        assert result["incremental"] is False
