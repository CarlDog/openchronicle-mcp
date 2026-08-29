"""Ollama embedding adapter — truthful request contract (0003 Phase C).

The pre-Phase-C adapter accepted a ``dimensions`` config it never sent,
inherited Ollama's silent prefix truncation, trusted the response
blindly, and flattened structured errors to ``HTTP <status>``. Every
one of those is now explicit: the request carries the requested
dimensions (when configured) and ``truncate: false`` (an over-length
input fails visibly with Ollama's own actionable message instead of
embedding only a prefix — a partial representation must never
masquerade as full content), and the response is validated at the
boundary before anything is normalized or stored.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any

import httpx

from openchronicle.core.domain.embedding_fingerprint import settings_fingerprint
from openchronicle.core.domain.errors.error_codes import CONNECTION_ERROR, PROVIDER_ERROR, TIMEOUT
from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.vector_norm import normalize_unit

logger = logging.getLogger(__name__)

# Bound on how much of Ollama's structured error body reaches our error
# message: actionable ("input exceeds maximum context length") without
# letting an arbitrary upstream body flood logs.
_ERROR_BODY_LIMIT = 300


class OllamaEmbeddingAdapter(EmbeddingPort):
    """Embedding adapter using Ollama's ``/api/embed`` endpoint.

    ``dimensions=None`` (the default) means "whatever the model natively
    produces" — nothing is requested and the actual vector length is
    recorded as fact downstream. A configured value is SENT with the
    request and the response is validated against it; Ollama reduces and
    renormalizes for smaller values but silently ignores larger ones,
    which is exactly why request and validation travel together.
    """

    def __init__(
        self,
        *,
        model: str = "nomic-embed-text",
        dimensions: int | None = None,
        host: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model = model
        self._requested_dimensions = dimensions
        self._host: str = host or os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        self._timeout = timeout_seconds
        # Lazy, cached, non-fatal capability probe (see _probe). The
        # sentinel distinguishes "never probed" from "probed, no answer".
        self._probed_revision: str | None | object = _UNPROBED

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            # No provider round-trip (and no model load) for an empty batch.
            return []
        url = f"{self._host.rstrip('/')}/api/embed"
        body: dict[str, Any] = {
            "model": self._model,
            "input": texts,
            # Fail-visible, never a silent prefix embedding. The memory
            # and its FTS5 row are unaffected by a refusal; the vector
            # stays a backfill candidate.
            "truncate": False,
        }
        if self._requested_dimensions is not None:
            body["dimensions"] = self._requested_dimensions
        try:
            response = httpx.post(url, json=body, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            self._validate(embeddings, expected=len(texts))
            return [normalize_unit(vec) for vec in embeddings]
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama embedding failed: HTTP {exc.response.status_code}: {_upstream_error(exc.response)}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": self._model},
            ) from exc
        except httpx.ConnectError as exc:
            # Connection-refused is not a timeout — reporting it as one
            # sent operators chasing latency when the service was down.
            raise LLMProviderError(
                f"Ollama connection failed: {type(exc).__name__}: {exc}",
                error_code=CONNECTION_ERROR,
                details={"provider": "ollama", "host": self._host},
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Ollama request timed out: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "ollama", "host": self._host},
            ) from exc
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama embedding failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": self._model},
            ) from exc

    def _validate(self, embeddings: object, *, expected: int) -> None:
        """Boundary validation — the response is upstream data, not truth.

        One vector per input, non-empty, finite floats, consistent
        dimensions across the batch, and agreement with an explicitly
        requested dimension. The old adapter checked none of these; its
        test suite even pinned a 3-element vector as acceptable output
        from a "768-dim" adapter.
        """

        def _fail(reason: str) -> LLMProviderError:
            return LLMProviderError(
                f"Ollama returned an invalid embedding response: {reason}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": self._model},
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
        if self._requested_dimensions is not None and first_len != self._requested_dimensions:
            raise _fail(
                f"requested {self._requested_dimensions} dimensions, got {first_len} — "
                "values above the model's native length are silently ignored by Ollama"
            )

    def dimensions(self) -> int:
        # The requested value when configured; otherwise the common
        # default for the default model — a CLAIM for display. The
        # stored `dimensions` column always records the measured length.
        return self._requested_dimensions if self._requested_dimensions is not None else 768

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "ollama"

    def model_revision(self) -> str | None:
        """Manifest digest behind the model tag, via a cached probe.

        Lazy, cached for the adapter's lifetime, and NON-FATAL: an
        unreachable server or an older Ollama without digest metadata
        yields None (rows then match by IS NULL) rather than failing the
        save path. Never runs on every request.
        """
        if self._probed_revision is _UNPROBED:
            self._probed_revision = self._probe_digest()
        return self._probed_revision  # type: ignore[return-value]

    def _probe_digest(self) -> str | None:
        url = f"{self._host.rstrip('/')}/api/tags"
        try:
            response = httpx.get(url, timeout=min(self._timeout, 5.0))
            response.raise_for_status()
            models = response.json().get("models") or []
        except Exception as exc:
            logger.debug("Ollama capability probe failed (%s); model_revision unavailable", exc)
            return None
        wanted = {self._model, f"{self._model}:latest"}
        for entry in models:
            if isinstance(entry, dict) and entry.get("name") in wanted:
                digest = entry.get("digest")
                return digest if isinstance(digest, str) and digest else None
        logger.debug("Ollama probe: model %r not in /api/tags; model_revision unavailable", self._model)
        return None

    def settings_fingerprint(self) -> str:
        return settings_fingerprint(
            {
                "dimensions": self._requested_dimensions,
                "truncate": False,
            }
        )


def _upstream_error(response: httpx.Response) -> str:
    """Ollama's structured ``{"error": ...}`` body, bounded and safe.

    "input exceeds maximum context length" is actionable; the old
    ``HTTP 400`` was not. Bounded so an arbitrary upstream body cannot
    flood a log line; falls back to a snippet of raw text when the body
    isn't the documented shape.
    """
    try:
        payload = response.json()
        message = payload.get("error") if isinstance(payload, dict) else None
    except Exception:
        message = None
    if not isinstance(message, str) or not message:
        message = response.text or "(no error body)"
    return message[:_ERROR_BODY_LIMIT]


class _Unprobed:
    """Sentinel distinguishing "never probed" from "probed → None"."""


_UNPROBED = _Unprobed()
