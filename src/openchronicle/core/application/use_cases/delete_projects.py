"""Preview or hard-delete several projects in one call.

Deleting 46 stale test projects through the singular `delete_project` cost
92 tool calls under the preview/confirm two-step. This is the batch form.

Two deliberate differences from `delete_project`:

**Missing ids are reported, not raised.** The singular use case raises
NotFoundError; aborting a 46-element batch because one id was mistyped
would force the caller to diff two lists by hand and re-issue the whole
thing — the exact friction a batch exists to remove. `missing` is an
explicit field, and because the preview step runs first, the caller sees
it before anything is deleted.

**Reporting is per-item; durability is all-or-nothing.** The confirm loop
runs inside one `store.transaction()`, so each `delete_project` cascade
nests as a savepoint under a single BEGIN IMMEDIATE. A failure part-way
rolls back the whole batch rather than leaving it half-applied.

`name` is preserved per project in both branches for the same reason it
matters on the singular tool: working from copied UUIDs, the name is what
lets a caller catch a wrong id before the irreversible call. At 46 ids
that check matters more, not less.
"""

from __future__ import annotations

from typing import Any

from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(
    *,
    store: StoragePort,
    memory_store: MemoryStorePort,
    project_ids: list[str],
    confirm: bool,
) -> dict[str, Any]:
    """Preview (confirm=False) or hard-delete (confirm=True) many projects."""
    ordered = list(dict.fromkeys(project_ids))

    found: list[Project] = []
    missing: list[str] = []
    for project_id in ordered:
        project = store.get_project(project_id)
        if project is None:
            missing.append(project_id)
        else:
            found.append(project)

    if not confirm:
        counts = [memory_store.count_memory(project_id=p.id) for p in found]
        return {
            "status": "preview",
            "deleted": False,
            "next_step": ("Nothing was deleted. Check the names under `found`, then call again with confirm=true."),
            "total_requested": len(ordered),
            "found": [
                {"project_id": p.id, "name": p.name, "memory_count": c} for p, c in zip(found, counts, strict=True)
            ],
            "missing": missing,
            "total_memory_count": sum(counts),
        }

    with store.transaction():
        deleted_counts = [store.delete_project(p.id) for p in found]

    return {
        "status": "ok",
        "deleted": True,
        "total_requested": len(ordered),
        "deleted_projects": [
            {"project_id": p.id, "name": p.name, "deleted_memories": c}
            for p, c in zip(found, deleted_counts, strict=True)
        ],
        "missing": missing,
        "total_deleted_memories": sum(deleted_counts),
    }
