from __future__ import annotations

from collections.abc import Callable

from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(store: MemoryStorePort, emit_event: Callable[[Event], None], memory_id: str) -> None:
    memory = store.get_memory(memory_id)
    if memory is None:
        raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
    project_id = memory.project_id or ""
    conversation_id = memory.conversation_id
    store.delete_memory(memory_id)
    emit_event(
        Event(
            project_id=project_id,
            task_id=conversation_id,
            type="memory.deleted",
            payload={"memory_id": memory_id},
        )
    )
