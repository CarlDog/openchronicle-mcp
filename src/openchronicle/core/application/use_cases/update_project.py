from __future__ import annotations

from typing import Any

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
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
    must be provided — enforced here (the memory twin's pattern) so every
    surface gets the same 422-mapped DomainValidationError; previously
    only REST's Pydantic model checked it and the MCP tool fell through
    to the store's bare ValueError. Raises NotFoundError when the
    project ID doesn't exist.
    """
    if name is None and metadata is None:
        raise DomainValidationError("Provide at least one of name or metadata")
    return store.update_project(project_id, name=name, metadata=metadata)
