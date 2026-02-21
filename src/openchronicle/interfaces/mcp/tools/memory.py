"""Memory tools — search, save, list, pin."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import add_memory, list_memory, pin_memory, search_memory
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def _memory_to_dict(m: MemoryItem) -> dict[str, Any]:
    return {
        "id": m.id,
        "content": m.content,
        "tags": m.tags,
        "pinned": m.pinned,
        "conversation_id": m.conversation_id,
        "project_id": m.project_id,
        "source": m.source,
        "created_at": m.created_at.isoformat(),
    }


def register(mcp: FastMCP) -> None:
    """Register memory tools on the MCP server."""

    @mcp.tool()
    @track_tool
    def memory_search(
        query: str,
        ctx: Context,
        top_k: int = 8,
        conversation_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search memory items by keyword.

        Args:
            query: Keywords to search for in memory content.
            top_k: Maximum number of results to return (default 8).
            conversation_id: Optional — restrict search to a specific conversation.
            project_id: Optional — restrict search to a specific project.
        """
        container = _get_container(ctx)
        results = search_memory.execute(
            store=container.storage,
            query=query,
            top_k=top_k,
            conversation_id=conversation_id,
            project_id=project_id,
        )
        return [_memory_to_dict(m) for m in results]

    @mcp.tool()
    @track_tool
    def memory_save(
        content: str,
        ctx: Context,
        tags: list[str] | None = None,
        pinned: bool = False,
        conversation_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Save a memory item for persistent retrieval across sessions.

        Either project_id or conversation_id must be provided. If conversation_id
        is given without project_id, the project is derived from the conversation.

        Args:
            content: The text content to remember.
            tags: Optional list of tags for categorization.
            pinned: If True, memory is always included in context retrieval.
            conversation_id: Optional conversation to associate the memory with.
            project_id: Project to store the memory under.
        """
        container = _get_container(ctx)

        # Derive project_id from conversation if needed
        resolved_project_id = project_id
        if resolved_project_id is None and conversation_id:
            convo = container.storage.get_conversation(conversation_id)
            if convo is None:
                raise ValueError(f"Conversation not found: {conversation_id}")
            resolved_project_id = convo.project_id

        if not resolved_project_id:
            raise ValueError("project_id is required (provide directly or via conversation_id)")

        item = MemoryItem(
            content=content,
            tags=tags or [],
            pinned=pinned,
            conversation_id=conversation_id,
            project_id=resolved_project_id,
            source="mcp",
        )
        saved = add_memory.execute(
            store=container.storage,
            emit_event=container.event_logger.append,
            item=item,
        )
        return _memory_to_dict(saved)

    @mcp.tool()
    @track_tool
    def memory_list(
        ctx: Context,
        limit: int | None = None,
        pinned_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List memory items.

        Args:
            limit: Maximum number of items to return (None for all).
            pinned_only: If True, only return pinned memories.
        """
        container = _get_container(ctx)
        results = list_memory.execute(
            store=container.storage,
            limit=limit,
            pinned_only=pinned_only,
        )
        return [_memory_to_dict(m) for m in results]

    @mcp.tool()
    @track_tool
    def memory_pin(
        memory_id: str,
        ctx: Context,
        pinned: bool = True,
    ) -> dict[str, str]:
        """Pin or unpin a memory item.

        Pinned memories are always included in context retrieval, ensuring
        important information persists across all future interactions.

        Args:
            memory_id: The ID of the memory to pin/unpin.
            pinned: True to pin, False to unpin (default True).
        """
        container = _get_container(ctx)
        pin_memory.execute(
            store=container.storage,
            emit_event=container.event_logger.append,
            memory_id=memory_id,
            pinned=pinned,
        )
        return {"status": "ok", "memory_id": memory_id, "pinned": str(pinned)}
