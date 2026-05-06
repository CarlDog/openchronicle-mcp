"""OpenAI embedding adapter."""

from __future__ import annotations

import logging
import math
import os
from typing import Any

from openchronicle.core.domain.errors.error_codes import MISSING_PACKAGE, PROVIDER_ERROR
from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


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
                vectors.append(_normalize(item.embedding))
            return vectors
        except Exception as exc:
            _type = type(exc).__name__
            raise LLMProviderError(
                f"OpenAI embedding failed: {_type}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "openai", "model": self._model},
            ) from exc

    def dimensions(self) -> int:
        return self._dimensions

    def model_name(self) -> str:
        return self._model


def _normalize(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0:
        return vec
    return [x / mag for x in vec]
