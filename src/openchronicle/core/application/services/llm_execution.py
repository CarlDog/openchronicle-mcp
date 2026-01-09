"""
Application-level LLM execution boundary.

This module enforces routing discipline: all LLM calls in the Application layer
must be anchored to a routing decision. This prevents accidental provider selection
or bypassing of the routing system.
"""

from __future__ import annotations

from openchronicle.core.application.routing.router_policy import RouteDecision
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse


async def execute_with_route(
    llm: LLMPort,
    route_decision: RouteDecision,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> LLMResponse:
    """
    Execute an LLM call with a routing decision.

    This is the canonical way for Application code to call LLMs.
    It enforces that a routing decision has been made before execution.

    Args:
        llm: The LLM port (infrastructure adapter)
        route_decision: The routing decision from RouterPolicy
        messages: The conversation messages
        max_output_tokens: Maximum tokens to generate
        temperature: Sampling temperature

    Returns:
        LLMResponse from the selected provider

    Raises:
        ValueError: If route_decision is missing or invalid
        LLMProviderError: If the LLM call fails

    Note:
        Application code should NEVER call llm.complete_async directly.
        Always use this function to ensure routing discipline.
    """
    if not route_decision:
        raise ValueError("route_decision is required - routing must happen before LLM execution")

    if not route_decision.provider:
        raise ValueError("route_decision.provider is required - provider must be explicitly selected")

    if not route_decision.model:
        raise ValueError("route_decision.model is required - model must be explicitly selected")

    # Pass through to infrastructure with explicit provider from routing
    return await llm.complete_async(
        messages=messages,
        model=route_decision.model,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        provider=route_decision.provider,
    )


async def execute_with_explicit_provider(
    llm: LLMPort,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> LLMResponse:
    """
    Execute an LLM call with explicitly provided provider and model.

    This is used within fallback/retry scenarios where the provider and model
    have been determined by routing logic and are being passed explicitly.

    Args:
        llm: The LLM port (infrastructure adapter)
        provider: Explicit provider name (must be non-empty)
        model: Explicit model name (must be non-empty)
        messages: The conversation messages
        max_output_tokens: Maximum tokens to generate
        temperature: Sampling temperature

    Returns:
        LLMResponse from the specified provider

    Raises:
        ValueError: If provider or model is missing/empty
        LLMProviderError: If the LLM call fails

    Note:
        This function still enforces routing discipline - provider and model
        must be explicitly provided (no defaults, no selection logic here).
        Application code should derive these from RouteDecision.
    """
    if not provider:
        raise ValueError("provider is required and must be explicitly specified")

    if not model:
        raise ValueError("model is required and must be explicitly specified")

    # Pass through to infrastructure with explicit provider
    return await llm.complete_async(
        messages=messages,
        model=model,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        provider=provider,
    )
