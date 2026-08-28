"""Shared access to the DI container from an MCP tool handler.

This was defined byte-identically in all five tool modules. One line
each, so the duplication was cheap — but it encodes a real contract
(the lifespan stores the container under the literal key ``"container"``,
set in ``interfaces/mcp/server.py``), and a contract repeated five times
is one that drifts the day the key changes and four copies are updated.

Deliberately module-private in name (``_get_container``) but importable
across this package: the five tool modules are one logical driver split
by tool family, not five independent consumers.
"""

from __future__ import annotations

from typing import cast

from mcp.server.fastmcp import Context

from openchronicle.core.infrastructure.wiring.container import CoreContainer

#: The key the FastMCP lifespan stores the container under. Must match
#: ``interfaces/mcp/server.py``; the boundary test pins that they agree.
CONTAINER_KEY = "container"


def get_container(ctx: Context) -> CoreContainer:
    """Return the DI container injected by the FastMCP lifespan."""
    return cast(CoreContainer, ctx.request_context.lifespan_context[CONTAINER_KEY])
