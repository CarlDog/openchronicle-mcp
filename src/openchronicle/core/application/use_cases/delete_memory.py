from __future__ import annotations

from typing import Any

from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(
    *,
    store: MemoryStorePort,
    memory_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Preview (confirm=False) or hard-delete (confirm=True) a memory.

    Two-step pattern, symmetric with `delete_project`. `confirm=False` does
    a get-then-return preview so the caller can see what they're about to
    drop (content, tags, project_id, pinned state). `confirm=True` skips
    the extra get and goes straight to `store.delete_memory`, which is
    atomic and raises NotFoundError if the row is missing — the previous
    no-confirm shape relied on that to avoid a TOCTOU window between get
    and delete; we preserve that posture on the delete path.
    """
    if not confirm:
        memory = store.get_memory(memory_id)
        if memory is None:
            raise NotFoundError(
                f"Memory not found: {memory_id}",
                code=MEMORY_NOT_FOUND,
            )
        return {
            "status": "preview",
            "memory_id": memory.id,
            "content": memory.content,
            "tags": memory.tags,
            "project_id": memory.project_id,
            "pinned": memory.pinned,
        }
    store.delete_memory(memory_id)
    return {
        "status": "ok",
        "memory_id": memory_id,
    }
