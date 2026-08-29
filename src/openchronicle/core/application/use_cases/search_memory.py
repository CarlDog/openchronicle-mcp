from __future__ import annotations

from typing import TYPE_CHECKING

from openchronicle.core.application.services import embedding_service as _ranking
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

    ``top_k`` bounds the whole response and ``offset`` paginates one
    ranked stream. Pins are a bounded ranking prior (ADR 0008): a
    pinned row's rank improves by ``min(PIN_RANK_LIFT, top_k)``
    positions inside each channel's honest ranking — the pre-0008
    float (a separate keyword-matched pinned query leading the page,
    bounded by ``pinned_limit``) is gone in every mode. Visibility is
    still ``include_pinned``: ``False`` hides pins outright, and
    ``list_memory(pinned_only=True)`` enumerates standing rules.
    """
    if mode not in VALID_MODES:
        raise DomainValidationError(f"mode must be one of {VALID_MODES}, got {mode!r}")

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
        )

    # mode == "keyword", or hybrid on a keyword-only deployment. Pins
    # are the same bounded ranking prior here (ADR 0008 mode parity):
    # this branch runs precisely when no EmbeddingService exists, so it
    # reads the module constant directly (module-attribute access, so a
    # sweep or test overriding the constant is honored).
    effective_top_k = top_k + offset
    effective_lift = _ranking.effective_pin_lift(top_k, _ranking.PIN_RANK_LIFT)
    # ADR 0008 §2 keyword-only fetch: effective_top_k + effective_lift
    # — this mode had no over-fetch window before the lift, so the
    # extension is the lift's reach and nothing more.
    items = store.search_memory(
        query,
        top_k=effective_top_k + effective_lift,
        project_id=project_id,
        include_pinned=include_pinned,
        tags=tags,
        phrase=phrase,
    )
    ordered = _ranking.lift_single_channel(list(enumerate(items, start=1)), effective_lift)
    # keyword_rank reports the raw pre-lift rank — the only honest
    # per-channel signal; a lifted pin's earlier position is explained
    # by its `pinned` flag, not by rewriting the rank.
    return [
        ScoredMemory(item=item, channel="keyword", keyword_rank=rank) for rank, item in ordered[offset : offset + top_k]
    ]
