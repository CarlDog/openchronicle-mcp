"""Project tools — create, get, list, update, delete projects."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import (
    create_project,
    delete_project,
    list_projects,
    update_project,
)
from openchronicle.core.domain.errors.error_codes import PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
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
    def project_get(
        project_id: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """Fetch a single project by id.

        Use when you have a `project_id` (e.g. from `memory_save`'s response)
        and want the project's name or metadata without listing every
        project. Raises if the id doesn't exist.

        Args:
            project_id: Project UUID to fetch.
        """
        container = _get_container(ctx)
        project = container.storage.get_project(project_id)
        if project is None:
            raise NotFoundError(
                f"Project not found: {project_id}",
                code=PROJECT_NOT_FOUND,
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

    @mcp.tool()
    def project_update(
        project_id: str,
        ctx: Context,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rename a project or update its metadata.

        Pass at least one of `name` or `metadata`. Either field omitted is
        left untouched (no field is set to null). Raises if the project
        id doesn't exist.

        Args:
            project_id: Project UUID to update.
            name: New name. Leave unset to keep the current name.
            metadata: New metadata dict. Leave unset to keep the current
                metadata. Pass `{}` to clear all metadata keys.
        """
        container = _get_container(ctx)
        project = update_project.execute(
            store=container.storage,
            project_id=project_id,
            name=name,
            metadata=metadata,
        )
        return project_to_dict(project)

    @mcp.tool()
    def project_delete(
        project_id: str,
        ctx: Context,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Preview or hard-delete a project and all its memories.

        Two-step safety pattern. Call once with `confirm=false` (the
        default) to see how many memories would be dropped — the response
        contains `status: "preview"`, the project name, and `memory_count`.
        Call again with `confirm=true` to actually delete; the response
        then contains `status: "ok"` and `deleted_memories`. There is no
        soft-delete and no recovery path beyond `oc db backup` — confirm
        once you've checked the count.

        Args:
            project_id: Project UUID to delete.
            confirm: Must be true to perform the delete (default false).
        """
        container = _get_container(ctx)
        return delete_project.execute(
            store=container.storage,
            memory_store=container.storage,
            project_id=project_id,
            confirm=confirm,
        )
