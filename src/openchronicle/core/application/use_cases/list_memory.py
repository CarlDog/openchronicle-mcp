from __future__ import annotations

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(
    store: MemoryStorePort,
    limit: int | None = None,
    pinned_only: bool = False,
    offset: int = 0,
    project_id: str | None = None,
) -> list[MemoryItem]:
    return store.list_memory(limit=limit, pinned_only=pinned_only, offset=offset, project_id=project_id)
