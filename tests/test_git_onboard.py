"""Tests for the git-onboard service.

Covers the drift-prone pure logic (filtering, agglomerative clustering,
label generation, numstat/body parsing) and the security-sensitive
bits: the OC_GIT_TOKEN host-scoping in _build_clone_env and the
repo-URL transport allowlist. Subprocess I/O is mock-boundaried so
these stay fast and git-free.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openchronicle.core.application.services.git_onboard import (
    _build_clone_env,
    _generate_label,
    _jaccard,
    _redact_url,
    _validate_repo_url,
    cluster_commits,
    extract_commits_from_git,
    extract_commits_from_url,
    filter_commits,
)
from openchronicle.core.domain.models.git_commit import CommitCluster, GitCommit

_SEP = "---GIT_ONBOARD_SEP---"
_FSEP = "---GIT_ONBOARD_FIELD---"
_BODYEND = "---GIT_ONBOARD_BODYEND---"


def _commit(
    subject: str,
    *,
    hash: str = "abc123",
    when: datetime | None = None,
    files: list[str] | None = None,
    ins: int = 5,
    dels: int = 1,
    body: str = "",
) -> GitCommit:
    return GitCommit(
        hash=hash,
        author="Alice",
        date=when or datetime(2026, 1, 1, tzinfo=UTC),
        subject=subject,
        body=body,
        files_changed=files or ["src/foo.py"],
        insertions=ins,
        deletions=dels,
    )


# ── filter_commits ────────────────────────────────────────────────


def test_filter_removes_merge_format_versionbump_and_empty() -> None:
    commits = [
        _commit("Merge branch 'main' into dev"),
        _commit("fmt: reformat"),
        _commit("chore: format everything"),
        _commit("bump version to 1.2.3"),
        _commit("v1.2.3"),
        _commit("noise", ins=0, dels=0),  # empty diff
        _commit("feat: real change"),
    ]
    kept = filter_commits(commits)
    assert [c.subject for c in kept] == ["feat: real change"]


# ── clustering ────────────────────────────────────────────────────


def test_jaccard_basic() -> None:
    assert _jaccard(set(), set()) == 0.0
    assert _jaccard({"a"}, {"a"}) == 1.0
    assert _jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_cluster_splits_on_time_window() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    commits = [
        _commit("a", hash="1", when=base, files=["x.py"]),
        _commit("b", hash="2", when=base + timedelta(hours=1), files=["x.py"]),
        # 100h gap and disjoint files → new cluster
        _commit("c", hash="3", when=base + timedelta(hours=100), files=["y.py"]),
    ]
    clusters = cluster_commits(commits, time_window_hours=72.0)
    assert len(clusters) == 2
    assert {c.hash for c in clusters[0].commits} == {"1", "2"}
    assert {c.hash for c in clusters[1].commits} == {"3"}


def test_cluster_merges_adjacent_groups_by_file_overlap() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    commits = [
        _commit("a", hash="1", when=base, files=["shared.py", "a.py"]),
        # outside the time window but heavy file overlap → merged in pass 2
        _commit("b", hash="2", when=base + timedelta(hours=200), files=["shared.py", "b.py"]),
    ]
    clusters = cluster_commits(commits, time_window_hours=72.0)
    assert len(clusters) == 1
    assert {c.hash for c in clusters[0].commits} == {"1", "2"}


def test_cluster_respects_max_clusters_cap() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    commits = [
        _commit(f"c{i}", hash=str(i), when=base + timedelta(hours=200 * i), files=[f"f{i}.py"]) for i in range(6)
    ]
    clusters = cluster_commits(commits, max_clusters=3)
    assert len(clusters) <= 3
    # No commits dropped by the cap-merge loop.
    assert sum(len(c.commits) for c in clusters) == 6


@pytest.mark.parametrize("max_clusters", [0, -1])
def test_non_positive_max_clusters_terminates(max_clusters: int) -> None:
    """A cap of 0 or less used to hang forever, not raise.

    Once the merge loop reduced `merged` to one entry, `smallest_idx` was 0
    and the `len(merged) > 1` arm was false, so `merge_into` was also 0 —
    the pop was skipped, no state changed, and `1 > 0` kept the loop alive.

    It was reachable from outside: the `onboard_git` MCP tool accepted
    `max_clusters` unbounded (its neighbour `max_commits_per_cluster` was
    clamped, this one was not), as did `oc onboard git --max-memories`. An
    agent passing 0 would wedge a worker thread permanently.

    Clamped rather than rejected: the value is a cap, and one nonsensical
    cap should degrade to a single cluster, not fail the onboarding run.
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    commits = [
        _commit(f"c{i}", hash=str(i), when=base + timedelta(hours=200 * i), files=[f"f{i}.py"]) for i in range(4)
    ]

    # Run in a worker with a join timeout rather than calling directly: if the
    # guard is ever removed, this fails in seconds with a clear message instead
    # of hanging the whole suite, which is how a regression here would present.
    #
    # Kept to two cases with a short join deliberately. A regression leaves the
    # daemon spinning in a tight Python loop, and several of those starve the
    # GIL badly enough to bury the very assertion message this exists to show —
    # measured, not guessed. Two cases cover the branch (zero and negative);
    # more would only make the failure harder to read.
    result: list[list[CommitCluster]] = []
    worker = threading.Thread(target=lambda: result.append(cluster_commits(commits, max_clusters=max_clusters)))
    worker.daemon = True
    worker.start()
    worker.join(timeout=5.0)

    assert not worker.is_alive(), f"cluster_commits did not terminate for max_clusters={max_clusters}"
    assert len(result) == 1
    clusters = result[0]

    assert len(clusters) == 1, "a non-positive cap floors to one cluster"
    assert sum(len(c.commits) for c in clusters) == 4, "no commit may be dropped"


def test_generate_label_from_paths_and_subject_type() -> None:
    commits = [
        _commit("feat: x", files=["src/api/a.py"]),
        _commit("feat: y", files=["src/api/b.py"]),
    ]
    label = _generate_label(commits)
    assert "src/api" in label
    assert "feat" in label


# ── numstat / multi-line body parsing (the #3 regression) ──────────


def _fake_log_output(entries: list[str]) -> str:
    return "".join(entries)


def _entry(hash: str, subject: str, body: str, numstat: list[str]) -> str:
    header = _FSEP.join([hash, "Alice", "2026-01-01T00:00:00+00:00", subject, body])
    return f"{_SEP}{header}{_BODYEND}\n" + "\n".join(numstat) + "\n"


def _run_extract(stdout: str) -> list[GitCommit]:
    fake = SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    with patch("openchronicle.core.application.services.git_onboard.subprocess.run", return_value=fake):
        return extract_commits_from_git("/fake/repo")


def test_extract_captures_full_multiline_body() -> None:
    body = "First line of the why.\nSecond line with detail.\nThird line."
    out = _fake_log_output([_entry("h1", "feat: thing", body, ["10\t2\tsrc/foo.py"])])
    commits = _run_extract(out)
    assert len(commits) == 1
    # The whole body survives — not just its first line.
    assert commits[0].body == body
    assert commits[0].insertions == 10
    assert commits[0].deletions == 2
    assert commits[0].files_changed == ["src/foo.py"]


def test_extract_multiline_body_does_not_pollute_numstat() -> None:
    # A body line that looks numstat-ish ("3   1  file") must NOT be counted
    # as a file change — it lives before the body sentinel.
    body = "Refactor.\n3\t1\tphantom.py"
    out = _fake_log_output([_entry("h1", "refactor: x", body, ["5\t5\tsrc/real.py"])])
    commits = _run_extract(out)
    assert commits[0].files_changed == ["src/real.py"]
    assert commits[0].insertions == 5
    assert commits[0].deletions == 5


def test_extract_counts_binary_numstat_rows() -> None:
    out = _fake_log_output([_entry("h1", "feat: img", "", ["10\t0\tsrc/a.py", "-\t-\tassets/logo.png"])])
    commits = _run_extract(out)
    assert commits[0].files_changed == ["src/a.py", "assets/logo.png"]
    assert commits[0].insertions == 10
    assert commits[0].deletions == 0


def test_extract_handles_multiple_commits() -> None:
    out = _fake_log_output(
        [
            _entry("h1", "feat: a", "body a\nline2", ["1\t0\ta.py"]),
            _entry("h2", "feat: b", "body b", ["2\t3\tb.py"]),
        ]
    )
    commits = _run_extract(out)
    assert [c.hash for c in commits] == ["h1", "h2"]
    assert commits[0].body == "body a\nline2"
    assert commits[1].body == "body b"


# ── _build_clone_env token host-scoping (security boundary) ────────


def test_clone_env_no_token_leaves_env_unmodified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_GIT_TOKEN", raising=False)
    env = _build_clone_env("https://github.com/CarlDog/openchronicle-mcp")
    assert "GIT_CONFIG_PARAMETERS" not in env


def test_clone_env_injects_host_scoped_header_for_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_GIT_TOKEN", "ghp_secrettoken")
    env = _build_clone_env("https://github.com/CarlDog/openchronicle-mcp")
    params = env["GIT_CONFIG_PARAMETERS"]
    # Header is scoped to github.com specifically, not a bare extraheader.
    assert "http.https://github.com/.extraheader=" in params
    # The raw token is never on the wire in plaintext — it's base64 in Basic auth.
    assert "ghp_secrettoken" not in params
    assert "Basic " in params


def test_clone_env_does_not_inject_token_for_non_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_GIT_TOKEN", "ghp_secrettoken")
    for url in (
        "https://gitlab.com/foo/bar",
        "https://evil.example.com/github.com/foo",  # not a github.com host
        "ssh://git@github.com/foo/bar",  # ssh carries no http header anyway
    ):
        env = _build_clone_env(url)
        assert "GIT_CONFIG_PARAMETERS" not in env, f"token leaked for {url}"


# ── repo URL transport allowlist (#4) ─────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/CarlDog/openchronicle-mcp",
        "https://gitlab.com/foo/bar.git",
        "ssh://git@github.com/foo/bar.git",
        "git@github.com:CarlDog/openchronicle-mcp.git",
    ],
)
def test_validate_accepts_clone_urls(url: str) -> None:
    _validate_repo_url(url)  # must not raise


@pytest.mark.parametrize(
    "url",
    [
        "ext::sh -c 'touch /tmp/pwned'",
        "fd::17/foo",
        "file:///etc/passwd",
        "/local/path/repo",
        "--upload-pack=touch /tmp/x",
        "-oProxyCommand=evil",
        "",
    ],
)
def test_validate_rejects_dangerous_urls(url: str) -> None:
    with pytest.raises(RuntimeError, match="Unsupported repo URL"):
        _validate_repo_url(url)


def test_extract_from_url_rejects_ext_transport_before_clone() -> None:
    with (
        patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
        pytest.raises(RuntimeError, match="Unsupported repo URL"),
    ):
        extract_commits_from_url("ext::sh -c 'evil'")
    mock_run.assert_not_called()


def test_redact_url_strips_embedded_credentials() -> None:
    assert _redact_url("https://x:ghp_secret@github.com/foo/bar") == "https://github.com/foo/bar"
    assert _redact_url("https://github.com/foo/bar") == "https://github.com/foo/bar"


def test_clone_command_uses_end_of_options_guard() -> None:
    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], **_kw: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    with (
        patch("openchronicle.core.application.services.git_onboard.subprocess.run", side_effect=_fake_run),
        pytest.raises(RuntimeError, match="git clone failed"),
    ):
        extract_commits_from_url("https://github.com/foo/bar")

    cmd = captured["cmd"]
    assert "--" in cmd
    # repo_url comes after the -- guard
    assert cmd.index("--") < cmd.index("https://github.com/foo/bar")


def test_clone_command_includes_branch_flag() -> None:
    captured: dict[str, list[str]] = {}

    def _fake_run(cmd: list[str], **_kw: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    with (
        patch("openchronicle.core.application.services.git_onboard.subprocess.run", side_effect=_fake_run),
        pytest.raises(RuntimeError, match="git clone failed"),
    ):
        extract_commits_from_url("https://github.com/foo/bar", branch="develop")

    cmd = captured["cmd"]
    branch_idx = cmd.index("--branch")
    assert cmd[branch_idx + 1] == "develop"
    # branch value stays inside the options section, before the -- guard
    assert branch_idx < cmd.index("--")


@pytest.mark.parametrize("branch", ["-upload-pack=evil", "--evil", ".hidden", "", "a b"])
def test_invalid_branch_rejected_before_clone(branch: str) -> None:
    with (
        patch("openchronicle.core.application.services.git_onboard.subprocess.run") as mock_run,
        pytest.raises(RuntimeError, match="Invalid branch name"),
    ):
        extract_commits_from_url("https://github.com/foo/bar", branch=branch)
    mock_run.assert_not_called()
