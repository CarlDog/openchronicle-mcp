from __future__ import annotations

from abc import ABC, abstractmethod

from openchronicle.core.domain.models.memory_item import MemoryItem


class MemoryStorePort(ABC):
    @abstractmethod
    def add_memory(self, item: MemoryItem) -> None: ...

    @abstractmethod
    def get_memory(self, memory_id: str) -> MemoryItem | None: ...

    @abstractmethod
    def list_memory(self, limit: int | None = None, pinned_only: bool = False, offset: int = 0) -> list[MemoryItem]: ...

    @abstractmethod
    def count_memory(self, project_id: str | None = None) -> int:
        """Return the total number of memory items, optionally project-scoped.

        Use this for health checks and stats — `list_memory(limit=None)` plus
        `len(...)` pulls every row into Python and is O(N) memory + I/O for a
        question that's O(1) at the SQL layer.
        """
        ...

    @abstractmethod
    def set_pinned(self, memory_id: str, pinned: bool) -> None: ...

    @abstractmethod
    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        """Update a memory item's content and/or tags.

        Sets updated_at. Raises ValueError if not found.
        """
        ...

    @abstractmethod
    def search_memory(
        self,
        query: str,
        *,
        top_k: int = 8,
        project_id: str | None = None,
        include_pinned: bool = True,
        tags: list[str] | None = None,
        offset: int = 0,
    ) -> list[MemoryItem]: ...

    @abstractmethod
    def delete_memory(self, memory_id: str) -> None:
        """Delete a memory item.

        Raises NotFoundError if the memory ID doesn't exist. Consistent with
        set_pinned and update_memory; lets the global API exception handler
        render 404 without per-route try/except.
        """
        ...

    @abstractmethod
    def list_memory_by_source(self, source: str, project_id: str | None = None) -> list[MemoryItem]:
        """List memory items filtered by source field."""
        ...

    @abstractmethod
    def pinned_items(self, project_id: str | None = None) -> list[MemoryItem]:
        """Return all pinned items, optionally project-scoped.

        Pinned items always surface in search results regardless of relevance
        ranking (standing rules / conventions). Cross-project pinned items
        (project_id IS NULL) are included even when a project_id is supplied.
        """
        ...
