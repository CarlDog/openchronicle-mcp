"""Load budget policy from config file and/or environment variables."""

from __future__ import annotations

from typing import Any

from openchronicle.core.domain.models.budget_policy import BudgetPolicy
from openchronicle.core.infrastructure.config.env_helpers import env_override, parse_int


def load_budget_policy(
    file_config: dict[str, Any] | None = None,
) -> BudgetPolicy:
    """Load budget policy from JSON config + env var overrides.

    Three-layer precedence: dataclass defaults -> JSON file -> env var.

    JSON schema (core.json "budget" section):
        {"max_total_tokens": 0, "max_llm_calls": 0}

    Environment variables:
    - OC_BUDGET_MAX_TOKENS: Maximum total tokens (optional, int)
    - OC_BUDGET_MAX_CALLS: Maximum LLM calls (optional, int)
    """
    fc = file_config or {}

    max_tokens = parse_int(
        env_override("OC_BUDGET_MAX_TOKENS", fc.get("max_total_tokens")),
        default=0,
    )
    max_calls = parse_int(
        env_override("OC_BUDGET_MAX_CALLS", fc.get("max_llm_calls")),
        default=0,
    )

    return BudgetPolicy(
        max_total_tokens=max_tokens or None,
        max_llm_calls=max_calls or None,
    )
