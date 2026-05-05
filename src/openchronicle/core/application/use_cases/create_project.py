from __future__ import annotations

from typing import Any

from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(store: StoragePort, name: str, metadata: dict[str, Any] | None = None) -> Project:
    project = Project(name=name, metadata=metadata or {})
    store.add_project(project)
    return project
