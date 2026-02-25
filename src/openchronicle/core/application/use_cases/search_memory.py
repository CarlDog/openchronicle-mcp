from __future__ import annotations

from typing import TYPE_CHECKING

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService


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
    embedding_service: EmbeddingService | None = None,
) -> list[MemoryItem]:
    if embedding_service is not None:
        return embedding_service.search_hybrid(
            query,
            top_k=top_k,
            conversation_id=conversation_id,
            project_id=project_id,
            include_pinned=include_pinned,
            tags=tags,
            offset=offset,
        )
    return store.search_memory(
        query,
        top_k=top_k,
        conversation_id=conversation_id,
        project_id=project_id,
        include_pinned=include_pinned,
        tags=tags,
        offset=offset,
    )
