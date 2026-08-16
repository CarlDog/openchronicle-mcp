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
from typing import Any

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
    """Watermark policy lives in onboard_git_prepare (shared by MCP + CLI)."""

    @staticmethod
    def _store(watermark: str | None = None) -> Any:
        from unittest.mock import MagicMock

        store = MagicMock()

        def _by_source(source: str, project_id: str | None = None) -> list[object]:
            if source == "git-onboard-watermark" and watermark is not None:
                wm = MagicMock()
                wm.content = watermark
                wm.id = "wm-id"
                return [wm]
            return []

        store.list_memory_by_source.side_effect = _by_source
        return store

    def test_watermark_advances_past_filtered_out_head(self) -> None:
        """The watermark tracks the newest commit WALKED, not the newest kept.

        Merge / format / version-bump commits are filtered out. Anchoring
        the watermark to the surviving set leaves anything newer to be
        re-walked forever — on a repo whose HEAD is a merge, the
        incremental path never advances.
        """
        from unittest.mock import patch

        from openchronicle.core.application.services.git_onboard import (
            ExtractedHistory,
            onboard_git_prepare,
        )

        kept = _commit(0, churn=10)
        # Newer than `kept`, but zero churn so filter_commits drops it.
        dropped_head = _commit(9, churn=0)
        # git log emits ancestry order, newest first.
        history = ExtractedHistory(commits=[dropped_head, kept], branch="main", head=dropped_head.hash)

        with patch("openchronicle.core.application.services.git_onboard.save_watermark") as mock_save:
            prepared = onboard_git_prepare(self._store(), "p1", lambda since: history)

        assert mock_save.call_args.args[2] == dropped_head.hash
        assert prepared.status == "ok"
        assert len(prepared.history.commits) == 2
        assert len(prepared.filtered) == 1

    def test_watermark_is_ancestry_head_not_max_author_date(self) -> None:
        """Regression (2026-08-15 review): the anchor was max(author date).

        Rebased/cherry-picked commits keep old author dates, and one
        future-dated commit would pin a date-anchored watermark to itself
        forever, re-walking everything after it on every run. The newest
        commit WALKED is simply commits[0] — git log is ancestry-ordered.
        """
        from unittest.mock import patch

        from openchronicle.core.application.services.git_onboard import (
            ExtractedHistory,
            onboard_git_prepare,
        )

        # Ancestry head (commits[0]) carries an OLDER author date than a
        # commit deeper in history — the rebase shape.
        ancestry_head = _commit(1, churn=10)  # date: _START + 1h
        future_dated = _commit(30, churn=10)  # date: _START + 30h, but older in ancestry
        history = ExtractedHistory(commits=[ancestry_head, future_dated], branch="main", head=ancestry_head.hash)

        with patch("openchronicle.core.application.services.git_onboard.save_watermark") as mock_save:
            onboard_git_prepare(self._store(), "p1", lambda since: history)

        assert mock_save.call_args.args[2] == ancestry_head.hash

    def test_malformed_watermark_is_ignored_not_executed(self) -> None:
        """The watermark's content is spliced into `git log <hash>..HEAD`
        argv. A watermark memory whose content isn't hash-shaped (imported
        or hand-written under the source tag) must be treated as absent —
        never handed to the extractor.
        """
        from unittest.mock import patch

        from openchronicle.core.application.services.git_onboard import (
            ExtractedHistory,
            onboard_git_prepare,
        )

        seen: list[str | None] = []

        def _extract(since: str | None) -> ExtractedHistory:
            seen.append(since)
            return ExtractedHistory(commits=[_commit(0)], branch="main", head="h")

        with patch("openchronicle.core.application.services.git_onboard.save_watermark"):
            prepared = onboard_git_prepare(self._store(watermark="--upload-pack=evil"), "p1", _extract)

        assert seen == [None]
        assert prepared.status == "ok"

    def test_force_wipes_memories_and_watermark(self) -> None:
        """--force / force=true must wipe BOTH sources. The CLI's old
        hand-rolled sibling wiped git-onboard memories but left the
        watermark, so a later run resumed from deleted state.
        """
        from unittest.mock import MagicMock, patch

        from openchronicle.core.application.services.git_onboard import (
            ExtractedHistory,
            onboard_git_prepare,
        )

        store: Any = MagicMock()
        mem = MagicMock()
        mem.id = "mem-id"
        wm = MagicMock()
        wm.id = "wm-id"
        wm.content = "a" * 40
        store.list_memory_by_source.side_effect = lambda source, project_id=None: (
            [mem] if source == "git-onboard" else [wm]
        )
        history = ExtractedHistory(commits=[_commit(0)], branch="main", head="h")

        with patch("openchronicle.core.application.services.git_onboard.save_watermark"):
            onboard_git_prepare(store, "p1", lambda since: history, force=True)

        deleted = {c.args[0] for c in store.delete_memory.call_args_list}
        assert deleted == {"mem-id", "wm-id"}

    def test_incremental_flag_is_false_after_unreachable_recovery(self) -> None:
        from unittest.mock import patch

        from openchronicle.core.application.services.git_onboard import (
            ExtractedHistory,
            onboard_git_prepare,
        )

        history = ExtractedHistory(
            commits=[_commit(0)],
            branch="main",
            head="h",
            watermark_unreachable=True,
        )

        with patch("openchronicle.core.application.services.git_onboard.save_watermark"):
            prepared = onboard_git_prepare(self._store(watermark="b" * 40), "p1", lambda since: history)

        assert prepared.watermark_before == "b" * 40
        assert prepared.incremental is False


class TestUnreachableWatermarkRecovery:
    def test_falls_back_to_full_walk(self) -> None:
        """Three live occurrences: the raw 'Invalid revision range' error
        gave no recovery path short of force=true, which wipes every
        git-derived memory. Recovery keeps them and re-walks.
        """
        from unittest.mock import patch

        from openchronicle.core.application.services.git_onboard import _extract_with_recovery

        calls: list[str | None] = []

        def _fake_extract(repo_path: str, max_commits: int = 500, since_commit: str | None = None) -> list[GitCommit]:
            calls.append(since_commit)
            if since_commit is not None:
                raise RuntimeError("git log failed: fatal: Invalid revision range abc123..HEAD")
            return [_commit(0)]

        with patch(
            "openchronicle.core.application.services.git_onboard.extract_commits_from_git",
            side_effect=_fake_extract,
        ):
            commits, unreachable = _extract_with_recovery("/repo", 500, "abc123" + "0" * 34)

        assert calls == ["abc123" + "0" * 34, None]
        assert unreachable is True
        assert len(commits) == 1

    def test_other_errors_are_not_swallowed(self) -> None:
        from unittest.mock import patch

        import pytest

        from openchronicle.core.application.services.git_onboard import _extract_with_recovery

        with (
            patch(
                "openchronicle.core.application.services.git_onboard.extract_commits_from_git",
                side_effect=RuntimeError("git log timed out after 60 seconds"),
            ),
            pytest.raises(RuntimeError, match="timed out"),
        ):
            _extract_with_recovery("/repo", 500, "a" * 40)


class TestMcpResponseSurface:
    def test_response_carries_ref_echo_and_recovery_flags(self) -> None:
        """The gemini mis-onboarding was undiagnosable because nothing said
        which ref was walked. branch/head are echoed on every response;
        recovery runs additionally flag watermark_unreachable and warn
        about duplicate suggestions in the instructions.
        """
        from unittest.mock import MagicMock, patch

        from openchronicle.core.application.services.git_onboard import ExtractedHistory
        from openchronicle.core.domain.models.project import Project
        from openchronicle.interfaces.mcp.tools import onboard as onboard_mod

        container = MagicMock()
        container.storage.get_project.return_value = Project(id="p1", name="p", metadata={})
        wm = MagicMock()
        wm.content = "c" * 40
        wm.id = "wm-id"
        container.storage.list_memory_by_source.side_effect = lambda source, project_id=None: (
            [wm] if source == "git-onboard-watermark" else []
        )

        history = ExtractedHistory(
            commits=[_commit(0)],
            branch="develop",
            head="d" * 40,
            watermark_unreachable=True,
        )
        with (
            patch.object(onboard_mod, "extract_commits_from_url", return_value=history),
            patch("openchronicle.core.application.services.git_onboard.save_watermark"),
        ):
            result = onboard_mod._onboard_git_sync(container, "p1", "https://example.com/r.git", 500, 15, False)

        assert result["branch"] == "develop"
        assert result["head"] == "d" * 40
        assert result["watermark_unreachable"] is True
        assert result["ran_full_walk"] is True
        assert result["incremental"] is False
        assert "full re-walk" in result["instructions"]
