from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any, Protocol

from openchronicle.core.domain.models.project import Project


class Page(Protocol):
    items: list[Any]
    total: int


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
    def list_projects(self) -> list[Project]: ...

    @abstractmethod
    def get_project(self, project_id: str) -> Project | None: ...
