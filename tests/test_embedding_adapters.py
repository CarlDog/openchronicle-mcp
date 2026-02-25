"""Tests for OpenAI and Ollama embedding adapters (mocked HTTP)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import httpx
import pytest

from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter
from openchronicle.core.infrastructure.embedding.openai_adapter import OpenAIEmbeddingAdapter


def _magnitude(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


# ── OpenAI adapter ──────────────────────────────────────────────────────


@dataclass
class _FakeEmbeddingItem:
    embedding: list[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])


@dataclass
class _FakeEmbeddingResponse:
    data: list[_FakeEmbeddingItem] = field(default_factory=lambda: [_FakeEmbeddingItem()])


class TestOpenAIEmbeddingAdapter:
    def _make_adapter(self) -> OpenAIEmbeddingAdapter:
        return OpenAIEmbeddingAdapter(api_key="test-key", dimensions=3, timeout_seconds=5.0)

    def test_returns_normalized_vector(self) -> None:
        adapter = self._make_adapter()
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _FakeEmbeddingResponse()
        adapter._client = mock_client

        vec = adapter.embed("hello")
        assert len(vec) == 3
        assert abs(_magnitude(vec) - 1.0) < 1e-6

    def test_batch_returns_correct_count(self) -> None:
        adapter = self._make_adapter()
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _FakeEmbeddingResponse(
            data=[_FakeEmbeddingItem() for _ in range(3)]
        )
        adapter._client = mock_client

        results = adapter.embed_batch(["a", "b", "c"])
        assert len(results) == 3

    def test_handles_api_error(self) -> None:
        adapter = self._make_adapter()
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = RuntimeError("timeout")
        adapter._client = mock_client

        with pytest.raises(LLMProviderError, match="OpenAI embedding failed"):
            adapter.embed("hello")

    def test_model_name(self) -> None:
        adapter = self._make_adapter()
        assert adapter.model_name() == "text-embedding-3-small"

    def test_dimensions(self) -> None:
        adapter = self._make_adapter()
        assert adapter.dimensions() == 3


# ── Ollama adapter ──────────────────────────────────────────────────────


class TestOllamaEmbeddingAdapter:
    def _make_adapter(self) -> OllamaEmbeddingAdapter:
        return OllamaEmbeddingAdapter(
            model="nomic-embed-text",
            dimensions=768,
            host="http://localhost:11434",
            timeout_seconds=5.0,
        )

    def test_returns_normalized_vector(self) -> None:
        adapter = self._make_adapter()
        response = httpx.Response(
            200,
            json={"embeddings": [[0.5, 0.5, 0.5]]},
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )
        with patch("httpx.post", return_value=response):
            vec = adapter.embed("hello")
            assert len(vec) == 3
            assert abs(_magnitude(vec) - 1.0) < 1e-6

    def test_batch_returns_correct_count(self) -> None:
        adapter = self._make_adapter()
        response = httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]},
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )
        with patch("httpx.post", return_value=response):
            results = adapter.embed_batch(["a", "b", "c"])
            assert len(results) == 3

    def test_handles_connection_error(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(LLMProviderError, match="Ollama connection failed"):
                adapter.embed("hello")

    def test_uses_ollama_host_env(self) -> None:
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://custom:9999"}):
            adapter = OllamaEmbeddingAdapter(model="test")
            assert adapter._host == "http://custom:9999"

    def test_model_name(self) -> None:
        adapter = self._make_adapter()
        assert adapter.model_name() == "nomic-embed-text"

    def test_dimensions(self) -> None:
        adapter = self._make_adapter()
        assert adapter.dimensions() == 768

    def test_handles_http_error(self) -> None:
        adapter = self._make_adapter()
        response = httpx.Response(
            500,
            json={"error": "model not found"},
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )
        with patch("httpx.post", return_value=response):
            with pytest.raises(LLMProviderError, match="Ollama embedding failed"):
                adapter.embed("hello")
