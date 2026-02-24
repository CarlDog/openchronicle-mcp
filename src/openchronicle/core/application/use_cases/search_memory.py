from __future__ import annotations

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(
    store: MemoryStorePort,
    query: str,
    *,
    top_k: int = 8,
    conversation_id: str | None = None,
    project_id: str | None = None,
    include_pinned: bool = True,
    tags: list[str] | None = None,
    offset: int = 0,
) -> list[MemoryItem]:
    return store.search_memory(
        query,
        top_k=top_k,
        conversation_id=conversation_id,
        project_id=project_id,
        include_pinned=include_pinned,
        tags=tags,
        offset=offset,
    )
