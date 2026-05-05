"""Export memory + project state as a portable JSON envelope.

Cross-version-portable disaster recovery surface independent of the
SQLite file format. Pairs with `import_memory` for restore-into-fresh-DB.
"""

from __future__ import annotations

from typing import Any

from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort

EXPORT_FORMAT_VERSION = 1


def execute(
    storage: StoragePort,
    memory_store: MemoryStorePort,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe export of projects + memory items.

    Embeddings are intentionally excluded — they are regenerable from
    content via `oc memory embed` and shipping vector blobs in JSON
    bloats the export by ~6kB per item with no recovery benefit.

    Args:
        storage: Project store (StoragePort).
        memory_store: Memory store (MemoryStorePort). In practice both
            are the same SqliteStore but keeping the ports distinct keeps
            this use case adapter-agnostic.
        project_id: Restrict export to a single project. If None, exports
            every project and memory item.
    """
    projects = storage.list_projects()
    if project_id is not None:
        projects = [p for p in projects if p.id == project_id]

    project_payload = [
        {
            "id": p.id,
            "name": p.name,
            "metadata": p.metadata,
            "created_at": p.created_at.isoformat(),
        }
        for p in projects
    ]

    items = memory_store.list_memory(limit=None, pinned_only=False)
    if project_id is not None:
        items = [m for m in items if m.project_id == project_id]

    memory_payload = [
        {
            "id": m.id,
            "content": m.content,
            "tags": m.tags,
            "pinned": m.pinned,
            "project_id": m.project_id,
            "source": m.source,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in items
    ]

    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "projects": project_payload,
        "memory_items": memory_payload,
    }
