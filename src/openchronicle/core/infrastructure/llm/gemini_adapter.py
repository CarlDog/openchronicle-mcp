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

from openchronicle.core.domain.errors import CLIENT_MISSING, MISSING_API_KEY
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage


class GeminiAdapter(LLMPort):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if not self.api_key:
            return None
        if genai is None:
            return None
        return genai.Client(api_key=self.api_key)

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
    ) -> LLMResponse:
        self._ensure_ready()

        # Convert OpenAI-format messages to Gemini format
        system_parts: list[str] = []
        contents: list[Any] = []
        for msg in messages:
            role = msg.get("role", "user")
            text = str(msg.get("content", ""))
            if role == "system":
                system_parts.append(text)
            else:
                # Gemini uses "model" instead of "assistant"
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
            response = await self._client.aio.models.generate_content(**kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            raise LLMProviderError(str(exc), status_code=status, error_code=None) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

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
        )
