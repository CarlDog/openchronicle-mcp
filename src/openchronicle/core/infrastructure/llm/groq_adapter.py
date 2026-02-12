from __future__ import annotations

import os
import time
from typing import Any

try:
    import groq
except ImportError:  # pragma: no cover - optional dependency
    groq = None  # type: ignore[assignment,unused-ignore]

from openchronicle.core.domain.errors import CLIENT_MISSING, MISSING_API_KEY
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage


class GroqAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if not self.api_key:
            return None
        if groq is None:
            return None
        return groq.AsyncGroq(api_key=self.api_key)

    def _ensure_ready(self) -> None:
        if not self.api_key:
            raise LLMProviderError("GROQ_API_KEY not set", status_code=401, error_code=MISSING_API_KEY)
        if groq is None or self._client is None:
            raise LLMProviderError("groq package not installed", status_code=None, error_code=CLIENT_MISSING)

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

        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception as exc:
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
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )

        return LLMResponse(
            content=content,
            provider="groq",
            model=model or self.model,
            request_id=getattr(response, "id", None),
            finish_reason=finish_reason,
            usage=usage_obj,
            latency_ms=latency_ms,
        )
