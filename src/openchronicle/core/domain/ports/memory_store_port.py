from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from openchronicle.core.domain.models.memory_item import MemoryItem

# Ceiling on the pinned float in a single search. Lives here rather than
# in the service or the store because both layers apply it and a second
# copy would drift.
DEFAULT_PINNED_LIMIT = 10


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
      everywhere. Used by `pinned_items`, `search_pinned`, and the
      ranked search's treatment of pinned rows.

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
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        order_by: str = "pinned_first",
    ) -> list[MemoryItem]:
        """List memory items — ENUMERATION, deliberately distinct from search.

        Scope-strict when ``project_id`` is supplied. ``tags`` requires
        ALL listed tags; ``exclude_tags`` drops a row carrying ANY of
        them; both apply in SQL before pagination (a filtered page is a
        page of the filtered set, never a filtered page). ``order_by``:

        - ``"pinned_first"`` (default): pins float, then newest — the
          browsing order this method has always had.
        - ``"created_at"``: pure chronology, NO pin float — "the N most
          recent rows matching these predicates" means exactly that.
          The one-call answer to the Mnemosyne recency-window need that
          previously took a full-project compact scan plus per-row gets.

        Raises ``ValueError`` on an unknown ``order_by``.
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
        phrase: bool = False,
        exclude_ids: set[str] | None = None,
    ) -> list[MemoryItem]:
        """Keyword search, ranked by relevance. No pinned float — see below.

        ``phrase=True`` matches the whole query as one adjacent-token
        phrase ("does the content literally contain this") instead of
        the default any-token match.

        ``include_pinned`` is a VISIBILITY switch, not a float switch:

        - ``True`` (default): pinned rows compete on relevance like any
          other row, scope-with-global (a standing rule belonging to no
          project still applies inside one).
        - ``False``: pinned rows are excluded outright and scope goes
          strict, matching ``list_memory``.

        ``exclude_ids`` drops specific rows before paging. Callers that
        float pins pass the floated ids here so a pin cannot both lead
        the page and consume a slot in the ranking.

        The pinned FLOAT (standing rules lead page one) is application
        policy and lives in the caller. Until 2026-08-23 it lived here as
        a blanket prepend of *every* pin regardless of the query — a
        `top_k=2` search returned 85 pins — and the accompanying
        all-pins exclusion made any pin past the cap unreachable by
        every query. Both defects came from conflating "float" with
        "visible"; keep them separate.
        """
        ...

    @abstractmethod
    def search_pinned(
        self,
        query: str,
        *,
        limit: int = DEFAULT_PINNED_LIMIT,
        project_id: str | None = None,
        tags: list[str] | None = None,
        phrase: bool = False,
    ) -> list[MemoryItem]:
        """Pinned items that MATCH the query — the float set.

        Scope-with-global, same reasoning as ``pinned_items``. Distinct
        from ``pinned_items``, which enumerates pins regardless of the
        query; this is what hybrid and semantic search float, so that a
        pin has to earn its place at the top instead of crowding out the
        results the caller asked for.
        """
        ...

    @abstractmethod
    def eligible_memory_ids(
        self,
        *,
        project_id: str | None = None,
        tags: list[str] | None = None,
    ) -> set[str]:
        """Ids of memories eligible for a search scoped by these predicates.

        Semantic search calls this BEFORE selecting its similarity top-N
        so out-of-scope vectors cannot consume the candidate window (the
        OpenClaw review's filter-after-limit defect: eligibility applied
        only after a global top-N could miss the best in-scope results
        entirely). Scope matches the ranked search's ``include`` mode:
        strict on ``project_id`` plus global pins
        (``pinned AND project_id IS NULL``); ``tags`` is all-of, same as
        ``search_memory``. With neither predicate the answer is "every
        memory", which callers should short-circuit rather than request.
        """
        ...

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
        are included even when a project_id is supplied — a standing rule
        that belongs to no single project still applies while working
        inside one.

        This is the ENUMERATION surface ("what standing rules exist?").
        Search floats pins via ``search_pinned``, which additionally
        requires them to match the query.
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
    def save_embedding(
        self,
        memory_id: str,
        embedding: list[float],
        model: str,
        provider: str,
        content_hash: str,
        model_revision: str | None = None,
        settings_fingerprint: str = "",
    ) -> bool:
        """Compare-and-swap upsert of a memory's vector (ADR 0005).

        Persists only if the memory still exists AND its current content
        hashes to ``content_hash`` — the whole check-and-write is atomic
        under the store lock, closing the slow-older-writer race the
        provider call (outside any lock) makes reachable. Returns True
        when published; False is a NORMAL refusal (content moved on, or
        the memory was deleted mid-flight) — the row stays a backfill
        candidate and callers must not count it as a provider failure.

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
    def get_embedding_identity(self, memory_id: str) -> dict[str, Any] | None:
        """Stored vector identity: provider/model/dimensions/content_hash.

        None when the memory has no vector. Freshness (ADR 0005) is
        judged by comparing this against the active port and the
        memory's current content hash.
        """
        ...

    @abstractmethod
    def stored_embedding_dimensions(self) -> list[int]:
        """Distinct stored vector lengths, ascending — measured fact for
        health's dimensions-truth display (0003 Finding 2)."""
        ...

    @abstractmethod
    def delete_embedding(self, memory_id: str) -> None:
        """Remove the stored embedding for a memory item, if any. Idempotent.

        The content-change invalidation primitive: a vector for content
        that no longer exists must become MISSING, not stay stale — the
        model-string freshness check cannot see it (same model, older
        content), so semantic search would rank the old content
        indefinitely and backfill would skip it forever (the OpenClaw
        review's stale-vector defect). An absent row is a no-op, not an
        error: invalidation runs on every content update, embedded or not.
        """
        ...

    @abstractmethod
    def count_embeddings(self) -> int:
        """Total stored embeddings (SQL COUNT, not a row load)."""
        ...

    @abstractmethod
    def stale_embedding_counts(
        self,
        provider: str,
        model: str,
        settings_fingerprint: str = "",
        model_revision: str | None = None,
    ) -> dict[str, int]:
        """Disjoint staleness buckets against the active space (ADR 0005).

        ``space_mismatch`` (wrong provider/model, migration sentinels
        included) and ``content_mismatch`` (right space, stale content
        hash — counted only among space-matching rows). Their sum is the
        row count a backfill will regenerate; no row is in both.
        """
        ...

    @abstractmethod
    def list_embeddings(
        self,
        memory_ids: list[str] | None = None,
        model: str | None = None,
        provider: str | None = None,
        dimensions: int | None = None,
        settings_fingerprint: str | None = None,
        model_revision: str | None = None,
        match_revision: bool = False,
    ) -> dict[str, list[float]]:
        """Map memory_id → vector, optionally filtered by ids and/or space.

        Semantic search MUST pass the full space identity (``model``,
        ``provider``, ``dimensions``): vectors from different spaces
        either crash the similarity computation (different dims) or
        silently corrupt ranking (same dims), and migration-sentinel
        rows must never rank.
        """
        ...
