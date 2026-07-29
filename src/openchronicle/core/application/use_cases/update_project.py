from __future__ import annotations

from typing import Any

from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(
    *,
    store: StoragePort,
    project_id: str,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Project:
    """Update a project's name and/or metadata. Returns the updated row.

    Mirrors `update_memory`'s shape: at least one of `name` or `metadata`
    must be provided. Validation of "at least one set" lives in the store
    implementation. Raises NotFoundError when the project ID doesn't
    exist.
    """
    return store.update_project(project_id, name=name, metadata=metadata)
