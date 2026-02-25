"""System tools — health check, tool usage stats."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import diagnose_runtime
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool
from openchronicle.interfaces.serializers import turn_to_dict


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register system tools on the MCP server."""

    @mcp.tool()
    def health(ctx: Context) -> dict[str, Any]:
        """Health check: database status, configuration, and provider environment summary.

        Returns diagnostics about the OC runtime including database reachability,
        config directory status, installed providers, model config summary,
        and embedding subsystem status.
        """
        report = diagnose_runtime.execute()
        container = _get_container(ctx)
        report.embedding_status = container.embedding_status_dict()
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

    @mcp.tool()
    @track_tool
    def moe_stats(
        ctx: Context,
        winner_provider: str | None = None,
        winner_model: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """MoE (Mixture-of-Experts) usage statistics.

        Returns per-winner-provider/model aggregate stats: run_count,
        avg_agreement_ratio, avg_total_tokens, avg_latency_ms,
        total_failures, last_run_at.

        Args:
            winner_provider: Optional — filter to a single provider.
            winner_model: Optional — filter to a single model.
            since: Optional — ISO datetime cutoff (only runs after this time).
        """
        container = _get_container(ctx)
        return container.storage.get_moe_stats(
            winner_provider=winner_provider,
            winner_model=winner_model,
            since=since,
        )

    @mcp.tool()
    @track_tool
    def search_turns(
        query: str,
        ctx: Context,
        top_k: int = 10,
        conversation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search conversation turns by keyword.

        Args:
            query: Keywords to search for in turn content.
            top_k: Maximum number of results to return (default 10).
            conversation_id: Optional — restrict search to a specific conversation.
        """
        if not query or not query.strip():
            raise DomainValidationError("query must be non-empty")
        top_k = min(max(top_k, 1), 1000)
        container = _get_container(ctx)
        turns = container.storage.search_turns(query, top_k=top_k, conversation_id=conversation_id)
        return [turn_to_dict(t) for t in turns]
