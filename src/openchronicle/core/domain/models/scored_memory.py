"""Search result value object: a memory item plus how it was found.

Q20 (2026-08-15 review): OC computed RRF scores and cosine similarities
internally and discarded them before returning, so a caller could not
distinguish "confident match" from "least-bad of the top-k window".
Every search path now returns these instead of bare items.
"""

from __future__ import annotations

from dataclasses import dataclass

from openchronicle.core.domain.models.memory_item import MemoryItem


@dataclass(frozen=True)
class ScoredMemory:
    """A search hit and the relevance signals that produced it.

    ``channel`` says which signal(s) surfaced the item:

    - ``keyword`` — FTS5/fallback ranking; ``keyword_rank`` is the
      1-based position in that ranking.
    - ``semantic`` — embedding cosine ranking; ``semantic_similarity``
      is unit-vector cosine (0..1, roughly interpretable).
    - ``hybrid`` — both channels contributed; all fields present.

    (A fourth value, ``pinned``, existed while pins were floated by
    policy; ADR 0008 replaced the float with a bounded rank lift, so
    pins surface through the ranked channels like every other row and
    the value no longer occurs.)

    The per-channel signals stay RAW under the lift: a pinned row can
    order ahead of what its ``keyword_rank``/``semantic_similarity``
    alone would suggest — the item's ``pinned`` flag is what explains
    such a reorder.

    ``rrf_score`` is the fused rank score used for hybrid ordering
    (computed over ADR 0008's effective ranks). It is a rank-fusion
    value (bounded ≈ 2/(k+1)), NOT calibrated confidence — do not
    threshold on it; ``semantic_similarity`` is the only roughly
    interpretable knob. (This caveat is why no ``min_confidence``
    parameter shipped with Q20.)
    """

    item: MemoryItem
    channel: str
    rrf_score: float | None = None
    semantic_similarity: float | None = None
    keyword_rank: int | None = None
