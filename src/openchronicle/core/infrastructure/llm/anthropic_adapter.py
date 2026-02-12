from __future__ import annotations

import os
import time
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore[assignment,unused-ignore]

from openchronicle.core.domain.errors import CLIENT_MISSING, MISSING_API_KEY
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage


class AnthropicAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if not self.api_key:
            return None
        if anthropic is None:
            return None
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
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
    ) -> LLMResponse:
        self._ensure_ready()

        # Anthropic requires system messages as a top-level param, not in the messages array
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
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=code) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        content = ""
        if response.content:
            content = getattr(response.content[0], "text", "") or ""

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
        )
