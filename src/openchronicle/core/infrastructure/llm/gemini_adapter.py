from __future__ import annotations

import os
import time
from typing import Any

try:
    from google import genai
    from google.genai.types import Content, GenerateContentConfig, Part
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment,unused-ignore]
    Content = None  # type: ignore[assignment,misc,unused-ignore]
    GenerateContentConfig = None  # type: ignore[assignment,misc,unused-ignore]
    Part = None  # type: ignore[assignment,misc,unused-ignore]

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


class GeminiAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
        self.timeout_seconds = timeout_seconds
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if not self.api_key:
            return None
        if genai is None:
            return None
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.timeout_seconds is not None:
            kwargs["http_options"] = {"timeout": self.timeout_seconds}
        return genai.Client(**kwargs)

    def _ensure_ready(self) -> None:
        if not self.api_key:
            raise LLMProviderError("GEMINI_API_KEY not set", status_code=401, error_code=MISSING_API_KEY)
        if genai is None or self._client is None:
            raise LLMProviderError("google-genai package not installed", status_code=None, error_code=CLIENT_MISSING)

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

        # Convert OpenAI-format messages to Gemini format
        system_parts: list[str] = []
        contents: list[Any] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system_parts.append(str(msg.get("content", "")))
            elif role == "tool":
                # Tool result → user message with function response part
                import json as json_mod

                result_content = msg.get("content", "")
                try:
                    response_data = json_mod.loads(result_content)
                except (json_mod.JSONDecodeError, TypeError):
                    response_data = {"result": result_content}
                contents.append(
                    Content(
                        role="user",
                        parts=[
                            Part.from_function_response(
                                name=msg.get("name", ""),
                                response=response_data,
                            )
                        ],
                    )
                )
            elif role == "assistant" and msg.get("tool_calls"):
                # Assistant with tool calls → model message with function call parts
                import json as json_mod

                parts: list[Any] = []
                if msg.get("content"):
                    parts.append(Part.from_text(text=str(msg["content"])))
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    args = json_mod.loads(fn["arguments"])
                    parts.append(Part.from_function_call(name=fn["name"], args=args))
                contents.append(Content(role="model", parts=parts))
            else:
                # Gemini uses "model" instead of "assistant"
                gemini_role = "model" if role == "assistant" else "user"
                text = str(msg.get("content", ""))
                contents.append(Content(role=gemini_role, parts=[Part.from_text(text=text)]))

        config_kwargs: dict[str, Any] = {}
        if system_parts:
            config_kwargs["system_instruction"] = "\n\n".join(system_parts)
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            config_kwargs["temperature"] = temperature

        # Add tools
        if tools:
            config_kwargs["tools"] = [
                {
                    "function_declarations": [
                        {"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools
                    ]
                }
            ]
        if tool_choice is not None and tools:
            if tool_choice == "auto":
                config_kwargs["tool_config"] = {"function_calling_config": {"mode": "AUTO"}}
            elif tool_choice == "required":
                config_kwargs["tool_config"] = {"function_calling_config": {"mode": "ANY"}}
            elif tool_choice == "none":
                config_kwargs["tool_config"] = {"function_calling_config": {"mode": "NONE"}}
            else:
                config_kwargs["tool_config"] = {
                    "function_calling_config": {
                        "mode": "ANY",
                        "allowed_function_names": [tool_choice],
                    }
                }

        config = GenerateContentConfig(**config_kwargs) if config_kwargs else None

        start = time.perf_counter()
        try:
            kwargs: dict[str, Any] = {
                "model": model or self.model,
                "contents": contents,
            }
            if config is not None:
                kwargs["config"] = config
            response = await self._client.aio.models.generate_content(**kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=None) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        # Parse response parts — may include text and function_call
        import json as json_mod
        import uuid

        content = ""
        result_tool_calls: list[ToolCall] | None = None
        candidates = getattr(response, "candidates", None)
        if candidates:
            text_parts: list[str] = []
            tc_list: list[ToolCall] = []
            parts = getattr(candidates[0].content, "parts", None) or []
            for part in parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                fn_call = getattr(part, "function_call", None)
                if fn_call:
                    tc_list.append(
                        ToolCall(
                            id=f"gemini_{uuid.uuid4().hex[:12]}",
                            name=fn_call.name,
                            arguments=json_mod.dumps(dict(fn_call.args)) if fn_call.args else "{}",
                        )
                    )
            content = "".join(text_parts)
            if tc_list:
                result_tool_calls = tc_list
        else:
            content = getattr(response, "text", None) or ""

        usage_obj = None
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is not None:
            input_tokens = getattr(usage_metadata, "prompt_token_count", None)
            output_tokens = getattr(usage_metadata, "candidates_token_count", None)
            total_tokens = getattr(usage_metadata, "total_token_count", None)
            usage_obj = LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

        return LLMResponse(
            content=content,
            provider="gemini",
            model=model or self.model,
            finish_reason=None,
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

        # Fall back to complete_async when tools are provided (v0)
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
        contents: list[Any] = []
        for msg in messages:
            role = msg.get("role", "user")
            text = str(msg.get("content", ""))
            if role == "system":
                system_parts.append(text)
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append(Content(role=gemini_role, parts=[Part.from_text(text=text)]))

        config_kwargs: dict[str, Any] = {}
        if system_parts:
            config_kwargs["system_instruction"] = "\n\n".join(system_parts)
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            config_kwargs["temperature"] = temperature

        config = GenerateContentConfig(**config_kwargs) if config_kwargs else None

        start = time.perf_counter()
        try:
            kwargs: dict[str, Any] = {
                "model": model or self.model,
                "contents": contents,
            }
            if config is not None:
                kwargs["config"] = config
            stream = self._client.aio.models.generate_content_stream(**kwargs)

            usage_obj: LLMUsage | None = None
            finish_reason: str | None = None
            async for chunk in stream:
                text = getattr(chunk, "text", None) or ""
                usage_metadata = getattr(chunk, "usage_metadata", None)
                if usage_metadata is not None:
                    usage_obj = LLMUsage(
                        input_tokens=getattr(usage_metadata, "prompt_token_count", None),
                        output_tokens=getattr(usage_metadata, "candidates_token_count", None),
                        total_tokens=getattr(usage_metadata, "total_token_count", None),
                    )
                candidates = getattr(chunk, "candidates", None)
                if candidates:
                    reason = getattr(candidates[0], "finish_reason", None)
                    if reason is not None:
                        finish_reason = str(reason)
                if text:
                    yield StreamChunk(
                        text=text,
                        finished=False,
                        provider="gemini",
                        model=model or self.model,
                    )

            latency_ms = int((time.perf_counter() - start) * 1000)
            yield StreamChunk(
                text="",
                finished=True,
                provider="gemini",
                model=model or self.model,
                finish_reason=finish_reason,
                usage=usage_obj,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=None) from exc
