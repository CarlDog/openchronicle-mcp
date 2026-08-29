"""Tests for OpenAI and Ollama embedding adapters (mocked HTTP)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import httpx
import pytest

from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
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

    def test_empty_base_url_env_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENAI_BASE_URL='' (compose ${VAR:-} interpolation) must not break the adapter.

        The OpenAI SDK uses ``is None`` for its default-fallback check, so an
        empty-string env defeats the fallback. We coerce empty to the documented
        default and always pass an explicit base_url to bypass the SDK env read.
        """
        monkeypatch.setenv("OPENAI_BASE_URL", "")
        adapter = OpenAIEmbeddingAdapter(api_key="test-key", dimensions=3)
        assert adapter._base_url == "https://api.openai.com/v1"

    def test_unset_base_url_env_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        adapter = OpenAIEmbeddingAdapter(api_key="test-key", dimensions=3)
        assert adapter._base_url == "https://api.openai.com/v1"

    def test_explicit_base_url_env_is_honored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
        adapter = OpenAIEmbeddingAdapter(api_key="test-key", dimensions=3)
        assert adapter._base_url == "https://example.test/v1"


# ── Ollama adapter ──────────────────────────────────────────────────────


class TestOllamaEmbeddingAdapter:
    """The Phase C request contract (0003): truthful in both directions.

    The pre-Phase-C suite here codified the defects — it constructed a
    "768-dim" adapter, fed it a 3-element vector, and asserted len == 3.
    These tests pin the opposite: what is requested is sent, and what
    returns is validated.
    """

    def _make_adapter(self, *, dimensions: int | None = None) -> OllamaEmbeddingAdapter:
        return OllamaEmbeddingAdapter(
            model="nomic-embed-text",
            dimensions=dimensions,
            host="http://localhost:11434",
            timeout_seconds=5.0,
        )

    @staticmethod
    def _ok(vectors: list[list[float]]) -> httpx.Response:
        return httpx.Response(
            200,
            json={"embeddings": vectors},
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )

    def test_returns_normalized_vector(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._ok([[0.5, 0.5, 0.5]])):
            vec = adapter.embed("hello")
            assert len(vec) == 3
            assert abs(_magnitude(vec) - 1.0) < 1e-6

    def test_request_sends_truncate_false_and_no_unrequested_dimensions(self) -> None:
        """Silent prefix embedding is Ollama's default; ours is fail-visible.
        And a dimensions value the operator never configured is not sent."""
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._ok([[1.0, 0.0]])) as mock_post:
            adapter.embed("hello")
        body = mock_post.call_args.kwargs["json"]
        assert body["truncate"] is False
        assert "dimensions" not in body

    def test_configured_dimensions_are_sent_and_validated(self) -> None:
        adapter = self._make_adapter(dimensions=2)
        with patch("httpx.post", return_value=self._ok([[1.0, 0.0]])) as mock_post:
            adapter.embed("hello")
        assert mock_post.call_args.kwargs["json"]["dimensions"] == 2

        # A response that ignores the request (Ollama silently ignores
        # values above the native length) must FAIL, not persist.
        adapter768 = self._make_adapter(dimensions=768)
        with patch("httpx.post", return_value=self._ok([[0.5, 0.5, 0.5]])):
            with pytest.raises(LLMProviderError, match="requested 768 dimensions, got 3"):
                adapter768.embed("hello")

    def test_batch_returns_correct_count(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._ok([[0.1, 0.2], [0.4, 0.5], [0.7, 0.8]])):
            results = adapter.embed_batch(["a", "b", "c"])
            assert len(results) == 3

    def test_empty_batch_never_calls_the_provider(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post") as mock_post:
            assert adapter.embed_batch([]) == []
        mock_post.assert_not_called()

    def test_response_cardinality_must_match_input(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._ok([[1.0, 0.0]])):
            with pytest.raises(LLMProviderError, match="expected 2 vector"):
                adapter.embed_batch(["a", "b"])

    def test_empty_and_nonfinite_vectors_are_rejected(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._ok([[]])):
            with pytest.raises(LLMProviderError, match="empty or not a list"):
                adapter.embed("a")
        # httpx can't json-serialize NaN; hand-craft the body the way a
        # real wire payload would arrive (Python's json.loads accepts NaN).
        nan_response = httpx.Response(
            200,
            content=b'{"embeddings": [[NaN, 1.0]]}',
            headers={"content-type": "application/json"},
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )
        with patch("httpx.post", return_value=nan_response):
            with pytest.raises(LLMProviderError, match="non-finite"):
                adapter.embed("a")

    def test_inconsistent_batch_dimensions_are_rejected(self) -> None:
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._ok([[1.0, 0.0], [1.0, 0.0, 0.0]])):
            with pytest.raises(LLMProviderError, match="inconsistent dimensions"):
                adapter.embed_batch(["a", "b"])

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

    def test_dimensions_reports_requested_or_default_claim(self) -> None:
        assert self._make_adapter(dimensions=384).dimensions() == 384
        assert self._make_adapter().dimensions() == 768

    def test_http_error_surfaces_the_structured_body(self) -> None:
        """ "input exceeds maximum context length" is actionable; the old
        message was the useless "HTTP 400"."""
        adapter = self._make_adapter()
        response = httpx.Response(
            400,
            json={"error": "input exceeds maximum context length"},
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )
        with patch("httpx.post", return_value=response):
            with pytest.raises(LLMProviderError, match="input exceeds maximum context length"):
                adapter.embed("hello")

    def test_probe_supplies_model_revision_and_is_nonfatal(self) -> None:
        adapter = self._make_adapter()
        tags = httpx.Response(
            200,
            json={"models": [{"name": "nomic-embed-text:latest", "digest": "sha256:abc123"}]},
            request=httpx.Request("GET", "http://localhost:11434/api/tags"),
        )
        with patch("httpx.get", return_value=tags) as mock_get:
            assert adapter.model_revision() == "sha256:abc123"
            assert adapter.model_revision() == "sha256:abc123"
        mock_get.assert_called_once()  # cached — never probed per request

        down = self._make_adapter()
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            assert down.model_revision() is None, "an unreachable server must not fail the save path"

    def test_settings_fingerprint_is_stable_and_setting_sensitive(self) -> None:
        a = self._make_adapter()
        b = self._make_adapter()
        assert a.settings_fingerprint() == b.settings_fingerprint(), "identical settings, identical fingerprint"
        c = self._make_adapter(dimensions=384)
        assert c.settings_fingerprint() != a.settings_fingerprint(), "a space-changing setting changes it"
