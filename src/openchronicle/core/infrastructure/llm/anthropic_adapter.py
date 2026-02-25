from __future__ import annotations

import json
import os
import time
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore[assignment,unused-ignore]

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


class AnthropicAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.timeout_seconds = timeout_seconds
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if not self.api_key:
            return None
        if anthropic is None:
            return None
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.timeout_seconds is not None:
            kwargs["timeout"] = self.timeout_seconds
        return anthropic.AsyncAnthropic(**kwargs)

    def _ensure_ready(self) -> None:
        if not self.api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY not set", status_code=401, error_code=MISSING_API_KEY)
        if anthropic is None or self._client is None:
            raise LLMProviderError("anthropic package not installed", status_code=None, error_code=CLIENT_MISSING)

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

        # Transform tool-related messages to Anthropic format before system extraction
        transformed: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role == "tool":
                # Tool result → user message with tool_result content block
                transformed.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg["tool_call_id"],
                                "content": msg.get("content", ""),
                            }
                        ],
                    }
                )
            elif role == "assistant" and msg.get("tool_calls"):
                # Assistant with tool calls → content blocks
                blocks: list[dict[str, Any]] = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": fn["name"],
                            "input": json.loads(fn["arguments"]),
                        }
                    )
                transformed.append({"role": "assistant", "content": blocks})
            else:
                transformed.append(msg)

        # Anthropic requires system messages as a top-level param, not in the messages array
        system_parts: list[str] = []
        filtered_messages: list[dict[str, Any]] = []
        for msg in transformed:
            if msg.get("role") == "system":
                system_parts.append(str(msg.get("content", "")))
            else:
                filtered_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": filtered_messages,
            "max_tokens": max_output_tokens or 4096,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        if temperature is not None:
            kwargs["temperature"] = temperature

        # Add tools
        if tools and tool_choice != "none":
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools
            ]
        if tool_choice is not None and tools:
            if tool_choice == "auto":
                kwargs["tool_choice"] = {"type": "auto"}
            elif tool_choice == "required":
                kwargs["tool_choice"] = {"type": "any"}
            elif tool_choice != "none":
                # "none" is handled above by omitting tools from kwargs
                kwargs["tool_choice"] = {"type": "tool", "name": tool_choice}

        start = time.perf_counter()
        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=code) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        # Parse content blocks — may include text and tool_use
        content = ""
        result_tool_calls: list[ToolCall] | None = None
        if response.content:
            text_parts: list[str] = []
            tc_list: list[ToolCall] = []
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    text_parts.append(getattr(block, "text", "") or "")
                elif block_type == "tool_use":
                    tc_list.append(
                        ToolCall(
                            id=block.id,
                            name=block.name,
                            arguments=json.dumps(block.input),
                        )
                    )
            content = "".join(text_parts)
            if tc_list:
                result_tool_calls = tc_list

        usage_obj = None
        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)
            total = None
            if input_tokens is not None and output_tokens is not None:
                total = input_tokens + output_tokens
            usage_obj = LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total,
            )

        return LLMResponse(
            content=content,
            provider="anthropic",
            model=model or self.model,
            request_id=getattr(response, "id", None),
            finish_reason=getattr(response, "stop_reason", None),
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

        # Fall back to complete_async when tools are provided (v0 — streaming
        # with tool use requires event-level parsing of Anthropic's stream)
        if tools:
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
            return

        system_parts: list[str] = []
        filtered_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(str(msg.get("content", "")))
            else:
                filtered_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": filtered_messages,
            "max_tokens": max_output_tokens or 4096,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        if temperature is not None:
            kwargs["temperature"] = temperature

        start = time.perf_counter()
        try:
            stream = self._client.messages.stream(**kwargs)

            async with stream as response:
                async for text in response.text_stream:
                    yield StreamChunk(
                        text=text,
                        finished=False,
                        provider="anthropic",
                        model=model or self.model,
                    )

                final_message = await response.get_final_message()
                usage_obj = None
                usage = getattr(final_message, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "input_tokens", None)
                    output_tokens = getattr(usage, "output_tokens", None)
                    total = None
                    if input_tokens is not None and output_tokens is not None:
                        total = input_tokens + output_tokens
                    usage_obj = LLMUsage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total,
                    )

                latency_ms = int((time.perf_counter() - start) * 1000)
                yield StreamChunk(
                    text="",
                    finished=True,
                    provider="anthropic",
                    model=model or self.model,
                    finish_reason=getattr(final_message, "stop_reason", None),
                    usage=usage_obj,
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=code) from exc
