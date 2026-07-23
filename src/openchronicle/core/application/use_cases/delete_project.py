from __future__ import annotations

from typing import Any

from openchronicle.core.domain.errors.error_codes import PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(
    *,
    store: StoragePort,
    memory_store: MemoryStorePort,
    project_id: str,
    confirm: bool,
) -> dict[str, Any]:
    """Preview or hard-delete a project and its memories.

    Two-step pattern matching the V3_PLAN follow-up shape: `confirm=False`
    returns the project's name and its memory count without touching the
    DB; `confirm=True` cascades and reports how many memories were
    dropped. The cascade happens atomically inside `store.delete_project`.

    `confirm` is required rather than defaulting to False, for the reason
    spelled out in `delete_memory.execute` — a success-shaped preview is a
    bad thing to hand a caller who never asked for one.

    The preview's `name` is load-bearing, not decoration: it is what lets
    a caller working from copied UUIDs confirm the id maps to the project
    they meant before the irreversible call. Keep it in any future variant.
    """
    project = store.get_project(project_id)
    if project is None:
        raise NotFoundError(
            f"Project not found: {project_id}",
            code=PROJECT_NOT_FOUND,
        )
    if not confirm:
        memory_count = memory_store.count_memory(project_id=project_id)
        return {
            "status": "preview",
            "deleted": False,
            "next_step": "Nothing was deleted. Call again with confirm=true to delete this project and its memories.",
            "project_id": project.id,
            "name": project.name,
            "memory_count": memory_count,
        }
    deleted = store.delete_project(project_id)
    return {
        "status": "ok",
        "deleted": True,
        "project_id": project.id,
        "name": project.name,
        "deleted_memories": deleted,
    }
