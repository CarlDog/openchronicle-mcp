"""Ollama embedding adapter."""

from __future__ import annotations

import logging
import os

import httpx

from openchronicle.core.domain.errors.error_codes import CONNECTION_ERROR, PROVIDER_ERROR, TIMEOUT
from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.vector_norm import normalize_unit

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
            return [normalize_unit(vec) for vec in embeddings]
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama embedding failed: HTTP {exc.response.status_code}",
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

    def provider_name(self) -> str:
        return "ollama"
