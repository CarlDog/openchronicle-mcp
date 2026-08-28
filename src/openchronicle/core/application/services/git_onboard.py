"""Git onboarding service — extract, filter, and cluster git history into memories.

Pure functions for filtering and clustering; git extraction is isolated behind
subprocess boundaries and easily mockable. v3 has no LLM: the MCP tool returns
clusters and the calling agent synthesizes the memory prose, while the CLI seeds
raw-format memories directly.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openchronicle.core.domain.models.git_commit import CommitCluster, GitCommit
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.time_utils import utc_now

_logger = logging.getLogger(__name__)

# --- Filtering ---

_MERGE_PATTERN = re.compile(r"^Merge (branch|pull request|remote-tracking)", re.IGNORECASE)
_FORMAT_PATTERN = re.compile(r"^(fmt|style|chore:\s*format)", re.IGNORECASE)
_VERSION_BUMP_PATTERN = re.compile(r"^(bump version|v?\d+\.\d+\.\d+$)", re.IGNORECASE)


def filter_commits(commits: list[GitCommit]) -> list[GitCommit]:
    """Remove merge, formatting, version-bump, and empty-diff commits."""
    result = []
    for c in commits:
        if _MERGE_PATTERN.match(c.subject):
            continue
        if _FORMAT_PATTERN.match(c.subject):
            continue
        if _VERSION_BUMP_PATTERN.match(c.subject):
            continue
        if c.insertions == 0 and c.deletions == 0:
            continue
        result.append(c)
    return result


# --- Clustering ---


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def cluster_commits(
    commits: list[GitCommit],
    *,
    max_clusters: int = 15,
    time_window_hours: float = 72.0,
) -> list[CommitCluster]:
    """Two-pass agglomerative clustering: time proximity, then file-overlap merge."""
    if not commits:
        return []

    # Sort chronologically
    sorted_commits = sorted(commits, key=lambda c: c.date)

    # Pass 1: time grouping
    groups: list[list[GitCommit]] = [[sorted_commits[0]]]
    for commit in sorted_commits[1:]:
        prev = groups[-1][-1]
        gap_hours = (commit.date - prev.date).total_seconds() / 3600
        if gap_hours > time_window_hours:
            groups.append([commit])
        else:
            groups[-1].append(commit)

    # Pass 2: file-overlap merge of adjacent groups
    merged: list[list[GitCommit]] = [groups[0]]
    for group in groups[1:]:
        prev_files = {f for c in merged[-1] for f in c.files_changed}
        curr_files = {f for c in group for f in c.files_changed}
        if _jaccard(prev_files, curr_files) > 0.2:
            merged[-1].extend(group)
        else:
            merged.append(group)

    # Cap total: merge smallest into nearest temporal neighbor
    while len(merged) > max_clusters:
        # Find smallest cluster
        smallest_idx = min(range(len(merged)), key=lambda i: len(merged[i]))
        merge_into = smallest_idx - 1 if smallest_idx > 0 else 1 if len(merged) > 1 else 0
        if merge_into != smallest_idx:
            merged[merge_into].extend(merged.pop(smallest_idx))

    # Build CommitCluster objects
    clusters = []
    for group in merged:
        sorted_group = sorted(group, key=lambda c: c.date)
        span_days = (sorted_group[-1].date - sorted_group[0].date).total_seconds() / 86400
        label = _generate_label(sorted_group)
        clusters.append(CommitCluster(commits=sorted_group, label=label, time_span_days=span_days))

    return clusters


def _generate_label(commits: list[GitCommit]) -> str:
    """Generate a cluster label from common path prefixes and subject prefixes."""
    # Collect path prefixes (first two path segments)
    path_parts: list[str] = []
    for c in commits:
        for f in c.files_changed:
            parts = f.replace("\\", "/").split("/")
            if len(parts) >= 2:
                path_parts.append(f"{parts[0]}/{parts[1]}")
            elif parts:
                path_parts.append(parts[0])

    # Collect subject prefixes (conventional commit type)
    subject_types: list[str] = []
    for c in commits:
        match = re.match(r"^(\w+)[\(:]", c.subject)
        if match:
            subject_types.append(match.group(1).lower())

    # Build label from most common elements
    label_parts = []
    if path_parts:
        most_common_path = Counter(path_parts).most_common(1)[0][0]
        label_parts.append(most_common_path)
    if subject_types:
        most_common_type = Counter(subject_types).most_common(1)[0][0]
        label_parts.append(most_common_type)

    return " — ".join(label_parts) if label_parts else f"{len(commits)} commits"


# --- Formatting ---


def top_files(cluster: CommitCluster, limit: int = 10) -> list[str]:
    """Files in the cluster ranked by how many of its commits touched them."""
    counts: Counter[str] = Counter()
    for c in cluster.commits:
        for f in c.files_changed:
            counts[f] += 1
    return [f for f, _ in counts.most_common(limit)]


def format_cluster_for_synthesis(
    cluster: CommitCluster,
    *,
    max_commits: int = 10,
    include_detail: bool = False,
) -> str:
    """Format a cluster's commits as structured text for LLM consumption.

    Commits are *selected* by churn (largest diff first) because that is
    the best available proxy for "which commits carry the story", but they
    are *presented* chronologically. Presenting date-prefixed lines in size
    order reads as a timeline that jumps around, which is worse than no
    dates at all.

    When the cluster has more commits than are shown, the header says so.
    A silent cut under a `Total commits: 153` header invites the reader to
    believe they are looking at all 153.

    `include_detail` gates the body, the per-commit file list, and the
    diffstat. Off by default because the body alone runs to 500 chars per
    commit, and the synthesis task ("write 3-8 sentences on WHY") is
    driven by subjects; cluster-level `key_files` already covers which
    files matter, without per-commit attribution.
    """
    shown = sorted(cluster.commits, key=lambda c: c.insertions + c.deletions, reverse=True)[:max_commits]
    shown = sorted(shown, key=lambda c: c.date)
    total = len(cluster.commits)

    lines = [
        f"Cluster: {cluster.label}",
        f"Date range: {cluster.commits[0].date.date()} to {cluster.commits[-1].date.date()}",
        f"Total commits: {total}",
    ]
    if len(shown) < total:
        lines.append(f"Showing: {len(shown)} of {total} commits (largest-diff first, listed chronologically)")
    lines.append("")

    for c in shown:
        lines.append(f"  [{c.date.date()}] {c.subject}")
        if include_detail:
            body_snippet = c.body[:500].strip() if c.body else ""
            if body_snippet:
                lines.append(f"    {body_snippet}")
            if c.files_changed:
                files = ", ".join(c.files_changed[:10])
                if len(c.files_changed) > 10:
                    files += f" (+{len(c.files_changed) - 10} more)"
                lines.append(f"    Files: {files}")
            lines.append(f"    +{c.insertions}/-{c.deletions}")
        lines.append("")

    return "\n".join(lines)


def cluster_to_summary(
    cluster: CommitCluster,
    *,
    max_commits: int = 10,
    include_detail: bool = False,
) -> dict[str, Any]:
    """Build the per-cluster response payload for the onboarding surface.

    Lives here rather than in the MCP tool because it is clustering logic —
    ranking files, deriving tags — not transport. Keeping it in the service
    also makes the response shape reachable from a plain unit test.
    """
    by_date = sorted(cluster.commits, key=lambda c: c.date)
    files = top_files(cluster)

    suggested_tags = ["git-derived"]
    path_parts = []
    for f in files[:5]:
        parts = f.replace("\\", "/").split("/")
        if len(parts) >= 2:
            path_parts.append(parts[1] if parts[0] in ("src", "tests", "plugins") else parts[0])
    if path_parts:
        suggested_tags.append(Counter(path_parts).most_common(1)[0][0])

    return {
        "label": cluster.label,
        "commit_count": len(cluster.commits),
        "shown_commit_count": min(max_commits, len(cluster.commits)),
        "date_range": f"{by_date[0].date.date().isoformat()} to {by_date[-1].date.date().isoformat()}",
        "created_at": by_date[-1].date.isoformat(),
        "key_files": files,
        "commits_summary": format_cluster_for_synthesis(
            cluster,
            max_commits=max_commits,
            include_detail=include_detail,
        ),
        "suggested_tags": suggested_tags,
    }


def format_cluster_as_raw_memory(cluster: CommitCluster) -> str:
    """No-LLM fallback: structured text from cluster data."""
    sorted_commits = sorted(cluster.commits, key=lambda c: c.date)
    date_start = sorted_commits[0].date.date()
    date_end = sorted_commits[-1].date.date()

    top_subjects = [c.subject for c in sorted(cluster.commits, key=lambda c: c.insertions + c.deletions, reverse=True)]
    top_subjects = top_subjects[:8]

    primary_files = top_files(cluster)

    lines = [
        f"[{date_start} to {date_end}] {cluster.label}",
        "",
        "Key changes:",
    ]
    for s in top_subjects:
        lines.append(f"  - {s}")

    if primary_files:
        lines.append("")
        lines.append("Primary files:")
        for f in primary_files:
            lines.append(f"  - {f}")

    return "\n".join(lines)


# --- Git Extraction ---

# Cloneable URL shapes we accept. Everything else — git's ext::/fd:: remote
# helpers, file:// / local paths, and option-looking args (-…) — is rejected
# before the URL ever reaches `git clone`.
_HTTPS_URL = re.compile(r"^https://[^\s]+$", re.IGNORECASE)
_SSH_URL = re.compile(r"^ssh://[^\s]+$", re.IGNORECASE)
_SCP_URL = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[^\s]+$")


def _redact_url(repo_url: str) -> str:
    """Strip ``user:secret@`` userinfo from a URL before it lands in an error.

    A token embedded in an https URL (``https://x:token@github.com/...``)
    would otherwise leak into the raised message and any log that captures it.
    """
    return re.sub(r"(https?://)[^/@\s]+@", r"\1", repo_url, flags=re.IGNORECASE)


def _validate_repo_url(repo_url: str) -> None:
    """Reject non-clone URL schemes and option-injection before `git clone`.

    Allows only ``https://``, ``ssh://``, and scp-style ``user@host:path``.
    Blocks git's ``ext::`` / ``fd::`` remote-helper transports (a code-exec
    vector) and ``file://`` / local paths, and refuses a leading ``-`` so the
    URL can't be parsed as an option. Belt-and-suspenders with the ``--``
    end-of-options guard in the clone command.
    """
    if not repo_url or not (_HTTPS_URL.match(repo_url) or _SSH_URL.match(repo_url) or _SCP_URL.match(repo_url)):
        raise RuntimeError(
            "Unsupported repo URL. Use an https:// or ssh:// URL, or scp-style user@host:path "
            "(ext::/fd::/file:// transports and local paths are not allowed)."
        )


# Conservative subset of valid git ref names: no leading dash (option
# injection), no leading dot/slash, none of git's forbidden characters.
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$")

# The watermark's content is spliced into `git log <hash>..HEAD` argv, so
# it must LOOK like a hash before it gets anywhere near a subprocess.
_WATERMARK_HASH_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")

WATERMARK_SOURCE = "git-onboard-watermark"
"""``MemoryItem.source`` marking the incremental-onboard watermark row.

Public because `export_memory` and `import_memory` filter on it: a
watermark is one device's git working state, not portable content, and
carrying it across devices corrupts the resume point (see
`docs/design/0001-cloud-backup.md` §11.3). Shared as a constant rather
than repeated as a literal precisely so renaming it here cannot silently
disable those filters.
"""


def _validate_branch(branch: str) -> None:
    """Reject branch names that could be parsed as options or garbage refs."""
    if not _BRANCH_RE.match(branch):
        raise RuntimeError(
            f"Invalid branch name: {branch!r}. Use a plain ref name (letters, digits, ., _, /, -; not starting with -)."
        )


# git's wording for a start-point that isn't in the clone: history was
# rewritten (hash gone everywhere) or the commit was orphaned by a
# force-push (still on the server, unreachable from any ref the clone
# fetched). Both mean the incremental walk cannot proceed from here.
_UNREACHABLE_MARKERS = ("invalid revision range", "unknown revision", "bad revision")


def _is_unreachable_revision_error(err: RuntimeError) -> bool:
    msg = str(err).lower()
    return any(marker in msg for marker in _UNREACHABLE_MARKERS)


def _resolve_ref(repo_path: str) -> tuple[str, str]:
    """Return (branch, head_sha) of the checked-out ref in ``repo_path``."""
    branch = subprocess.run(
        ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    head = subprocess.run(
        ["git", "-C", repo_path, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if branch.returncode != 0 or head.returncode != 0:
        raise RuntimeError(f"git rev-parse failed: {(branch.stderr + head.stderr).strip()}")
    return branch.stdout.strip(), head.stdout.strip()


@dataclass(frozen=True)
class ExtractedHistory:
    """Commits walked plus the resolved ref they came from.

    ``branch``/``head`` make a wrong-ref run self-evident from the
    response (a mirror-style ``main`` silently onboarding vendor history
    is otherwise indistinguishable from "this repo has no history").
    ``watermark_unreachable`` is True when the stored watermark could not
    be resolved and the walk automatically fell back to a full run.
    """

    commits: list[GitCommit] = field(default_factory=list)
    branch: str = ""
    head: str = ""
    watermark_unreachable: bool = False


def _extract_with_recovery(
    repo_path: str,
    max_commits: int,
    since_commit: str | None,
) -> tuple[list[GitCommit], bool]:
    """Run the incremental walk, falling back to a full walk when the
    watermark commit is unreachable (history rewrite / orphaning force-
    push). Returns (commits, watermark_unreachable).

    Three live occurrences motivated the auto-recovery: the raw
    ``git log failed: fatal: Invalid revision range <sha>..HEAD`` error
    gave no hint that force=true was the fix, and force wipes every
    git-derived memory just to repair the watermark. Falling back keeps
    existing memories and re-anchors the watermark from the fresh walk;
    the caller surfaces ``watermark_unreachable`` so duplicate cluster
    suggestions are explainable.
    """
    if since_commit is None:
        return extract_commits_from_git(repo_path, max_commits=max_commits), False
    try:
        return extract_commits_from_git(repo_path, max_commits=max_commits, since_commit=since_commit), False
    except RuntimeError as err:
        if not _is_unreachable_revision_error(err):
            raise
        _logger.warning(
            "git-onboard watermark %s is unreachable (history rewritten or commit orphaned); running a full walk",
            since_commit[:12],
        )
        return extract_commits_from_git(repo_path, max_commits=max_commits), True


def extract_commits_from_git(
    repo_path: str, max_commits: int = 500, since_commit: str | None = None
) -> list[GitCommit]:
    """Extract commits from a git repository via subprocess."""
    separator = "---GIT_ONBOARD_SEP---"
    field_sep = "---GIT_ONBOARD_FIELD---"
    # %b (body) is multi-line and comes last, so we need an explicit
    # end-of-body sentinel: everything from the last field_sep up to the
    # sentinel is the body (newlines and all); everything after it is the
    # --numstat block. Without this, only the body's first line was kept
    # and the rest was misparsed as numstat rows (and silently dropped).
    body_end = "---GIT_ONBOARD_BODYEND---"

    git_format = field_sep.join(["%H", "%an", "%aI", "%s", "%b"]) + body_end

    cmd = [
        "git",
        "-C",
        repo_path,
        "log",
        f"--max-count={max_commits}",
        "--no-merges",
        f"--format={separator}{git_format}",
        "--numstat",
    ]
    if since_commit:
        cmd.insert(4, f"{since_commit}..HEAD")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as err:
        raise RuntimeError("git is not installed or not in PATH") from err
    except subprocess.TimeoutExpired as err:
        raise RuntimeError("git log timed out after 60 seconds") from err

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not a git repository" in stderr.lower():
            raise RuntimeError(f"Not a git repository: {repo_path}")
        raise RuntimeError(f"git log failed: {stderr}")

    output = result.stdout
    if not output.strip():
        return []

    commits = []
    # Split by separator, skip empty first element
    raw_entries = output.split(separator)
    for entry in raw_entries:
        entry = entry.strip()
        if not entry:
            continue

        # Split the header (which contains the possibly-multi-line body) from
        # the numstat block at the body sentinel.
        header_part, sentinel_found, numstat_part = entry.partition(body_end)
        if not sentinel_found:
            continue
        # maxsplit=4 so a field_sep that happens to appear inside the body
        # doesn't spill into a phantom sixth field.
        fields = header_part.split(field_sep, 4)
        if len(fields) < 4:
            continue

        commit_hash = fields[0]
        author = fields[1]
        date_str = fields[2]
        subject = fields[3]
        body = fields[4] if len(fields) > 4 else ""

        # Parse date
        try:
            date = datetime.fromisoformat(date_str)
        except ValueError:
            date = utc_now()

        # Parse numstat lines
        files_changed = []
        insertions = 0
        deletions = 0
        for line in numstat_part.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    ins = int(parts[0]) if parts[0] != "-" else 0
                    dels = int(parts[1]) if parts[1] != "-" else 0
                    insertions += ins
                    deletions += dels
                    files_changed.append(parts[2])
                except ValueError:
                    continue

        commits.append(
            GitCommit(
                hash=commit_hash,
                author=author,
                date=date,
                subject=subject,
                body=body.strip(),
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
            )
        )

    return commits


def _build_clone_env(repo_url: str) -> dict[str, str]:
    """Build the subprocess env for ``git clone``, injecting auth when configured.

    If ``OC_GIT_TOKEN`` is set in the process env AND ``repo_url`` is an
    https://github.com/ URL, inject an ``Authorization: Basic <b64>`` header
    for github.com requests via ``GIT_CONFIG_PARAMETERS``.

    Why Basic and not Bearer: GitHub's git-over-HTTPS server accepts Basic
    auth with the PAT as the password (username is a literal placeholder
    ``x-access-token`` that GitHub ignores for PATs). Bearer works for the
    REST API but is unreliable for git operations. This matches the
    actions/checkout pattern.

    Why ``GIT_CONFIG_PARAMETERS`` instead of ``git -c http.extraheader=...``:
    the env-var path keeps the secret entirely off argv, so it never appears
    in process listings (``ps``) or in git's own error messages. Same effect
    as ``-c`` from git's POV.

    The header key is URL-scoped (``http.https://github.com/.extraheader``)
    so the token is only sent on github.com requests, never to other hosts
    that the clone might somehow follow. v1 supports github.com only;
    GitLab/Bitbucket/etc. would need their own host-scoped tokens.
    """
    env = os.environ.copy()
    token = os.environ.get("OC_GIT_TOKEN")
    if token and repo_url.startswith("https://github.com/"):
        # GitHub ignores the username for PATs, but the Basic-auth wire
        # format requires *something* before the colon. ``x-access-token``
        # is the GitHub-documented placeholder.
        basic_b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        # GIT_CONFIG_PARAMETERS format: space-separated single-quoted entries,
        # each of the form 'key=value'. The base64 alphabet contains no
        # single-quotes so no escaping needed.
        env["GIT_CONFIG_PARAMETERS"] = f"'http.https://github.com/.extraheader=AUTHORIZATION: Basic {basic_b64}'"
    return env


def extract_commits_from_url(
    repo_url: str,
    max_commits: int = 500,
    since_commit: str | None = None,
    branch: str | None = None,
) -> ExtractedHistory:
    """Extract commits by cloning a remote repo into a tmpdir.

    Used by the MCP server (and any other server-side caller) which doesn't
    have local repo paths available. Clones shallow when there's no watermark
    (depth=max_commits) and full when ``since_commit`` is set (shallow clones
    can't resolve arbitrary historical revisions).

    Private repos: set ``OC_GIT_TOKEN`` on the OC server to a GitHub PAT
    with ``contents:read`` scope. The token is injected as an HTTP Basic
    ``Authorization`` header (``x-access-token:<PAT>``, GitHub's documented
    placeholder username) only on github.com requests — see
    ``_build_clone_env``, whose docstring records why Bearer was rejected. Currently
    github.com only — other hosts would need their own scoping.

    Args:
        repo_url: A git-cloneable URL (HTTPS or SSH). Public repos work
            without auth; private github.com repos require ``OC_GIT_TOKEN``.
        max_commits: Cap on commits to extract.
        since_commit: Optional commit hash; only commits after it are
            returned. Forces a full clone since the hash must be reachable.
        branch: Optional branch/ref to walk. Default: the remote's default
            branch — which is the WRONG branch for mirror-style repos whose
            work lives elsewhere, so the resolved ref is echoed either way.

    Returns an :class:`ExtractedHistory`; if ``since_commit`` turns out to
    be unreachable in the clone, the walk automatically falls back to a
    full run and flags ``watermark_unreachable``. The clone tmpdir is
    deleted before this function returns.
    """
    _validate_repo_url(repo_url)
    if branch is not None:
        _validate_branch(branch)

    # Pick clone depth: shallow is fine when we just want the most recent
    # max_commits. With a watermark, the arbitrary `since_commit` SHA must be
    # reachable, so do a full clone (--depth changes git's view of history).
    clone_cmd: list[str] = ["git", "clone", "--quiet"]
    if since_commit is None:
        # +1 to ensure we don't truncate exactly at max_commits and miss a parent
        clone_cmd.extend(["--depth", str(max_commits + 1)])
    if branch is not None:
        clone_cmd.extend(["--branch", branch])
    # `--` ends option parsing so repo_url/tmpdir can never be read as flags.
    clone_cmd.append("--")
    clone_cmd.append(repo_url)

    clone_env = _build_clone_env(repo_url)

    with tempfile.TemporaryDirectory(prefix="oc-git-onboard-") as tmpdir:
        clone_cmd.append(tmpdir)
        try:
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env=clone_env,
            )
        except FileNotFoundError as err:
            raise RuntimeError("git is not installed or not in PATH") from err
        except subprocess.TimeoutExpired as err:
            raise RuntimeError("git clone timed out after 300 seconds") from err

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"git clone failed for {_redact_url(repo_url)}: {stderr}")

        resolved_branch, head = _resolve_ref(tmpdir)
        commits, unreachable = _extract_with_recovery(tmpdir, max_commits, since_commit)
        return ExtractedHistory(
            commits=commits,
            branch=resolved_branch,
            head=head,
            watermark_unreachable=unreachable,
        )


def extract_history_from_path(
    repo_path: str,
    max_commits: int = 500,
    since_commit: str | None = None,
) -> ExtractedHistory:
    """Local-path twin of :func:`extract_commits_from_url`.

    Same ref echo and same watermark-unreachable auto-recovery, against
    an existing working tree instead of a fresh clone. Used by the CLI.
    """
    resolved_branch, head = _resolve_ref(repo_path)
    commits, unreachable = _extract_with_recovery(repo_path, max_commits, since_commit)
    return ExtractedHistory(
        commits=commits,
        branch=resolved_branch,
        head=head,
        watermark_unreachable=unreachable,
    )


# --- Orchestration ---


def materialize_clusters(
    clusters: list[CommitCluster],
    *,
    store: MemoryStorePort,
    project_id: str,
    progress_callback: Callable[[str], None] | None = None,
) -> list[MemoryItem]:
    """Save each cluster as a raw-format memory (the CLI path; no LLM).

    The MCP surface instead returns cluster summaries for the calling
    agent to synthesize — that divergence is deliberate; everything
    upstream of it lives in :func:`onboard_git_prepare`.
    """
    memories: list[MemoryItem] = []
    for i, cluster in enumerate(clusters):
        if progress_callback:
            progress_callback(f"Processing cluster {i + 1}/{len(clusters)}: {cluster.label}")

        content = format_cluster_as_raw_memory(cluster)
        latest_date = max(c.date for c in cluster.commits)

        item = MemoryItem(
            content=content,
            tags=["git-derived"],
            pinned=False,
            project_id=project_id,
            source="git-onboard",
            created_at=latest_date,
        )
        store.add_memory(item)
        memories.append(item)

    return memories


@dataclass(frozen=True)
class OnboardPrepared:
    """Outcome of the shared onboard orchestration (transport-agnostic)."""

    status: str  # "ok" | "up_to_date" | "exists" | "empty"
    history: ExtractedHistory = field(default_factory=ExtractedHistory)
    filtered: list[GitCommit] = field(default_factory=list)
    clusters: list[CommitCluster] = field(default_factory=list)
    watermark_before: str | None = None
    existing_count: int = 0

    @property
    def incremental(self) -> bool:
        """True when this run walked only commits past a usable watermark."""
        return self.watermark_before is not None and not self.history.watermark_unreachable


def onboard_git_prepare(
    store: MemoryStorePort,
    project_id: str,
    extract: Callable[[str | None], ExtractedHistory],
    *,
    max_clusters: int = 15,
    force: bool = False,
) -> OnboardPrepared:
    """Shared onboard orchestration: watermark policy, extraction (with
    unreachable auto-recovery inside the extractor), filter, cluster,
    watermark re-anchor.

    Both surfaces run through here so the watermark semantics can't
    diverge again — the CLI's hand-rolled sibling used to save no
    watermark at all, and its ``--force`` wiped ``git-onboard`` memories
    while leaving a stale ``git-onboard-watermark`` behind, so a later
    MCP run resumed from deleted state.
    """
    existing = store.list_memory_by_source("git-onboard", project_id)
    watermark_items = store.list_memory_by_source(WATERMARK_SOURCE, project_id)
    watermark_hash: str | None = watermark_items[0].content if watermark_items else None
    if watermark_hash is not None and not _WATERMARK_HASH_RE.match(watermark_hash):
        # The watermark is spliced into `git log <hash>..HEAD` argv.
        # Anything that doesn't look like a hash (an imported or
        # hand-written memory under the watermark source tag) is ignored,
        # never executed.
        _logger.warning("Ignoring malformed git-onboard watermark for project %s", project_id)
        watermark_hash = None

    if force:
        for m in [*existing, *watermark_items]:
            store.delete_memory(m.id)
        existing = []
        watermark_hash = None
    elif existing and not watermark_hash:
        return OnboardPrepared(status="exists", existing_count=len(existing))

    history = extract(watermark_hash)
    if not history.commits:
        if watermark_hash:
            return OnboardPrepared(status="up_to_date", history=history, watermark_before=watermark_hash)
        return OnboardPrepared(status="empty", history=history)

    filtered = filter_commits(history.commits)
    clusters = cluster_commits(filtered, max_clusters=max_clusters)

    # Watermark the newest commit WALKED. `git log` output is
    # ancestry-ordered newest-first, so that is commits[0] — NOT the max
    # author date: rebased/cherry-picked commits keep their old author
    # dates, and a single future-dated commit would pin a date-anchored
    # watermark to itself forever, re-walking (and re-suggesting)
    # everything after it on every run.
    save_watermark(store, project_id, history.commits[0].hash)

    return OnboardPrepared(
        status="ok",
        history=history,
        filtered=filtered,
        clusters=clusters,
        watermark_before=watermark_hash,
    )


def save_watermark(
    store: MemoryStorePort,
    project_id: str,
    latest_hash: str,
) -> None:
    """Save or update the git-onboard watermark for incremental runs."""
    existing = store.list_memory_by_source(WATERMARK_SOURCE, project_id)
    for wm in existing:
        store.delete_memory(wm.id)
    store.add_memory(
        MemoryItem(
            content=latest_hash,
            tags=[WATERMARK_SOURCE],
            pinned=False,
            project_id=project_id,
            source=WATERMARK_SOURCE,
        )
    )
