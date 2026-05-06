"""Project tools — create and list projects."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import create_project, list_projects
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.serializers import project_to_dict


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register project tools on the MCP server."""

    @mcp.tool()
    def project_create(
        name: str,
        ctx: Context,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new project namespace for memories.

        Projects partition the memory keyspace; every memory item belongs
        to exactly one. Call once per logical workstream (a codebase,
        client engagement, research thread). The returned `id` is the UUID
        you pass as `project_id` to `memory_save` and `onboard_git`.

        Args:
            name: Human-readable project name.
            metadata: Arbitrary key-value annotations (optional).
        """
        container = _get_container(ctx)
        project = create_project.execute(
            store=container.storage,
            name=name,
            metadata=metadata,
        )
        return project_to_dict(project)

    @mcp.tool()
    def project_list(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """List every project, with id, name, and creation timestamp.

        Use to find the right `project_id` for `memory_save`. If only one
        project should exist for your use case but `project_list` returns
        several, consolidate before saving — projects are not auto-merged.
        """
        container = _get_container(ctx)
        projects = list_projects.execute(store=container.storage)
        return [project_to_dict(p) for p in projects]
