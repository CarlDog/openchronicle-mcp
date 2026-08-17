from __future__ import annotations

from abc import ABC, abstractmethod

from openchronicle.core.domain.models.memory_item import MemoryItem


class MemoryStorePort(ABC):
    """Persistence operations for memory items.

    Two project-scoping rules are in play. They look inconsistent side by
    side, but they answer different questions:

    - **scope-strict** (``project_id = ?``) — enumeration and accounting.
      "What is in project X?", "how many?", "delete them all." A row from
      outside the project is simply a wrong answer. Used by `list_memory`,
      `count_memory`, and `list_memory_by_source`.
    - **scope-with-global** (``project_id = ? OR project_id IS NULL``) —
      relevance retrieval. "What should I know while working in X?"
      Standing rules that belong to no single project have to surface
      everywhere. Used by `pinned_items`, and through it, hybrid search.

    One consequence worth stating outright, because it looks like a bug to
    anyone who meets the two rules for the first time:
    ``list_memory(project_id=X, pinned_only=True)`` is scope-strict and so
    returns a different set than ``pinned_items(X)``. That is intended.
    """

    @abstractmethod
    def add_memory(self, item: MemoryItem) -> None: ...

    @abstractmethod
    def get_memory(self, memory_id: str) -> MemoryItem | None: ...

    @abstractmethod
    def list_memory(
        self,
        limit: int | None = None,
        pinned_only: bool = False,
        offset: int = 0,
        project_id: str | None = None,
    ) -> list[MemoryItem]:
        """List memory items, newest first, with pinned items floated to the top.

        Scope-strict when `project_id` is supplied.
        """
        ...

    @abstractmethod
    def count_memory(self, project_id: str | None = None) -> int:
        """Return the total number of memory items, optionally project-scoped.

        Scope-strict when `project_id` is supplied.

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
        """List memory items filtered by source field.

        Scope-strict when `project_id` is supplied.
        """
        ...

    @abstractmethod
    def pinned_items(self, project_id: str | None = None) -> list[MemoryItem]:
        """Return all pinned items, optionally project-scoped.

        Scope-with-global: cross-project pinned items (project_id IS NULL)
        are included even when a project_id is supplied. Pinned items always
        surface in search results regardless of relevance ranking (standing
        rules / conventions), and a standing rule that belongs to no single
        project still applies while working inside one.
        """
        ...

    # ── Embedding persistence ───────────────────────────────────────
    # Embedding rows live beside memory rows (FK + cascade), so the
    # surface belongs on this port. Until 2026-08-17 these methods
    # existed only on SqliteStore and EmbeddingService was typed against
    # the concrete store — the application layer's contract was defined
    # by infrastructure, invisibly to the boundary guard (a
    # TYPE_CHECKING import the old regex scanner couldn't see).

    @abstractmethod
    def save_embedding(self, memory_id: str, embedding: list[float], model: str) -> None:
        """Persist ``embedding`` for a memory item (upsert by memory_id).

        Implementations record the ACTUAL vector length, never a
        caller-supplied claim — a mismatched claim made every read fail
        (the 2026-08-16 dimensions fix).
        """
        ...

    @abstractmethod
    def get_embedding_model(self, memory_id: str) -> str | None:
        """Return the model that produced the stored embedding, or None."""
        ...

    @abstractmethod
    def count_embeddings(self) -> int:
        """Total stored embeddings (SQL COUNT, not a row load)."""
        ...

    @abstractmethod
    def count_stale_embeddings(self, current_model: str) -> int:
        """Count embeddings generated by a model other than ``current_model``."""
        ...

    @abstractmethod
    def list_embeddings(
        self,
        memory_ids: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, list[float]]:
        """Map memory_id → vector, optionally filtered by ids and/or model.

        Semantic search MUST pass ``model``: vectors from different
        models live in different spaces, so mixing them either crashes
        the similarity computation (different dims) or silently corrupts
        ranking (same dims).
        """
        ...
