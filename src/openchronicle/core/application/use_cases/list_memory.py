from __future__ import annotations

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(
    store: MemoryStorePort,
    limit: int | None = None,
    pinned_only: bool = False,
    offset: int = 0,
    project_id: str | None = None,
    tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    order_by: str = "pinned_first",
) -> list[MemoryItem]:
    if order_by not in ("pinned_first", "created_at"):
        raise DomainValidationError(f"order_by must be 'pinned_first' or 'created_at', got {order_by!r}")
    return store.list_memory(
        limit=limit,
        pinned_only=pinned_only,
        offset=offset,
        project_id=project_id,
        tags=tags,
        exclude_tags=exclude_tags,
        order_by=order_by,
    )
