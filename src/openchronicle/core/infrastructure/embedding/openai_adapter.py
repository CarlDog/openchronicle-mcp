"""OpenAI embedding adapter."""

from __future__ import annotations

import logging
import os
from typing import Any

from openchronicle.core.domain.embedding_fingerprint import settings_fingerprint
from openchronicle.core.domain.errors.error_codes import CONTENT_TOO_LONG, MISSING_PACKAGE, PROVIDER_ERROR
from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.vector_norm import normalize_unit

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

# Over-length phrases the 4xx message fallback matches (ADR 0009):
# - "context length" — the SDK-documented `context_length_exceeded`
#   family's wording, kept for hosts that phrase it that way;
# - "maximum input length" — the LIVE OpenAI embeddings rejection,
#   captured 2026-08-29: `BadRequestError`, HTTP 400, `code=None`,
#   "Invalid 'input[0]': maximum input length is 8192 tokens."
#   (the real endpoint sets NO error code, so without the captured
#   phrase the fallback would never fire where it matters most).
_OVERLENGTH_MESSAGE_MARKERS = ("context length", "maximum input length")


def _classify_error(exc: Exception) -> str:
    """Classify an SDK error: over-length content vs provider health (ADR 0009).

    Inspects the SDK error's STRUCTURED attributes (duck-typed, so no
    ``openai`` import is needed here and non-SDK exceptions fall through
    cleanly): ``code == "context_length_exceeded"`` classifies outright;
    otherwise a message-substring fallback applies ONLY to 400-family
    (4xx) errors — an ungated fallback would classify any error whose
    stringification happens to contain a marker phrase. Caveat, accepted
    and documented (ADR 0009 §1): on generic OpenAI-compatible hosts
    (``OPENAI_BASE_URL`` — Voyage, Gemini, Mistral) neither may match;
    the conservative bias means those deployments keep today's
    retry-forever behavior rather than risk a false-permanent.
    """
    if getattr(exc, "code", None) == "context_length_exceeded":
        return CONTENT_TOO_LONG
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and 400 <= status < 500:
        message = str(getattr(exc, "message", None) or exc).lower()
        if any(marker in message for marker in _OVERLENGTH_MESSAGE_MARKERS):
            return CONTENT_TOO_LONG
    return PROVIDER_ERROR


class OpenAIEmbeddingAdapter(EmbeddingPort):
    """Embedding adapter using OpenAI's embeddings API.

    Uses ``text-embedding-3-small`` by default (1536 dims, $0.02/1M tokens).
    Requires the ``openai`` package (installed via ``pip install -e '.[openai]'``).
    """

    def __init__(
        self,
        *,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        # `or` chain coerces empty-string env values to None, then falls back to
        # the SDK's documented default. Empty-string env defeats the SDK's
        # `is None` default-fallback check, so we must always pass an explicit
        # base_url to bypass the SDK's own env read.
        self._api_key = api_key or os.getenv("OPENAI_API_KEY") or None
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
        self._timeout_seconds = timeout_seconds
        self._client = self._build_client()

    def _build_client(self) -> Any:
        try:
            import openai
        except ImportError as exc:
            raise LLMProviderError(
                "openai package not installed",
                error_code=MISSING_PACKAGE,
                hint="Install with: pip install -e '.[openai]'",
            ) from exc
        kwargs: dict[str, Any] = {"base_url": self._base_url, "timeout": self._timeout_seconds}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        return openai.OpenAI(**kwargs)

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            client = self._client
            response = client.embeddings.create(
                input=texts,
                model=self._model,
                dimensions=self._dimensions,
            )
            vectors: list[list[float]] = []
            for item in response.data:
                vectors.append(normalize_unit(item.embedding))
            return vectors
        except Exception as exc:
            _type = type(exc).__name__
            raise LLMProviderError(
                f"OpenAI embedding failed: {_type}: {exc}",
                error_code=_classify_error(exc),
                details={"provider": "openai", "model": self._model},
            ) from exc

    def dimensions(self) -> int:
        return self._dimensions

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return "openai"

    def model_revision(self) -> str | None:
        # OpenAI exposes no per-model revision; rows match by IS NULL.
        return None

    def settings_fingerprint(self) -> str:
        # `dimensions` is always sent (see embed_batch). `base_url` is
        # in the fingerprint because this adapter is the GENERIC
        # OpenAI-compatible path (operator-directed 2026-08-29): pointed
        # at Voyage, Gemini, Mistral, or any /v1/embeddings host via
        # OPENAI_BASE_URL, the same model label can name a different
        # vector space per host — the endpoint IS an embedding-affecting
        # setting. On the default OpenAI URL it is a stable constant.
        return settings_fingerprint({"dimensions": self._dimensions, "base_url": self._base_url})
