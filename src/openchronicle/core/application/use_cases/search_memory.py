from __future__ import annotations

from typing import TYPE_CHECKING

from openchronicle.core.application.services.embedding_service import DEFAULT_PINNED_LIMIT
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.scored_memory import ScoredMemory
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

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

    ``pinned_limit`` bounds the pinned prepend (newest pins first;
    0 disables it like ``include_pinned=False``). Pins beyond the cap
    are omitted entirely — they never re-enter through ranking. Use
    ``list_memory(pinned_only=True)`` to enumerate every standing rule.
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
    items = store.search_memory(
        query,
        top_k=top_k,
        project_id=project_id,
        include_pinned=include_pinned,
        tags=tags,
        offset=offset,
        phrase=phrase,
    )
    # The store prepends pinned items (by policy, unranked) and ranks the
    # rest; item.pinned is exact because the store's ranking excludes
    # pinned rows in SQL. The prepend is capped here rather than in the
    # store so the port surface stays unchanged.
    results: list[ScoredMemory] = []
    rank = 0
    pins_kept = 0
    for item in items:
        if item.pinned:
            if pins_kept < pinned_limit:
                pins_kept += 1
                results.append(ScoredMemory(item=item, channel="pinned"))
        else:
            rank += 1
            results.append(ScoredMemory(item=item, channel="keyword", keyword_rank=offset + rank))
    return results
