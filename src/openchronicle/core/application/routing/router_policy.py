"""Smart routing policy for LLM provider and model selection."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RouteDecision:
    """Decision for LLM provider and model selection."""

    provider: str
    model: str
    mode: str  # "fast" or "quality"
    reasons: list[str]


class RouterPolicy:
    """
    Deterministic routing policy for selecting LLM provider and model.

    Routes based on:
    - Agent tags (fast/quality hints)
    - Explicit quality preference
    - Budget constraints (downgrade to fast if low)
    - Rate limit constraints (downgrade to fast if constrained)
    - Environment configuration
    """

    def __init__(self) -> None:
        """Initialize router with environment configuration."""
        # Provider selection
        self.default_provider = os.getenv("OC_LLM_PROVIDER", "stub")

        # Model selection
        self.model_fast = os.getenv("OC_LLM_MODEL_FAST") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.model_quality = os.getenv("OC_LLM_MODEL_QUALITY") or os.getenv("OPENAI_MODEL", "gpt-4o")

        # Default mode
        self.default_mode = os.getenv("OC_LLM_DEFAULT_MODE", "fast")

        # Budget thresholds
        self.low_budget_threshold = int(os.getenv("OC_LLM_LOW_BUDGET_THRESHOLD", "500"))

        # Rate limit downgrade
        self.downgrade_on_rate_limit = os.getenv("OC_LLM_DOWNGRADE_ON_RATE_LIMIT", "1") == "1"

    def route(
        self,
        task_type: str,
        agent_role: str,
        agent_tags: list[str] | None = None,
        desired_quality: str | None = None,
        provider_preference: str | None = None,
        current_task_tokens: int | None = None,
        max_tokens_per_task: int | None = None,
        rate_limit_triggered: bool = False,
        rpm_limit: int | None = None,
    ) -> RouteDecision:
        """
        Route LLM call to appropriate provider and model.

        Args:
            task_type: Type of task being executed
            agent_role: Role of agent (worker/supervisor/manager)
            agent_tags: Tags on the agent (may include "fast" or "quality")
            desired_quality: Explicit quality hint ("fast" or "quality")
            provider_preference: Override provider selection
            current_task_tokens: Tokens already consumed by task
            max_tokens_per_task: Budget limit per task
            rate_limit_triggered: Whether rate limiting was recently triggered
            rpm_limit: RPM limit if rate limiting enabled

        Returns:
            RouteDecision with provider, model, mode, and reasons
        """
        reasons: list[str] = []
        agent_tags = agent_tags or []

        # Step 1: Determine provider
        provider = provider_preference or self.default_provider
        if provider_preference:
            reasons.append(f"provider_override:{provider_preference}")
        else:
            reasons.append(f"default_provider:{provider}")

        # Step 2: Determine desired mode from hints
        mode = self._determine_mode(agent_tags, desired_quality, reasons)

        # Step 3: Budget-aware downgrade
        if max_tokens_per_task is not None and current_task_tokens is not None:
            remaining = max_tokens_per_task - current_task_tokens
            if remaining < self.low_budget_threshold and mode == "quality":
                mode = "fast"
                reasons.append(f"low_budget_downgrade:remaining={remaining}")

        # Step 4: Rate-limit-aware downgrade
        if (
            self.downgrade_on_rate_limit
            and mode == "quality"
            and (rate_limit_triggered or (rpm_limit is not None and rpm_limit <= 1))
        ):
            mode = "fast"
            reasons.append("rate_limit_downgrade")

        # Step 5: Select model based on mode
        model = self._select_model(mode, provider, reasons)

        return RouteDecision(
            provider=provider,
            model=model,
            mode=mode,
            reasons=reasons,
        )

    def _determine_mode(
        self,
        agent_tags: list[str],
        desired_quality: str | None,
        reasons: list[str],
    ) -> str:
        """Determine mode from agent tags and explicit hint."""
        # Explicit quality preference takes precedence (from task payload)
        if desired_quality in ("fast", "quality"):
            reasons.append(f"mode_from_task_payload:{desired_quality}")
            return desired_quality

        # Agent tags
        if "quality" in agent_tags:
            reasons.append("mode_from_agent_tags:quality")
            return "quality"
        if "fast" in agent_tags:
            reasons.append("mode_from_agent_tags:fast")
            return "fast"

        # Default mode
        reasons.append(f"mode_from_default:{self.default_mode}")
        return self.default_mode

    def _select_model(self, mode: str, provider: str, reasons: list[str]) -> str:
        """Select model based on mode and provider."""
        # For stub provider, model doesn't matter
        if provider == "stub":
            reasons.append("stub_provider")
            return "stub-model"

        # For other providers, use configured models
        if mode == "quality":
            model = self.model_quality or "gpt-4o"  # Fallback to default
            reasons.append(f"quality_model:{model}")
            return model

        model = self.model_fast or "gpt-4o-mini"  # Fallback to default
        reasons.append(f"fast_model:{model}")
        return model
