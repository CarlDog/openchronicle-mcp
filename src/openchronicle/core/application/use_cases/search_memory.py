from __future__ import annotations

from typing import TYPE_CHECKING

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.scored_memory import ScoredMemory
from openchronicle.core.domain.ports.memory_store_port import DEFAULT_PINNED_LIMIT, MemoryStorePort

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService

VALID_MODES = ("hybrid", "keyword", "semantic")


def execute(
    store: MemoryStorePort,
    query: str,
    *,
    top_k: int = 8,
    project_id: str | None = None,
    include_pinned: bool = True,
    tags: list[str] | None = None,
    offset: int = 0,
    embedding_service: EmbeddingService | None = None,
    mode: str = "hybrid",
    phrase: bool = False,
    pinned_limit: int = DEFAULT_PINNED_LIMIT,
) -> list[ScoredMemory]:
    """Search memory, returning scored results (Q20/Q21, 2026-08-17).

    ``mode`` selects the retrieval channel per call — before this, the
    hybrid-vs-keyword dispatch was deployment-wide and semantic-only did
    not exist:

    - ``hybrid`` (default): keyword + semantic via RRF when an embedding
      service is configured; keyword-only otherwise (and on provider
      failure — the documented degradation policy).
    - ``keyword``: FTS5/fallback only; never touches the provider.
    - ``semantic``: embedding ranking only; requires a configured
      provider and does NOT degrade silently — the explicit request is
      honored or fails loudly.

    ``phrase`` makes the keyword channel match the whole query as one
    adjacent-token phrase instead of any-token.

    ``pinned_limit`` bounds the pinned FLOAT — pins that match the query
    lead the first page, newest-first, capped. It is not a visibility
    switch: a pin that does not win a float slot still ranks on its
    merits and surfaces with its true channel, and ``pinned_limit=0``
    means "do not float" rather than "hide pins". Use
    ``include_pinned=False`` to hide them, or
    ``list_memory(pinned_only=True)`` to enumerate standing rules.
    """
    if mode not in VALID_MODES:
        raise DomainValidationError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    pinned_limit = max(0, pinned_limit)

    if mode == "semantic":
        if embedding_service is None:
            raise DomainValidationError(
                "mode='semantic' requires an embedding provider; this deployment is "
                "keyword-only (set OC_EMBEDDING_PROVIDER to enable embeddings)"
            )
        return embedding_service.search_semantic(
            query,
            top_k=top_k,
            project_id=project_id,
            include_pinned=include_pinned,
            tags=tags,
            offset=offset,
            pinned_limit=pinned_limit,
        )

    if mode == "hybrid" and embedding_service is not None:
        return embedding_service.search_hybrid(
            query,
            top_k=top_k,
            project_id=project_id,
            include_pinned=include_pinned,
            tags=tags,
            offset=offset,
            phrase=phrase,
            pinned_limit=pinned_limit,
        )

    # mode == "keyword", or hybrid on a keyword-only deployment.
    # The float: pins that MATCH the query, capped, scope-with-global.
    # Computed even when offset > 0 — it is not emitted there, but it is
    # still the exclusion key, or a pin floated on page 1 would reappear
    # in page 2's ranking.
    floated: list[MemoryItem] = []
    if include_pinned and pinned_limit > 0:
        floated = store.search_pinned(
            query,
            limit=pinned_limit,
            project_id=project_id,
            tags=tags,
            phrase=phrase,
        )
    floated_ids = {i.id for i in floated}

    # Pins that did not win a float slot still rank here on their own
    # merits — that is what keeps them reachable, and it is coupled to
    # the exclusion above covering ONLY the floated ids.
    items = store.search_memory(
        query,
        top_k=top_k,
        project_id=project_id,
        include_pinned=include_pinned,
        tags=tags,
        offset=offset,
        phrase=phrase,
        exclude_ids=floated_ids,
    )
    # Floated pins lead the FIRST page only; `offset` paginates the
    # ranking underneath them. A pinned row inside `items` got there by
    # ranking, so it reports channel="keyword" with a real rank — the
    # float set is known by id, never guessed from position.
    results: list[ScoredMemory] = []
    if offset == 0:
        results.extend(ScoredMemory(item=i, channel="pinned") for i in floated)
    for rank, item in enumerate(items, start=1):
        results.append(ScoredMemory(item=item, channel="keyword", keyword_rank=offset + rank))
    return results
