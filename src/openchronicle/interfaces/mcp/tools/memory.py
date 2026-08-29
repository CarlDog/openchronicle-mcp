"""Memory tools — save, search, list, get, update, delete, pin, stats, embed.

Handlers are async and offload store/embedding work via asyncio.to_thread:
FastMCP dispatches sync tools inline on the event loop, so a blocking
embed call (network, up to the provider timeout) would stall every
in-flight request and the maintenance loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import (
    add_memory,
    delete_memory,
    embed_memory,
    list_memory,
    pin_memory,
    search_memory,
    stats_memory,
    update_memory,
)
from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MAX_CONTENT_CHARS, MemoryItem
from openchronicle.interfaces.mcp.tools._context import get_container as _get_container
from openchronicle.interfaces.serializers import memory_to_dict, scored_memory_to_dict


def register(mcp: FastMCP) -> None:
    """Register memory tools on the MCP server."""

    @mcp.tool()
    async def memory_search(
        query: str,
        ctx: Context,
        top_k: int = 8,
        project_id: str | None = None,
        tags: list[str] | None = None,
        offset: int = 0,
        compact: bool = False,
        mode: str = "hybrid",
        phrase: bool = False,
        pinned_limit: int = 10,
        include_pinned: bool = True,
    ) -> list[dict[str, Any]]:
        """Find memory items relevant to a query (hybrid semantic + keyword).

        Use this to look up prior decisions, rejected approaches, or context
        from earlier sessions before re-deriving from scratch. Pair `query`
        with `tags` to narrow by topic. Prefer this over `memory_list` when
        you have keywords; use `memory_list` to enumerate a project and
        `context_recent` for project-scoped session catch-up.

        Scoping note: `project_id` here also surfaces cross-project pinned
        items, because a standing rule that belongs to no single project
        still applies while working inside one. `memory_list` is strict.

        Args:
            query: Keywords or a natural-language question.
            top_k: Maximum number of results, TOTAL — floated pinned
                items count against it (1-1000, default 8).
            project_id: Restrict to a specific project (optional, recommended).
            tags: Require ALL listed tags on each result (AND logic).
            offset: Skip the first N results for pagination.
            compact: Return a content preview instead of full content.
            mode: Retrieval channel — "hybrid" (default; keyword +
                semantic fused via RRF), "keyword" (FTS5 only, never
                touches the embedding provider), or "semantic"
                (embeddings only; errors if no provider is configured
                rather than silently degrading).
            phrase: Match the whole query as one adjacent-token phrase
                on the keyword channel ("does content literally contain
                this") instead of the default any-token match.
            pinned_limit: Cap on how many matching pinned items lead the
                results (default 10, best-matching first), each
                consuming a `top_k` slot. This bounds the FLOAT, not
                visibility: 0 means "don't float them", and a pin that
                doesn't win a slot still ranks normally.
            include_pinned: Visibility switch — false excludes pinned
                items from the results entirely (no float, no ranking;
                scope goes strict). Distinct from `pinned_limit=0`,
                which only stops the float. Use
                `memory_list(pinned_only=true)` to enumerate every
                standing rule.

        Each result carries a `relevance` object: `channel` says what
        surfaced it ("pinned" = a standing rule that matched and was
        floated to the top, no scores);
        `semantic_similarity` (unit cosine, 0-1) is the only roughly
        interpretable score — `rrf_score` is a rank-fusion value, NOT
        calibrated confidence; `keyword_rank` is the 1-based keyword
        position.
        """
        if not query or not query.strip():
            raise DomainValidationError("query must be non-empty")
        top_k = min(max(top_k, 1), 1000)
        offset = max(offset, 0)
        pinned_limit = min(max(pinned_limit, 0), 1000)
        container = _get_container(ctx)

        def _run() -> list[dict[str, Any]]:
            results = search_memory.execute(
                store=container.storage,
                query=query,
                top_k=top_k,
                project_id=project_id,
                tags=tags,
                offset=offset,
                embedding_service=container.embedding_service,
                mode=mode,
                phrase=phrase,
                pinned_limit=pinned_limit,
                include_pinned=include_pinned,
            )
            return [scored_memory_to_dict(s, compact=compact) for s in results]

        return await asyncio.to_thread(_run)

    @mcp.tool()
    async def memory_save(
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
        if len(content) > MAX_CONTENT_CHARS:
            raise DomainValidationError(f"content exceeds maximum length of {MAX_CONTENT_CHARS:,} characters")
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
            try:
                kwargs["created_at"] = datetime.fromisoformat(created_at)
            except ValueError as exc:
                raise DomainValidationError(f"created_at must be an ISO 8601 datetime, got {created_at!r}") from exc
        item = MemoryItem(**kwargs)

        def _run() -> dict[str, Any]:
            saved = add_memory.execute(
                store=container.storage,
                item=item,
                embedding_service=container.embedding_service,
            )
            return memory_to_dict(saved)

        return await asyncio.to_thread(_run)

    @mcp.tool()
    async def memory_list(
        ctx: Context,
        limit: int | None = None,
        pinned_only: bool = False,
        offset: int = 0,
        project_id: str | None = None,
        compact: bool = False,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        order_by: str = "pinned_first",
    ) -> list[dict[str, Any]]:
        """Browse memory items — enumeration, distinct from relevance search.

        Use this for pagination through stored memories — for example,
        "what did I save recently?" or "what is in this project?" Prefer
        `memory_search` when you have keywords. Set `pinned_only=true` to
        enumerate standing rules.

        The one-call recency window: `tags` + `order_by="created_at"` +
        a small `limit` answers "the N newest rows carrying tag X"
        exactly — filters apply in SQL before pagination and pure
        chronology never floats pins into the window.

        Ordering note (default `order_by="pinned_first"`): pinned items
        sort ahead of everything else, so a small `limit` can return
        only pinned rows. Ordering is by `created_at`, which
        `memory_save` lets callers backdate — items imported from git
        history will not appear in a "recent" window. Use `project_id`
        rather than a limit when you want completeness.

        `project_id` is a strict filter: only items belonging to that
        project, never global ones. That differs from `memory_search`,
        where cross-project pinned items surface deliberately because a
        standing rule still applies inside a project.

        Set `compact=true` when browsing rather than reading. It swaps
        `content` for `content_preview` + `content_length`, which is the
        difference between a listing that fits in context and one that
        does not.

        Args:
            limit: Max items to return (1-10,000; None = no limit).
            pinned_only: Only return pinned items.
            offset: Skip the first N items for pagination.
            project_id: Restrict to a specific project (strict; excludes global items).
            compact: Return a content preview instead of full content.
            tags: Require ALL listed tags on each row (AND logic, same
                semantics as `memory_search`).
            exclude_tags: Drop any row carrying ANY of these tags.
            order_by: "pinned_first" (default — pins float, then newest)
                or "created_at" (pure chronology, no pin float).
        """
        if limit is not None:
            limit = min(max(limit, 1), 10_000)
        offset = max(offset, 0)
        container = _get_container(ctx)

        def _run() -> list[dict[str, Any]]:
            results = list_memory.execute(
                store=container.storage,
                limit=limit,
                pinned_only=pinned_only,
                offset=offset,
                project_id=project_id,
                tags=tags,
                exclude_tags=exclude_tags,
                order_by=order_by,
            )
            return [memory_to_dict(m, compact=compact) for m in results]

        return await asyncio.to_thread(_run)

    @mcp.tool()
    async def memory_pin(
        memory_id: str,
        ctx: Context,
        pinned: bool = True,
    ) -> dict[str, str]:
        """Mark a memory as pinned (or unpin it).

        A pinned memory that MATCHES a `memory_search` query is floated
        above the ranked results (up to `pinned_limit`); it is not
        injected into unrelated searches. Use for standing rules,
        conventions, and project-wide invariants, and
        `memory_list(pinned_only=true)` to enumerate them all. Use
        `memory_update` for content/tag edits — pin state is separate.

        Args:
            memory_id: The memory's ID.
            pinned: True to pin, False to unpin (default True).
        """
        container = _get_container(ctx)
        await asyncio.to_thread(
            pin_memory.execute,
            store=container.storage,
            memory_id=memory_id,
            pinned=pinned,
        )
        return {"status": "ok", "memory_id": memory_id, "pinned": str(pinned)}

    @mcp.tool()
    async def memory_update(
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
        if content is not None and len(content) > MAX_CONTENT_CHARS:
            raise DomainValidationError(f"content exceeds maximum length of {MAX_CONTENT_CHARS:,} characters")
        container = _get_container(ctx)

        def _run() -> dict[str, Any]:
            updated = update_memory.execute(
                store=container.storage,
                memory_id=memory_id,
                content=content,
                tags=tags,
                embedding_service=container.embedding_service,
            )
            return memory_to_dict(updated)

        return await asyncio.to_thread(_run)

    @mcp.tool()
    async def memory_get(
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
        item = await asyncio.to_thread(container.storage.get_memory, memory_id)
        if item is None:
            raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
        return memory_to_dict(item)

    @mcp.tool()
    async def memory_delete(
        memory_id: str,
        ctx: Context,
        confirm: bool,
    ) -> dict[str, Any]:
        """Preview or hard-delete a memory item.

        Two-step safety pattern (matches `project_delete`). Call with
        `confirm=false` to see the memory you're about to drop — the
        response has `status: "preview"`, `deleted: false`, a `next_step`
        telling you what to do, plus content, tags, project_id and pinned
        state. Call with `confirm=true` to actually delete; the response is
        `status: "ok"` with `deleted: true`. There is no soft-delete and no
        recovery path beyond `oc db backup` — use `memory_update` if you
        want to revise rather than remove.

        `confirm` has no default: omitting it is an error, not a preview
        request. A preview looks like success to code that doesn't read the
        payload, so silently returning one to a caller who never asked
        would hide a failed delete.

        Args:
            memory_id: The memory's ID.
            confirm: Required. True deletes; false returns a preview.
        """
        container = _get_container(ctx)
        return await asyncio.to_thread(
            delete_memory.execute,
            store=container.storage,
            memory_id=memory_id,
            confirm=confirm,
        )

    @mcp.tool()
    async def memory_stats(
        ctx: Context,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Summarize memory contents: total/pinned counts, breakdowns by tag and source.

        Use to inspect what's stored before a search session, or to verify
        backfill/migration outcomes. Scope to a project for accurate counts
        in multi-project deployments; `project_id` is a strict filter, the
        same rule `memory_list` uses.

        Args:
            project_id: Restrict stats to a specific project (optional).
        """
        container = _get_container(ctx)
        return await asyncio.to_thread(
            stats_memory.execute,
            container.storage,
            project_id,
        )

    @mcp.tool()
    async def memory_embed(
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
        return await asyncio.to_thread(embed_memory.execute, container.embedding_service, force=force)
