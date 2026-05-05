from __future__ import annotations

from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(store: StoragePort) -> list[Project]:
    return store.list_projects()
