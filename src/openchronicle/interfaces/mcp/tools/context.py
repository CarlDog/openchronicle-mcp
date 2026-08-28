"""Context tools — memory-scoped catch-up.

Handlers are async and offload store/embedding work via asyncio.to_thread:
FastMCP dispatches sync tools inline on the event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import list_memory, search_memory
from openchronicle.interfaces.mcp.tools._context import get_container as _get_container
from openchronicle.interfaces.serializers import memory_to_dict, scored_memory_to_dict


def register(mcp: FastMCP) -> None:
    """Register context tools on the MCP server."""

    @mcp.tool()
    async def context_recent(
        ctx: Context,
        query: str | None = None,
        project_id: str | None = None,
        memory_limit: int = 5,
        compact: bool = False,
    ) -> dict[str, Any]:
        """Catch up on prior context for a project: returns recent memory items.

        Use at session start (especially post-compression) to recover decisions,
        rejected approaches, and working state from earlier sessions. Pair with a
        topical `query` to narrow the catch-up to a specific area of work.

        Args:
            query: Keywords to filter memories (optional; omitted = recent overall).
            project_id: Project to scope to (optional).
            memory_limit: Max memory items to return (default 5).
            compact: Return a content preview instead of full content.
        """
        memory_limit = min(max(memory_limit, 1), 1000)
        container = _get_container(ctx)

        if query:
            scored = await asyncio.to_thread(
                search_memory.execute,
                store=container.storage,
                query=query,
                top_k=memory_limit,
                project_id=project_id,
                embedding_service=container.embedding_service,
            )
            return {"memories": [scored_memory_to_dict(s, compact=compact) for s in scored]}
        # "Omitted = recent overall" must not route through search:
        # FTS5 MATCH returns nothing for an empty query, so on
        # FTS5-active deployments the search path degrades to pinned
        # items only. Recency listing is the honest no-query semantic
        # (pinned first, then newest; scope-strict under project_id).
        memories = await asyncio.to_thread(
            list_memory.execute,
            store=container.storage,
            limit=memory_limit,
            project_id=project_id,
        )
        return {"memories": [memory_to_dict(m, compact=compact) for m in memories]}
