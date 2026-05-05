"""MCP server factory — creates and configures a FastMCP instance."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.config import MCPConfig

logger = logging.getLogger(__name__)


def create_server(container: CoreContainer, config: MCPConfig) -> FastMCP:
    """Build a fully-wired FastMCP server with all OC tools registered.

    The container is injected into tool handlers via the lifespan context.
    Tools access it as ``ctx.request_context.lifespan_context["container"]``.
    """

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        logger.info("OpenChronicle MCP server starting")
        yield {"container": container}
        logger.info("OpenChronicle MCP server shutting down")

    mcp = FastMCP(
        config.server_name,
        instructions=(
            "OpenChronicle is a memory database for LLM agents. Use memory_save "
            "to persist decisions, milestones, and context that should outlive "
            "the current session; memory_search for hybrid semantic + keyword "
            "retrieval scoped to a project; memory_pin for standing rules; "
            "onboard_git to seed memory from a repo's commit history."
        ),
        lifespan=lifespan,
        host=config.host,
        port=config.port,
    )

    # Register tool modules
    from openchronicle.interfaces.mcp.tools import (
        context,
        memory,
        onboard,
        project,
        system,
    )

    system.register(mcp)
    project.register(mcp)
    memory.register(mcp)
    context.register(mcp)
    onboard.register(mcp)

    return mcp
