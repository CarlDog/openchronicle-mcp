from __future__ import annotations

import os
import time
from typing import Any

import httpx

from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage


class OllamaAdapter(LLMPort):
    """
    Ollama LLM adapter for local model inference.

    Env vars:
    - OLLAMA_BASE_URL: Base URL for Ollama API (default: http://localhost:11434)
    - OLLAMA_MODEL: Default model to use if not specified
    """

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.default_model = model or os.getenv("OLLAMA_MODEL", "llama3.1")

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a chat completion using Ollama API."""
        start = time.perf_counter()

        # Prepare request payload
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
        }

        # Add optional parameters
        options: dict[str, Any] = {}
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        if temperature is not None:
            options["temperature"] = temperature
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Ollama request timed out: {exc}",
                status_code=None,
                error_code="timeout",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama HTTP error {exc.response.status_code}: {exc.response.text}",
                status_code=exc.response.status_code,
                error_code=f"http_{exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Ollama connection error: {exc}",
                status_code=None,
                error_code="connection_error",
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama unexpected error: {exc}",
                status_code=None,
                error_code="unknown",
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        # Parse response
        content = data.get("message", {}).get("content", "")

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
        )
