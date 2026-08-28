"""System tools — health check.

Handlers are async and offload store work via asyncio.to_thread:
FastMCP dispatches sync tools inline on the event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases.diagnose_runtime import build_health_payload
from openchronicle.interfaces.mcp.tools._context import get_container as _get_container


def register(mcp: FastMCP) -> None:
    """Register system tools on the MCP server."""

    @mcp.tool()
    async def health(ctx: Context) -> dict[str, Any]:
        """Probe the OC server: DB reachability, config status, embedding subsystem.

        Use to verify the server is responsive and configured before a
        session, or to diagnose retrieval issues (e.g. embedding provider
        down → search degrades to FTS5-only). Returns a snapshot of
        runtime state, not historical metrics.

        `package_version` and `schema_version` identify what you're
        talking to, which is worth checking when a tool behaves unlike
        its documentation. `fts5_active` distinguishes "search is
        degraded" from "search is broken" — it falls back silently
        otherwise.
        """
        container = _get_container(ctx)
        return await asyncio.to_thread(build_health_payload, container)
