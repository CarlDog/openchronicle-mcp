"""MCP server factory — creates and configures a FastMCP instance."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

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
        # FastMCP's streamable-HTTP transport defaults to handling `/mcp`
        # internally. When the FastAPI host mounts that ASGI app at /mcp,
        # the result is path-doubling: requests must hit /mcp/mcp instead
        # of the documented /mcp. Setting this to "/" makes the inner app
        # handle its own root, so the host's mount path is the full URL.
        # Discovered post-cutover 2026-05-06 — see triage doc.
        streamable_http_path="/",
        # Defense against DNS rebinding: FastMCP rejects any Host header
        # not on this allowlist with a 421. Defaults are localhost-only;
        # operators binding to a LAN-reachable interface configure the
        # allowlist via OC_MCP_ALLOWED_HOSTS. See MCPConfig docstring.
        transport_security=TransportSecuritySettings(
            allowed_hosts=list(config.allowed_hosts),
        ),
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
