"""Memory tools — search, save, list, pin."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import (
    add_memory,
    delete_memory,
    list_memory,
    pin_memory,
    search_memory,
    update_memory,
)
from openchronicle.core.domain.errors.error_codes import CONVERSATION_NOT_FOUND, MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool
from openchronicle.interfaces.serializers import memory_to_dict


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


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
        tags: list[str] | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search memory items by keyword.

        Args:
            query: Keywords to search for in memory content.
            top_k: Maximum number of results to return (default 8).
            conversation_id: Optional — restrict search to a specific conversation.
            project_id: Optional — restrict search to a specific project.
            tags: Optional — filter results to items having ALL specified tags (AND logic).
        """
        if not query or not query.strip():
            raise DomainValidationError("query must be non-empty")
        top_k = min(max(top_k, 1), 1000)
        offset = max(offset, 0)
        container = _get_container(ctx)
        results = search_memory.execute(
            store=container.storage,
            query=query,
            top_k=top_k,
            conversation_id=conversation_id,
            project_id=project_id,
            tags=tags,
            offset=offset,
            embedding_service=container.embedding_service,
        )
        return [memory_to_dict(m) for m in results]

    @mcp.tool()
    @track_tool
    def memory_save(
        content: str,
        ctx: Context,
        tags: list[str] | None = None,
        pinned: bool = False,
        conversation_id: str | None = None,
        project_id: str | None = None,
        created_at: str | None = None,
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
            created_at: Optional ISO datetime to backdate the memory (e.g. "2026-01-15T12:00:00+00:00").
        """
        if not content or not content.strip():
            raise DomainValidationError("content must be non-empty")
        if len(content) > 100_000:
            raise DomainValidationError("content exceeds maximum length of 100,000 characters")
        container = _get_container(ctx)

        # Derive project_id from conversation if needed
        resolved_project_id = project_id
        if resolved_project_id is None and conversation_id:
            convo = container.storage.get_conversation(conversation_id)
            if convo is None:
                raise NotFoundError(f"Conversation not found: {conversation_id}", code=CONVERSATION_NOT_FOUND)
            resolved_project_id = convo.project_id

        if not resolved_project_id:
            raise DomainValidationError("project_id is required (provide directly or via conversation_id)")

        kwargs: dict[str, Any] = {
            "content": content,
            "tags": tags or [],
            "pinned": pinned,
            "conversation_id": conversation_id,
            "project_id": resolved_project_id,
            "source": "mcp",
        }
        if created_at is not None:
            kwargs["created_at"] = datetime.fromisoformat(created_at)
        item = MemoryItem(**kwargs)
        saved = add_memory.execute(
            store=container.storage,
            emit_event=container.emit_event,
            item=item,
            embedding_service=container.embedding_service,
        )
        return memory_to_dict(saved)

    @mcp.tool()
    @track_tool
    def memory_list(
        ctx: Context,
        limit: int | None = None,
        pinned_only: bool = False,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List memory items.

        Args:
            limit: Maximum number of items to return (None for all).
            pinned_only: If True, only return pinned memories.
        """
        if limit is not None:
            limit = min(max(limit, 1), 10_000)
        offset = max(offset, 0)
        container = _get_container(ctx)
        results = list_memory.execute(
            store=container.storage,
            limit=limit,
            pinned_only=pinned_only,
            offset=offset,
        )
        return [memory_to_dict(m) for m in results]

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
            emit_event=container.emit_event,
            memory_id=memory_id,
            pinned=pinned,
        )
        return {"status": "ok", "memory_id": memory_id, "pinned": str(pinned)}

    @mcp.tool()
    @track_tool
    def memory_update(
        memory_id: str,
        ctx: Context,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing memory item's content and/or tags.

        Preserves identity (id, created_at). Sets updated_at automatically.
        At least one of content or tags must be provided.

        Args:
            memory_id: The ID of the memory to update.
            content: New content (replaces existing). Omit to keep current.
            tags: New tags (replaces existing). Omit to keep current.
        """
        if content is not None and len(content) > 100_000:
            raise DomainValidationError("content exceeds maximum length of 100,000 characters")
        container = _get_container(ctx)
        updated = update_memory.execute(
            store=container.storage,
            emit_event=container.emit_event,
            memory_id=memory_id,
            content=content,
            tags=tags,
            embedding_service=container.embedding_service,
        )
        return memory_to_dict(updated)

    @mcp.tool()
    @track_tool
    def memory_get(
        memory_id: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """Get a single memory item by ID.

        Args:
            memory_id: The ID of the memory to retrieve.
        """
        container = _get_container(ctx)
        item = container.storage.get_memory(memory_id)
        if item is None:
            raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
        return memory_to_dict(item)

    @mcp.tool()
    @track_tool
    def memory_delete(
        memory_id: str,
        ctx: Context,
    ) -> dict[str, str]:
        """Delete a memory item permanently.

        Args:
            memory_id: The ID of the memory to delete.
        """
        container = _get_container(ctx)
        delete_memory.execute(
            store=container.storage,
            emit_event=container.emit_event,
            memory_id=memory_id,
        )
        return {"status": "ok", "memory_id": memory_id}

    @mcp.tool()
    @track_tool
    def memory_stats(
        ctx: Context,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Get memory usage statistics.

        Returns counts of total, pinned, and per-tag/per-source breakdowns.

        Args:
            project_id: Optional — restrict stats to a specific project.
        """
        container = _get_container(ctx)
        all_items = container.storage.list_memory(limit=None, pinned_only=False)
        if project_id:
            all_items = [i for i in all_items if i.project_id == project_id]

        pinned_count = sum(1 for i in all_items if i.pinned)
        by_tag: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for item in all_items:
            for tag in item.tags:
                by_tag[tag] = by_tag.get(tag, 0) + 1
            source = item.source or "unknown"
            by_source[source] = by_source.get(source, 0) + 1

        return {
            "total": len(all_items),
            "pinned": pinned_count,
            "by_tag": by_tag,
            "by_source": by_source,
        }

    @mcp.tool()
    @track_tool
    def memory_embed(
        ctx: Context,
        force: bool = False,
    ) -> dict[str, Any]:
        """Generate embeddings for memories that don't have them.

        Requires OC_EMBEDDING_PROVIDER to be configured (stub, openai, ollama).

        Args:
            force: If True, regenerate all embeddings (e.g. after model change).
        """
        container = _get_container(ctx)
        if container.embedding_service is None:
            return {
                "status": "not_configured",
                "message": "Set OC_EMBEDDING_PROVIDER to enable embeddings.",
            }
        count = container.embedding_service.generate_missing(force=force)
        status = container.embedding_service.embedding_status()
        return {
            "status": "ok",
            "generated": count,
            "force": force,
            **status,
        }
