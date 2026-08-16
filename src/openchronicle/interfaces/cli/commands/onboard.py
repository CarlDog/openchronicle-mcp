"""CLI handler for `oc onboard git`."""

from __future__ import annotations

import argparse

from openchronicle.core.application.services.git_onboard import (
    ExtractedHistory,
    cluster_commits,
    extract_history_from_path,
    filter_commits,
    materialize_clusters,
    onboard_git_prepare,
)
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def cmd_onboard(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch to onboard subcommands."""
    from collections.abc import Callable

    onboard_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "git": cmd_onboard_git,
    }
    handler = onboard_dispatch.get(args.onboard_command)
    if handler is None:
        print("Usage: oc onboard <subcommand>")
        return 1
    return handler(args, container)


def cmd_onboard_git(args: argparse.Namespace, container: CoreContainer) -> int:
    """Bootstrap OC memories from git history (raw cluster format).

    v3 onboard does not call an LLM. Each cluster is saved as a structured
    raw memory; downstream LLM-aware tools (Claude Code, etc.) can re-read
    and refine via `memory_update` if synthesis is desired.

    Shares `onboard_git_prepare` with the MCP tool, so the watermark
    semantics are identical: runs are incremental past the stored
    watermark, and --force wipes both the memories and the watermark.
    """
    project_id: str = args.project_id
    repo_path: str = args.repo_path
    max_commits: int = args.max_commits
    max_memories: int = args.max_memories
    force: bool = args.force
    dry_run: bool = args.dry_run

    project = container.storage.get_project(project_id)
    if project is None:
        print(f"Error: project not found: {project_id}")
        return 1

    store = container.storage

    if dry_run:
        # Preview only: no memories, no watermark, no wipes.
        try:
            history = extract_history_from_path(repo_path, max_commits)
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1
        print(f"Branch {history.branch} @ {history.head[:12]}")
        filtered = filter_commits(history.commits)
        clusters = cluster_commits(filtered, max_clusters=max_memories)
        print(f"Filtered: {len(history.commits)} -> {len(filtered)} commits")
        print(f"Clusters: {len(clusters)}")
        for i, cluster in enumerate(clusters):
            sorted_commits = sorted(cluster.commits, key=lambda c: c.date)
            date_start = sorted_commits[0].date.date()
            date_end = sorted_commits[-1].date.date()
            print(f"  [{i + 1}] {cluster.label} ({len(cluster.commits)} commits, {date_start} to {date_end})")
        return 0

    def _extract(since_commit: str | None) -> ExtractedHistory:
        return extract_history_from_path(repo_path, max_commits, since_commit=since_commit)

    try:
        prepared = onboard_git_prepare(
            store,
            project_id,
            _extract,
            max_clusters=max_memories,
            force=force,
        )
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    if prepared.status == "exists":
        print(f"Error: {prepared.existing_count} git-onboard memories already exist for this project.")
        print("(They predate incremental onboarding, so there is no watermark to resume from.)")
        print("Use --force to delete and re-run.")
        return 1

    history = prepared.history
    print(f"Branch {history.branch} @ {history.head[:12]}")

    if prepared.status == "up_to_date":
        print("Up to date — no commits past the stored watermark.")
        return 0
    if prepared.status == "empty":
        print("No commits found.")
        return 0

    if history.watermark_unreachable:
        print(
            "Note: the stored watermark was unreachable (history rewritten or "
            "force-pushed); ran a full walk — some memories may duplicate "
            "existing ones."
        )
    print(f"Walked {len(history.commits)} commits ({len(prepared.filtered)} after filtering)")

    def progress(msg: str) -> None:
        print(f"  {msg}")

    memories = materialize_clusters(
        prepared.clusters,
        store=store,
        project_id=project_id,
        progress_callback=progress,
    )

    print(f"\nCreated {len(memories)} memories from git history.")
    for m in memories:
        print(f"  [{m.created_at.date()}] {m.content[:80]}...")

    return 0
