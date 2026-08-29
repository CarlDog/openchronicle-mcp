"""Embedding service — generates embeddings and performs hybrid search."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.domain.errors.error_codes import CONTENT_TOO_LONG
from openchronicle.core.domain.exceptions import ProviderError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.scored_memory import ScoredMemory
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.time_utils import utc_now

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original RRF paper
_RRF_K = 60

# ── Pin ranking prior (ADR 0008) ────────────────────────────────────
# Pins influence search as a bounded RANK lift, not a float: wherever a
# pinned row appears in a channel's ranked candidate list, its rank
# improves by `effective_lift = min(PIN_RANK_LIFT, top_k)` positions
# before fusion/cut. The old float (a separate keyword-matched pinned
# query leading the page) could consume the entire response on a
# pin-heavy corpus; the lift is relevance-gated and bounded instead.
#
# Deliberately code-only — no env var, no `core.json` key: retuning is
# a code change by design (ADR 0008 §3). 0 = lift disabled, the
# rollout-step-3 default until the §3 tuning sweep lands a winning
# constant (rollout step 4). The benchmark sweep injects other values
# via the `EmbeddingService` constructor; the keyword-only search path
# — which runs precisely when no `EmbeddingService` exists — reads
# this module constant directly.
PIN_RANK_LIFT = 0


def effective_pin_lift(top_k: int, pin_rank_lift: int) -> int:
    """The per-request lift strength: ``min(pin_rank_lift, top_k)``.

    Clamped on ``top_k``, never on ``top_k + offset`` — the lift must
    be offset-invariant so one paginated logical query applies one lift
    (ADR 0008 § Definitions; the rev-3 clamp grew with page depth and
    broke pagination). A small ``top_k`` shrinks the lift; nothing
    errors.
    """
    return max(0, min(pin_rank_lift, top_k))


def lift_single_channel(
    ranked: list[tuple[int, MemoryItem]],
    effective_lift: int,
) -> list[tuple[int, MemoryItem]]:
    """Order one channel's ranked candidates under the pin lift.

    ``ranked`` is ``(original rank, item)`` pairs — ranks are raw
    1-based positions in the channel's fetched ranking. They may carry
    gaps when a caller filtered rows AFTER ranking; the gaps are the
    honest ranks and must not be re-linearized (see the RRF-merge
    comment in ``search_hybrid`` — same rule, same reason).

    Returns the pairs in ADR 0008 §1's single-channel total order
    ``(effective rank, original rank, memory id)``: a lifted pin TIES
    with the row already holding its target rank and sorts after it
    (original rank breaks the tie), so it passes only the rows
    between; pile-ups at the rank-1 floor order by original rank.
    ``effective_lift=0`` is the identity ordering.
    """
    return sorted(
        ranked,
        key=lambda entry: (
            max(1, entry[0] - effective_lift) if entry[1].pinned else entry[0],
            entry[0],
            entry[1].id,
        ),
    )


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

    ``tombstoned`` (ADR 0009) counts rows parked as unembeddable —
    classified permanent outcomes, in NEITHER ``generated`` nor
    ``failed``: a tombstoned-only run is a success (the maintenance
    guard's ``failed and not generated`` doesn't match, ``embed_memory``
    maps it to ``ok``, the CLI exits 0).
    """

    generated: int
    failed: int
    tombstoned: int
    elapsed_ms: int


class EmbeddingService:
    """Coordinates embedding generation and hybrid (FTS5 + semantic) search."""

    def __init__(
        self,
        port: EmbeddingPort,
        store: MemoryStorePort,
        *,
        pin_rank_lift: int | None = None,
        fetch_extension: int | None = None,
    ) -> None:
        self._port = port
        self._store = store
        # ADR 0008: injectable so the benchmark sweep can score many
        # lift cells against one embedded store; production wiring
        # passes nothing and gets the named module default. Resolved at
        # construction time (not def time) so tests can monkeypatch the
        # module constant.
        self._pin_rank_lift = PIN_RANK_LIFT if pin_rank_lift is None else pin_rank_lift
        # Harness-facing (ADR 0008 §3): the sweep's window-only ablation
        # cells extend the candidate fetch by the paired lift cell's
        # effective_lift while disabling the lift itself. When set, the
        # fetch extension follows THIS value (clamped exactly like the
        # lift: min(value, top_k)) while the rank lift keeps following
        # pin_rank_lift. None — production wiring — means the fetch
        # extension follows the lift (ADR 0008 §2).
        self._fetch_extension = fetch_extension
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

    def _fetch_lift(self, top_k: int, effective_lift: int) -> int:
        """The fetch-extension term of ADR 0008 §2's widened window.

        Equal to the lift itself in production (``fetch_extension``
        unset); the sweep's window-only ablation cells override it so
        the fetch widens exactly as if the paired lift were active
        while no rank moves — the §2 fetch-depth side effect and the
        lift's own effect stay separately attributable.
        """
        if self._fetch_extension is None:
            return effective_lift
        return effective_pin_lift(top_k, self._fetch_extension)

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

    @staticmethod
    def _is_content_too_long(exc: Exception) -> bool:
        """Did the adapter classify this failure as over-length content?

        Consulted ONLY in per-item handlers (ADR 0009): the adapter
        classifies wherever the upstream rejection matches — batch or
        single call — but a batch-level ``CONTENT_TOO_LONG`` must never
        attribute the failure to every item, so the batch handler falls
        to the existing per-item isolation retry regardless of code.
        """
        return isinstance(exc, ProviderError) and exc.error_code == CONTENT_TOO_LONG

    def _write_tombstone(self, memory_id: str, content: str) -> bool:
        """Park ``memory_id`` as unembeddable for this exact content.

        The tombstone goes through the SAME CAS as a real save (full
        space identity, the FAILED content's hash, empty vector →
        dimensions 0, ``status='content_too_long'``), so content that
        moved on mid-run refuses cleanly and the row simply stays a
        candidate. One INFO line names the id and the remedy — this is
        a designed outcome, never a traceback (ADR 0009).
        """
        published = self._store.save_embedding(
            memory_id,
            [],
            model=self._port.model_name(),
            provider=self._port.provider_name(),
            content_hash=hash_content(content),
            model_revision=self._port.model_revision(),
            settings_fingerprint=self._port.settings_fingerprint(),
            status="content_too_long",
        )
        if published:
            logger.info(
                "memory %s parked as unembeddable: content exceeds the embedding model's context — "
                "shorten the content, or use a larger-context model (force=true retries it)",
                memory_id,
            )
        else:
            logger.info("tombstone for memory %s not published (content changed or memory deleted)", memory_id)
        return published

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

        A classified ``CONTENT_TOO_LONG`` is a HANDLED outcome (ADR
        0009): the tombstone is written, the INFO line logged, and this
        RETURNS NORMALLY — no raise, no caller traceback, no failure
        counted (nor a success: the counters ignore classified
        outcomes). The save itself already succeeded — the memory is
        stored and FTS5-searchable; health's ``unembeddable`` and the
        INFO line are the surfaces. Transient failures keep the
        raise-on-failure contract unchanged.
        """
        if not force and self._is_current(memory_id, content):
            return

        try:
            vec = self._port.embed(content)
        except Exception as exc:
            if self._is_content_too_long(exc):
                self._write_tombstone(memory_id, content)
                return
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
            return BackfillResult(generated=0, failed=0, tombstoned=0, elapsed_ms=0)

        logger.info(
            "Embedding backfill started: %d candidates (model=%s, force=%s)",
            len(candidates),
            self._port.model_name(),
            force,
        )

        t0 = time.monotonic()
        count = 0
        failed = 0
        tombstoned = 0
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
                    if self._is_content_too_long(exc):
                        # Classified permanent outcome (ADR 0009): park
                        # the row, count it in `tombstoned` ONLY, and
                        # touch neither failure nor success counters. A
                        # CAS-refused tombstone (content moved mid-run)
                        # counts nothing — the row stays a candidate,
                        # mirroring the ok-path refusal.
                        if self._write_tombstone(item.id, item.content):
                            tombstoned += 1
                        continue
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
            "Embedding backfill completed: %d generated, %d failed, %d tombstoned, %dms elapsed",
            count,
            failed,
            tombstoned,
            elapsed_ms,
        )
        return BackfillResult(generated=count, failed=failed, tombstoned=tombstoned, elapsed_ms=elapsed_ms)

    def embedding_status(self) -> dict[str, int]:
        """Return embedding coverage stats.

        ``stale`` is the sum of two DISJOINT buckets (ADR 0005):
        ``space_mismatch`` (wrong provider/model, migration sentinels
        included) + ``content_mismatch`` (right space, stale content
        hash). The old model-string-only predicate under-counted —
        this refinement is the field's documented MINOR change.

        Row classes partition (ADR 0009): every stored row is exactly
        one of {``status='ok'``, current tombstone, non-current
        tombstone}. ``embedded`` counts the ok rows (byte-identical to
        the old all-rows count on any pre-ADR database); current
        tombstones are ``unembeddable``; non-current tombstones are
        genuine candidates and land in the stale buckets. The health
        FIELDS legitimately overlay — an ok-but-stale row is in
        ``embedded`` AND a stale bucket, exactly as before. Cross-field
        relationships: ``stale ⊆ embedded`` no longer holds; what DOES
        hold is ``embedded + tombstones = total rows`` and
        ``missing = total_memories − total rows`` (a tombstone is
        known, not missing); ``stale`` counts regeneration work
        regardless of row status.
        """
        total_memories = self._store.count_memory()
        total_rows = self._store.count_embeddings()
        embedded = self._store.count_embeddings(status="ok")
        buckets = self._store.stale_embedding_counts(
            self._port.provider_name(),
            self._port.model_name(),
            settings_fingerprint=self._port.settings_fingerprint(),
            model_revision=self._port.model_revision(),
        )
        unembeddable = self._store.count_unembeddable_embeddings(
            self._port.provider_name(),
            self._port.model_name(),
            settings_fingerprint=self._port.settings_fingerprint(),
            model_revision=self._port.model_revision(),
        )
        return {
            "total_memories": total_memories,
            "embedded": embedded,
            "missing": total_memories - total_rows,
            "unembeddable": unembeddable,
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
    ) -> list[ScoredMemory]:
        """Hybrid search: FTS5 keyword + embedding similarity via RRF.

        1. Run keyword search (FTS5) for ranked list A
        2. Embed query → cosine similarity → ranked list B
        3. Combine via Reciprocal Rank Fusion
        4. Return the requested page as ScoredMemory (Q20: the fused
           score, per-channel signals, and the producing channel travel
           with each hit instead of being discarded after ordering)

        Pins are a bounded ranking prior (ADR 0008): a pinned row's
        rank in each channel improves by ``effective_lift`` positions
        before fusion — no float, no separate pinned query. RRF
        consumes the collided effective ranks as numbers, and the fused
        stream's total order is (fused score descending, memory id
        ascending) — a deterministic tie-break where set-iteration
        order used to decide.

        ``phrase`` applies to the keyword channel only — the query
        embedding already encodes the full phrase on the semantic side.
        """
        effective_top_k = top_k + offset
        effective_lift = effective_pin_lift(top_k, self._pin_rank_lift)
        # ADR 0008 §2: the candidate fetch extends by the lift's reach
        # so every rank the lift operates on is an honest rank from the
        # fetch itself. At lift 0 this is exactly the old 2× over-fetch.
        fetch = 2 * effective_top_k + self._fetch_lift(top_k, effective_lift)

        # ── Keyword search (list A) ─────────────────────────────────────
        # include_pinned mirrors the CALLER's intent (are pins visible
        # at all); a visible pin competes in this ranking like any
        # other row.
        keyword_results = self._store.search_memory(
            query,
            top_k=fetch,
            project_id=project_id,
            include_pinned=include_pinned,
            tags=tags,
            phrase=phrase,
        )

        # ── Semantic search (list B) ─────────────────────────────────────
        # Embedding-failure degradation: if the provider raises, log it,
        # mark the service degraded, and return FTS5-only results — with
        # the SAME lift and single-channel ordering as keyword mode (ADR
        # 0008 mode parity). The caller never sees the exception;
        # /api/v1/health surfaces the degraded state via the failure
        # counters on the service.
        try:
            semantic_ranked = self._semantic_search(
                query,
                project_id=project_id,
                tags=tags,
                limit=fetch,
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
            if self._is_content_too_long(exc):
                # An over-length QUERY is caller content, not provider
                # health (ADR 0009): degrade to keyword-only without
                # touching either failure counter.
                logger.info("semantic query exceeds the embedding model's context; returning keyword-only results")
                return _page(_wrap_keyword_ranked(keyword_results))
            self._search_failure_count += 1
            self._record_failure("search")
            self._last_search_failure_at = self._last_failure_at
            logger.warning(
                "embedding search failed (%d total); degrading to FTS5-only: %s",
                self._search_failure_count,
                exc,
            )
            degraded = lift_single_channel(list(enumerate(keyword_results, start=1)), effective_lift)
            return [
                ScoredMemory(item=item, channel="keyword", keyword_rank=rank)
                for rank, item in degraded[offset : offset + top_k]
            ]

        # ── RRF merge ──────────────────────────────────────────────────
        # Ranks are raw positions in each channel's FETCHED list — NOT
        # positions after the filters below. Post-filter ranks would
        # close gaps and change RRF scores whenever a filter drops a
        # row, breaking the LIFT=0 identity with the pre-ADR-0008
        # stream (rollout step 3's equivalence claim). Do not "fix"
        # this to post-filter positions.
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

        def _effective_rank(rank: int, pinned: bool) -> int:
            # ADR 0008 §1: a pinned row's rank improves by
            # effective_lift, floored at 1; RRF consumes the collided
            # value as a number (never a re-linearized tuple position).
            return max(1, rank - effective_lift) if pinned else rank

        rrf_scores: list[tuple[str, float]] = []
        for mid in all_ids:
            if mid not in item_map:
                continue
            item = item_map[mid]
            # Visibility gate: the semantic channel has no
            # include_pinned predicate of its own, so a hidden pin is
            # dropped here before it can enter the fusion.
            if item.pinned and not include_pinned:
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
                score += 1.0 / (_RRF_K + _effective_rank(kr, item.pinned))
            if sr is not None:
                score += 1.0 / (_RRF_K + _effective_rank(sr, item.pinned))
            rrf_scores.append((mid, score))

        # Fused total order (ADR 0008 §1): score descending, memory id
        # ascending. Fused-score ties are structural (a keyword-only
        # row and a semantic-only row at the same effective rank score
        # identically), so the id leg is load-bearing — and
        # deterministic where the old set-iteration order was
        # hash-dependent across restarts.
        rrf_scores.sort(key=lambda entry: (-entry[1], entry[0]))

        merged: list[ScoredMemory] = []
        for mid, score in rrf_scores[offset : offset + top_k]:
            kr = keyword_rank.get(mid)
            sim = semantic_sim.get(mid)
            if kr is not None and sim is not None:
                channel = "hybrid"
            elif kr is not None:
                channel = "keyword"
            else:
                channel = "semantic"
            # keyword_rank / semantic_similarity report the RAW
            # per-channel signals (score domains untouched — ADR 0008):
            # under a lift > 0 the fused order can disagree with them,
            # and the row's `pinned` flag is what explains a pin-caused
            # reorder.
            merged.append(
                ScoredMemory(
                    item=item_map[mid],
                    channel=channel,
                    rrf_score=score,
                    semantic_similarity=sim,
                    keyword_rank=kr,
                )
            )
        return merged

    def _semantic_search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        tags: list[str] | None = None,
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

        ids = list(all_embeddings)
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
    ) -> list[ScoredMemory]:
        """Pure semantic ranking (mode="semantic").

        Unlike ``search_hybrid`` there is NO silent degradation: the
        caller explicitly asked for semantic results, so a provider
        failure raises instead of quietly returning keyword matches.

        Pins get the same bounded rank lift as every other mode (ADR
        0008). The reported ``semantic_similarity`` stays raw, so under
        a lift > 0 the order can disagree with it — the row's
        ``pinned`` flag is what explains a pin-caused reorder.
        """
        effective_top_k = top_k + offset
        effective_lift = effective_pin_lift(top_k, self._pin_rank_lift)
        ranked = self._semantic_search(
            query,
            project_id=project_id,
            tags=tags,
            # ADR 0008 §2: the over-fetch (filters below discard)
            # extends by the lift's reach; at lift 0 it is exactly the
            # old 2× window.
            limit=2 * effective_top_k + self._fetch_lift(top_k, effective_lift),
        )

        # Original ranks are raw positions in the FETCHED ranking (see
        # the RRF-merge comment in search_hybrid — same rule, same
        # reason); rows the filters drop leave honest gaps.
        sims: dict[str, float] = {}
        candidates: list[tuple[int, MemoryItem]] = []
        for rank, (mid, sim) in enumerate(ranked, start=1):
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
            sims[item.id] = sim
            candidates.append((rank, item))

        page = lift_single_channel(candidates, effective_lift)[offset : offset + top_k]
        return [ScoredMemory(item=item, channel="semantic", semantic_similarity=sims[item.id]) for _rank, item in page]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product of unit vectors = cosine similarity.

    Kept as a small helper for tests + diagnostic callers. The hot search
    path uses numpy (see _semantic_search).
    """
    return sum(x * y for x, y in zip(a, b, strict=False))
