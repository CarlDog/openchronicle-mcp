"""Context tools — recent activity composite."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import search_memory, show_conversation
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register context tools on the MCP server."""

    @mcp.tool()
    @track_tool
    def context_recent(
        ctx: Context,
        conversation_id: str | None = None,
        query: str | None = None,
        turn_limit: int = 5,
        memory_limit: int = 5,
    ) -> dict[str, Any]:
        """Get recent context: conversation turns + relevant memories.

        This is the "what happened last session" tool — ideal for resuming
        work or catching up on prior decisions.

        Args:
            conversation_id: Conversation to retrieve turns from (optional).
            query: Keywords to search memories for (optional).
            turn_limit: Max recent turns to include (default 5).
            memory_limit: Max memory items to include (default 5).
        """
        container = _get_container(ctx)
        result: dict[str, Any] = {}

        # Recent turns
        if conversation_id:
            convo, turns = show_conversation.execute(
                convo_store=container.storage,
                conversation_id=conversation_id,
                limit=turn_limit,
            )
            result["conversation"] = {
                "id": convo.id,
                "title": convo.title,
                "mode": convo.mode,
            }
            result["recent_turns"] = [
                {
                    "turn_index": t.turn_index,
                    "user_text": t.user_text,
                    "assistant_text": t.assistant_text,
                    "created_at": t.created_at.isoformat(),
                }
                for t in turns
            ]

        # Relevant memories
        if query:
            memories = search_memory.execute(
                store=container.storage,
                query=query,
                top_k=memory_limit,
                conversation_id=conversation_id,
            )
            result["memories"] = [
                {
                    "id": m.id,
                    "content": m.content,
                    "tags": m.tags,
                    "pinned": m.pinned,
                    "created_at": m.created_at.isoformat(),
                }
                for m in memories
            ]

        if not result:
            result["message"] = "Provide conversation_id and/or query to retrieve context."

        return result
