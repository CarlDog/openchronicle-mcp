"""Provider pool configuration and parsing for multi-provider routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openchronicle.core.infrastructure.config.env_helpers import (
    env_override,
    parse_bool,
    parse_int,
    parse_str,
)


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


def _parse_weights_string(weights_str: str) -> dict[str, int]:
    """Parse a 'provider:weight,...' string into a dict."""
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
    return provider_weights


def _parse_weights(value: object) -> dict[str, int]:
    """Parse weights from a JSON object or CSV string.

    JSON: {"ollama": 100, "openai": 20}
    CSV:  "ollama:100,openai:20"
    """
    if isinstance(value, dict):
        result: dict[str, int] = {}
        for k, v in value.items():
            try:
                result[str(k)] = int(v)
            except (ValueError, TypeError):
                continue
        return result
    if isinstance(value, str):
        return _parse_weights_string(value)
    return {}


def load_pool_config(
    file_config: dict[str, Any] | None = None,
) -> PoolConfig:
    """Load provider pool configuration from JSON config + env var overrides.

    Three-layer precedence: defaults -> JSON file -> env var.

    JSON schema (routing.json):
        {"pools": {"fast": "...", "quality": "...", "nsfw": ""},
         "weights": {"ollama": 100, "openai": 20},
         "fallback": {"max_fallbacks": 1, ...}}
    """
    fc = file_config or {}
    pools_fc = fc.get("pools", {}) if isinstance(fc.get("pools"), dict) else {}
    fallback_fc = fc.get("fallback", {}) if isinstance(fc.get("fallback"), dict) else {}

    # Weights: JSON object or CSV string
    raw_weights = env_override("OC_LLM_PROVIDER_WEIGHTS", fc.get("weights"))
    if raw_weights is None:
        # No file config and no env var — use built-in defaults
        provider_weights = _parse_weights_string("ollama:100,openai:20")
    else:
        provider_weights = _parse_weights(raw_weights)

    # Pool strings
    fast_pool_str = parse_str(
        env_override("OC_LLM_FAST_POOL", pools_fc.get("fast")),
        default="",
    )
    quality_pool_str = parse_str(
        env_override("OC_LLM_QUALITY_POOL", pools_fc.get("quality")),
        default="",
    )
    nsfw_pool_str = parse_str(
        env_override("OC_LLM_POOL_NSFW", pools_fc.get("nsfw")),
        default="",
    )

    fast_pool = parse_pool_string(fast_pool_str, provider_weights)
    quality_pool = parse_pool_string(quality_pool_str, provider_weights)
    nsfw_pool = parse_pool_string(nsfw_pool_str, provider_weights)

    # Fallback controls
    max_fallbacks = parse_int(
        env_override("OC_LLM_MAX_FALLBACKS", fallback_fc.get("max_fallbacks")),
        default=1,
    )
    fallback_on_transient = parse_bool(
        env_override("OC_LLM_FALLBACK_ON_TRANSIENT", fallback_fc.get("on_transient")),
        default=True,
    )
    fallback_on_constraint = parse_bool(
        env_override("OC_LLM_FALLBACK_ON_CONSTRAINT", fallback_fc.get("on_constraint")),
        default=True,
    )
    fallback_on_refusal = parse_bool(
        env_override("OC_LLM_FALLBACK_ON_REFUSAL", fallback_fc.get("on_refusal")),
        default=False,
    )

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
