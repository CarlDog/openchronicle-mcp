from __future__ import annotations

from collections.abc import Callable

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(store: MemoryStorePort, emit_event: Callable[[Event], None], item: MemoryItem) -> MemoryItem:
    if item.project_id is None:
        raise DomainValidationError("project_id is required for memory events")
    store.add_memory(item)
    emit_event(
        Event(
            project_id=item.project_id,
            task_id=item.conversation_id,
            type="memory.written",
            payload={
                "id": item.id,
                "pinned": item.pinned,
                "tags": item.tags,
                "source": item.source,
                "conversation_id": item.conversation_id,
                "project_id": item.project_id,
            },
        )
    )
    return item
