"""Embedding service — generates embeddings and performs hybrid search."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original RRF paper
_RRF_K = 60


@dataclass(frozen=True)
class BackfillResult:
    """Outcome of a backfill run.

    The per-item resilience in ``generate_missing`` keeps a single bad item
    from blocking the rest, but it must NOT hide total failure from callers.
    Carrying ``failed`` alongside ``generated`` lets the MCP/API/CLI surfaces
    return an honest status to clients.
    """

    generated: int
    failed: int
    elapsed_ms: int


class EmbeddingService:
    """Coordinates embedding generation and hybrid (FTS5 + semantic) search."""

    def __init__(self, port: EmbeddingPort, store: SqliteStore) -> None:
        self._port = port
        self._store = store
        # Degraded-search bookkeeping — flips on when the embedding
        # provider raises during a search, flips off the next time
        # it succeeds. Surfaced via container.embedding_status_dict
        # for /api/v1/health.
        self._search_failure_count: int = 0
        self._last_failure_at: str | None = None

    @property
    def port(self) -> EmbeddingPort:
        return self._port

    @property
    def search_failure_count(self) -> int:
        return self._search_failure_count

    @property
    def last_failure_at(self) -> str | None:
        return self._last_failure_at

    def generate_for_memory(
        self,
        memory_id: str,
        content: str,
        *,
        force: bool = False,
    ) -> None:
        """Generate and store embedding for a single memory item.

        Skips generation if an embedding already exists with the same model,
        unless ``force`` is True (used when content changes).
        """
        if not force:
            existing_model = self._store.get_embedding_model(memory_id)
            if existing_model == self._port.model_name():
                return

        vec = self._port.embed(content)
        self._store.save_embedding(
            memory_id,
            vec,
            model=self._port.model_name(),
            dimensions=self._port.dimensions(),
        )

    def generate_missing(self, *, project_id: str | None = None, force: bool = False) -> BackfillResult:
        """Backfill embeddings for memories that don't have one.

        If *force* is True, regenerate all embeddings (model change scenario).
        Individual failures are logged and skipped so the backfill always
        completes — but the failure count is returned so callers can surface
        a partial/total-failure status instead of falsely reporting "ok".
        """
        import time

        items = self._store.list_memory(limit=None, pinned_only=False)
        if project_id:
            items = [i for i in items if i.project_id == project_id]

        candidates = []
        for item in items:
            if not force:
                existing_model = self._store.get_embedding_model(item.id)
                if existing_model == self._port.model_name():
                    continue
            candidates.append(item)

        if not candidates:
            logger.info("Embedding backfill: 0 candidates, nothing to do")
            return BackfillResult(generated=0, failed=0, elapsed_ms=0)

        logger.info(
            "Embedding backfill started: %d candidates (model=%s, force=%s)",
            len(candidates),
            self._port.model_name(),
            force,
        )

        t0 = time.monotonic()
        count = 0
        failed = 0
        for item in candidates:
            try:
                vec = self._port.embed(item.content)
                self._store.save_embedding(
                    item.id,
                    vec,
                    model=self._port.model_name(),
                    dimensions=self._port.dimensions(),
                )
                count += 1
            except Exception:
                failed += 1
                logger.warning("Embedding generation failed for memory %s", item.id, exc_info=True)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Embedding backfill completed: %d generated, %d failed, %dms elapsed",
            count,
            failed,
            elapsed_ms,
        )
        return BackfillResult(generated=count, failed=failed, elapsed_ms=elapsed_ms)

    def embedding_status(self) -> dict[str, int]:
        """Return embedding coverage stats."""
        total_memories = self._store.count_memory()
        embedded = self._store.count_embeddings()
        stale = self._store.count_stale_embeddings(self._port.model_name())
        return {
            "total_memories": total_memories,
            "embedded": embedded,
            "missing": total_memories - embedded,
            "stale": stale,
        }

    def search_hybrid(
        self,
        query: str,
        *,
        top_k: int = 8,
        project_id: str | None = None,
        include_pinned: bool = True,
        tags: list[str] | None = None,
        offset: int = 0,
    ) -> list[MemoryItem]:
        """Hybrid search: FTS5 keyword + embedding similarity via RRF.

        1. Run keyword search (FTS5) for ranked list A
        2. Embed query → cosine similarity → ranked list B
        3. Combine via Reciprocal Rank Fusion
        4. Return top_k results
        """
        effective_top_k = top_k + offset

        # ── Pinned items (always included) ──────────────────────────────
        pinned_items: list[MemoryItem] = []
        if include_pinned:
            pinned_items = self._store._fetch_pinned_items(project_id)
            if tags:
                pinned_items = [i for i in pinned_items if all(t in i.tags for t in tags)]

        # Pinned items have separate budget — don't reduce search/RRF limit
        # (prevents pinned items from crowding out query-relevant results)

        pinned_ids = {i.id for i in pinned_items}

        # ── Keyword search (list A) ─────────────────────────────────────
        keyword_results = self._store.search_memory(
            query,
            top_k=effective_top_k * 2,  # over-fetch for RRF merge
            project_id=project_id,
            include_pinned=False,
            tags=tags,
        )
        keyword_results = [i for i in keyword_results if i.id not in pinned_ids]

        # ── Semantic search (list B) ─────────────────────────────────────
        # Embedding-failure degradation: if the provider raises, log it,
        # mark the service degraded, and return FTS5-only results. The
        # caller never sees the exception; /api/v1/health surfaces the
        # degraded state via the failure counters on the service.
        try:
            semantic_ranked = self._semantic_search(
                query,
                project_id=project_id,
                tags=tags,
                exclude_ids=pinned_ids,
                limit=effective_top_k * 2,
            )
            # Successful call clears any prior degraded marker.
            if self._search_failure_count:
                logger.info(
                    "embedding search recovered after %d prior failures",
                    self._search_failure_count,
                )
                self._search_failure_count = 0
        except Exception as exc:
            from datetime import UTC, datetime

            self._search_failure_count += 1
            self._last_failure_at = datetime.now(UTC).isoformat()
            logger.warning(
                "embedding search failed (%d total); degrading to FTS5-only: %s",
                self._search_failure_count,
                exc,
            )
            non_pinned_page = keyword_results[offset : offset + top_k]
            if offset == 0:
                return list(pinned_items) + non_pinned_page
            return non_pinned_page

        # ── RRF merge ──────────────────────────────────────────────────
        keyword_rank: dict[str, int] = {item.id: rank for rank, item in enumerate(keyword_results, start=1)}
        semantic_rank: dict[str, int] = {mid: rank for rank, mid in enumerate(semantic_ranked, start=1)}

        all_ids = set(keyword_rank) | set(semantic_rank)
        # Build lookup for MemoryItem objects
        item_map: dict[str, MemoryItem] = {i.id: i for i in keyword_results}

        # For semantic-only results, fetch MemoryItem from store
        for mid in semantic_rank:
            if mid not in item_map:
                mem = self._store.get_memory(mid)
                if mem:
                    item_map[mid] = mem

        rrf_scores: list[tuple[str, float]] = []
        for mid in all_ids:
            if mid not in item_map:
                continue
            # Apply tag filter to semantic-only results
            if tags and not all(t in item_map[mid].tags for t in tags):
                continue
            # Apply project filter to semantic-only results
            if project_id and item_map[mid].project_id != project_id:
                continue

            kr = keyword_rank.get(mid)
            sr = semantic_rank.get(mid)
            score = 0.0
            if kr is not None:
                score += 1.0 / (_RRF_K + kr)
            if sr is not None:
                score += 1.0 / (_RRF_K + sr)
            rrf_scores.append((mid, score))

        rrf_scores.sort(key=lambda x: x[1], reverse=True)

        merged = [item_map[mid] for mid, _ in rrf_scores[:effective_top_k]]

        # Pinned items prepended on first page only; offset paginates non-pinned results
        non_pinned_page = merged[offset : offset + top_k]
        if offset == 0:
            return list(pinned_items) + non_pinned_page
        return non_pinned_page

    def _semantic_search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        tags: list[str] | None = None,
        exclude_ids: set[str] | None = None,
        limit: int = 16,
    ) -> list[str]:
        """Return memory IDs ranked by cosine similarity to query embedding."""
        query_vec = self._port.embed(query)
        all_embeddings = self._store.list_embeddings()

        if not all_embeddings:
            return []

        # Score all embeddings
        scores: list[tuple[str, float]] = []
        for mid, vec in all_embeddings.items():
            if exclude_ids and mid in exclude_ids:
                continue
            sim = _cosine_similarity(query_vec, vec)
            scores.append((mid, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [mid for mid, _ in scores[:limit]]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product of unit vectors = cosine similarity."""
    return sum(x * y for x, y in zip(a, b, strict=False))
