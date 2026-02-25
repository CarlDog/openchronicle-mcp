"""
Application-level LLM execution boundary.

This module enforces routing discipline: all LLM calls in the Application layer
must be anchored to a routing decision. This prevents accidental provider selection
or bypassing of the routing system.

Optional budget enforcement gate ensures projects stay within defined constraints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from openchronicle.core.application.routing.router_policy import RouteDecision
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse, StreamChunk, ToolDefinition

if TYPE_CHECKING:
    from openchronicle.core.application.policies.budget_gate import BudgetGate
    from openchronicle.core.domain.models.budget_policy import BudgetPolicy


import logging

_logger = logging.getLogger(__name__)


async def execute_with_route(
    llm: LLMPort,
    route_decision: RouteDecision,
    messages: list[dict[str, Any]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    budget_gate: BudgetGate | None = None,
    project_id: str | None = None,
    budget_policy: BudgetPolicy | None = None,
    tools: list[ToolDefinition] | None = None,
    tool_choice: str | None = None,
) -> LLMResponse:
    """
    Execute an LLM call with a routing decision.

    This is the canonical way for Application code to call LLMs.
    It enforces that a routing decision has been made before execution.

    Optionally enforces budget constraints before attempting the call.

    Args:
        llm: The LLM port (infrastructure adapter)
        route_decision: The routing decision from RouterPolicy
        messages: The conversation messages
        max_output_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        budget_gate: Optional budget enforcement gate
        project_id: Required if budget_gate is provided
        budget_policy: Optional budget policy; if provided, must have budget_gate set

    Returns:
        LLMResponse from the selected provider

    Raises:
        ValueError: If route_decision is missing or invalid
        BudgetExceededError: If budget policy is violated
        LLMProviderError: If the LLM call fails

    Note:
        Application code should NEVER call llm.complete_async directly.
        Always use this function to ensure routing discipline.
    """
    if not route_decision:
        raise DomainValidationError("route_decision is required - routing must happen before LLM execution")

    if not route_decision.provider:
        raise DomainValidationError("route_decision.provider is required - provider must be explicitly selected")

    if not route_decision.model:
        raise DomainValidationError("route_decision.model is required - model must be explicitly selected")

    # Check budget before attempting LLM call
    if budget_gate is not None and budget_policy is not None and project_id is not None:
        budget_gate.check(project_id, budget_policy, max_output_tokens)

    # Pass through to infrastructure with explicit provider from routing
    return await llm.complete_async(
        messages=messages,
        model=route_decision.model,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        provider=route_decision.provider,
        tools=tools,
        tool_choice=tool_choice,
    )


async def stream_with_route(
    llm: LLMPort,
    route_decision: RouteDecision,
    messages: list[dict[str, Any]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    budget_gate: BudgetGate | None = None,
    project_id: str | None = None,
    budget_policy: BudgetPolicy | None = None,
    tools: list[ToolDefinition] | None = None,
    tool_choice: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Stream an LLM call with a routing decision.

    Same routing discipline as execute_with_route, but yields StreamChunks.
    """
    if not route_decision:
        raise DomainValidationError("route_decision is required - routing must happen before LLM execution")
    if not route_decision.provider:
        raise DomainValidationError("route_decision.provider is required")
    if not route_decision.model:
        raise DomainValidationError("route_decision.model is required")

    if budget_gate is not None and budget_policy is not None and project_id is not None:
        budget_gate.check(project_id, budget_policy, max_output_tokens)

    async for chunk in llm.stream_async(
        messages=messages,
        model=route_decision.model,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        provider=route_decision.provider,
        tools=tools,
        tool_choice=tool_choice,
    ):
        yield chunk


async def execute_with_explicit_provider(
    llm: LLMPort,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    budget_gate: BudgetGate | None = None,
    project_id: str | None = None,
    budget_policy: BudgetPolicy | None = None,
    tools: list[ToolDefinition] | None = None,
    tool_choice: str | None = None,
) -> LLMResponse:
    """
    Execute an LLM call with explicitly provided provider and model.

    This is used within fallback/retry scenarios where the provider and model
    have been determined by routing logic and are being passed explicitly.

    Optionally enforces budget constraints before attempting the call.

    Args:
        llm: The LLM port (infrastructure adapter)
        provider: Explicit provider name (must be non-empty)
        model: Explicit model name (must be non-empty)
        messages: The conversation messages
        max_output_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        budget_gate: Optional budget enforcement gate
        project_id: Required if budget_gate is provided
        budget_policy: Optional budget policy; if provided, must have budget_gate set

    Returns:
        LLMResponse from the specified provider

    Raises:
        ValueError: If provider or model is missing/empty
        BudgetExceededError: If budget policy is violated
        LLMProviderError: If the LLM call fails

    Note:
        This function still enforces routing discipline - provider and model
        must be explicitly provided (no defaults, no selection logic here).
        Application code should derive these from RouteDecision.
    """
    if not provider:
        raise DomainValidationError("provider is required and must be explicitly specified")

    if not model:
        raise DomainValidationError("model is required and must be explicitly specified")

    # Check budget before attempting LLM call
    if budget_gate is not None and budget_policy is not None and project_id is not None:
        budget_gate.check(project_id, budget_policy, max_output_tokens)

    # Pass through to infrastructure with explicit provider
    return await llm.complete_async(
        messages=messages,
        model=model,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        provider=provider,
        tools=tools,
        tool_choice=tool_choice,
    )
