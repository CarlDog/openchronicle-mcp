"""Memory routes — search, save, list, pin."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from openchronicle.core.application.config.env_helpers import parse_csv_tags  # noqa: F401
from openchronicle.core.application.use_cases import (
    add_memory,
    delete_memory,
    list_memory,
    pin_memory,
    search_memory,
    update_memory,
)
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.serializers import memory_to_dict

router = APIRouter(prefix="/memory")

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


@router.get("/search")
def memory_search(
    container: ContainerDep,
    query: str,
    top_k: int = Query(default=8, ge=1, le=1000),
    project_id: str | None = None,
    tags: str | None = None,
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """Search memory items by keyword.

    Tags parameter accepts comma-separated tag names for AND filtering.
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
    )
    return [memory_to_dict(m) for m in results]


@router.get("/stats")
def memory_stats(
    container: ContainerDep,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Get memory usage statistics."""
    all_items = list_memory.execute(store=container.storage, limit=None, pinned_only=False)
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
        kwargs["created_at"] = datetime.fromisoformat(body.created_at)
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
) -> list[dict[str, Any]]:
    """List memory items."""
    results = list_memory.execute(
        store=container.storage,
        limit=limit,
        pinned_only=pinned_only,
        offset=offset,
    )
    return [memory_to_dict(m) for m in results]


@router.get("/{memory_id}")
def memory_get(
    memory_id: Annotated[str, Path(min_length=1, max_length=200)],
    container: ContainerDep,
) -> dict[str, Any]:
    """Get a single memory item by ID."""
    item = container.storage.get_memory(memory_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
    return memory_to_dict(item)


@router.delete("/{memory_id}")
def memory_delete(
    memory_id: Annotated[str, Path(min_length=1, max_length=200)],
    container: ContainerDep,
) -> dict[str, str]:
    """Delete a memory item permanently."""
    delete_memory.execute(
        store=container.storage,
        memory_id=memory_id,
    )
    return {"status": "ok", "memory_id": memory_id}


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
    if container.embedding_service is None:
        return {
            "status": "not_configured",
            "message": "Set OC_EMBEDDING_PROVIDER to enable embeddings.",
        }
    result = container.embedding_service.generate_missing(force=body.force)
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
        "force": body.force,
        **status,
    }
