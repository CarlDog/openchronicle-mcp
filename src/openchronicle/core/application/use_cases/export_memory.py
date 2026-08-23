"""Export memory + project state as a portable JSON envelope.

Cross-version-portable disaster recovery surface independent of the
SQLite file format. Pairs with `import_memory` for restore-into-fresh-DB.
"""

from __future__ import annotations

from typing import Any

from openchronicle.core.application.services.git_onboard import WATERMARK_SOURCE
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.time_utils import utc_now

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
    bloats the export by ~6kB per item with no recovery benefit. The
    git-onboard watermark is excluded for the opposite reason: it is
    device-local state that is actively harmful elsewhere (see below).

    Args:
        storage: Project store (StoragePort).
        memory_store: Memory store (MemoryStorePort). In practice both
            are the same SqliteStore but keeping the ports distinct keeps
            this use case adapter-agnostic.
        project_id: Restrict export to a single project. If None, exports
            every project and memory item.
    """
    if project_id is not None:
        scoped = storage.get_project(project_id)
        projects = [scoped] if scoped is not None else []
    else:
        projects = storage.list_projects()

    project_payload = [
        {
            "id": p.id,
            "name": p.name,
            "metadata": p.metadata,
            "created_at": p.created_at.isoformat(),
        }
        for p in projects
    ]

    # Drop the git-onboard watermark: it is one device's git resume
    # point, not portable content. Carried across devices it corrupts
    # incremental onboarding — a stale hash unreachable in the
    # destination clone forces a full re-walk and duplicate cluster
    # memories, one *ahead* of the destination silently skips commits.
    # Filtered here rather than via a port parameter because it is a
    # property of the export format, not of the query.
    items = [
        m
        for m in memory_store.list_memory(limit=None, pinned_only=False, project_id=project_id)
        if m.source != WATERMARK_SOURCE
    ]

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

    # `exported_at` deliberately does NOT bump format_version: import
    # treats it as optional (an envelope written before this field
    # existed still imports), and an envelope carrying it still imports
    # into an older build, which ignores unknown keys. Its only consumer
    # is import's staleness warning.
    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": utc_now().isoformat(),
        "projects": project_payload,
        "memory_items": memory_payload,
    }
