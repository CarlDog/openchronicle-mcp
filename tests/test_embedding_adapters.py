"""Tests for OpenAI and Ollama embedding adapters (mocked HTTP)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import httpx
import pytest

from openchronicle.core.domain.errors.error_codes import CONTENT_TOO_LONG, PROVIDER_ERROR
from openchronicle.core.domain.exceptions import ProviderError as LLMProviderError
from openchronicle.core.infrastructure.embedding.ollama_adapter import (
    OllamaEmbeddingAdapter,
    _is_context_length_rejection,
)
from openchronicle.core.infrastructure.embedding.openai_adapter import (
    OpenAIEmbeddingAdapter,
    _classify_error,
)

# The LIVE OpenAI embeddings over-length rejection, captured 2026-08-29
# (one deliberately-oversized request against text-embedding-3-small):
# BadRequestError, HTTP 400, code=None — the real endpoint sets NO
# error code, and its message says "maximum input length", not
# "context length". This capture is the classification ground truth.
CAPTURED_OPENAI_OVERLENGTH_MESSAGE = "Invalid 'input[0]': maximum input length is 8192 tokens."


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


def test_openai_fingerprint_distinguishes_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The openai adapter is the GENERIC OpenAI-compatible path
    (operator-directed 2026-08-29): pointed at Voyage/Gemini/Mistral via
    OPENAI_BASE_URL, the same model label can name a different vector
    space per host — so the endpoint must be part of the space
    fingerprint, making silent cross-host mixing impossible."""
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    default = OpenAIEmbeddingAdapter()
    voyage = OpenAIEmbeddingAdapter(base_url="https://api.voyageai.com/v1")
    same_as_default = OpenAIEmbeddingAdapter()

    assert default.settings_fingerprint() == same_as_default.settings_fingerprint()
    assert default.settings_fingerprint() != voyage.settings_fingerprint(), (
        "a different embeddings host is a different vector space"
    )


class TestOllamaContextLengthClassification:
    """ADR 0009 §1: the over-length rejection classifies as CONTENT_TOO_LONG.

    The predicate is one module-level function; ground truth is the
    captured rejection string pinned in this file. Near-misses stay
    PROVIDER_ERROR — the misclassification bias is deliberately
    conservative (a false positive would park a row).
    """

    def test_predicate_matches_the_captured_rejection(self) -> None:
        assert _is_context_length_rejection(400, "input exceeds maximum context length")

    def test_predicate_is_case_insensitive(self) -> None:
        assert _is_context_length_rejection(400, "Input exceeds maximum CONTEXT LENGTH")

    def test_predicate_near_misses_stay_negative(self) -> None:
        # Wrong status: the same body on a 500 is server trouble, not
        # a content fact.
        assert not _is_context_length_rejection(500, "input exceeds maximum context length")
        # Other 400s: bad model, malformed request, timeout-ish wording.
        assert not _is_context_length_rejection(400, 'model "nope" not found')
        assert not _is_context_length_rejection(400, "invalid request body")
        assert not _is_context_length_rejection(400, "request timed out")
        assert not _is_context_length_rejection(400, "")

    def _adapter(self) -> OllamaEmbeddingAdapter:
        return OllamaEmbeddingAdapter(model="nomic-embed-text", host="http://localhost:11434", timeout_seconds=5.0)

    @staticmethod
    def _error_response(status: int, body: dict[str, str]) -> httpx.Response:
        return httpx.Response(
            status,
            json=body,
            request=httpx.Request("POST", "http://localhost:11434/api/embed"),
        )

    def test_captured_rejection_raises_content_too_long(self) -> None:
        response = self._error_response(400, {"error": "input exceeds maximum context length"})
        with patch("httpx.post", return_value=response):
            with pytest.raises(LLMProviderError, match="input exceeds maximum context length") as excinfo:
                self._adapter().embed("hello")
        assert excinfo.value.error_code == CONTENT_TOO_LONG

    def test_other_400_bodies_stay_provider_error(self) -> None:
        response = self._error_response(400, {"error": 'model "nope" not found'})
        with patch("httpx.post", return_value=response):
            with pytest.raises(LLMProviderError) as excinfo:
                self._adapter().embed("hello")
        assert excinfo.value.error_code == PROVIDER_ERROR

    def test_500_with_the_phrase_stays_provider_error(self) -> None:
        response = self._error_response(500, {"error": "internal: context length probe failed"})
        with patch("httpx.post", return_value=response):
            with pytest.raises(LLMProviderError) as excinfo:
                self._adapter().embed("hello")
        assert excinfo.value.error_code == PROVIDER_ERROR


class _FakeSDKError(Exception):
    """Duck-typed stand-in for the openai SDK's APIStatusError shape."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.code = code


class TestOpenAIContextLengthClassification:
    """ADR 0009 §1: structured `code` first, 4xx-gated message fallback.

    The live embeddings endpoint's over-length rejection (captured
    2026-08-29) carries `code=None` and says "maximum input length" —
    the fallback's marker list is grounded in that capture, and the ADR's
    documented `context_length_exceeded` / "context length" shapes are
    kept for hosts that use them.
    """

    def test_structured_code_classifies(self) -> None:
        exc = _FakeSDKError("This model's maximum context length is 8192 tokens", code="context_length_exceeded")
        assert _classify_error(exc) == CONTENT_TOO_LONG

    def test_captured_live_rejection_classifies(self) -> None:
        exc = _FakeSDKError(CAPTURED_OPENAI_OVERLENGTH_MESSAGE, status_code=400, code=None)
        assert _classify_error(exc) == CONTENT_TOO_LONG

    def test_documented_context_length_message_classifies_on_4xx(self) -> None:
        exc = _FakeSDKError("This model's maximum context length is 8192 tokens", status_code=400)
        assert _classify_error(exc) == CONTENT_TOO_LONG

    def test_message_fallback_is_gated_to_4xx(self) -> None:
        # The same phrase on a 500 is server trouble, not a content fact.
        assert _classify_error(_FakeSDKError("context length exceeded", status_code=500)) == PROVIDER_ERROR
        # No structured status at all (a bare exception whose str happens
        # to contain the phrase) must NOT classify — the ungated fallback
        # the ADR review rejected.
        assert _classify_error(RuntimeError("context length exceeded")) == PROVIDER_ERROR

    def test_compat_host_unclassifiable_stays_provider_error(self) -> None:
        # A generic OpenAI-compatible host (Voyage/Gemini/Mistral via
        # OPENAI_BASE_URL) phrasing its over-length error differently:
        # conservative bias keeps today's retry behavior.
        exc = _FakeSDKError("input too large for this model", status_code=400)
        assert _classify_error(exc) == PROVIDER_ERROR
        assert _classify_error(_FakeSDKError("rate limit exceeded", status_code=429)) == PROVIDER_ERROR

    def test_adapter_raises_content_too_long_for_classified_errors(self) -> None:
        adapter = OpenAIEmbeddingAdapter(api_key="test-key", dimensions=3, timeout_seconds=5.0)
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = _FakeSDKError(
            CAPTURED_OPENAI_OVERLENGTH_MESSAGE, status_code=400, code=None
        )
        adapter._client = mock_client
        with pytest.raises(LLMProviderError, match="maximum input length") as excinfo:
            adapter.embed("hello")
        assert excinfo.value.error_code == CONTENT_TOO_LONG

    def test_adapter_keeps_provider_error_for_transients(self) -> None:
        adapter = OpenAIEmbeddingAdapter(api_key="test-key", dimensions=3, timeout_seconds=5.0)
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = RuntimeError("timeout")
        adapter._client = mock_client
        with pytest.raises(LLMProviderError) as excinfo:
            adapter.embed("hello")
        assert excinfo.value.error_code == PROVIDER_ERROR


class TestOllamaHostHandling:
    """Local connections are first-class over BOTH http and https
    (operator-directed 2026-08-29)."""

    def test_scheme_less_host_gets_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OLLAMA_HOST=carldog-nas:11434 used to build a broken URL."""
        monkeypatch.setenv("OLLAMA_HOST", "carldog-nas:11434")
        adapter = OllamaEmbeddingAdapter(model="test")
        assert adapter._host == "http://carldog-nas:11434"

    def test_https_host_is_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_HOST", "https://nas.local:11435/")
        adapter = OllamaEmbeddingAdapter(model="test")
        assert adapter._host == "https://nas.local:11435"

    def test_tls_verification_defaults_on_and_is_passed_to_httpx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_VERIFY_TLS", raising=False)
        monkeypatch.setenv("OLLAMA_HOST", "https://nas.local:11434")
        adapter = OllamaEmbeddingAdapter(model="test")
        ok = httpx.Response(
            200,
            json={"embeddings": [[1.0, 0.0]]},
            request=httpx.Request("POST", "https://nas.local:11434/api/embed"),
        )
        with patch("httpx.post", return_value=ok) as mock_post:
            adapter.embed("hello")
        assert mock_post.call_args.kwargs["verify"] is True

    def test_verify_tls_can_be_disabled_for_lan_self_signed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The knob that makes a self-signed LAN https endpoint usable —
        same shape as the fleet's PORTAINER_VERIFY_TLS."""
        monkeypatch.setenv("OLLAMA_VERIFY_TLS", "0")
        monkeypatch.setenv("OLLAMA_HOST", "https://192.168.1.50:11434")
        adapter = OllamaEmbeddingAdapter(model="test")
        ok = httpx.Response(
            200,
            json={"embeddings": [[1.0, 0.0]]},
            request=httpx.Request("POST", "https://192.168.1.50:11434/api/embed"),
        )
        with patch("httpx.post", return_value=ok) as mock_post:
            adapter.embed("hello")
        assert mock_post.call_args.kwargs["verify"] is False
