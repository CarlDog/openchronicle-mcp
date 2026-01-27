"""Stub LLM adapter for testing and default behavior."""

from __future__ import annotations

import json
import os
from typing import Any

from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse


class StubLLMAdapter(LLMPort):
    """Simple stub LLM that returns truncated input for testing."""

    def __init__(self) -> None:
        self.model = "stub"

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """Return a stub response based on input messages."""
        # Only use user messages for stub summary (ignore system prompts)
        user_messages = [msg.get("content", "") for msg in messages if msg.get("role") == "user"]
        text = " ".join(str(content) for content in user_messages if isinstance(content, str))

        meta_echo = os.getenv("OC_STUB_META_ECHO", "0") == "1"
        if meta_echo:
            ids_raw = os.getenv("OC_STUB_META_IDS", "")
            used_ids = [item.strip() for item in ids_raw.split(",") if item.strip()]
            meta = json.dumps({"used_memory_ids": used_ids}, sort_keys=True)
            summary = f"stub response\n<OC_META>{meta}</OC_META>"
        else:
            # Simple stub summarization: truncate to max length
            cleaned = " ".join(text.split())
            summary = cleaned if len(cleaned) <= 160 else cleaned[:150].rsplit(" ", 1)[0] + "..."

        return LLMResponse(
            content=summary,
            provider="stub",
            model=model or self.model,
            request_id=None,
            finish_reason="stop",
            usage=None,
            latency_ms=0,
        )
