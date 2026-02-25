"""Git onboarding service — extract, filter, cluster, and synthesize git history into memories.

Pure functions for filtering and clustering. I/O functions for git extraction
and LLM synthesis are isolated and easily mockable.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from openchronicle.core.application.routing.router_policy import RouteDecision
from openchronicle.core.application.services.llm_execution import execute_with_route
from openchronicle.core.domain.models.git_commit import CommitCluster, GitCommit
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.llm_port import LLMPort
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

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


def format_cluster_for_synthesis(cluster: CommitCluster) -> str:
    """Format a cluster's commits as structured text for LLM consumption."""
    sorted_commits = sorted(cluster.commits, key=lambda c: c.insertions + c.deletions, reverse=True)
    top_commits = sorted_commits[:20]

    lines = [
        f"Cluster: {cluster.label}",
        f"Date range: {cluster.commits[0].date.date()} to {cluster.commits[-1].date.date()}",
        f"Total commits: {len(cluster.commits)}",
        "",
    ]

    for c in top_commits:
        body_snippet = c.body[:500].strip() if c.body else ""
        files = ", ".join(c.files_changed[:10])
        lines.append(f"  [{c.date.date()}] {c.subject}")
        if body_snippet:
            lines.append(f"    {body_snippet}")
        if files:
            lines.append(f"    Files: {files}")
        lines.append(f"    +{c.insertions}/-{c.deletions}")
        lines.append("")

    return "\n".join(lines)


def format_cluster_as_raw_memory(cluster: CommitCluster) -> str:
    """No-LLM fallback: structured text from cluster data."""
    sorted_commits = sorted(cluster.commits, key=lambda c: c.date)
    date_start = sorted_commits[0].date.date()
    date_end = sorted_commits[-1].date.date()

    top_subjects = [c.subject for c in sorted(cluster.commits, key=lambda c: c.insertions + c.deletions, reverse=True)]
    top_subjects = top_subjects[:8]

    all_files: Counter[str] = Counter()
    for c in cluster.commits:
        for f in c.files_changed:
            all_files[f] += 1
    top_files = [f for f, _ in all_files.most_common(10)]

    lines = [
        f"[{date_start} to {date_end}] {cluster.label}",
        "",
        "Key changes:",
    ]
    for s in top_subjects:
        lines.append(f"  - {s}")

    if top_files:
        lines.append("")
        lines.append("Primary files:")
        for f in top_files:
            lines.append(f"  - {f}")

    return "\n".join(lines)


# --- LLM Synthesis ---

_SYNTHESIS_PROMPT = """\
You are analyzing a cluster of related git commits from a software project.
Your job is to synthesize a concise memory capturing WHY these changes were made.

Focus on:
- Decisions made and the reasoning behind them
- Rejected alternatives or approaches that were tried and abandoned
- Architectural shifts or design patterns introduced
- Non-obvious gotchas or constraints that influenced the implementation

Write 3-8 sentences as if explaining to a new developer joining the project.
Do NOT list individual commits or include commit hashes.
Do NOT describe WHAT the code does line by line — focus on the WHY.

Commit data:
{cluster_text}
"""


async def synthesize_cluster(
    llm: LLMPort,
    route_decision: RouteDecision,
    cluster: CommitCluster,
) -> str:
    """Call the LLM to synthesize a memory from a commit cluster."""
    cluster_text = format_cluster_for_synthesis(cluster)
    prompt = _SYNTHESIS_PROMPT.format(cluster_text=cluster_text)

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    response = await execute_with_route(
        llm=llm,
        route_decision=route_decision,
        messages=messages,
        max_output_tokens=500,
        temperature=0.3,
    )
    return response.content.strip()


# --- Git Extraction ---


def extract_commits_from_git(
    repo_path: str, max_commits: int = 500, since_commit: str | None = None
) -> list[GitCommit]:
    """Extract commits from a git repository via subprocess."""
    separator = "---GIT_ONBOARD_SEP---"
    field_sep = "---GIT_ONBOARD_FIELD---"

    git_format = field_sep.join(["%H", "%an", "%aI", "%s", "%b"])

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

        # Split header from numstat
        lines = entry.split("\n")
        header_line = lines[0]
        fields = header_line.split(field_sep)
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
            date = datetime.now(UTC)

        # Parse numstat lines
        files_changed = []
        insertions = 0
        deletions = 0
        for line in lines[1:]:
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


# --- Orchestration ---


async def run_git_onboard(
    commits: list[GitCommit],
    *,
    llm: LLMPort | None = None,
    route_decision: RouteDecision | None = None,
    store: MemoryStorePort,
    emit_event: Callable[[Event], None],
    project_id: str,
    max_clusters: int = 15,
    progress_callback: Callable[[str], None] | None = None,
) -> list[MemoryItem]:
    """Orchestrate: filter -> cluster -> synthesize each -> save each via add_memory."""
    filtered = filter_commits(commits)
    if not filtered:
        if progress_callback:
            progress_callback("No commits to process after filtering.")
        return []

    clusters = cluster_commits(filtered, max_clusters=max_clusters)

    emit_event(
        Event(
            project_id=project_id,
            type="onboard.git.started",
            payload={
                "project_id": project_id,
                "commit_count": len(filtered),
                "cluster_count": len(clusters),
            },
        )
    )

    if progress_callback:
        progress_callback(f"Filtered {len(commits)} -> {len(filtered)} commits, {len(clusters)} clusters")

    memories: list[MemoryItem] = []
    use_llm = llm is not None and route_decision is not None

    for i, cluster in enumerate(clusters):
        if progress_callback:
            progress_callback(f"Processing cluster {i + 1}/{len(clusters)}: {cluster.label}")

        if use_llm:
            assert llm is not None
            assert route_decision is not None
            content = await synthesize_cluster(llm, route_decision, cluster)
        else:
            content = format_cluster_as_raw_memory(cluster)

        # Use latest commit date as memory timestamp
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
        emit_event(
            Event(
                project_id=project_id,
                type="memory.written",
                payload={
                    "id": item.id,
                    "pinned": item.pinned,
                    "tags": item.tags,
                    "source": item.source,
                    "project_id": project_id,
                },
            )
        )
        memories.append(item)

    emit_event(
        Event(
            project_id=project_id,
            type="onboard.git.completed",
            payload={
                "project_id": project_id,
                "memory_count": len(memories),
                "memory_ids": [m.id for m in memories],
                "source": "cli",
            },
        )
    )

    return memories


def save_watermark(
    store: MemoryStorePort,
    project_id: str,
    latest_hash: str,
) -> None:
    """Save or update the git-onboard watermark for incremental runs."""
    existing = store.list_memory_by_source("git-onboard-watermark", project_id)
    for wm in existing:
        store.delete_memory(wm.id)
    store.add_memory(
        MemoryItem(
            content=latest_hash,
            tags=["git-onboard-watermark"],
            pinned=False,
            project_id=project_id,
            source="git-onboard-watermark",
        )
    )
