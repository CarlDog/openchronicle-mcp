"""Context tools — memory-scoped catch-up."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import search_memory
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register context tools on the MCP server."""

    @mcp.tool()
    def context_recent(
        ctx: Context,
        query: str | None = None,
        project_id: str | None = None,
        memory_limit: int = 5,
    ) -> dict[str, Any]:
        """Catch up on prior context for a project: returns recent memory items.

        Use at session start (especially post-compression) to recover decisions,
        rejected approaches, and working state from earlier sessions. Pair with a
        topical `query` to narrow the catch-up to a specific area of work.

        Args:
            query: Keywords to filter memories (optional; omitted = recent overall).
            project_id: Project to scope to (optional).
            memory_limit: Max memory items to return (default 5).
        """
        memory_limit = min(max(memory_limit, 1), 1000)
        container = _get_container(ctx)

        memories = search_memory.execute(
            store=container.storage,
            query=query or "",
            top_k=memory_limit,
            project_id=project_id,
            embedding_service=container.embedding_service,
        )
        return {
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "tags": m.tags,
                    "pinned": m.pinned,
                    "project_id": m.project_id,
                    "created_at": m.created_at.isoformat(),
                }
                for m in memories
            ],
        }
