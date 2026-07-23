"""Project tools — create, get, list, update, delete projects.

Handlers are async and offload store work via asyncio.to_thread:
FastMCP dispatches sync tools inline on the event loop.
"""

from __future__ import annotations

import asyncio
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
    async def project_create(
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
        project = await asyncio.to_thread(
            create_project.execute,
            store=container.storage,
            name=name,
            metadata=metadata,
        )
        return project_to_dict(project)

    @mcp.tool()
    async def project_get(
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
        project = await asyncio.to_thread(container.storage.get_project, project_id)
        if project is None:
            raise NotFoundError(
                f"Project not found: {project_id}",
                code=PROJECT_NOT_FOUND,
            )
        return project_to_dict(project)

    @mcp.tool()
    async def project_list(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """List every project, with id, name, and creation timestamp.

        Use to find the right `project_id` for `memory_save`. If only one
        project should exist for your use case but `project_list` returns
        several, consolidate before saving — projects are not auto-merged.
        """
        container = _get_container(ctx)
        projects = await asyncio.to_thread(list_projects.execute, store=container.storage)
        return [project_to_dict(p) for p in projects]

    @mcp.tool()
    async def project_update(
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
        project = await asyncio.to_thread(
            update_project.execute,
            store=container.storage,
            project_id=project_id,
            name=name,
            metadata=metadata,
        )
        return project_to_dict(project)

    @mcp.tool()
    async def project_delete(
        project_id: str,
        ctx: Context,
        confirm: bool,
    ) -> dict[str, Any]:
        """Preview or hard-delete a project and all its memories.

        Two-step safety pattern. Call with `confirm=false` to see how many
        memories would be dropped — the response contains
        `status: "preview"`, `deleted: false`, a `next_step`, the project
        `name`, and `memory_count`. Check the name against the project you
        meant before confirming; it is the guard against acting on a
        mistyped UUID. Call with `confirm=true` to actually delete; the
        response then contains `status: "ok"`, `deleted: true`, and
        `deleted_memories`. There is no soft-delete and no recovery path
        beyond `oc db backup`.

        `confirm` has no default: omitting it is an error, not a preview
        request. See `memory_delete` for why.

        Args:
            project_id: Project UUID to delete.
            confirm: Required. True deletes; false returns a preview.
        """
        container = _get_container(ctx)
        return await asyncio.to_thread(
            delete_project.execute,
            store=container.storage,
            memory_store=container.storage,
            project_id=project_id,
            confirm=confirm,
        )
