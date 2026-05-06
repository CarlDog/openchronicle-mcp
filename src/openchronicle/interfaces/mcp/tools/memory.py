"""Memory tools — save, search, list, get, update, delete, pin, stats, embed."""

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
from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.serializers import memory_to_dict


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def register(mcp: FastMCP) -> None:
    """Register memory tools on the MCP server."""

    @mcp.tool()
    def memory_search(
        query: str,
        ctx: Context,
        top_k: int = 8,
        project_id: str | None = None,
        tags: list[str] | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Find memory items relevant to a query (hybrid semantic + keyword).

        Use this to look up prior decisions, rejected approaches, or context
        from earlier sessions before re-deriving from scratch. Pair `query`
        with `tags` to narrow by topic. Prefer this over `memory_list` when
        you have keywords; use `memory_list` for unfiltered pagination and
        `context_recent` for project-scoped session catch-up.

        Args:
            query: Keywords or a natural-language question.
            top_k: Maximum number of results (1-1000, default 8).
            project_id: Restrict to a specific project (optional, recommended).
            tags: Require ALL listed tags on each result (AND logic).
            offset: Skip the first N results for pagination.
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
            project_id=project_id,
            tags=tags,
            offset=offset,
            embedding_service=container.embedding_service,
        )
        return [memory_to_dict(m) for m in results]

    @mcp.tool()
    def memory_save(
        content: str,
        ctx: Context,
        project_id: str,
        tags: list[str] | None = None,
        pinned: bool = False,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """Persist a memory item that should outlive the current session.

        Call when a decision is made, an approach is rejected, a milestone
        is completed, or working state should survive context compression.
        Use `pinned=true` for standing rules and conventions that must
        always surface; use `tags` (decision/rejected/milestone/context/
        convention/scope) for retrievability.

        Args:
            content: The text to remember (max 100,000 chars).
            project_id: Project to scope the memory to (required).
            tags: Tags for categorization and `memory_search` filtering.
            pinned: True for standing rules; pinned items always surface.
            created_at: ISO datetime to backdate (e.g. for git-onboard imports).
        """
        if not content or not content.strip():
            raise DomainValidationError("content must be non-empty")
        if len(content) > 100_000:
            raise DomainValidationError("content exceeds maximum length of 100,000 characters")
        if not project_id:
            raise DomainValidationError("project_id is required")
        container = _get_container(ctx)

        kwargs: dict[str, Any] = {
            "content": content,
            "tags": tags or [],
            "pinned": pinned,
            "project_id": project_id,
            "source": "mcp",
        }
        if created_at is not None:
            kwargs["created_at"] = datetime.fromisoformat(created_at)
        item = MemoryItem(**kwargs)
        saved = add_memory.execute(
            store=container.storage,
            item=item,
            embedding_service=container.embedding_service,
        )
        return memory_to_dict(saved)

    @mcp.tool()
    def memory_list(
        ctx: Context,
        limit: int | None = None,
        pinned_only: bool = False,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Browse memory items in reverse-chronological order.

        Use this for unfiltered pagination through stored memories — for
        example, "what did I save recently?" Prefer `memory_search` when
        you have keywords. Set `pinned_only=true` to enumerate standing
        rules.

        Args:
            limit: Max items to return (1-10,000; None = no limit).
            pinned_only: Only return pinned items.
            offset: Skip the first N items for pagination.
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
    def memory_pin(
        memory_id: str,
        ctx: Context,
        pinned: bool = True,
    ) -> dict[str, str]:
        """Mark a memory as pinned (or unpin it).

        Pinned memories always surface in `memory_search` and
        `context_recent` results regardless of relevance ranking. Use for
        standing rules, conventions, and project-wide invariants. Use
        `memory_update` for content/tag edits — pin state is separate.

        Args:
            memory_id: The memory's ID.
            pinned: True to pin, False to unpin (default True).
        """
        container = _get_container(ctx)
        pin_memory.execute(
            store=container.storage,
            memory_id=memory_id,
            pinned=pinned,
        )
        return {"status": "ok", "memory_id": memory_id, "pinned": str(pinned)}

    @mcp.tool()
    def memory_update(
        memory_id: str,
        ctx: Context,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Edit an existing memory's content or tags in place.

        Use this to correct or refine a memory rather than `memory_delete` +
        `memory_save`, which would create a new ID and lose the original
        `created_at`. Identity (id, created_at) is preserved; `updated_at`
        is bumped automatically. Use `memory_pin` to change pin state — this
        tool does not touch it.

        Args:
            memory_id: The memory's ID.
            content: New content (replaces existing). Omit to keep current.
            tags: New tags (replaces existing). Omit to keep current.
        """
        if content is not None and len(content) > 100_000:
            raise DomainValidationError("content exceeds maximum length of 100,000 characters")
        container = _get_container(ctx)
        updated = update_memory.execute(
            store=container.storage,
            memory_id=memory_id,
            content=content,
            tags=tags,
            embedding_service=container.embedding_service,
        )
        return memory_to_dict(updated)

    @mcp.tool()
    def memory_get(
        memory_id: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """Fetch a single memory by ID.

        Use after `memory_search` returns IDs of interest and you need full
        content + metadata for one specific item. For bulk reads, prefer
        `memory_list` or `memory_search`.

        Args:
            memory_id: The memory's ID.
        """
        container = _get_container(ctx)
        item = container.storage.get_memory(memory_id)
        if item is None:
            raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
        return memory_to_dict(item)

    @mcp.tool()
    def memory_delete(
        memory_id: str,
        ctx: Context,
    ) -> dict[str, str]:
        """Permanently delete a memory item.

        Hard delete — no soft-delete recovery. Backups are the recovery path.
        Use `memory_update` instead if you want to revise rather than remove.

        Args:
            memory_id: The memory's ID.
        """
        container = _get_container(ctx)
        delete_memory.execute(
            store=container.storage,
            memory_id=memory_id,
        )
        return {"status": "ok", "memory_id": memory_id}

    @mcp.tool()
    def memory_stats(
        ctx: Context,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Summarize memory contents: total/pinned counts, breakdowns by tag and source.

        Use to inspect what's stored before a search session, or to verify
        backfill/migration outcomes. Scope to a project for accurate counts
        in multi-project deployments.

        Args:
            project_id: Restrict stats to a specific project (optional).
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
    def memory_embed(
        ctx: Context,
        force: bool = False,
    ) -> dict[str, Any]:
        """Generate embeddings for memories that lack them (or regenerate all).

        Embeddings power the semantic half of `memory_search`'s hybrid
        retrieval. Run after migrating from a config without embeddings,
        or with `force=true` after switching embedding model. The
        maintenance loop also backfills periodically — manual invocation
        is for explicit control, not normal operation.

        Args:
            force: Regenerate every embedding from scratch (default False).
        """
        container = _get_container(ctx)
        if container.embedding_service is None:
            return {
                "status": "not_configured",
                "message": "Set OC_EMBEDDING_PROVIDER to enable embeddings.",
            }
        result = container.embedding_service.generate_missing(force=force)
        status = container.embedding_service.embedding_status()
        if result.failed == 0:
            outcome = "ok"
        elif result.generated == 0:
            outcome = "failed"
        else:
            outcome = "partial"
        return {
            "status": outcome,
            "generated": result.generated,
            "failed": result.failed,
            "elapsed_ms": result.elapsed_ms,
            "force": force,
            **status,
        }
