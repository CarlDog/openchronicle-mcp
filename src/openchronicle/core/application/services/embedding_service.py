"""Embedding service — generates embeddings and performs hybrid search."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.scored_memory import ScoredMemory
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.ports.memory_store_port import DEFAULT_PINNED_LIMIT, MemoryStorePort
from openchronicle.core.domain.time_utils import utc_now

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

    def __init__(self, port: EmbeddingPort, store: MemoryStorePort) -> None:
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
        self._store.save_embedding(memory_id, vec, model=self._port.model_name())

    def generate_missing(self, *, project_id: str | None = None, force: bool = False) -> BackfillResult:
        """Backfill embeddings for memories that don't have one.

        If *force* is True, regenerate all embeddings (model change scenario).
        Individual failures are logged and skipped so the backfill always
        completes — but the failure count is returned so callers can surface
        a partial/total-failure status instead of falsely reporting "ok".
        """
        import time

        items = self._store.list_memory(limit=None, pinned_only=False, project_id=project_id)

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
                self._store.save_embedding(item.id, vec, model=self._port.model_name())
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
        phrase: bool = False,
        pinned_limit: int = DEFAULT_PINNED_LIMIT,
    ) -> list[ScoredMemory]:
        """Hybrid search: FTS5 keyword + embedding similarity via RRF.

        1. Run keyword search (FTS5) for ranked list A
        2. Embed query → cosine similarity → ranked list B
        3. Combine via Reciprocal Rank Fusion
        4. Return top_k results as ScoredMemory (Q20: the fused score,
           per-channel signals, and the producing channel travel with
           each hit instead of being discarded after ordering)

        ``phrase`` applies to the keyword channel only — the query
        embedding already encodes the full phrase on the semantic side.
        """
        effective_top_k = top_k + offset

        # ── Pinned items ────────────────────────────────────────────────
        # The FLOAT set is pins that MATCH the query, capped — not a
        # blanket prepend of every pin. The EXCLUSION set is exactly the
        # floated pins, so an unfloated pin still ranks on its merits
        # through either channel. These two facts are coupled: widening
        # the exclusion back to ALL pins (as it was until 2026-08-23)
        # makes every unfloated pin unreachable by any query, and
        # floating without excluding duplicates it.
        pinned_items: list[MemoryItem] = []
        if include_pinned and pinned_limit > 0:
            pinned_items = self._store.search_pinned(
                query,
                limit=pinned_limit,
                project_id=project_id,
                tags=tags,
                phrase=phrase,
            )

        # Pinned items have separate budget — don't reduce search/RRF limit
        # (prevents pinned items from crowding out query-relevant results)

        pinned_ids = {i.id for i in pinned_items}

        def _page(ranked: list[ScoredMemory]) -> list[ScoredMemory]:
            # The pinned-float pagination rule, in one place for both the
            # hybrid and degraded return paths: floated pins get a
            # separate budget, surface as channel="pinned" (policy, not
            # relevance — no scores), and lead the FIRST page only;
            # `offset` paginates the ranking underneath them.
            page = ranked[offset : offset + top_k]
            if offset == 0:
                return [ScoredMemory(item=i, channel="pinned") for i in pinned_items] + page
            return page

        # ── Keyword search (list A) ─────────────────────────────────────
        # include_pinned mirrors the CALLER's intent (are pins visible at
        # all); exclude_ids drops the ones already floated above. Passing
        # include_pinned=False unconditionally here — as this did until
        # 2026-08-23 — is what kept every unfloated pin invisible to the
        # keyword channel.
        keyword_results = self._store.search_memory(
            query,
            top_k=effective_top_k * 2,  # over-fetch for RRF merge
            project_id=project_id,
            include_pinned=include_pinned,
            tags=tags,
            phrase=phrase,
            exclude_ids=pinned_ids,
        )

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
            self._search_failure_count += 1
            self._last_failure_at = utc_now().isoformat()
            logger.warning(
                "embedding search failed (%d total); degrading to FTS5-only: %s",
                self._search_failure_count,
                exc,
            )
            return _page(_wrap_keyword_ranked(keyword_results))

        # ── RRF merge ──────────────────────────────────────────────────
        keyword_rank: dict[str, int] = {item.id: rank for rank, item in enumerate(keyword_results, start=1)}
        semantic_rank: dict[str, int] = {mid: rank for rank, (mid, _sim) in enumerate(semantic_ranked, start=1)}
        semantic_sim: dict[str, float] = dict(semantic_ranked)

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
            item = item_map[mid]
            # A pin is skipped only if it already floated (avoid a
            # duplicate) or the caller hid pins entirely. An unfloated
            # pin ranks like any other row — that is what makes pins
            # past the float cap reachable at all.
            if item.pinned and (mid in pinned_ids or not include_pinned):
                continue
            # Apply tag filter to semantic-only results
            if tags and not all(t in item.tags for t in tags):
                continue
            # Apply project filter to semantic-only results. Pinned rows
            # are scope-with-global, matching the store's ranked query: a
            # standing rule belonging to no project still applies inside
            # one.
            if project_id and item.project_id != project_id and not (item.pinned and item.project_id is None):
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

        merged: list[ScoredMemory] = []
        for mid, score in rrf_scores[:effective_top_k]:
            kr = keyword_rank.get(mid)
            sim = semantic_sim.get(mid)
            if kr is not None and sim is not None:
                channel = "hybrid"
            elif kr is not None:
                channel = "keyword"
            else:
                channel = "semantic"
            merged.append(
                ScoredMemory(
                    item=item_map[mid],
                    channel=channel,
                    rrf_score=score,
                    semantic_similarity=sim,
                    keyword_rank=kr,
                )
            )
        return _page(merged)

    def _semantic_search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        tags: list[str] | None = None,
        exclude_ids: set[str] | None = None,
        limit: int = 16,
    ) -> list[tuple[str, float]]:
        """Return (memory ID, cosine similarity) ranked by similarity.

        All adapters normalize at output, so dot product = cosine similarity.
        Numpy single-matmul replaces a per-item Python loop; for ~5k memories
        at 1536 dims this is ~50-100x faster than the prior pure-Python path.
        Memory cost is unchanged: list_embeddings still loads the full
        embedding table — that's the architectural ceiling addressed by a
        future move to a vector-indexed store (sqlite-vec).
        """
        import numpy as np

        query_vec = self._port.embed(query)
        # Model-scoped: vectors from other models live in other spaces —
        # a stale row after a model switch either crashed the matmul
        # (different dims) or silently corrupted ranking (same dims).
        all_embeddings = self._store.list_embeddings(model=self._port.model_name())

        if not all_embeddings:
            return []

        ids = [mid for mid in all_embeddings if mid not in exclude_ids] if exclude_ids else list(all_embeddings)
        # Eligibility BEFORE the top-k window: with the filter applied
        # only after selection (as until 2026-08-28), out-of-scope
        # vectors consumed the candidate slots and the best in-scope
        # matches could be missed entirely. The callers' post-filters
        # remain as invariants, but the window itself is now scope-aware.
        if project_id is not None or tags:
            eligible = self._store.eligible_memory_ids(project_id=project_id, tags=tags)
            ids = [mid for mid in ids if mid in eligible]
        if not ids:
            return []

        matrix = np.asarray([all_embeddings[mid] for mid in ids], dtype=np.float32)
        q = np.asarray(query_vec, dtype=np.float32)
        scores = matrix @ q  # (N,) cosine similarities

        # argpartition gives top-k unsorted in O(N); sort the slice for ranks.
        k = min(limit, scores.shape[0])
        top_unsorted = np.argpartition(-scores, k - 1)[:k] if k < scores.shape[0] else np.arange(scores.shape[0])
        top_sorted = top_unsorted[np.argsort(-scores[top_unsorted])]
        # float() — np.float32 is not JSON-serializable downstream.
        return [(ids[i], float(scores[i])) for i in top_sorted]

    def search_semantic(
        self,
        query: str,
        *,
        top_k: int = 8,
        project_id: str | None = None,
        include_pinned: bool = True,
        tags: list[str] | None = None,
        offset: int = 0,
        pinned_limit: int = DEFAULT_PINNED_LIMIT,
    ) -> list[ScoredMemory]:
        """Pure semantic ranking (mode="semantic").

        Unlike ``search_hybrid`` there is NO silent degradation: the
        caller explicitly asked for semantic results, so a provider
        failure raises instead of quietly returning keyword matches.
        """
        # Same float/rank split as search_hybrid: the float set is pins
        # that MATCH the query (keyword-matched via the store), and the
        # exclusion covers only those, so an unfloated pin still ranks
        # semantically below.
        pinned_items: list[MemoryItem] = []
        if include_pinned and pinned_limit > 0:
            pinned_items = self._store.search_pinned(
                query,
                limit=pinned_limit,
                project_id=project_id,
                tags=tags,
            )
        pinned_ids = {i.id for i in pinned_items}

        ranked = self._semantic_search(
            query,
            project_id=project_id,
            tags=tags,
            exclude_ids=pinned_ids,
            limit=(top_k + offset) * 2,  # over-fetch: filters below discard
        )

        results: list[ScoredMemory] = []
        for mid, sim in ranked:
            item = self._store.get_memory(mid)
            if item is None:
                continue
            if item.pinned and not include_pinned:
                continue
            if tags and not all(t in item.tags for t in tags):
                continue
            # Pinned rows are scope-with-global; see search_hybrid.
            if project_id and item.project_id != project_id and not (item.pinned and item.project_id is None):
                continue
            results.append(ScoredMemory(item=item, channel="semantic", semantic_similarity=sim))

        page = results[offset : offset + top_k]
        if offset == 0:
            return [ScoredMemory(item=i, channel="pinned") for i in pinned_items] + page
        return page


def _wrap_keyword_ranked(items: list[MemoryItem], offset: int = 0) -> list[ScoredMemory]:
    """Wrap a keyword-ranked item list as ScoredMemory (channel=keyword).

    ``keyword_rank`` is the 1-based position in the keyword ranking —
    position is the only honest signal the keyword channel has (raw
    bm25 values are unbounded negatives, not worth surfacing).
    """
    return [
        ScoredMemory(item=item, channel="keyword", keyword_rank=offset + rank)
        for rank, item in enumerate(items, start=1)
    ]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product of unit vectors = cosine similarity.

    Kept as a small helper for tests + diagnostic callers. The hot search
    path uses numpy (see _semantic_search).
    """
    return sum(x * y for x, y in zip(a, b, strict=False))
