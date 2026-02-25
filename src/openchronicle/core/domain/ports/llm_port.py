from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class ToolDefinition:
    """A tool/function the model may call."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class ToolCall:
    """A tool call returned by the model."""

    id: str
    name: str
    arguments: str  # Always JSON string (adapters normalize)


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    request_id: str | None = None
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    latency_ms: int | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    text: str
    finished: bool = False
    provider: str = ""
    model: str = ""
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    latency_ms: int | None = None
    tool_calls: list[ToolCall] | None = None


class LLMProviderError(Exception):
    """Exception raised when LLM provider encounters an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        provider: str | None = None,
        configured_providers: list[str] | None = None,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize LLM provider error with structured context.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (if applicable)
            error_code: Machine-readable error code (e.g., "PROVIDER_NOT_CONFIGURED")
            provider: Provider that was requested
            configured_providers: List of available providers
            hint: Actionable hint for resolving the error
            details: Additional structured error details
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.provider = provider
        self.configured_providers = configured_providers or []
        self.hint = hint
        self.details = details or {}


class LLMPort(ABC):
    @abstractmethod
    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Generate a chat completion asynchronously.

        Messages use OpenAI-like dict format. Tool-related messages:
        - Assistant with tool calls: {"role": "assistant", "content": None,
          "tool_calls": [{"id": "...", "type": "function",
          "function": {"name": "...", "arguments": "..."}}]}
        - Tool result: {"role": "tool", "tool_call_id": "...", "name": "...",
          "content": "..."}
        The ``name`` field on tool results is included because Gemini requires it.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            max_output_tokens: Maximum tokens in response
            temperature: Sampling temperature
            provider: Provider name (e.g., 'openai', 'ollama', 'stub').
                      If None, adapter uses its default provider.
            tools: Optional list of tool definitions the model may call
            tool_choice: Tool choice strategy - "auto", "required", "none",
                         or a specific tool name. None means provider default.

        Returns:
            LLMResponse with content, provider, model, usage, etc.

        Raises:
            LLMProviderError: If the call fails or provider is not available
        """

    async def stream_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion as chunks.

        Default implementation falls back to complete_async and yields the
        full response as a single chunk. Override in adapters that support
        native streaming.
        """
        response = await self.complete_async(
            messages,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            provider=provider,
            tools=tools,
            tool_choice=tool_choice,
        )
        yield StreamChunk(
            text=response.content,
            finished=True,
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            latency_ms=response.latency_ms,
            tool_calls=response.tool_calls,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Synchronous convenience wrapper."""

        raise NotImplementedError
