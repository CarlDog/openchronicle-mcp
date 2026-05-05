from __future__ import annotations

from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(store: MemoryStorePort, memory_id: str, pinned: bool) -> None:
    memory = store.get_memory(memory_id)
    if memory is None:
        raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
    store.set_pinned(memory_id, pinned)
