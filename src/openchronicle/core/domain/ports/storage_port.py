from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any

from openchronicle.core.domain.models.project import Project


class StoragePort(ABC):
    """Persistence operations for project metadata.

    Memory operations live on `MemoryStorePort`. SqliteStore implements both.
    """

    @abstractmethod
    def init_schema(self) -> None: ...

    @abstractmethod
    def transaction(self) -> AbstractContextManager[Any]: ...

    @abstractmethod
    def add_project(self, project: Project) -> None: ...

    @abstractmethod
    def list_projects(self, name_contains: str | None = None) -> list[Project]:
        """List projects, newest first.

        `name_contains` is a case-insensitive substring match. The value is
        matched literally — LIKE metacharacters inside it are escaped, so a
        project actually named "100%" matches only itself rather than
        everything.
        """
        ...

    @abstractmethod
    def get_project(self, project_id: str) -> Project | None: ...

    @abstractmethod
    def delete_project(self, project_id: str) -> int:
        """Delete a project and all its memories. Returns the number of
        memories deleted in the cascade.

        Atomic — the project row and every memory_items row with this
        project_id are dropped in a single transaction. memory_embeddings
        rows for those memories cascade via the existing FK.

        Raises NotFoundError when the project ID doesn't exist.
        """
        ...

    @abstractmethod
    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        """Update a project's name and/or metadata. Returns the updated row.

        Either ``name`` or ``metadata`` must be non-None; passing both leaves
        any unset field untouched. Raises NotFoundError when the project ID
        doesn't exist.
        """
        ...
