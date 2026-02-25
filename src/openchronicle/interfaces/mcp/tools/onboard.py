"""Onboarding tools — bootstrap memories from git history."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.services.git_onboard import (
    cluster_commits,
    extract_commits_from_git,
    filter_commits,
    format_cluster_for_synthesis,
    save_watermark,
)
from openchronicle.core.domain.errors.error_codes import PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.project import Event
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register onboarding tools on the MCP server."""

    @mcp.tool()
    @track_tool
    def onboard_git(
        project_id: str,
        ctx: Context,
        repo_path: str = ".",
        max_commits: int = 500,
        max_clusters: int = 15,
        force: bool = False,
    ) -> dict[str, Any]:
        """Analyze git history and return commit clusters for memory creation.

        Returns clusters of related commits. For each cluster, synthesize a
        memory capturing WHY changes were made (decisions, rejected approaches,
        architectural shifts) and save it using memory_save with
        tags=["git-derived"] and the cluster's created_at timestamp.

        Args:
            project_id: Project to associate memories with.
            repo_path: Path to git repository (default: current directory).
            max_commits: Maximum commits to analyze (default: 500).
            max_clusters: Maximum clusters/memories to produce (default: 15).
            force: Delete existing git-onboard memories before re-running.
        """
        container = _get_container(ctx)

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

        # Extract commits — incremental if watermark exists
        commits = extract_commits_from_git(repo_path, max_commits, since_commit=watermark_hash)
        if not commits:
            if watermark_hash:
                return {"status": "up_to_date", "watermark": watermark_hash}
            return {"project_id": project_id, "commit_count": 0, "cluster_count": 0, "clusters": []}

        filtered = filter_commits(commits)
        clusters = cluster_commits(filtered, max_clusters=max_clusters)

        # Emit started event
        container.event_logger.append(
            Event(
                project_id=project_id,
                type="onboard.git.started",
                payload={
                    "project_id": project_id,
                    "commit_count": len(filtered),
                    "cluster_count": len(clusters),
                    "incremental": watermark_hash is not None,
                },
            )
        )

        # Build response
        cluster_data = []
        for cluster in clusters:
            sorted_commits = sorted(cluster.commits, key=lambda c: c.date)
            date_start = sorted_commits[0].date.date().isoformat()
            date_end = sorted_commits[-1].date.date().isoformat()

            # Collect key files
            from collections import Counter

            file_counts: Counter[str] = Counter()
            for c in cluster.commits:
                for f in c.files_changed:
                    file_counts[f] += 1
            key_files = [f for f, _ in file_counts.most_common(10)]

            # Suggested tags
            suggested_tags = ["git-derived"]
            path_parts = []
            for f in key_files[:5]:
                parts = f.replace("\\", "/").split("/")
                if len(parts) >= 2:
                    path_parts.append(parts[1] if parts[0] in ("src", "tests", "plugins") else parts[0])
            if path_parts:
                from collections import Counter as C2

                dominant = C2(path_parts).most_common(1)[0][0]
                suggested_tags.append(dominant)

            cluster_data.append(
                {
                    "label": cluster.label,
                    "commit_count": len(cluster.commits),
                    "date_range": f"{date_start} to {date_end}",
                    "created_at": sorted_commits[-1].date.isoformat(),
                    "key_files": key_files,
                    "commits_summary": format_cluster_for_synthesis(cluster),
                    "suggested_tags": suggested_tags,
                }
            )

        # Save watermark with latest commit hash
        if filtered:
            latest_hash = max(filtered, key=lambda c: c.date).hash
            save_watermark(store, project_id, latest_hash)

        return {
            "project_id": project_id,
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
