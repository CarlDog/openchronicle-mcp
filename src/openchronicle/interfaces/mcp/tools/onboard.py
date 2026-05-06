"""Onboarding tools — bootstrap memories from git history."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.services.git_onboard import (
    cluster_commits,
    extract_commits_from_url,
    filter_commits,
    format_cluster_for_synthesis,
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
    def onboard_git(
        project_id: str,
        repo_url: str,
        ctx: Context,
        max_commits: int = 500,
        max_clusters: int = 15,
        force: bool = False,
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

        Args:
            project_id: Project to attach memories to.
            repo_url: Cloneable URL (HTTPS or SSH).
            max_commits: Cap on commits walked (default 500).
            max_clusters: Cap on clusters/memories produced (default 15).
            force: Wipe prior git-onboard memories and re-run from scratch.
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
