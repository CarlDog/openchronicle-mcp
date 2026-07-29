"""Onboarding tools — bootstrap memories from git history.

Handlers are async and offload their work via asyncio.to_thread:
FastMCP dispatches sync tools inline on the event loop, and this
tool's git clone can block for minutes on a large repo.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.services.git_onboard import (
    cluster_commits,
    cluster_to_summary,
    extract_commits_from_url,
    filter_commits,
    save_watermark,
)
from openchronicle.core.domain.errors.error_codes import PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register onboarding tools on the MCP server."""

    @mcp.tool()
    async def onboard_git(
        project_id: str,
        repo_url: str,
        ctx: Context,
        max_commits: int = 500,
        max_clusters: int = 15,
        force: bool = False,
        max_commits_per_cluster: int = 10,
        include_commit_detail: bool = False,
    ) -> dict[str, Any]:
        """Bootstrap project memory from a remote git repo's commit clusters.

        Use once per project to seed long-term memory with the WHY behind
        existing code. The server clones `repo_url` shallow into a tmpdir,
        clusters related commits, and returns suggestions ready for
        `memory_save` — write 3-8 sentences per cluster capturing the
        decision/rejected approach/architectural shift, then save with
        the suggested tags and `created_at`. Re-running is incremental
        (a watermark tracks the last processed commit); pass `force=true`
        to wipe and start over.

        Private github.com repos require `OC_GIT_TOKEN` set on the server
        with `contents:read` scope. For unpushed local history use the
        `oc onboard git` CLI instead.

        Each cluster lists its highest-churn commits, presented oldest to
        newest, and says `Showing: n of N` when it holds more than are
        listed. `key_files` already covers which files the whole cluster
        touched, so per-commit bodies and file lists stay behind
        `include_commit_detail` — turning it on can grow the response by
        roughly an order of magnitude on a large repo.

        Args:
            project_id: Project to attach memories to.
            repo_url: Cloneable URL (HTTPS or SSH).
            max_commits: Cap on commits walked (default 500).
            max_clusters: Cap on clusters/memories produced (default 15).
            force: Wipe prior git-onboard memories and re-run from scratch.
            max_commits_per_cluster: Commits listed per cluster (1-100, default 10).
            include_commit_detail: Add each commit's body, file list, and diffstat.
        """
        max_commits_per_cluster = min(max(max_commits_per_cluster, 1), 100)
        container = _get_container(ctx)
        return await asyncio.to_thread(
            _onboard_git_sync,
            container,
            project_id,
            repo_url,
            max_commits,
            max_clusters,
            force,
            max_commits_per_cluster,
            include_commit_detail,
        )


def _onboard_git_sync(
    container: CoreContainer,
    project_id: str,
    repo_url: str,
    max_commits: int,
    max_clusters: int,
    force: bool,
    max_commits_per_cluster: int = 10,
    include_commit_detail: bool = False,
) -> dict[str, Any]:
    """Blocking body of onboard_git — runs on a worker thread."""
    # Validate project
    project = container.storage.get_project(project_id)
    if project is None:
        raise NotFoundError(f"Project not found: {project_id}", code=PROJECT_NOT_FOUND)

    store = container.storage
    existing = store.list_memory_by_source("git-onboard", project_id)
    watermark_items = store.list_memory_by_source("git-onboard-watermark", project_id)
    watermark_hash = watermark_items[0].content if watermark_items else None

    if force:
        # Delete all git-onboard memories AND watermark
        for m in existing:
            store.delete_memory(m.id)
        for wm in watermark_items:
            store.delete_memory(wm.id)
        watermark_hash = None
    elif existing and not watermark_hash:
        # Existing memories but no watermark (pre-incremental run) — require force
        return {
            "error": f"{len(existing)} git-onboard memories already exist. Use force=True to re-run.",
            "existing_count": len(existing),
        }

    # Extract commits — incremental if watermark exists. Clones the
    # remote repo into a tmpdir inside the server's container/filesystem,
    # walks its history, then discards the clone.
    commits = extract_commits_from_url(repo_url, max_commits, since_commit=watermark_hash)
    if not commits:
        if watermark_hash:
            return {"status": "up_to_date", "watermark": watermark_hash}
        return {"project_id": project_id, "commit_count": 0, "cluster_count": 0, "clusters": []}

    filtered = filter_commits(commits)
    clusters = cluster_commits(filtered, max_clusters=max_clusters)

    cluster_data = [
        cluster_to_summary(
            cluster,
            max_commits=max_commits_per_cluster,
            include_detail=include_commit_detail,
        )
        for cluster in clusters
    ]

    # Watermark the newest commit WALKED, not the newest one kept. Merge,
    # format and version-bump commits are filtered out, so anchoring to
    # `filtered` leaves anything newer than the last kept commit to be
    # re-walked on every subsequent run — on a repo whose HEAD is a merge,
    # the incremental path never advances at all.
    latest_hash = max(commits, key=lambda c: c.date).hash
    save_watermark(store, project_id, latest_hash)

    return {
        "project_id": project_id,
        "walked_commit_count": len(commits),
        "commit_count": len(filtered),
        "cluster_count": len(clusters),
        "clusters": cluster_data,
        "incremental": watermark_hash is not None,
        "instructions": (
            "For each cluster above, synthesize a memory capturing WHY the changes "
            "were made (decisions, rejected approaches, architectural shifts). Write "
            "3-8 sentences. Save each using memory_save with the cluster's suggested_tags "
            "and created_at timestamp."
        ),
    }
