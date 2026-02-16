"""Smart routing policy for LLM provider and model selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openchronicle.core.application.routing.pool_config import PoolConfig, ProviderCandidate, load_pool_config
from openchronicle.core.infrastructure.config.env_helpers import (
    env_override,
    parse_bool,
    parse_int,
    parse_str,
)


@dataclass
class RouteDecision:
    """Decision for LLM provider and model selection."""

    provider: str
    model: str
    mode: str  # "fast" or "quality"
    reasons: list[str]
    candidates: list[tuple[str, str, int]] | None = None  # [(provider, model, weight), ...]


class RouterPolicy:
    """
    Deterministic routing policy for selecting LLM provider and model.

    Routes based on:
    - Provider pools (multi-provider with weighted selection)
    - Agent tags (fast/quality hints)
    - Explicit quality preference
    - Budget constraints (downgrade to fast if low)
    - Rate limit constraints (downgrade to fast if constrained)
    - Environment configuration
    """

    def __init__(
        self,
        file_config: dict[str, Any] | None = None,
        *,
        pool_config: PoolConfig | None = None,
    ) -> None:
        """Initialize router with JSON config + env var overrides.

        Args:
            file_config: Parsed app.json contents (or None for env-only).
            pool_config: Pre-built PoolConfig (avoids double loading in container).
        """
        fc = file_config or {}

        # Provider selection
        self.default_provider = parse_str(
            env_override("OC_LLM_PROVIDER", fc.get("provider")),
            default="stub",
        )

        # Model selection (fallback when pools not configured)
        model_fast_raw = env_override("OC_LLM_MODEL_FAST", fc.get("model_fast"))
        if model_fast_raw is None:
            model_fast_raw = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.model_fast = parse_str(model_fast_raw, default="gpt-4o-mini")

        model_quality_raw = env_override("OC_LLM_MODEL_QUALITY", fc.get("model_quality"))
        if model_quality_raw is None:
            model_quality_raw = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.model_quality = parse_str(model_quality_raw, default="gpt-4o")

        # Default mode
        self.default_mode = parse_str(
            env_override("OC_LLM_DEFAULT_MODE", fc.get("default_mode")),
            default="fast",
        )

        # Budget thresholds
        self.low_budget_threshold = parse_int(
            env_override("OC_LLM_LOW_BUDGET_THRESHOLD", fc.get("low_budget_threshold")),
            default=500,
        )

        # Rate limit downgrade
        self.downgrade_on_rate_limit = parse_bool(
            env_override("OC_LLM_DOWNGRADE_ON_RATE_LIMIT", fc.get("downgrade_on_rate_limit")),
            default=True,
        )

        # Load pool configuration (use pre-built if provided)
        self.pool_config: PoolConfig = pool_config if pool_config is not None else load_pool_config()

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

        Supports both pool-based routing (when pools configured) and single-provider fallback when pools are empty.

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
            RouteDecision with provider, model, mode, reasons, and optional candidates
        """
        reasons: list[str] = []
        agent_tags = agent_tags or []

        # Step 1: Determine desired mode from hints
        mode = self._determine_mode(agent_tags, desired_quality, reasons)

        # Step 2: Budget-aware downgrade
        if max_tokens_per_task is not None and current_task_tokens is not None:
            remaining = max_tokens_per_task - current_task_tokens
            if remaining < self.low_budget_threshold and mode == "quality":
                mode = "fast"
                reasons.append(f"low_budget_downgrade:remaining={remaining}")

        # Step 3: Rate-limit-aware downgrade
        if (
            self.downgrade_on_rate_limit
            and mode == "quality"
            and (rate_limit_triggered or (rpm_limit is not None and rpm_limit <= 1))
        ):
            mode = "fast"
            reasons.append("rate_limit_downgrade")

        # Step 4: Choose provider and model (pool-based or fallback)
        pool = self.pool_config.fast_pool if mode == "fast" else self.pool_config.quality_pool

        if pool:
            # Pool-based routing
            return self._route_from_pool(pool, mode, reasons, provider_preference)

        # Single-provider mode when pools not configured
        provider = provider_preference or self.default_provider
        if provider_preference:
            reasons.append(f"provider_override:{provider_preference}")
        else:
            reasons.append(f"default_provider:{provider}")

        model = self._select_model(mode, provider, reasons)

        return RouteDecision(
            provider=provider,
            model=model,
            mode=mode,
            reasons=reasons,
        )

    def route_with_pool(
        self,
        pool: list[ProviderCandidate],
        *,
        mode: str,
        provider_preference: str | None = None,
        reasons: list[str] | None = None,
    ) -> RouteDecision:
        route_reasons = reasons or []
        return self._route_from_pool(pool, mode, route_reasons, provider_preference)

    def _route_from_pool(
        self,
        pool: list[ProviderCandidate],
        mode: str,
        reasons: list[str],
        provider_preference: str | None,
    ) -> RouteDecision:
        """
        Route from a provider pool using weighted selection.

        Args:
            pool: List of provider candidates
            mode: Routing mode (fast/quality)
            reasons: List to append routing reasons to
            provider_preference: Optional provider override

        Returns:
            RouteDecision with selected provider, model, and candidate list
        """
        if not pool:
            # Fallback to single-provider if pool is empty
            provider = provider_preference or self.default_provider
            reasons.append(f"empty_pool_fallback:{provider}")
            model = self._select_model(mode, provider, reasons)
            return RouteDecision(provider=provider, model=model, mode=mode, reasons=reasons)

        # Apply provider override if specified
        if provider_preference:
            filtered = [c for c in pool if c.provider == provider_preference]
            if filtered:
                pool = filtered
                reasons.append(f"provider_override:{provider_preference}")
            else:
                reasons.append(f"provider_override_not_in_pool:{provider_preference}")

        # Sort by weight (desc), then provider name, then model name for determinism
        sorted_candidates = sorted(pool, key=lambda c: (-c.weight, c.provider, c.model))

        # Select top candidate
        primary = sorted_candidates[0]
        reasons.append(f"pool_selection:{primary.provider}:{primary.model}:weight={primary.weight}")

        # Build candidate list for debugging/events
        candidates = [(c.provider, c.model, c.weight) for c in sorted_candidates]

        return RouteDecision(
            provider=primary.provider,
            model=primary.model,
            mode=mode,
            reasons=reasons,
            candidates=candidates,
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
