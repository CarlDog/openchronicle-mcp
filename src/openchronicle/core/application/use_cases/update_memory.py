"""Update an existing memory item's content and/or tags."""

from __future__ import annotations

from collections.abc import Callable

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(
    store: MemoryStorePort,
    emit_event: Callable[[Event], None],
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
) -> MemoryItem:
    if content is None and tags is None:
        raise DomainValidationError("At least one of content or tags must be provided")

    updated = store.update_memory(memory_id, content=content, tags=tags)

    updated_fields = [f for f in ("content", "tags") if locals()[f] is not None]
    emit_event(
        Event(
            type="memory.updated",
            project_id=updated.project_id or "",
            payload={"memory_id": memory_id, "updated_fields": updated_fields},
        )
    )
    return updated
