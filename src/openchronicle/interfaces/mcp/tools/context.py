"""Context tools — recent activity composite."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import assemble_context, search_memory, show_conversation
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool
from openchronicle.interfaces.serializers import assembled_context_to_dict


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
        turn_limit = min(max(turn_limit, 1), 1000)
        memory_limit = min(max(memory_limit, 1), 1000)
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

    @mcp.tool()
    @track_tool
    def context_assemble(
        conversation_id: str,
        prompt: str,
        ctx: Context,
        last_n: int = 10,
        top_k_memory: int = 8,
        include_pinned_memory: bool = True,
    ) -> dict[str, Any]:
        """Assemble context for an external agent without forcing an LLM call.

        Returns messages ready to send to any LLM, plus retrieved memory
        metadata. Use this when your agent handles its own LLM calls but
        wants OC's memory retrieval intelligence.

        Args:
            conversation_id: The conversation to assemble context for.
            prompt: The user message to include.
            last_n: Number of prior turns to include (default 10).
            top_k_memory: Number of memory items to retrieve (default 8).
            include_pinned_memory: Whether to include pinned memories (default True).
        """
        if not prompt or not prompt.strip():
            raise DomainValidationError("prompt must be non-empty")
        if len(prompt) > 200_000:
            raise DomainValidationError("prompt exceeds maximum length of 200,000 characters")
        last_n = min(max(last_n, 1), 1000)
        top_k_memory = min(max(top_k_memory, 1), 1000)
        container = _get_container(ctx)
        result = assemble_context.execute(
            convo_store=container.storage,
            memory_store=container.storage,
            conversation_id=conversation_id,
            prompt_text=prompt,
            last_n=last_n,
            top_k_memory=top_k_memory,
            include_pinned_memory=include_pinned_memory,
        )
        return assembled_context_to_dict(result)
