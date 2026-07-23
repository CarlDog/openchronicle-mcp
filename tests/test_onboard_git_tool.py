"""Response shape and size of the onboard_git surface.

Nothing tested `onboard_git`'s response before this: the payload was built
inside the MCP tool, so reaching it needed a live MCP context. Moving the
per-cluster construction into `cluster_to_summary` made it a plain
function call, and these are the tests that became possible as a result.

The size assertion is the real guard. The filed complaint was an 86,006
character response on a 491-commit repo; a cap catches a regression that
no shape assertion would.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from openchronicle.core.application.services.git_onboard import (
    cluster_commits,
    cluster_to_summary,
    format_cluster_for_synthesis,
    top_files,
)
from openchronicle.core.domain.models.git_commit import CommitCluster, GitCommit

_START = datetime(2026, 1, 1, tzinfo=UTC)


def _commit(i: int, *, files: list[str] | None = None, churn: int = 10) -> GitCommit:
    return GitCommit(
        hash=f"{i:040x}",
        subject=f"feat: change number {i}",
        body=f"Body for commit {i}. " + ("detail " * 60),
        author="Someone",
        date=_START + timedelta(hours=i),
        files_changed=files if files is not None else [f"src/module_{i % 7}.py"],
        insertions=churn,
        deletions=churn,
    )


def _cluster(count: int, **kw: object) -> CommitCluster:
    commits = [_commit(i, **kw) for i in range(count)]  # type: ignore[arg-type]
    return CommitCluster(commits=commits, label="src — feat", time_span_days=1.0)


class TestFormatClusterBounds:
    def test_respects_max_commits(self) -> None:
        text = format_cluster_for_synthesis(_cluster(50), max_commits=5)
        assert text.count("feat: change number") == 5

    def test_selected_commits_are_listed_chronologically(self) -> None:
        """Dates must ascend down the page.

        Selection is by churn, but presentation is by date. Date-prefixed
        lines in size order read as a timeline that jumps around.
        """
        commits = [_commit(i, churn=100 - i) for i in range(20)]
        cluster = CommitCluster(commits=commits, label="x", time_span_days=1.0)
        text = format_cluster_for_synthesis(cluster, max_commits=10)
        dates = [line.split("]")[0].strip(" [") for line in text.splitlines() if line.strip().startswith("[")]
        assert dates == sorted(dates)

    def test_header_announces_truncation_when_capped(self) -> None:
        text = format_cluster_for_synthesis(_cluster(50), max_commits=10)
        assert "Total commits: 50" in text
        assert "Showing: 10 of 50" in text

    def test_header_omits_truncation_notice_when_complete(self) -> None:
        text = format_cluster_for_synthesis(_cluster(4), max_commits=10)
        assert "Total commits: 4" in text
        assert "Showing:" not in text

    def test_detail_off_omits_body_files_and_diffstat(self) -> None:
        text = format_cluster_for_synthesis(_cluster(3), include_detail=False)
        assert "Files:" not in text
        assert "Body for commit" not in text
        assert "+10/-10" not in text

    def test_detail_on_includes_body_files_and_diffstat(self) -> None:
        text = format_cluster_for_synthesis(_cluster(3), include_detail=True)
        assert "Files:" in text
        assert "Body for commit" in text
        assert "+10/-10" in text

    def test_files_line_reports_overflow_count(self) -> None:
        many = [f"src/f{i}.py" for i in range(25)]
        cluster = CommitCluster(commits=[_commit(0, files=many)], label="x", time_span_days=0.0)
        text = format_cluster_for_synthesis(cluster, include_detail=True)
        assert "(+15 more)" in text


class TestTopFiles:
    def test_ranks_by_touch_count(self) -> None:
        commits = [
            _commit(0, files=["a.py", "b.py"]),
            _commit(1, files=["a.py"]),
            _commit(2, files=["a.py", "c.py"]),
        ]
        cluster = CommitCluster(commits=commits, label="x", time_span_days=0.0)
        assert top_files(cluster)[0] == "a.py"


class TestClusterToSummary:
    def test_reports_shown_versus_total(self) -> None:
        summary = cluster_to_summary(_cluster(50), max_commits=10)
        assert summary["commit_count"] == 50
        assert summary["shown_commit_count"] == 10

    def test_shown_count_never_exceeds_total(self) -> None:
        summary = cluster_to_summary(_cluster(3), max_commits=10)
        assert summary["shown_commit_count"] == 3

    def test_suggested_tags_derive_from_dominant_path(self) -> None:
        commits = [_commit(i, files=["src/billing/x.py"]) for i in range(3)]
        cluster = CommitCluster(commits=commits, label="x", time_span_days=0.0)
        summary = cluster_to_summary(cluster)
        assert summary["suggested_tags"][0] == "git-derived"
        assert "billing" in summary["suggested_tags"]

    def test_date_range_runs_oldest_to_newest(self) -> None:
        summary = cluster_to_summary(_cluster(5))
        start, end = summary["date_range"].split(" to ")
        assert start <= end

    def test_expected_keys(self) -> None:
        assert set(cluster_to_summary(_cluster(3))) == {
            "label",
            "commit_count",
            "shown_commit_count",
            "date_range",
            "created_at",
            "key_files",
            "commits_summary",
            "suggested_tags",
        }


class TestResponseSizeIsBounded:
    def test_large_repo_summary_stays_small(self) -> None:
        """The regression guard for the filed 86,006-character response.

        500 commits across many clusters, rendered at the defaults, must
        stay well inside a usable context budget.
        """
        commits = [_commit(i) for i in range(500)]
        clusters = cluster_commits(commits, max_clusters=15)
        payload = [cluster_to_summary(c) for c in clusters]
        assert len(json.dumps(payload)) < 20_000

    def test_detail_opt_in_is_what_costs(self) -> None:
        commits = [_commit(i) for i in range(500)]
        clusters = cluster_commits(commits, max_clusters=15)
        lean = len(json.dumps([cluster_to_summary(c) for c in clusters]))
        rich = len(json.dumps([cluster_to_summary(c, include_detail=True) for c in clusters]))
        assert rich > lean * 3


class TestWatermark:
    def test_watermark_advances_past_filtered_out_head(self) -> None:
        """The watermark tracks the newest commit WALKED, not the newest kept.

        Merge / format / version-bump commits are filtered out. Anchoring
        the watermark to the surviving set leaves anything newer to be
        re-walked forever — on a repo whose HEAD is a merge, the
        incremental path never advances.
        """
        from unittest.mock import MagicMock, patch

        from openchronicle.core.domain.models.project import Project
        from openchronicle.interfaces.mcp.tools import onboard as onboard_mod

        kept = _commit(0, churn=10)
        # Newer than `kept`, but zero churn so filter_commits drops it.
        dropped_head = _commit(9, churn=0)

        container = MagicMock()
        container.storage.get_project.return_value = Project(id="p1", name="p", metadata={})
        container.storage.list_memory_by_source.return_value = []

        with (
            patch.object(onboard_mod, "extract_commits_from_url", return_value=[kept, dropped_head]),
            patch.object(onboard_mod, "save_watermark") as mock_save,
        ):
            result = onboard_mod._onboard_git_sync(container, "p1", "https://example.com/r.git", 500, 15, False)

        assert mock_save.call_args.args[2] == dropped_head.hash
        assert result["walked_commit_count"] == 2
        assert result["commit_count"] == 1
