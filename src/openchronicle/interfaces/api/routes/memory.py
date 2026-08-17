"""Memory routes — search, save, list, pin."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from openchronicle.core.application.config.env_helpers import parse_csv_tags  # noqa: F401
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
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.serializers import memory_to_dict, scored_memory_to_dict

router = APIRouter(prefix="/memory")

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


@router.get("/search")
def memory_search(
    container: ContainerDep,
    query: str = Query(min_length=1),
    top_k: int = Query(default=8, ge=1, le=1000),
    project_id: str | None = None,
    tags: str | None = None,
    offset: int = Query(default=0, ge=0),
    compact: bool = False,
    mode: str = Query(default="hybrid", pattern="^(hybrid|keyword|semantic)$"),
    phrase: bool = False,
    pinned_limit: int = Query(default=10, ge=0, le=1000),
) -> list[dict[str, Any]]:
    """Search memory items; each result carries a `relevance` block.

    Tags parameter accepts comma-separated tag names for AND filtering.
    `compact` swaps content for a preview plus its length. `mode`
    selects the retrieval channel (hybrid/keyword/semantic); `phrase`
    makes the keyword channel match the whole query as one
    adjacent-token phrase. `pinned_limit` bounds the pinned prepend
    (newest first; 0 = none) — enumerate all pins via
    `GET /memory?pinned_only=true`.
    """
    tag_list = parse_csv_tags(tags)
    results = search_memory.execute(
        store=container.storage,
        query=query,
        top_k=top_k,
        project_id=project_id,
        tags=tag_list,
        offset=offset,
        embedding_service=container.embedding_service,
        mode=mode,
        phrase=phrase,
        pinned_limit=pinned_limit,
    )
    return [scored_memory_to_dict(s, compact=compact) for s in results]


@router.get("/stats")
def memory_stats(
    container: ContainerDep,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Get memory usage statistics. `project_id` is a strict filter."""
    return stats_memory.execute(container.storage, project_id)


class MemorySaveRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    project_id: str = Field(min_length=1, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=50)
    pinned: bool = False
    created_at: str | None = None


@router.post("")
def memory_save(
    body: MemorySaveRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Save a memory item for persistent retrieval across sessions."""
    kwargs: dict[str, Any] = {
        "content": body.content,
        "tags": body.tags or [],
        "pinned": body.pinned,
        "project_id": body.project_id,
        "source": "api",
    }
    if body.created_at is not None:
        try:
            kwargs["created_at"] = datetime.fromisoformat(body.created_at)
        except ValueError as exc:
            # The global DomainValidationError handler maps this to 422 —
            # a caller typo used to surface as a 500.
            raise DomainValidationError(f"created_at must be an ISO 8601 datetime, got {body.created_at!r}") from exc
    item = MemoryItem(**kwargs)
    saved = add_memory.execute(
        store=container.storage,
        item=item,
        embedding_service=container.embedding_service,
    )
    return memory_to_dict(saved)


@router.get("")
def memory_list(
    container: ContainerDep,
    limit: int | None = Query(default=None, ge=1, le=10_000),
    pinned_only: bool = False,
    offset: int = Query(default=0, ge=0),
    project_id: str | None = None,
    compact: bool = False,
) -> list[dict[str, Any]]:
    """List memory items.

    `project_id` is a strict filter — global (project-less) items are
    excluded. `compact` swaps content for a preview plus its length.
    """
    results = list_memory.execute(
        store=container.storage,
        limit=limit,
        pinned_only=pinned_only,
        offset=offset,
        project_id=project_id,
    )
    return [memory_to_dict(m, compact=compact) for m in results]


@router.get("/{memory_id}")
def memory_get(
    memory_id: Annotated[str, Path(min_length=1, max_length=200)],
    container: ContainerDep,
) -> dict[str, Any]:
    """Get a single memory item by ID."""
    item = container.storage.get_memory(memory_id)
    if item is None:
        # Domain exception, not an inline HTTPException: the global
        # handler adds the "code" field every sibling 404 carries.
        raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
    return memory_to_dict(item)


@router.delete("/{memory_id}")
def memory_delete(
    memory_id: Annotated[str, Path(min_length=1, max_length=200)],
    container: ContainerDep,
    confirm: Annotated[bool, Query(description="Required. True deletes; false returns a preview.")],
) -> dict[str, Any]:
    """Preview (confirm=false) or hard-delete (confirm=true) a memory.

    The preview returns content, tags, project_id, and pinned state
    without touching the DB, alongside `deleted: false` and a `next_step`.
    There is no soft-delete and no recovery path beyond `oc db backup`.

    `confirm` is required — omitting it is a 422, not a preview. A
    success-shaped preview handed to a caller who never asked for one
    reads as a completed delete.
    """
    return delete_memory.execute(
        store=container.storage,
        memory_id=memory_id,
        confirm=confirm,
    )


class MemoryPinRequest(BaseModel):
    pinned: bool = True


@router.put("/{memory_id}/pin")
def memory_pin(
    memory_id: Annotated[str, Path(min_length=1, max_length=200)],
    body: MemoryPinRequest,
    container: ContainerDep,
) -> dict[str, str]:
    """Pin or unpin a memory item."""
    pin_memory.execute(
        store=container.storage,
        memory_id=memory_id,
        pinned=body.pinned,
    )
    return {"status": "ok", "memory_id": memory_id, "pinned": str(body.pinned)}


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    tags: list[str] | None = Field(default=None, max_length=50)


@router.put("/{memory_id}")
def memory_update(
    memory_id: Annotated[str, Path(min_length=1, max_length=200)],
    body: MemoryUpdateRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Update an existing memory item's content and/or tags."""
    updated = update_memory.execute(
        store=container.storage,
        memory_id=memory_id,
        content=body.content,
        tags=body.tags,
        embedding_service=container.embedding_service,
    )
    return memory_to_dict(updated)


class MemoryEmbedRequest(BaseModel):
    force: bool = Field(default=False, description="Regenerate all embeddings")


@router.post("/embed")
def memory_embed(
    container: ContainerDep,
    body: MemoryEmbedRequest = Body(default=MemoryEmbedRequest()),  # noqa: B008
) -> dict[str, Any]:
    """Generate embeddings for memories that don't have them."""
    return embed_memory.execute(container.embedding_service, force=body.force)
