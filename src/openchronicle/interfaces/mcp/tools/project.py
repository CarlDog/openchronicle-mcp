"""Project tools — create and list projects."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import create_project, list_projects
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def _project_to_dict(p: Project) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "metadata": p.metadata,
        "created_at": p.created_at.isoformat(),
    }


def register(mcp: FastMCP) -> None:
    """Register project tools on the MCP server."""

    @mcp.tool()
    @track_tool
    def project_create(
        name: str,
        ctx: Context,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new project.

        Projects are the top-level organizing concept. Conversations and
        memories belong to projects. You need a project_id before you can
        save memories.

        Args:
            name: Human-readable name for the project.
            metadata: Optional key-value metadata.
        """
        container = _get_container(ctx)
        project = create_project.execute(
            orchestrator=container.orchestrator,
            name=name,
            metadata=metadata,
        )
        return _project_to_dict(project)

    @mcp.tool()
    @track_tool
    def project_list(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """List all projects.

        Returns all projects, most useful for finding an existing project_id
        to use with memory_save.
        """
        container = _get_container(ctx)
        projects = list_projects.execute(orchestrator=container.orchestrator)
        return [_project_to_dict(p) for p in projects]
