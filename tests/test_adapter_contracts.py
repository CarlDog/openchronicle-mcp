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

from openchronicle.core.domain.ports.llm_port import (
    LLMProviderError,
    LLMResponse,
    LLMUsage,
    StreamChunk,
    ToolDefinition,
)

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
            adapter.base_url = ""
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

    def test_empty_base_url_env_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENAI_BASE_URL='' (compose ${VAR:-} interpolation) must not break the adapter.

        The OpenAI SDK uses ``is None`` for its default-fallback check, so an
        empty-string env defeats the fallback. The adapter coerces empty to the
        documented default and always passes an explicit base_url.
        """
        monkeypatch.setenv("OPENAI_BASE_URL", "")
        with patch("openchronicle.core.infrastructure.llm.openai_adapter.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key="test-key", model="gpt-4o-mini")
            assert adapter.base_url == "https://api.openai.com/v1"

    def test_explicit_base_url_env_is_honored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
        with patch("openchronicle.core.infrastructure.llm.openai_adapter.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapter = OpenAIAdapter(api_key="test-key", model="gpt-4o-mini")
            assert adapter.base_url == "https://example.test/v1"


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
            adapter.base_url = ""
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

    def test_empty_base_url_env_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_BASE_URL='' (compose ${VAR:-} interpolation) must not break the adapter."""
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "")
        with patch("openchronicle.core.infrastructure.llm.anthropic_adapter.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

            adapter = AnthropicAdapter(api_key="test-key", model="claude-sonnet-4-20250514")
            assert adapter.base_url == "https://api.anthropic.com"

    def test_explicit_base_url_env_is_honored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.test")
        with patch("openchronicle.core.infrastructure.llm.anthropic_adapter.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

            adapter = AnthropicAdapter(api_key="test-key", model="claude-sonnet-4-20250514")
            assert adapter.base_url == "https://example.test"


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


class TestGeminiErrorClassification:
    """Verify _classify_gemini_error maps exceptions to standard error codes."""

    def test_timeout_error(self) -> None:
        from openchronicle.core.domain.errors import TIMEOUT as TIMEOUT_CODE
        from openchronicle.core.infrastructure.llm.gemini_adapter import _classify_gemini_error

        exc = TimeoutError("Request timed out")
        assert _classify_gemini_error(exc) == TIMEOUT_CODE

    def test_connection_error(self) -> None:
        from openchronicle.core.domain.errors import CONNECTION_ERROR as CONN_CODE
        from openchronicle.core.infrastructure.llm.gemini_adapter import _classify_gemini_error

        exc = Exception("connection refused by host")
        assert _classify_gemini_error(exc) == CONN_CODE

    def test_http_status_code(self) -> None:
        from openchronicle.core.domain.errors import PROVIDER_ERROR as PROV_CODE
        from openchronicle.core.infrastructure.llm.gemini_adapter import _classify_gemini_error

        exc = Exception("rate limit")
        exc.code = 429  # type: ignore[attr-defined]
        assert _classify_gemini_error(exc) == PROV_CODE

    def test_unknown_error(self) -> None:
        from openchronicle.core.domain.errors import UNKNOWN_ERROR as UNK_CODE
        from openchronicle.core.infrastructure.llm.gemini_adapter import _classify_gemini_error

        exc = Exception("something unexpected")
        assert _classify_gemini_error(exc) == UNK_CODE


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


# ===================================================================
# Streaming Contract Tests
# ===================================================================


class TestStubStreamAsync:
    """Verify stub adapter streaming produces word-by-word chunks."""

    async def test_stream_yields_chunks(self) -> None:
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        chunks: list[StreamChunk] = []
        async for chunk in adapter.stream_async(
            [{"role": "user", "content": "hello world"}],
            model="stub",
        ):
            chunks.append(chunk)

        assert len(chunks) >= 1
        full_text = "".join(c.text for c in chunks)
        assert "hello" in full_text
        # Last chunk should be marked finished
        assert chunks[-1].finished is True
        assert chunks[-1].provider == "stub"

    async def test_stream_single_word(self) -> None:
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        chunks: list[StreamChunk] = []
        async for chunk in adapter.stream_async(
            [{"role": "user", "content": "hi"}],
            model="stub",
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].text == "hi"
        assert chunks[0].finished is True


class TestLLMPortDefaultStreamFallback:
    """Verify the default stream_async falls back to complete_async."""

    async def test_fallback_yields_single_chunk(self) -> None:
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        # Use a subclass that only has complete_async (not stream_async)
        # We test the base class fallback by calling it through super()
        adapter = StubLLMAdapter()
        # Call the base class stream_async directly to test fallback
        from openchronicle.core.domain.ports.llm_port import LLMPort

        chunks: list[StreamChunk] = []
        async for chunk in LLMPort.stream_async(
            adapter,
            [{"role": "user", "content": "test fallback"}],
            model="stub",
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].finished is True
        assert "test fallback" in chunks[0].text


# ===================================================================
# Shared helpers for tool-use tests
# ===================================================================

SAMPLE_TOOLS = [
    ToolDefinition(
        name="get_weather",
        description="Get weather for a location",
        parameters={"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]},
    ),
]

TOOL_MESSAGES: list[dict[str, Any]] = [
    {"role": "user", "content": "What's the weather in Seattle?"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location":"Seattle"}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_123", "name": "get_weather", "content": '{"temp": 72}'},
]


# Fake SDK objects for tool call responses
@dataclass
class _FakeToolCallFunction:
    name: str
    arguments: str


@dataclass
class _FakeToolCallObj:
    id: str
    type: str
    function: _FakeToolCallFunction
    index: int = 0


@dataclass
class _FakeMessageWithToolCalls:
    content: str | None
    tool_calls: list[_FakeToolCallObj]


@dataclass
class _FakeChoiceWithToolCalls:
    message: _FakeMessageWithToolCalls
    finish_reason: str = "tool_calls"


@dataclass
class _FakeOpenAIToolResponse:
    id: str = "chatcmpl-tools"
    choices: list[Any] = None  # type: ignore[assignment]
    usage: _FakeUsage | None = None

    def __post_init__(self) -> None:
        if self.choices is None:
            self.choices = [
                _FakeChoiceWithToolCalls(
                    message=_FakeMessageWithToolCalls(
                        content=None,
                        tool_calls=[
                            _FakeToolCallObj(
                                id="call_abc",
                                type="function",
                                function=_FakeToolCallFunction(name="get_weather", arguments='{"location":"Seattle"}'),
                            )
                        ],
                    )
                )
            ]
        if self.usage is None:
            self.usage = _FakeUsage()


@dataclass
class _FakeAnthropicToolUseBlock:
    type: str = "tool_use"
    id: str = "toolu_abc"
    name: str = "get_weather"
    input: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.input is None:
            self.input = {"location": "Seattle"}


# ===================================================================
# Tool-Use: Stub Adapter
# ===================================================================


class TestStubToolUse:
    async def test_stub_accepts_tools_silently(self) -> None:
        """When no env var is set, tools are accepted but ignored."""
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        result = await adapter.complete_async(
            [{"role": "user", "content": "hello"}],
            model="stub",
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
        )
        assert isinstance(result, LLMResponse)
        assert result.tool_calls is None
        assert result.content  # normal text response

    async def test_stub_tool_calls_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OC_STUB_TOOL_CALLS env var triggers tool call response."""
        import json

        monkeypatch.setenv("OC_STUB_TOOL_CALLS", json.dumps([{"name": "get_weather", "arguments": "{}"}]))

        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        result = await adapter.complete_async(
            [{"role": "user", "content": "weather?"}],
            model="stub",
            tools=SAMPLE_TOOLS,
        )
        assert result.finish_reason == "tool_calls"
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_weather"
        assert result.tool_calls[0].id  # auto-generated

    async def test_stub_tool_calls_env_var_without_tools_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OC_STUB_TOOL_CALLS is ignored when no tools are provided."""
        import json

        monkeypatch.setenv("OC_STUB_TOOL_CALLS", json.dumps([{"name": "fn"}]))

        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        result = await adapter.complete_async(
            [{"role": "user", "content": "hello"}],
            model="stub",
        )
        assert result.tool_calls is None

    async def test_stub_stream_with_tool_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Streaming with tool calls yields single chunk."""
        import json

        monkeypatch.setenv("OC_STUB_TOOL_CALLS", json.dumps([{"name": "get_weather", "arguments": "{}"}]))

        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        chunks: list[StreamChunk] = []
        async for chunk in adapter.stream_async(
            [{"role": "user", "content": "weather?"}],
            model="stub",
            tools=SAMPLE_TOOLS,
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].finished is True
        assert chunks[0].tool_calls is not None
        assert chunks[0].tool_calls[0].name == "get_weather"


# ===================================================================
# Tool-Use: OpenAI Adapter
# ===================================================================


class TestOpenAIToolUse:
    def _make_adapter(self) -> Any:
        with patch("openchronicle.core.infrastructure.llm.openai_adapter.openai") as mock_openai:
            mock_openai.AsyncOpenAI.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            return OpenAIAdapter(api_key="test-key", model="gpt-4o-mini")

    async def test_complete_passes_tools(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIResponse())

        await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini", tools=SAMPLE_TOOLS, tool_choice="auto")

        call_kwargs = adapter._client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "get_weather"
        assert call_kwargs["tool_choice"] == "auto"

    async def test_tool_choice_mapping(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIResponse())

        # "required" passes through
        await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini", tools=SAMPLE_TOOLS, tool_choice="required")
        assert adapter._client.chat.completions.create.call_args[1]["tool_choice"] == "required"

        # "none" passes through
        await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini", tools=SAMPLE_TOOLS, tool_choice="none")
        assert adapter._client.chat.completions.create.call_args[1]["tool_choice"] == "none"

        # Specific name → function object
        await adapter.complete_async(
            SAMPLE_MESSAGES, model="gpt-4o-mini", tools=SAMPLE_TOOLS, tool_choice="get_weather"
        )
        tc = adapter._client.chat.completions.create.call_args[1]["tool_choice"]
        assert tc == {"type": "function", "function": {"name": "get_weather"}}

    async def test_tool_calls_extracted(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIToolResponse())

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini", tools=SAMPLE_TOOLS)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_abc"
        assert result.tool_calls[0].name == "get_weather"
        assert result.tool_calls[0].arguments == '{"location":"Seattle"}'

    async def test_tools_none_backward_compat(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIResponse())

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="gpt-4o-mini")

        assert result.tool_calls is None
        call_kwargs = adapter._client.chat.completions.create.call_args[1]
        assert "tools" not in call_kwargs

    async def test_stream_tool_call_accumulation(self) -> None:
        """Streaming accumulates tool call deltas and emits on final chunk."""
        adapter = self._make_adapter()

        # Simulate streaming deltas for a tool call
        @dataclass
        class _Delta:
            content: str | None = None
            tool_calls: list[Any] | None = None

        @dataclass
        class _StreamChoice:
            delta: _Delta
            finish_reason: str | None = None

        @dataclass
        class _StreamChunkObj:
            choices: list[Any]
            usage: Any = None

        tc_delta_1 = MagicMock()
        tc_delta_1.index = 0
        tc_delta_1.id = "call_stream"
        tc_delta_1.function = MagicMock()
        tc_delta_1.function.name = "get_weather"
        tc_delta_1.function.arguments = '{"loc'

        tc_delta_2 = MagicMock()
        tc_delta_2.index = 0
        tc_delta_2.id = None
        tc_delta_2.function = MagicMock()
        tc_delta_2.function.name = None
        tc_delta_2.function.arguments = 'ation":"Seattle"}'

        chunks_data = [
            _StreamChunkObj(choices=[_StreamChoice(delta=_Delta(tool_calls=[tc_delta_1]))]),
            _StreamChunkObj(choices=[_StreamChoice(delta=_Delta(tool_calls=[tc_delta_2]))]),
            _StreamChunkObj(choices=[_StreamChoice(delta=_Delta(), finish_reason="tool_calls")]),
        ]

        async def fake_stream() -> Any:
            for c in chunks_data:
                yield c

        adapter._client.chat.completions.create = AsyncMock(return_value=fake_stream())

        collected: list[StreamChunk] = []
        async for chunk in adapter.stream_async(
            SAMPLE_MESSAGES,
            model="gpt-4o-mini",
            tools=SAMPLE_TOOLS,
        ):
            collected.append(chunk)

        final = collected[-1]
        assert final.finished is True
        assert final.tool_calls is not None
        assert len(final.tool_calls) == 1
        assert final.tool_calls[0].id == "call_stream"
        assert final.tool_calls[0].name == "get_weather"
        assert final.tool_calls[0].arguments == '{"location":"Seattle"}'


# ===================================================================
# Tool-Use: Groq Adapter
# ===================================================================


class TestGroqToolUse:
    def _make_adapter(self) -> Any:
        with patch("openchronicle.core.infrastructure.llm.groq_adapter.groq") as mock_groq:
            mock_groq.AsyncGroq.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.groq_adapter import GroqAdapter

            return GroqAdapter(api_key="test-key", model="llama-3.3-70b-versatile")

    async def test_complete_passes_tools(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIResponse())

        await adapter.complete_async(
            SAMPLE_MESSAGES, model="llama-3.3-70b-versatile", tools=SAMPLE_TOOLS, tool_choice="auto"
        )

        call_kwargs = adapter._client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tool_choice"] == "auto"

    async def test_tool_calls_extracted(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIToolResponse())

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="llama-3.3-70b-versatile", tools=SAMPLE_TOOLS)

        assert result.tool_calls is not None
        assert result.tool_calls[0].name == "get_weather"

    async def test_tools_none_backward_compat(self) -> None:
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = AsyncMock(return_value=_FakeOpenAIResponse())

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="llama-3.3-70b-versatile")

        assert result.tool_calls is None
        assert "tools" not in adapter._client.chat.completions.create.call_args[1]


# ===================================================================
# Tool-Use: Anthropic Adapter
# ===================================================================


class TestAnthropicToolUse:
    def _make_adapter(self) -> Any:
        with patch("openchronicle.core.infrastructure.llm.anthropic_adapter.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = MagicMock()
            from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

            return AnthropicAdapter(api_key="test-key", model="claude-sonnet-4-20250514")

    async def test_complete_passes_tools_as_input_schema(self) -> None:
        """Anthropic uses 'input_schema' instead of 'parameters'."""
        adapter = self._make_adapter()
        adapter._client.messages.create = AsyncMock(return_value=_FakeAnthropicResponse())

        await adapter.complete_async(
            SAMPLE_MESSAGES, model="claude-sonnet-4-20250514", tools=SAMPLE_TOOLS, tool_choice="auto"
        )

        call_kwargs = adapter._client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        tool_def = call_kwargs["tools"][0]
        assert "input_schema" in tool_def
        assert "parameters" not in tool_def
        assert tool_def["name"] == "get_weather"
        assert call_kwargs["tool_choice"] == {"type": "auto"}

    async def test_tool_choice_mapping(self) -> None:
        adapter = self._make_adapter()
        adapter._client.messages.create = AsyncMock(return_value=_FakeAnthropicResponse())

        # "required" → {"type": "any"}
        await adapter.complete_async(
            SAMPLE_MESSAGES, model="claude-sonnet-4-20250514", tools=SAMPLE_TOOLS, tool_choice="required"
        )
        assert adapter._client.messages.create.call_args[1]["tool_choice"] == {"type": "any"}

        # "none" → tools omitted
        await adapter.complete_async(
            SAMPLE_MESSAGES, model="claude-sonnet-4-20250514", tools=SAMPLE_TOOLS, tool_choice="none"
        )
        assert "tools" not in adapter._client.messages.create.call_args[1]

        # Specific name
        await adapter.complete_async(
            SAMPLE_MESSAGES, model="claude-sonnet-4-20250514", tools=SAMPLE_TOOLS, tool_choice="get_weather"
        )
        assert adapter._client.messages.create.call_args[1]["tool_choice"] == {"type": "tool", "name": "get_weather"}

    async def test_tool_use_blocks_extracted(self) -> None:
        """Mixed text + tool_use content blocks are parsed correctly."""
        adapter = self._make_adapter()

        mixed_response = _FakeAnthropicResponse(
            content=[
                _FakeAnthropicTextBlock(text="Let me check the weather."),
                _FakeAnthropicToolUseBlock(),
            ],
            stop_reason="tool_use",
        )
        adapter._client.messages.create = AsyncMock(return_value=mixed_response)

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="claude-sonnet-4-20250514", tools=SAMPLE_TOOLS)

        assert result.content == "Let me check the weather."
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_abc"
        assert result.tool_calls[0].name == "get_weather"
        import json

        assert json.loads(result.tool_calls[0].arguments) == {"location": "Seattle"}

    async def test_tool_result_message_transformed(self) -> None:
        """Canonical tool result messages are transformed to Anthropic format."""
        adapter = self._make_adapter()
        adapter._client.messages.create = AsyncMock(return_value=_FakeAnthropicResponse())

        await adapter.complete_async(TOOL_MESSAGES, model="claude-sonnet-4-20250514")

        call_kwargs = adapter._client.messages.create.call_args[1]
        messages = call_kwargs["messages"]

        # TOOL_MESSAGES: user, assistant+tool_calls, tool_result
        # First message: user (plain text)
        assert messages[0]["role"] == "user"

        # Second message: assistant with tool_use content blocks
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"][0]["type"] == "tool_use"

        # Third message: user with tool_result content block
        assert messages[2]["role"] == "user"
        assert messages[2]["content"][0]["type"] == "tool_result"
        assert messages[2]["content"][0]["tool_use_id"] == "call_123"

    async def test_tools_none_backward_compat(self) -> None:
        adapter = self._make_adapter()
        adapter._client.messages.create = AsyncMock(return_value=_FakeAnthropicResponse())

        result = await adapter.complete_async(SAMPLE_MESSAGES, model="claude-sonnet-4-20250514")
        assert result.tool_calls is None
        assert "tools" not in adapter._client.messages.create.call_args[1]

    async def test_stream_falls_back_with_tools(self) -> None:
        """Streaming with tools falls back to single-chunk via complete_async."""
        adapter = self._make_adapter()
        adapter._client.messages.create = AsyncMock(return_value=_FakeAnthropicResponse())

        chunks: list[StreamChunk] = []
        async for chunk in adapter.stream_async(
            SAMPLE_MESSAGES,
            model="claude-sonnet-4-20250514",
            tools=SAMPLE_TOOLS,
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].finished is True


# ===================================================================
# Tool-Use: Gemini Adapter
# ===================================================================


class TestGeminiToolUse:
    @staticmethod
    def _gemini_patches() -> tuple[Any, Any, Any, Any]:
        return MagicMock(), MagicMock(), MagicMock(), MagicMock()

    async def test_complete_passes_tools_as_function_declarations(self) -> None:
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            adapter._client.aio.models.generate_content = AsyncMock(return_value=_FakeGeminiResponse())

            await adapter.complete_async(
                SAMPLE_MESSAGES, model="gemini-2.0-flash", tools=SAMPLE_TOOLS, tool_choice="auto"
            )

        # Check that GenerateContentConfig was called with tools
        config_kwargs = mock_config.call_args[1]
        assert "tools" in config_kwargs
        assert config_kwargs["tools"][0]["function_declarations"][0]["name"] == "get_weather"
        assert config_kwargs["tool_config"] == {"function_calling_config": {"mode": "AUTO"}}

    async def test_tool_choice_mapping(self) -> None:
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            adapter._client.aio.models.generate_content = AsyncMock(return_value=_FakeGeminiResponse())

            # "required" → ANY
            await adapter.complete_async(
                SAMPLE_MESSAGES, model="gemini-2.0-flash", tools=SAMPLE_TOOLS, tool_choice="required"
            )
            assert mock_config.call_args[1]["tool_config"] == {"function_calling_config": {"mode": "ANY"}}

            # "none" → NONE
            await adapter.complete_async(
                SAMPLE_MESSAGES, model="gemini-2.0-flash", tools=SAMPLE_TOOLS, tool_choice="none"
            )
            assert mock_config.call_args[1]["tool_config"] == {"function_calling_config": {"mode": "NONE"}}

            # Specific name → ANY with allowed_function_names
            await adapter.complete_async(
                SAMPLE_MESSAGES, model="gemini-2.0-flash", tools=SAMPLE_TOOLS, tool_choice="get_weather"
            )
            assert mock_config.call_args[1]["tool_config"] == {
                "function_calling_config": {"mode": "ANY", "allowed_function_names": ["get_weather"]}
            }

    async def test_function_call_parts_extracted(self) -> None:
        """Function call parts in response → ToolCall with synthetic ID."""
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()

        # Build a response with function_call part
        fake_fn_call = MagicMock()
        fake_fn_call.name = "get_weather"
        fake_fn_call.args = {"location": "Seattle"}

        fake_part = MagicMock()
        fake_part.text = None
        fake_part.function_call = fake_fn_call

        fake_candidate = MagicMock()
        fake_candidate.content.parts = [fake_part]

        fake_response = MagicMock()
        fake_response.candidates = [fake_candidate]
        fake_response.usage_metadata = _FakeGeminiUsageMetadata()

        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            adapter._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

            result = await adapter.complete_async(SAMPLE_MESSAGES, model="gemini-2.0-flash", tools=SAMPLE_TOOLS)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_weather"
        assert result.tool_calls[0].id.startswith("gemini_")
        import json

        assert json.loads(result.tool_calls[0].arguments) == {"location": "Seattle"}

    async def test_tools_none_backward_compat(self) -> None:
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            adapter._client.aio.models.generate_content = AsyncMock(return_value=_FakeGeminiResponse())

            result = await adapter.complete_async(SAMPLE_MESSAGES, model="gemini-2.0-flash")

        assert result.tool_calls is None

    async def test_stream_falls_back_with_tools(self) -> None:
        mock_genai, mock_content, mock_part, mock_config = self._gemini_patches()
        with (
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.genai", mock_genai),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Content", mock_content),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.Part", mock_part),
            patch("openchronicle.core.infrastructure.llm.gemini_adapter.GenerateContentConfig", mock_config),
        ):
            from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

            adapter = GeminiAdapter(api_key="test-key", model="gemini-2.0-flash")
            adapter._client.aio.models.generate_content = AsyncMock(return_value=_FakeGeminiResponse())

            chunks: list[StreamChunk] = []
            async for chunk in adapter.stream_async(
                SAMPLE_MESSAGES,
                model="gemini-2.0-flash",
                tools=SAMPLE_TOOLS,
            ):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].finished is True


# ===================================================================
# Tool-Use: Ollama Adapter
# ===================================================================


class TestOllamaToolUse:
    async def test_complete_passes_tools(self) -> None:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        adapter = OllamaAdapter(model="llama3.1", base_url="http://localhost:11434")

        fake_json: dict[str, Any] = {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "get_weather", "arguments": {"location": "Seattle"}}}],
            },
            "model": "llama3.1",
            "done_reason": "tool_calls",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("openchronicle.core.infrastructure.llm.ollama_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.complete_async(
                [{"role": "user", "content": "weather?"}],
                model="llama3.1",
                tools=SAMPLE_TOOLS,
            )

        # Check tools were sent in payload
        payload = mock_client.post.call_args[1]["json"]
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "function"

        # Check tool calls extracted with dict→JSON normalization
        assert result.tool_calls is not None
        assert result.tool_calls[0].name == "get_weather"
        import json

        assert json.loads(result.tool_calls[0].arguments) == {"location": "Seattle"}
        assert result.tool_calls[0].id.startswith("ollama_")

    async def test_tools_none_backward_compat(self) -> None:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        adapter = OllamaAdapter(model="llama3.1", base_url="http://localhost:11434")

        fake_json: dict[str, Any] = {
            "message": {"content": "hello"},
            "model": "llama3.1",
            "done_reason": "stop",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("openchronicle.core.infrastructure.llm.ollama_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.complete_async([{"role": "user", "content": "hi"}], model="llama3.1")

        assert result.tool_calls is None
        payload = mock_client.post.call_args[1]["json"]
        assert "tools" not in payload

    async def test_stream_falls_back_with_tools(self) -> None:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        adapter = OllamaAdapter(model="llama3.1", base_url="http://localhost:11434")

        fake_json: dict[str, Any] = {
            "message": {"content": "ok"},
            "model": "llama3.1",
            "done_reason": "stop",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("openchronicle.core.infrastructure.llm.ollama_adapter.httpx.AsyncClient", return_value=mock_client):
            chunks: list[StreamChunk] = []
            async for chunk in adapter.stream_async(
                [{"role": "user", "content": "test"}],
                model="llama3.1",
                tools=SAMPLE_TOOLS,
            ):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].finished is True


# ===================================================================
# Tool-Use: Provider Facade Pass-Through
# ===================================================================


class TestFacadeToolPassThrough:
    async def test_facade_forwards_tools_to_adapter(self) -> None:
        from openchronicle.core.infrastructure.llm.provider_facade import ProviderAwareLLMFacade
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        stub = StubLLMAdapter()
        facade = ProviderAwareLLMFacade(adapters={"stub": stub}, default_provider="stub")

        result = await facade.complete_async(
            [{"role": "user", "content": "hi"}],
            model="stub",
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
        )
        assert isinstance(result, LLMResponse)


# ===================================================================
# Tool-Use: LLM Execution Pass-Through
# ===================================================================


class TestLLMExecutionToolPassThrough:
    async def test_execute_with_route_forwards_tools(self) -> None:
        from openchronicle.core.application.routing.router_policy import RouteDecision
        from openchronicle.core.application.services.llm_execution import execute_with_route
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        stub = StubLLMAdapter()
        route = RouteDecision(provider="stub", model="stub", mode="fast", reasons=["test"])

        result = await execute_with_route(
            stub,
            route,
            [{"role": "user", "content": "test"}],
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
        )
        assert isinstance(result, LLMResponse)

    async def test_stream_with_route_forwards_tools(self) -> None:
        from openchronicle.core.application.routing.router_policy import RouteDecision
        from openchronicle.core.application.services.llm_execution import stream_with_route
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        stub = StubLLMAdapter()
        route = RouteDecision(provider="stub", model="stub", mode="fast", reasons=["test"])

        chunks: list[StreamChunk] = []
        async for chunk in stream_with_route(
            stub,
            route,
            [{"role": "user", "content": "test"}],
            tools=SAMPLE_TOOLS,
        ):
            chunks.append(chunk)
        assert len(chunks) >= 1


# ===================================================================
# Tool-Use: Base LLMPort stream_async Fallback
# ===================================================================


class TestBasePortStreamFallbackWithTools:
    async def test_fallback_passes_tools_and_includes_tool_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Base stream_async passes tools through and includes tool_calls on chunk."""
        import json

        monkeypatch.setenv("OC_STUB_TOOL_CALLS", json.dumps([{"name": "get_weather", "arguments": "{}"}]))

        from openchronicle.core.domain.ports.llm_port import LLMPort
        from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

        adapter = StubLLMAdapter()
        chunks: list[StreamChunk] = []
        async for chunk in LLMPort.stream_async(
            adapter,
            [{"role": "user", "content": "test"}],
            model="stub",
            tools=SAMPLE_TOOLS,
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].finished is True
        assert chunks[0].tool_calls is not None
        assert chunks[0].tool_calls[0].name == "get_weather"
