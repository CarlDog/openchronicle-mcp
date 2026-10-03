"""Boundary validation for embedding responses, shared by the adapters.

An embedding response is upstream data, not truth. A malformed one has to
fail at the adapter as a ``ProviderError``. Otherwise a NaN, empty or
wrong-length vector is stored against a memory, where it silently corrupts
ranking. Ollama had these checks from the start. The OpenAI adapter, now
the generic path for any OpenAI-compatible host, had none until 2026-09-23
(fleet-review #27): the openai SDK's own parser rejects an empty ``data``
list, but nothing checked the vector count, NaN/Inf, mixed lengths or empty
vectors (corrected 2026-09-23 by the pre-deploy review; an earlier note
here claimed an ``IndexError`` the real SDK never lets happen).
"""

from __future__ import annotations

import math

from openchronicle.core.domain.errors.error_codes import PROVIDER_ERROR
from openchronicle.core.domain.exceptions import ProviderError


def validate_embeddings(
    embeddings: object,
    *,
    expected: int,
    provider: str,
    label: str,
    model: str,
    requested_dimensions: int | None = None,
    dimensions_hint: str = "",
) -> None:
    """Require one non-empty, finite vector per input, all the same length.

    With ``requested_dimensions``, the vectors must also have exactly
    that length. ``label`` names the provider in the message;
    ``provider`` and ``model`` go into the error's details.
    """

    def _fail(reason: str) -> ProviderError:
        return ProviderError(
            f"{label} returned an invalid embedding response: {reason}",
            error_code=PROVIDER_ERROR,
            details={"provider": provider, "model": model},
        )

    if not isinstance(embeddings, list) or len(embeddings) != expected:
        got = len(embeddings) if isinstance(embeddings, list) else type(embeddings).__name__
        raise _fail(f"expected {expected} vector(s), got {got}")
    first_len: int | None = None
    for i, vec in enumerate(embeddings):
        if not isinstance(vec, list) or not vec:
            raise _fail(f"vector {i} is empty or not a list")
        if first_len is None:
            first_len = len(vec)
        elif len(vec) != first_len:
            raise _fail(f"inconsistent dimensions in one batch: {first_len} then {len(vec)}")
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vec):
            raise _fail(f"vector {i} contains non-finite or non-numeric values")
    if requested_dimensions is not None and first_len != requested_dimensions:
        raise _fail(f"requested {requested_dimensions} dimensions, got {first_len}{dimensions_hint}")
