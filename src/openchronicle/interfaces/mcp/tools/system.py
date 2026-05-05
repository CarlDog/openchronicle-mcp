"""System tools — health check."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import diagnose_runtime
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register system tools on the MCP server."""

    @mcp.tool()
    def health(ctx: Context) -> dict[str, Any]:
        """Probe the OC server: DB reachability, config status, embedding subsystem.

        Use to verify the server is responsive and configured before a
        session, or to diagnose retrieval issues (e.g. embedding provider
        down → search degrades to FTS5-only). Returns a snapshot of
        runtime state, not historical metrics.
        """
        report = diagnose_runtime.execute()
        container = _get_container(ctx)
        report.embedding_status = container.embedding_status_dict()
        data = asdict(report)
        if data.get("timestamp_utc"):
            data["timestamp_utc"] = data["timestamp_utc"].isoformat()
        if data.get("db_modified_utc"):
            data["db_modified_utc"] = data["db_modified_utc"].isoformat()
        return data
