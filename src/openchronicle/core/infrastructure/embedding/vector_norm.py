"""Unit-normalization shared by every embedding adapter.

This carries a load-bearing correctness rule, which is why it is one
function and not three copies (it was byte-identical in all three
adapters until 2026-08-17): ``EmbeddingService._semantic_search`` scores
candidates with a plain dot product on the assumption that **all
adapters normalize at output, so dot product = cosine similarity**. A
new adapter that skips normalization silently breaks ranking — import
this, don't reimplement it.
"""

from __future__ import annotations

import math


def normalize_unit(vec: list[float]) -> list[float]:
    """Scale ``vec`` to unit length; zero vectors pass through unchanged."""
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0:
        return vec
    return [x / mag for x in vec]
