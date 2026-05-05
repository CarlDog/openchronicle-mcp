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
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory item.

        Returns True if deleted, False if not found.
        """
        ...

    @abstractmethod
    def list_memory_by_source(self, source: str, project_id: str | None = None) -> list[MemoryItem]:
        """List memory items filtered by source field."""
        ...
