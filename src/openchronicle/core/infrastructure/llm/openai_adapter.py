from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass

try:
    import openai
except ImportError:  # pragma: no cover - optional dependency
    openai = None  # type: ignore[assignment,unused-ignore]

from collections.abc import AsyncIterator

from openchronicle.core.domain.errors import CLIENT_MISSING, MISSING_API_KEY
from openchronicle.core.domain.ports.llm_port import (
    LLMPort,
    LLMProviderError,
    LLMResponse,
    LLMUsage,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)


class OpenAIAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if not self.api_key:
            return None
        if openai is None:
            return None
        return openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _ensure_ready(self) -> None:
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY not set", status_code=401, error_code=MISSING_API_KEY)
        if openai is None or self._client is None:
            raise LLMProviderError("openai package not installed", status_code=None, error_code=CLIENT_MISSING)

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
        self._ensure_ready()

        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]
        if tool_choice is not None and tools:
            if tool_choice in ("auto", "required", "none"):
                kwargs["tool_choice"] = tool_choice
            else:
                kwargs["tool_choice"] = {"type": "function", "function": {"name": tool_choice}}

        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - exercised via fake in tests
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=code) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = response.choices[0]
        content = getattr(choice.message, "content", None) or ""
        finish_reason = getattr(choice, "finish_reason", None)
        usage = getattr(response, "usage", None)

        # Extract tool calls
        result_tool_calls: list[ToolCall] | None = None
        raw_tool_calls = getattr(choice.message, "tool_calls", None)
        if raw_tool_calls:
            result_tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                )
                for tc in raw_tool_calls
            ]

        usage_obj = None
        if usage is not None:
            usage_obj = LLMUsage(
                input_tokens=getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )

        return LLMResponse(
            content=content,
            provider="openai",
            model=model or self.model,
            request_id=getattr(response, "id", None),
            finish_reason=finish_reason,
            usage=usage_obj,
            latency_ms=latency_ms,
            tool_calls=result_tool_calls,
        )

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
        self._ensure_ready()

        stream_kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            stream_kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]
        if tool_choice is not None and tools:
            if tool_choice in ("auto", "required", "none"):
                stream_kwargs["tool_choice"] = tool_choice
            else:
                stream_kwargs["tool_choice"] = {"type": "function", "function": {"name": tool_choice}}

        start = time.perf_counter()
        try:
            stream = await self._client.chat.completions.create(**stream_kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=code) from exc

        usage_obj: LLMUsage | None = None
        finish_reason: str | None = None
        # Accumulate tool call deltas: {index: {"id": ..., "name": ..., "arguments": ...}}
        tc_buffer: dict[int, dict[str, str]] = {}
        async for chunk in stream:
            # Usage comes on the final chunk with empty choices
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage_obj = LLMUsage(
                    input_tokens=getattr(chunk_usage, "prompt_tokens", None),
                    output_tokens=getattr(chunk_usage, "completion_tokens", None),
                    total_tokens=getattr(chunk_usage, "total_tokens", None),
                )

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None) or ""
            chunk_finish = getattr(chunk.choices[0], "finish_reason", None)
            if chunk_finish:
                finish_reason = chunk_finish

            # Accumulate tool call deltas
            delta_tool_calls = getattr(delta, "tool_calls", None)
            if delta_tool_calls:
                for dtc in delta_tool_calls:
                    idx = dtc.index
                    if idx not in tc_buffer:
                        tc_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                    if getattr(dtc, "id", None):
                        tc_buffer[idx]["id"] = dtc.id
                    fn = getattr(dtc, "function", None)
                    if fn:
                        if getattr(fn, "name", None):
                            tc_buffer[idx]["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            tc_buffer[idx]["arguments"] += fn.arguments

            if text or chunk_finish:
                # Build tool_calls on final chunk
                result_tool_calls: list[ToolCall] | None = None
                if chunk_finish and tc_buffer:
                    result_tool_calls = [
                        ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"])
                        for _, v in sorted(tc_buffer.items())
                    ]

                latency_ms = int((time.perf_counter() - start) * 1000) if chunk_finish else None
                yield StreamChunk(
                    text=text,
                    finished=bool(chunk_finish),
                    provider="openai",
                    model=model or self.model,
                    finish_reason=finish_reason if chunk_finish else None,
                    usage=usage_obj if chunk_finish else None,
                    latency_ms=latency_ms,
                    tool_calls=result_tool_calls,
                )
