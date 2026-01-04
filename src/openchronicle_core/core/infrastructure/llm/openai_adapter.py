from __future__ import annotations

import asyncio
from typing import Any

from openchronicle_core.core.domain.ports.llm_port import LLMPort


class OpenAIAdapter(LLMPort):
    def __init__(self, model: str = "gpt-4.1") -> None:
        self.model = model

    def generate(self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None) -> str:
        return f"[openai mock:{model or self.model}] {prompt}"

    async def generate_async(
        self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None
    ) -> str:
        await asyncio.sleep(0)
        return self.generate(prompt, model=model, parameters=parameters)
