from __future__ import annotations

from typing import Any

from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


def execute(
    *,
    store: MemoryStorePort,
    memory_id: str,
    confirm: bool,
) -> dict[str, Any]:
    """Preview (confirm=False) or hard-delete (confirm=True) a memory.

    Two-step pattern, symmetric with `delete_project`.

    `confirm` is required rather than defaulting to False. A caller that
    omits it is far more likely to be a client written before the flag
    existed than one asking for a preview, and the preview response is
    success-shaped — so a default turns the omission into a silent no-op.
    That is exactly what bit mnemosyne-mcp: its void-returning wrapper
    reported success while the memory stayed put, and nothing surfaced
    until an integration test recalled the "deleted" entity. A missing
    argument now fails loudly instead.

    `confirm=False` does a get-then-return preview so the caller can see
    what they're about to drop (content, tags, project_id, pinned state),
    and says so in `deleted`/`next_step` for anything that only skims the
    payload. `confirm=True` skips the extra get and goes straight to
    `store.delete_memory`, which is atomic and raises NotFoundError if the
    row is missing — the original one-shot shape relied on that to avoid a
    TOCTOU window between get and delete; we preserve that posture on the
    delete path.
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
            "deleted": False,
            "next_step": "Nothing was deleted. Call again with confirm=true to delete this memory.",
            "memory_id": memory.id,
            "content": memory.content,
            "tags": memory.tags,
            "project_id": memory.project_id,
            "pinned": memory.pinned,
        }
    store.delete_memory(memory_id)
    return {
        "status": "ok",
        "deleted": True,
        "memory_id": memory_id,
    }
