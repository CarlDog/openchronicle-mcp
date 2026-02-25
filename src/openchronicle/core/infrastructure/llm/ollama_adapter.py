from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from openchronicle.core.domain.errors.error_codes import (
    CONNECTION_ERROR,
    PROVIDER_ERROR,
    TIMEOUT,
    UNKNOWN_ERROR,
)
from openchronicle.core.domain.ports.llm_port import (
    LLMPort,
    LLMProviderError,
    LLMResponse,
    LLMUsage,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)


class OllamaAdapter(LLMPort):
    """
    Ollama LLM adapter for local model inference.

    Env vars:
    - OLLAMA_BASE_URL: Base URL for Ollama API (default: http://localhost:11434)
    - OLLAMA_MODEL: Default model to use if not specified
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.default_model = model or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.timeout_seconds = timeout_seconds or 60.0

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
        """Generate a chat completion using Ollama API."""
        start = time.perf_counter()

        # Prepare request payload
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
        }

        # Add tools (OpenAI-compatible format)
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]

        # Add optional parameters
        options: dict[str, Any] = {}
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        if temperature is not None:
            options["temperature"] = temperature
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Ollama request timed out: {exc}",
                status_code=None,
                error_code=TIMEOUT,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Ollama connection error: {exc}",
                status_code=None,
                error_code=CONNECTION_ERROR,
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama unexpected error: {exc}",
                status_code=None,
                error_code=UNKNOWN_ERROR,
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        # Parse response
        content = data.get("message", {}).get("content", "")

        # Extract tool calls
        import json as json_mod
        import uuid

        result_tool_calls: list[ToolCall] | None = None
        raw_tool_calls = data.get("message", {}).get("tool_calls")
        if raw_tool_calls:
            tc_list: list[ToolCall] = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                # Normalize: Ollama may return parsed dict instead of JSON string
                if isinstance(args, dict):
                    args = json_mod.dumps(args)
                tc_list.append(
                    ToolCall(
                        id=tc.get("id", f"ollama_{uuid.uuid4().hex[:12]}"),
                        name=fn.get("name", ""),
                        arguments=args,
                    )
                )
            result_tool_calls = tc_list

        # Ollama may not always return token usage; handle gracefully
        usage_data = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage_data = LLMUsage(
                input_tokens=data.get("prompt_eval_count"),
                output_tokens=data.get("eval_count"),
                total_tokens=(data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0),
            )

        return LLMResponse(
            content=content,
            provider="ollama",
            model=data.get("model") or model,
            finish_reason=data.get("done_reason"),
            usage=usage_data,
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
        """Stream a chat completion using Ollama API."""
        # Fall back to complete_async when tools are provided (v0)
        if tools:
            fallback = await self.complete_async(
                messages,
                model=model,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                provider=provider,
                tools=tools,
                tool_choice=tool_choice,
            )
            yield StreamChunk(
                text=fallback.content,
                finished=True,
                provider=fallback.provider,
                model=fallback.model,
                finish_reason=fallback.finish_reason,
                usage=fallback.usage,
                latency_ms=fallback.latency_ms,
                tool_calls=fallback.tool_calls,
            )
            return

        import json as json_mod

        start = time.perf_counter()

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
        }

        options: dict[str, Any] = {}
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        if temperature is not None:
            options["temperature"] = temperature
        if options:
            payload["options"] = options

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_seconds) as client,
                client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response,
            ):
                if response.status_code >= 400:
                    await response.aread()
                    raise LLMProviderError(
                        f"Ollama HTTP error {response.status_code}: {response.text}",
                        status_code=response.status_code,
                        error_code=PROVIDER_ERROR,
                    )
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    data = json_mod.loads(line)
                    text = data.get("message", {}).get("content", "")
                    done = data.get("done", False)

                    usage_obj: LLMUsage | None = None
                    if done and ("prompt_eval_count" in data or "eval_count" in data):
                        usage_obj = LLMUsage(
                            input_tokens=data.get("prompt_eval_count"),
                            output_tokens=data.get("eval_count"),
                            total_tokens=(data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0),
                        )

                    if text or done:
                        latency_ms = int((time.perf_counter() - start) * 1000) if done else None
                        yield StreamChunk(
                            text=text,
                            finished=bool(done),
                            provider="ollama",
                            model=str(data.get("model") or model or self.default_model),
                            finish_reason=data.get("done_reason") if done else None,
                            usage=usage_obj,
                            latency_ms=latency_ms,
                        )
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Ollama request timed out: {exc}",
                status_code=None,
                error_code=TIMEOUT,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Ollama connection error: {exc}",
                status_code=None,
                error_code=CONNECTION_ERROR,
            ) from exc
        except LLMProviderError:
            raise
        except json_mod.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Ollama streaming JSON decode error: {exc}",
                status_code=None,
                error_code=PROVIDER_ERROR,
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama streaming error: {exc}",
                status_code=None,
                error_code=UNKNOWN_ERROR,
            ) from exc
