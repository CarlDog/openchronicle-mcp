"""System tools — health check, tool usage stats."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import diagnose_runtime
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register system tools on the MCP server."""

    @mcp.tool()
    def health() -> dict[str, Any]:
        """Health check: database status, configuration, and provider environment summary.

        Returns diagnostics about the OC runtime including database reachability,
        config directory status, installed providers, and model config summary.
        """
        report = diagnose_runtime.execute()
        data = asdict(report)
        # Convert datetime to ISO string for JSON serialization
        if data.get("timestamp_utc"):
            data["timestamp_utc"] = data["timestamp_utc"].isoformat()
        if data.get("db_modified_utc"):
            data["db_modified_utc"] = data["db_modified_utc"].isoformat()
        return data

    @mcp.tool()
    @track_tool
    def tool_stats(
        ctx: Context,
        tool_name: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """MCP tool usage statistics.

        Returns per-tool aggregate stats: call_count, avg_latency_ms,
        max_latency_ms, error_count, last_called_at.

        Args:
            tool_name: Optional — filter to a single tool.
            since: Optional — ISO datetime cutoff (only calls after this time).
        """
        container = _get_container(ctx)
        return container.storage.get_mcp_tool_stats(
            tool_name=tool_name,
            since=since,
        )
