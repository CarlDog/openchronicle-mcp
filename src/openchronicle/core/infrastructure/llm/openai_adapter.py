from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass

try:
    import openai  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    openai = None

from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage


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
        return openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_ready(self) -> None:
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY not set", status_code=401, error_code="missing_api_key")
        if openai is None or self._client is None:
            raise LLMProviderError("openai package not installed", status_code=None, error_code="client_missing")

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        return asyncio.run(
            self.complete_async(
                messages,
                model=model,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        )

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        self._ensure_ready()

        start = time.perf_counter()
        try:
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=model or self.model,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception as exc:  # pragma: no cover - exercised via fake in tests
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=code) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = response.choices[0]
        content = getattr(choice.message, "content", None) or ""
        finish_reason = getattr(choice, "finish_reason", None)
        usage = getattr(response, "usage", None)

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
        )
