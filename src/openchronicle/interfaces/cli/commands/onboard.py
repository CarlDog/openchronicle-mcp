"""CLI handler for `oc onboard git`."""

from __future__ import annotations

import argparse
import asyncio

from openchronicle.core.application.services.git_onboard import (
    cluster_commits,
    extract_commits_from_git,
    filter_commits,
    run_git_onboard,
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
    """Bootstrap OC memories from git history."""
    project_id: str = args.project_id
    repo_path: str = args.repo_path
    max_commits: int = args.max_commits
    max_memories: int = args.max_memories
    force: bool = args.force
    no_llm: bool = args.no_llm
    dry_run: bool = args.dry_run

    # Validate project exists
    project = container.storage.get_project(project_id)
    if project is None:
        print(f"Error: project not found: {project_id}")
        return 1

    # Idempotency check
    store = container.storage
    if hasattr(store, "list_memory_by_source"):
        existing = store.list_memory_by_source("git-onboard", project_id)
        if existing and not force:
            print(f"Error: {len(existing)} git-onboard memories already exist for this project.")
            print("Use --force to delete and re-run.")
            return 1
        if existing and force:
            for m in existing:
                store.delete_memory(m.id)
            print(f"Deleted {len(existing)} existing git-onboard memories.")

    # Extract commits
    try:
        commits = extract_commits_from_git(repo_path, max_commits)
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    if not commits:
        print("No commits found.")
        return 0

    print(f"Extracted {len(commits)} commits from {repo_path}")

    # Dry run: just show clusters
    if dry_run:
        filtered = filter_commits(commits)
        clusters = cluster_commits(filtered, max_clusters=max_memories)
        print(f"Filtered: {len(commits)} -> {len(filtered)} commits")
        print(f"Clusters: {len(clusters)}")
        for i, cluster in enumerate(clusters):
            sorted_commits = sorted(cluster.commits, key=lambda c: c.date)
            date_start = sorted_commits[0].date.date()
            date_end = sorted_commits[-1].date.date()
            print(f"  [{i + 1}] {cluster.label} ({len(cluster.commits)} commits, {date_start} to {date_end})")
        return 0

    # Set up LLM if available
    llm = None
    route_decision = None
    if not no_llm:
        try:
            route_decision = container.router_policy.route(task_type="onboard.git", agent_role="worker")
            llm = container.llm
        except Exception:
            print("Warning: LLM not available, using raw memory format.")

    def progress(msg: str) -> None:
        print(f"  {msg}")

    # Run
    memories = asyncio.run(
        run_git_onboard(
            commits,
            llm=llm,
            route_decision=route_decision,
            store=container.storage,
            emit_event=container.emit_event,
            project_id=project_id,
            max_clusters=max_memories,
            progress_callback=progress,
        )
    )

    print(f"\nCreated {len(memories)} memories from git history.")
    for m in memories:
        print(f"  [{m.created_at.date()}] {m.content[:80]}...")

    return 0
