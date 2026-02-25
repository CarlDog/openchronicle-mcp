"""Ollama embedding adapter."""

from __future__ import annotations

import logging
import math
import os

import httpx

from openchronicle.core.domain.errors.error_codes import PROVIDER_ERROR, TIMEOUT
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.ports.llm_port import LLMProviderError

logger = logging.getLogger(__name__)


class OllamaEmbeddingAdapter(EmbeddingPort):
    """Embedding adapter using Ollama's ``/api/embed`` endpoint.

    Supports models like ``nomic-embed-text`` (768 dims),
    ``all-minilm`` (384 dims), etc. Uses ``OLLAMA_HOST`` or
    ``OLLAMA_BASE_URL`` env vars for the server address.
    """

    def __init__(
        self,
        *,
        model: str = "nomic-embed-text",
        dimensions: int = 768,
        host: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._host: str = host or os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        self._timeout = timeout_seconds

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = f"{self._host.rstrip('/')}/api/embed"
        try:
            response = httpx.post(
                url,
                json={"model": self._model, "input": texts},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            embeddings: list[list[float]] = data["embeddings"]
            return [_normalize(vec) for vec in embeddings]
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama embedding failed: HTTP {exc.response.status_code}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": self._model},
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"Ollama connection failed: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "ollama", "host": self._host},
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama embedding failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": self._model},
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
