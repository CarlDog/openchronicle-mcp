"""LLM provider selection based on environment configuration."""

from __future__ import annotations

import os
from typing import Literal

from openchronicle.core.domain.error_codes import (
    INVALID_PROVIDER,
    MISSING_API_KEY,
    MISSING_PACKAGE,
)
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError

ProviderType = Literal["stub", "openai"]


class LLMProviderSelector:
    """Centralized LLM provider selection logic."""

    @staticmethod
    def get_provider_type(override: ProviderType | None = None) -> ProviderType:
        """
        Determine which LLM provider to use.

        Priority:
        1. Runtime override (e.g., from CLI flag)
        2. OC_LLM_PROVIDER environment variable
        3. Default to "stub"

        Args:
            override: Optional runtime override for provider selection

        Returns:
            Provider type: "stub" or "openai"
        """
        if override:
            return override

        env_provider = os.getenv("OC_LLM_PROVIDER", "stub").lower()
        if env_provider not in ("stub", "openai"):
            return "stub"

        return env_provider  # type: ignore[return-value]

    @staticmethod
    def create_provider(provider_type: ProviderType) -> LLMPort:
        """
        Create an LLM provider instance.

        Args:
            provider_type: Type of provider to create

        Returns:
            LLMPort instance

        Raises:
            LLMProviderError: If provider requirements are not met
        """
        if provider_type == "stub":
            from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

            return StubLLMAdapter()

        if provider_type == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise LLMProviderError(
                    "OPENAI_API_KEY environment variable is required when OC_LLM_PROVIDER=openai",
                    status_code=401,
                    error_code=MISSING_API_KEY,
                )

            try:
                from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter
            except ImportError as exc:
                raise LLMProviderError(
                    "OpenAI adapter requires the openai package. Install with: pip install openchronicle-core[openai]",
                    status_code=None,
                    error_code=MISSING_PACKAGE,
                ) from exc

            return OpenAIAdapter(api_key=api_key)

        # This should never happen due to type checking, but be defensive
        raise LLMProviderError(f"Unknown provider type: {provider_type}", status_code=None, error_code=INVALID_PROVIDER)
