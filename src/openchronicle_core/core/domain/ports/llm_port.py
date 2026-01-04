from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None) -> str:
        """Generate a response synchronously."""

    @abstractmethod
    async def generate_async(
        self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None
    ) -> str:
        """Async variant for orchestration pipelines."""
