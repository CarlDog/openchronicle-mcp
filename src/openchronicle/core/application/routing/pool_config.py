"""Provider pool configuration and parsing for multi-provider routing."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ProviderCandidate:
    """A candidate provider+model combination."""

    provider: str
    model: str
    weight: int = 100


@dataclass
class PoolConfig:
    """Configuration for fast and quality provider pools."""

    fast_pool: list[ProviderCandidate]
    quality_pool: list[ProviderCandidate]
    nsfw_pool: list[ProviderCandidate]
    provider_weights: dict[str, int]
    max_fallbacks: int
    fallback_on_transient: bool
    fallback_on_constraint: bool
    fallback_on_refusal: bool


def parse_pool_string(pool_str: str, provider_weights: dict[str, int]) -> list[ProviderCandidate]:
    """
    Parse provider pool string into candidate list.

    Format: "ollama:llama3.1,openai:gpt-4o-mini,..."

    Args:
        pool_str: Comma-separated provider:model pairs
        provider_weights: Weight mapping for providers

    Returns:
        List of ProviderCandidate with weights applied
    """
    candidates: list[ProviderCandidate] = []

    if not pool_str or not pool_str.strip():
        return candidates

    for entry in pool_str.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue

        parts = entry.split(":", 1)
        if len(parts) != 2:
            continue

        provider = parts[0].strip()
        model = parts[1].strip()

        if not provider or not model:
            continue

        weight = provider_weights.get(provider, 100)
        candidates.append(ProviderCandidate(provider=provider, model=model, weight=weight))

    return candidates


def load_pool_config() -> PoolConfig:
    """
    Load provider pool configuration from environment variables.

    Environment Variables:
    - OC_LLM_FAST_POOL: Fast mode pool (e.g., "ollama:llama3.1,openai:gpt-4o-mini")
    - OC_LLM_QUALITY_POOL: Quality mode pool (e.g., "openai:gpt-4o,ollama:mixtral")
    - OC_LLM_POOL_NSFW: NSFW mode pool (e.g., "openai:gpt-4o,ollama:mixtral")
    - OC_LLM_PROVIDER_WEIGHTS: Provider preference weights (e.g., "ollama:100,openai:20")
    - OC_LLM_MAX_FALLBACKS: Maximum fallback attempts (default: 1)
    - OC_LLM_FALLBACK_ON_TRANSIENT: Allow fallback on transient errors (default: 1)
    - OC_LLM_FALLBACK_ON_CONSTRAINT: Allow fallback on constraint errors (default: 1)
    - OC_LLM_FALLBACK_ON_REFUSAL: Allow fallback on refusals (default: 0)

    Returns:
        PoolConfig with parsed pools and settings
    """
    # Parse provider weights
    weights_str = os.getenv("OC_LLM_PROVIDER_WEIGHTS", "ollama:100,openai:20")
    provider_weights: dict[str, int] = {}

    for entry in weights_str.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        parts = entry.split(":", 1)
        if len(parts) == 2:
            provider = parts[0].strip()
            try:
                weight = int(parts[1].strip())
                provider_weights[provider] = weight
            except ValueError:
                continue

    # Parse pools
    fast_pool_str = os.getenv("OC_LLM_FAST_POOL", "")
    quality_pool_str = os.getenv("OC_LLM_QUALITY_POOL", "")
    nsfw_pool_str = os.getenv("OC_LLM_POOL_NSFW", "")

    fast_pool = parse_pool_string(fast_pool_str, provider_weights)
    quality_pool = parse_pool_string(quality_pool_str, provider_weights)
    nsfw_pool = parse_pool_string(nsfw_pool_str, provider_weights)

    # Parse fallback controls
    max_fallbacks = int(os.getenv("OC_LLM_MAX_FALLBACKS", "1"))
    fallback_on_transient = os.getenv("OC_LLM_FALLBACK_ON_TRANSIENT", "1") == "1"
    fallback_on_constraint = os.getenv("OC_LLM_FALLBACK_ON_CONSTRAINT", "1") == "1"
    fallback_on_refusal = os.getenv("OC_LLM_FALLBACK_ON_REFUSAL", "0") == "1"

    return PoolConfig(
        fast_pool=fast_pool,
        quality_pool=quality_pool,
        nsfw_pool=nsfw_pool,
        provider_weights=provider_weights,
        max_fallbacks=max_fallbacks,
        fallback_on_transient=fallback_on_transient,
        fallback_on_constraint=fallback_on_constraint,
        fallback_on_refusal=fallback_on_refusal,
    )
