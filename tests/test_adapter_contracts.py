"""Contract tests for all LLM adapter implementations.

Each adapter must follow the LLMPort contract:
- complete_async returns LLMResponse with correct fields
- _ensure_ready raises LLMProviderError for missing key / missing package
- SDK errors are mapped to LLMProviderError
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openchronicle.core.domain.ports.llm_port import LLMProviderError, LLMResponse, LLMUsage

# ---------------------------------------------------------------------------
# Helpers: fake SDK response objects
# ---------------------------------------------------------------------------


@dataclass
class _FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 20
    total_tokens: int = 30


@dataclass
class _FakeMessage:
    content: str = "hello world"


@dataclass
class _FakeChoice:
    message: _FakeMessage
    finish_reason: str = "stop"


@dataclass
class _FakeOpenAIResponse:
    id: str = "chatcmpl-abc"
    choices: list[Any] = None  # type: ignore[assignment]
    usage: _FakeUsage | None = None

    def __post_init__(self) -> None:
        if self.choices is None:
            self.choices = [_FakeChoice(message=_FakeMessage())]
        if self.usage is None:
            self.usage = _FakeUsage()


@dataclass
class _FakeAnthropicTextBlock:
    text: str = "hello from claude"
    type: str = "text"


@dataclass
class _FakeAnthropicUsage:
    input_tokens: int = 15
    output_tokens: int = 25


@dataclass
class _FakeAnthropicResponse:
    id: str = "msg-abc"
    content: list[Any] = None  # type: ignore[assignment]
    usage: _FakeAnthropicUsage | None = None
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = [_FakeAnthropicTextBlock()]
        if self.usage is None:
            self.usage = _FakeAnthropicUsage()


@dataclass
class _FakeGeminiUsageMetadata:
    prompt_token_count: int = 12
    candidates_token_count: int = 18
    total_token_count: int = 30


@dataclass
class _FakeGeminiResponse:
    text: str = "hello from gemini"
    usage_metadata: _FakeGeminiUsageMetadata | None = None

    def __post_init__(self) -> None:
        if self.usage_metadata is None:
            self.usage_metadata = _FakeGeminiUsageMetadata()


SAMPLE_MESSAGES: list[dict[str, Any]] = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"},
]


# ===================================================================
# OpenAI Adapter
# ===================================================================


class TestOpenAIAdapter:
    def _make_adapter(self, api_key: str = "test-key") -> Any:
        with patch("openchronicle.core.infrastructure.llm.openai_adapter.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key=api_key, model="gpt-4o-mini")
            return adapter, mock_openai

    async def test_ensure_ready_missing_key(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.openai_adapter.openai"):
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key="", model="gpt-4o-mini")
            adapter.api_key = ""
            with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
                adapter._ensure_ready()

    async def test_ensure_ready_missing_package(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.openai_adapter.openai", None):
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter.__new__(OpenAIAdapter)
            adapter.api_key = "test-key"
            adapter.model = "gpt-4o-mini"
            adapter.base_url = None
            adapter._client = None
            with pytest.raises(LLMProviderError, match="openai package"):
                adapter._ensure_ready()

    async def test_complete_async_response_mapping(self) -> None:
        adapter, _ = self._make_adapter()
        fake_response = _FakeOpenAIResponse()
        adapter._client.chat.completions.create = AsyncMock(return_value=fake_response)

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini")

        assert isinstance(result, LLMResponse)
        assert result.content == "hello world"
        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.request_id == "chatcmpl-abc"
        assert result.finish_reason == "stop"
        assert isinstance(result.usage, LLMUsage)
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 20
        assert result.usage.total_tokens == 30
        assert result.latency_ms is not None

    async def test_complete_async_error_mapping(self) -> None:
        adapter, _ = self._make_adapter()
        exc = Exception("API error")
        exc.status_code = 429  # type: ignore[attr-defined]
        adapter._client.chat.completions.create = AsyncMock(side_effect=exc)

        with pytest.raises(LLMProviderError, match="API error"):
            await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini")


# ===================================================================
# Anthropic Adapter
# ===================================================================


class TestAnthropicAdapter:
    def _make_adapter(self, api_key: str = "test-key") -> Any:
        with patch("openchronicle.core.infrastructure.llm.anthropic_adapter.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

            adapter = AnthropicAdapter(api_key=api_key, model="claude-sonnet-4-20250514")
            return adapter, mock_anthropic

    async def test_ensure_ready_missing_key(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.anthropic_adapter.anthropic"):
            from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

            adapter = AnthropicAdapter(api_key="", model="claude-sonnet-4-20250514")
            adapter.api_key = ""
            with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):
                adapter._ensure_ready()

    async def test_ensure_ready_missing_package(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.anthropic_adapter.anthropic", None):
            from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

            adapter = AnthropicAdapter.__new__(AnthropicAdapter)
            adapter.api_key = "test-key"
            adapter.model = "claude-sonnet-4-20250514"
            adapter.base_url = None
            adapter._client = None
            with pytest.raises(LLMProviderError, match="anthropic package"):
                adapter._ensure_ready()

    async def test_complete_async_response_mapping(self) -> None:
        adapter, _ = self._make_adapter()
        fake_response = _FakeAnthropicResponse()
        adapter._client.messages.create = AsyncMock(return_value=fake_response)

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="claude-sonnet-4-20250514")

        assert isinstance(result, LLMResponse)
        assert result.content == "hello from claude"
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.request_id == "msg-abc"
        assert result.finish_reason == "end_turn"
        assert isinstance(result.usage, LLMUsage)
        assert result.usage.input_tokens == 15
        assert result.usage.output_tokens == 25
        assert result.usage.total_tokens == 40
        assert result.latency_ms is not None

    async def test_system_message_extraction(self) -> None:
        """Anthropic requires system messages as a top-level param, not in messages array."""
        adapter, _ = self._make_adapter()
        fake_response = _FakeAnthropicResponse()
        adapter._client.messages.create = AsyncMock(return_value=fake_response)

        await adapter.complete_async(SAMPLE_MESSAGES, model="claude-sonnet-4-20250514")

        call_kwargs = adapter._client.messages.create.call_args[1]
        # System message should be extracted to top-level 'system' param
        assert call_kwargs["system"] == "You are helpful."
        # Messages should not contain the system message
        for msg in call_kwargs["messages"]:
            assert msg["role"] != "system"

    async def test_max_tokens_default(self) -> None:
        """Anthropic requires max_tokens; defaults to 4096 if not provided."""
        adapter, _ = self._make_adapter()
        fake_response = _FakeAnthropicResponse()
        adapter._client.messages.create = AsyncMock(return_value=fake_response)

        await adapter.complete_async([{"role": "user", "content": "Hi"}], model="claude-sonnet-4-20250514")

        call_kwargs = adapter._client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 4096

    async def test_complete_async_error_mapping(self) -> None:
        adapter, _ = self._make_adapter()
        exc = Exception("rate limited")
        exc.status_code = 429  # type: ignore[attr-defined]
        adapter._client.messages.create = AsyncMock(side_effect=exc)

        with pytest.raises(LLMProviderError, match="rate limited"):
            await adapter.complete_async(SAMPLE_MESSAGES, model="claude-sonnet-4-20250514")


# ===================================================================
# Groq Adapter
# ===================================================================


class TestGroqAdapter:
    def _make_adapter(self, api_key: str = "test-key") -> Any:
        with patch("openchronicle.core.infrastructure.llm.groq_adapter.groq") as mock_groq:
            mock_groq.AsyncGroq.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.groq_adapter import GroqAdapter

            adapter = GroqAdapter(api_key=api_key, model="llama-3.3-70b-versatile")
            return adapter, mock_groq

    async def test_ensure_ready_missing_key(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.groq_adapter.groq"):
            from openchronicle.core.infrastructure.llm.groq_adapter import GroqAdapter

            adapter = GroqAdapter(api_key="", model="llama-3.3-70b-versatile")
            adapter.api_key = ""
            with pytest.raises(LLMProviderError, match="GROQ_API_KEY"):
                adapter._ensure_ready()

    async def test_ensure_ready_missing_package(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.groq_adapter.groq", None):
            from openchronicle.core.infrastructure.llm.groq_adapter import GroqAdapter

            adapter = GroqAdapter.__new__(GroqAdapter)
            adapter.api_key = "test-key"
            adapter.model = "llama-3.3-70b-versatile"
            adapter._client = None
            with pytest.raises(LLMProviderError, match="groq package"):
                adapter._ensure_ready()

    async def test_complete_async_response_mapping(self) -> None:
        adapter, _ = self._make_adapter()
        fake_response = _FakeOpenAIResponse()  # Groq uses OpenAI-compatible format
        adapter._client.chat.completions.create = AsyncMock(return_value=fake_response)

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="llama-3.3-70b-versatile")

        assert isinstance(result, LLMResponse)
        assert result.content == "hello world"
        assert result.provider == "groq"
        assert result.model == "llama-3.3-70b-versatile"
        assert result.finish_reason == "stop"
        assert isinstance(result.usage, LLMUsage)
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 20
        assert result.latency_ms is not None

    async def test_complete_async_error_mapping(self) -> None:
        adapter, _ = self._make_adapter()
        exc = Exception("quota exceeded")
        exc.status_code = 429  # type: ignore[attr-defined]
        adapter._client.chat.completions.create = AsyncMock(side_effect=exc)

        with pytest.raises(LLMProviderError, match="quota exceeded"):
            await adapter.complete_async(SAMPLE_MESSAGES, model="llama-3.3-70b-versatile")


# ===================================================================
# Gemini Adapter
# ===================================================================


class TestGeminiAdapter:
    """Gemini tests keep patches active during complete_async since genai may not be installed."""

    @staticmethod
    def _gemini_patches() -> tuple[Any, Any, Any, Any]:
        return MagicMock(), MagicMock(), MagicMock(), MagicMock()

    async def test_ensure_ready_missing_key(self) -> None:
        mock_genai = MagicMock()
        with patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="", model="gemini-2.0-flash")
            adapter.api_key = ""
            with pytest.raises(LLMProviderError, match="GEMINI_API_KEY"):
                adapter._ensure_ready()

    async def test_ensure_ready_missing_package(self) -> None:
        with patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", None):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter.__new__(GeminiAdapter)
            adapter.api_key = "test-key"
            adapter.model = "gemini-2.0-flash"
            adapter._client = None
            with pytest.raises(LLMProviderError, match="google-genai package"):
                adapter._ensure_ready()

    async def test_complete_async_response_mapping(self) -> None:
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            fake_response = _FakeGeminiResponse()
            adapter._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

            result = await adapter.complete_async(SAMPLE_MESSAGES, model="gemini-2.0-flash")

        assert isinstance(result, LLMResponse)
        assert result.content == "hello from gemini"
        assert result.provider == "gemini"
        assert result.model == "gemini-2.0-flash"
        assert isinstance(result.usage, LLMUsage)
        assert result.usage.input_tokens == 12
        assert result.usage.output_tokens == 18
        assert result.usage.total_tokens == 30
        assert result.latency_ms is not None

    async def test_message_format_conversion(self) -> None:
        """Gemini uses 'model' role instead of 'assistant' and Content/Part types."""
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            fake_response = _FakeGeminiResponse()
            adapter._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ]
            await adapter.complete_async(messages, model="gemini-2.0-flash")

            # Verify Content was called with correct roles
            content_calls = mock_content.call_args_list
            # System message is extracted, so 3 Content calls for user/assistant/user
            assert len(content_calls) == 3
            assert content_calls[0][1]["role"] == "user"
            assert content_calls[1][1]["role"] == "model"  # assistant -> model
            assert content_calls[2][1]["role"] == "user"

    async def test_complete_async_error_mapping(self) -> None:
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            adapter._client.aio.models.generate_content = AsyncMock(side_effect=Exception("quota error"))

            with pytest.raises(LLMProviderError, match="quota error"):
                await adapter.complete_async(SAMPLE_MESSAGES, model="gemini-2.0-flash")


# ===================================================================
# Ollama Adapter (existing, verify contract)
# ===================================================================


class TestOllamaAdapterContract:
    async def test_response_mapping(self) -> None:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        adapter = OllamaAdapter(model="llama3.1", base_url="http://localhost:11434")

        fake_json = {
            "message": {"content": "hello from ollama"},
            "model": "llama3.1",
            "done_reason": "stop",
            "prompt_eval_count": 8,
            "eval_count": 16,
        }

        mock_response = MagicMock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("openchronicle.core.infrastructure.llm.ollama_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.complete_async([{"role": "user", "content": "Hello"}], model="llama3.1")

        assert isinstance(result, LLMResponse)
        assert result.content == "hello from ollama"
        assert result.provider == "ollama"
        assert result.model == "llama3.1"
        assert result.finish_reason == "stop"
        assert isinstance(result.usage, LLMUsage)
        assert result.usage.input_tokens == 8
        assert result.usage.output_tokens == 16
        assert result.usage.total_tokens == 24
