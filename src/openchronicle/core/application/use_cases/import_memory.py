"""Import a previously-exported memory JSON envelope into a store.

Modes:
- ``merge`` (default): insert items whose IDs are not already present;
  skip items whose IDs collide. Project rows behave the same way.
- ``replace``: refuse if the destination is non-empty (prevents
  silently overwriting). Caller is expected to back up first and
  start with a fresh store.

Embeddings are not part of the export format (see ``export_memory``); run
``oc memory embed`` after import to regenerate them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openchronicle.core.domain.exceptions import ValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort

VALID_MODES = ("merge", "replace")


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def execute(
    storage: StoragePort,
    memory_store: MemoryStorePort,
    payload: dict[str, Any],
    *,
    mode: str = "merge",
) -> dict[str, int]:
    """Apply ``payload`` to the store. Returns counts of inserted rows.

    Raises ``ValidationError`` for unknown modes, missing ``format_version``,
    or non-empty destinations in ``replace`` mode.
    """
    if mode not in VALID_MODES:
        raise ValidationError(
            f"mode must be one of {VALID_MODES}, got {mode!r}",
        )
    if "format_version" not in payload:
        raise ValidationError("payload missing required 'format_version' field")

    if mode == "replace":
        existing_projects = storage.list_projects()
        existing_memory = memory_store.list_memory(limit=1)
        if existing_projects or existing_memory:
            raise ValidationError(
                "destination is non-empty; refuse to replace. Start with a fresh DB or use mode='merge'.",
            )

    existing_project_ids = {p.id for p in storage.list_projects()}
    existing_memory_ids = {m.id for m in memory_store.list_memory(limit=None)}

    projects_added = 0
    memory_added = 0

    for raw_project in payload.get("projects", []):
        if raw_project["id"] in existing_project_ids:
            continue
        storage.add_project(
            Project(
                id=raw_project["id"],
                name=raw_project["name"],
                metadata=raw_project.get("metadata") or {},
                created_at=_parse_dt(raw_project["created_at"]) or datetime.now(),
            )
        )
        projects_added += 1

    for raw_memory in payload.get("memory_items", []):
        if raw_memory["id"] in existing_memory_ids:
            continue
        memory_store.add_memory(
            MemoryItem(
                id=raw_memory["id"],
                content=raw_memory["content"],
                tags=raw_memory.get("tags") or [],
                pinned=bool(raw_memory.get("pinned", False)),
                project_id=raw_memory.get("project_id"),
                source=raw_memory.get("source") or "import",
                created_at=_parse_dt(raw_memory["created_at"]) or datetime.now(),
                updated_at=_parse_dt(raw_memory.get("updated_at")),
            )
        )
        memory_added += 1

    return {"projects_added": projects_added, "memory_added": memory_added}
