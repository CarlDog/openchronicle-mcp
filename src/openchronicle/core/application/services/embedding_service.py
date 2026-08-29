"""Embedding service — generates embeddings and performs hybrid search."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.domain.exceptions import ProviderError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.scored_memory import ScoredMemory
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.ports.memory_store_port import DEFAULT_PINNED_LIMIT, MemoryStorePort
from openchronicle.core.domain.time_utils import utc_now

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original RRF paper
_RRF_K = 60

# Backfill chunk size (ADR 0005 Phase D / 0003 Finding 3). One
# provider round-trip per chunk instead of per memory — the reliable
# win is fewer HTTP round-trips, not compute parallelism (Ollama runs
# embedding inference with restricted runner parallelism regardless).
# Deliberately NOT derived from Ollama's internal `num_batch`, which
# governs runner token processing, not request items. Bounded because
# one failed input fails Ollama's whole HTTP batch — the smaller the
# chunk, the less work one bad item can take down before the per-item
# fallback isolates it.
_BACKFILL_CHUNK_SIZE = 32


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
        # Degraded-provider bookkeeping. Two counters on purpose:
        # `_search_failure_count` keeps its original search-only meaning
        # (and its health-payload keys), while `_failure_count` covers
        # EVERY provider operation — search, save, backfill. Until
        # 2026-08-28 only search failures existed, so a dead provider
        # with no search traffic read "active" while every save and
        # backfill silently failed (the Ollama review's success-shaped
        # health defect). Any successful provider call clears both.
        self._search_failure_count: int = 0
        self._last_search_failure_at: str | None = None
        self._failure_count: int = 0
        self._last_failure_at: str | None = None
        self._last_failure_op: str | None = None
        # Handle for an operator-started background backfill (the MCP/REST
        # `background=true` path). One at a time per service: a second
        # start while one runs is refused, not queued. Overlap with the
        # maintenance loop's own periodic backfill stays safe regardless —
        # CAS publication makes concurrent runs correct, merely wasteful.
        self._background_backfill: asyncio.Task[BackfillResult] | None = None

    @property
    def backfill_running(self) -> bool:
        """True while an operator-started background backfill is in flight."""
        return self._background_backfill is not None and not self._background_backfill.done()

    def start_background_backfill(self, *, force: bool = False) -> bool:
        """Start ``generate_missing`` on a worker thread; False if one runs.

        Must be called from a running event loop (the MCP tool and the
        REST route both are). Exists because a real reindex takes tens of
        minutes — far past any MCP host tool timeout — so the interactive
        surfaces need started-job semantics; progress is observable in
        health (`stale`/`missing` count down) rather than in this call.
        """
        if self.backfill_running:
            return False
        self._background_backfill = asyncio.get_running_loop().create_task(
            asyncio.to_thread(self.generate_missing, force=force)
        )
        return True

    @property
    def port(self) -> EmbeddingPort:
        return self._port

    @property
    def search_failure_count(self) -> int:
        return self._search_failure_count

    @property
    def failure_count(self) -> int:
        """Consecutive provider failures across every operation."""
        return self._failure_count

    @property
    def last_failure_at(self) -> str | None:
        return self._last_failure_at

    @property
    def last_failure_op(self) -> str | None:
        """Which operation failed last: "search", "save", or "backfill"."""
        return self._last_failure_op

    @property
    def last_search_failure_at(self) -> str | None:
        return self._last_search_failure_at

    def _record_failure(self, op: str) -> None:
        self._failure_count += 1
        self._last_failure_at = utc_now().isoformat()
        self._last_failure_op = op

    def _record_success(self) -> None:
        if self._failure_count:
            logger.info("embedding provider recovered after %d failure(s)", self._failure_count)
        self._failure_count = 0
        self._last_failure_op = None

    def _is_current(self, memory_id: str, content: str) -> bool:
        """ADR 0005 freshness: stored identity matches the active space
        AND the stored content hash matches this content.

        Dimensions are deliberately not compared here — pre-embed, only
        the port's *claimed* dimensions exist (unreliable per 0003); the
        measured check happens at search time via list_embeddings.
        """
        identity = self._store.get_embedding_identity(memory_id)
        if identity is None:
            return False
        return bool(
            identity["provider"] == self._port.provider_name()
            and identity["model"] == self._port.model_name()
            and identity["settings_fingerprint"] == self._port.settings_fingerprint()
            and identity["model_revision"] == self._port.model_revision()
            and identity["content_hash"] == hash_content(content)
        )

    def generate_for_memory(
        self,
        memory_id: str,
        content: str,
        *,
        force: bool = False,
    ) -> None:
        """Generate and store embedding for a single memory item.

        Skips generation when the stored vector is current (same space
        identity, same content hash — ADR 0005), unless ``force``.
        Publication is compare-and-swap: a refusal (content moved on, or
        the memory was deleted mid-flight) is logged and NOT a provider
        failure — the row stays a backfill candidate.
        """
        if not force and self._is_current(memory_id, content):
            return

        try:
            vec = self._port.embed(content)
        except Exception:
            # Counted at the boundary (op="save") so a dead provider is
            # visible in health even when nothing ever searches; the
            # exception still propagates — save-path policy belongs to
            # the caller (update_memory logs and continues).
            self._record_failure("save")
            raise
        published = self._store.save_embedding(
            memory_id,
            vec,
            model=self._port.model_name(),
            provider=self._port.provider_name(),
            content_hash=hash_content(content),
            model_revision=self._port.model_revision(),
            settings_fingerprint=self._port.settings_fingerprint(),
        )
        if not published:
            logger.info("embedding for memory %s not published (content changed or memory deleted)", memory_id)
        self._record_success()

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
            # Currency, not mere existence (ADR 0005): a row in the
            # wrong space or with a stale content hash — including the
            # '' migration sentinels — is a candidate. This is what
            # makes the post-migration reindex just "the next backfill".
            if not force and self._is_current(item.id, item.content):
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
        # Bounded chunks through embed_batch (ADR 0005 Phase D): one
        # provider round-trip per chunk. A failed CHUNK falls back to
        # per-item calls so one bad memory cannot discard its
        # chunk-mates' results — Ollama fails the whole HTTP batch on
        # one bad input, and the old per-item loop's resilience is a
        # contract, not an implementation accident.
        for start in range(0, len(candidates), _BACKFILL_CHUNK_SIZE):
            chunk = candidates[start : start + _BACKFILL_CHUNK_SIZE]
            vectors: list[list[float]] | None
            try:
                vectors = self._port.embed_batch([item.content for item in chunk])
                if len(vectors) != len(chunk):
                    # Boundary distrust at the service too: a wrong
                    # cardinality means per-vector attribution would be
                    # a guess — retry the chunk item-by-item instead.
                    logger.warning(
                        "backfill: batch returned %d vector(s) for %d input(s); retrying per item",
                        len(vectors),
                        len(chunk),
                    )
                    vectors = None
            except Exception as exc:
                # A ProviderError is a KNOWN, categorized failure whose
                # message already carries the actionable upstream detail
                # ("input exceeds maximum context length") — one line,
                # no stack. A backfill against a small-context model can
                # hit hundreds of these; tracebacks at WARNING flooded
                # OC_LOG_FILE with noise for a fully-handled condition
                # (observed 2026-08-29 benchmarking; operator-ratified).
                # Truly unexpected exceptions keep the full traceback.
                is_known = isinstance(exc, ProviderError)
                logger.warning(
                    "backfill: batch of %d failed (%s); retrying per item to isolate the failure",
                    len(chunk),
                    exc,
                    exc_info=not is_known,
                )
                if is_known:
                    logger.debug("backfill: batch failure detail", exc_info=True)
                vectors = None

            for i, item in enumerate(chunk):
                try:
                    vec = vectors[i] if vectors is not None else self._port.embed(item.content)
                    published = self._store.save_embedding(
                        item.id,
                        vec,
                        model=self._port.model_name(),
                        provider=self._port.provider_name(),
                        content_hash=hash_content(item.content),
                        model_revision=self._port.model_revision(),
                        settings_fingerprint=self._port.settings_fingerprint(),
                    )
                    if published:
                        count += 1
                    else:
                        # CAS refusal: the memory changed or vanished
                        # while this batch ran. Not a provider failure —
                        # the next backfill sees the row again.
                        logger.info("backfill: embedding for %s not published (content moved on)", item.id)
                    self._record_success()
                except Exception as exc:
                    failed += 1
                    self._record_failure("backfill")
                    # Same split as the batch path: known ProviderError →
                    # one line with the actionable message, stack at DEBUG.
                    is_known = isinstance(exc, ProviderError)
                    logger.warning(
                        "Embedding generation failed for memory %s: %s",
                        item.id,
                        exc,
                        exc_info=not is_known,
                    )
                    if is_known:
                        logger.debug("backfill: failure detail for %s", item.id, exc_info=True)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Embedding backfill completed: %d generated, %d failed, %dms elapsed",
            count,
            failed,
            elapsed_ms,
        )
        return BackfillResult(generated=count, failed=failed, elapsed_ms=elapsed_ms)

    def embedding_status(self) -> dict[str, int]:
        """Return embedding coverage stats.

        ``stale`` is the sum of two DISJOINT buckets (ADR 0005):
        ``space_mismatch`` (wrong provider/model, migration sentinels
        included) + ``content_mismatch`` (right space, stale content
        hash). The old model-string-only predicate under-counted —
        this refinement is the field's documented MINOR change.
        """
        total_memories = self._store.count_memory()
        embedded = self._store.count_embeddings()
        buckets = self._store.stale_embedding_counts(
            self._port.provider_name(),
            self._port.model_name(),
            settings_fingerprint=self._port.settings_fingerprint(),
            model_revision=self._port.model_revision(),
        )
        return {
            "total_memories": total_memories,
            "embedded": embedded,
            "missing": total_memories - embedded,
            "space_mismatch": buckets["space_mismatch"],
            "content_mismatch": buckets["content_mismatch"],
            "stale": buckets["space_mismatch"] + buckets["content_mismatch"],
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
            # hybrid and degraded return paths: floated pins surface as
            # channel="pinned" (policy, not relevance — no scores) and
            # lead ONE combined stream that `top_k` bounds and `offset`
            # paginates. top_k is a TOTAL response budget (decided
            # 2026-08-28): a floated pin consumes a slot, so a caller
            # asking for 8 gets at most 8 — the pre-decision shape
            # returned top_k ranked hits PLUS up to pinned_limit pins,
            # and the documented "maximum number of results" was false.
            combined = [ScoredMemory(item=i, channel="pinned") for i in pinned_items] + ranked
            return combined[offset : offset + top_k]

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
            self._record_success()
        except Exception as exc:
            self._search_failure_count += 1
            self._record_failure("search")
            self._last_search_failure_at = self._last_failure_at
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
        # Space-scoped (ADR 0005): provider + model + MEASURED query
        # dimensions. A row from another provider under the same label,
        # a migration sentinel, or a different-dims row is invisible to
        # ranking — never mixed in.
        all_embeddings = self._store.list_embeddings(
            model=self._port.model_name(),
            provider=self._port.provider_name(),
            dimensions=len(query_vec),
            settings_fingerprint=self._port.settings_fingerprint(),
            model_revision=self._port.model_revision(),
            match_revision=True,
        )

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

        # Same combined-stream budget as search_hybrid's _page: top_k is
        # the total, floated pins consume slots, offset walks the stream.
        combined = [ScoredMemory(item=i, channel="pinned") for i in pinned_items] + results
        return combined[offset : offset + top_k]


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
