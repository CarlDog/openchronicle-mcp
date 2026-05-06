from __future__ import annotations

from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(store: MemoryStorePort, memory_id: str) -> None:
    """Delete a memory by ID.

    Atomic: store.delete_memory raises NotFoundError if the row is missing,
    which the global exception handler renders as 404. The previous get-
    then-delete shape had a TOCTOU window between the two queries.
    """
    store.delete_memory(memory_id)
