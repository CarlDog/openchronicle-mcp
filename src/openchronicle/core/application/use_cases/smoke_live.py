"""Smoke test use case for minimal end-to-end LLM execution.

This use case proves that:
- Composition root wiring can construct real provider adapters from env
- Routing decisions affect runtime provider selection
- One live LLM call can be executed safely
- System emits expected events/records (execution_id, attempt_id, provider used)

It does NOT:
- Require API keys for unit tests (integration tests must be opt-in)
- Change routing logic, budget logic, retry logic, or resume logic
- Print secrets in logs/events
"""

from __future__ import annotations

import logging
from uuid import uuid4

from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.application.services.llm_execution import execute_with_route
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.errors import BUDGET_EXCEEDED, PROVIDER_ERROR, UNEXPECTED_ERROR
from openchronicle.core.domain.exceptions import BudgetExceededError
from openchronicle.core.domain.models.failure_category import classify_failure_category
from openchronicle.core.domain.models.project import Event, TaskStatus
from openchronicle.core.domain.models.smoke_result import SmokeResult
from openchronicle.core.domain.ports.llm_port import LLMProviderError

_logger = logging.getLogger(__name__)


DEFAULT_SMOKE_PROMPT = "Summarize this test: The sky is blue. Water is wet. Summarize in one sentence."


async def execute(
    orchestrator: OrchestratorService,
    *,
    prompt: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> SmokeResult:
    """Execute a minimal end-to-end smoke test with one LLM call.

    Creates a minimal project with one task and executes it through the normal
    application execution boundary, proving that:
    - Wiring works (orchestrator is functional)
    - Routing is exercised (provider selection happens)
    - Live LLM call can be executed
    - Events are emitted correctly

    Args:
        orchestrator: OrchestratorService instance (fully wired)
        prompt: Optional prompt text; defaults to built-in test prompt
        provider: Optional provider override (forces provider selection)
        model: Optional model override (forces model selection)

    Returns:
        SmokeResult with correlated IDs and execution details

    Raises:
        LLMProviderError: If provider is unavailable or has missing credentials
        BudgetExceededError: If budget blocks execution
        ValueError: If wiring is broken or storage unavailable
    """
    # Use defaults if not provided
    prompt_text = prompt or DEFAULT_SMOKE_PROMPT
    project_name = "smoke-test"
    task_type = "smoke.test"

    # Step 1: Create minimal project
    project = orchestrator.create_project(project_name, metadata={"type": "smoke_test"})
    project_id = project.id

    # Step 2: Register a minimal agent (just for context, routing will handle selection)
    agent = orchestrator.register_agent(
        project_id=project_id,
        name="smoke-agent",
        role="worker",
        provider=provider or "",  # Override provider if specified
        model=model or "",  # Override model if specified
        tags=[],
    )

    # Step 3: Create a simple task
    execution_id = uuid4().hex
    attempt_id = uuid4().hex

    task_payload = {
        "text": prompt_text,
        "execution_id": execution_id,
        "attempt_id": attempt_id,
    }

    task = orchestrator.submit_task(
        project_id=project_id,
        task_type=task_type,
        payload=task_payload,
        agent_id=agent.id,
    )
    task_id = task.id

    # Step 4: Prepare routing decision
    # Use the orchestrator's router to make a routing decision
    router = RouterPolicy()

    # Determine mode (default to fast for smoke tests)
    desired_quality = None
    route_decision = router.route(
        task_type=task_type,
        agent_role=agent.role,
        agent_tags=agent.tags,
        desired_quality=desired_quality,
        provider_preference=provider,  # Use override if provided
        current_task_tokens=None,
        max_tokens_per_task=None,
        rate_limit_triggered=False,
        rpm_limit=None,
    )

    provider_used = route_decision.provider
    model_used = route_decision.model

    # Step 5: Emit routing decision event
    orchestrator.emit_event(
        Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent.id,
            type="llm.routed",
            payload={
                "provider_selected": provider_used,
                "model_selected": model_used,
                "mode": route_decision.mode,
                "reasons": route_decision.reasons,
                "task_type": task_type,
                "agent_id": agent.id,
                "predictor_hint": route_decision.predictor_hint,
                "predictor_source": route_decision.predictor_source,
            },
        )
    )

    # Step 6: Execute LLM call through application boundary
    outcome = "completed"
    error_code = None
    error_message = None
    failure_category = None
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None
    latency_ms = None

    try:
        # Prepare messages for LLM call
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer briefly."},
            {"role": "user", "content": prompt_text},
        ]

        # Execute through the application boundary with routed provider
        response = await execute_with_route(
            orchestrator.llm,
            route_decision,
            messages,
            max_output_tokens=256,
            temperature=0.2,
            budget_gate=None,  # Smoke test doesn't enforce budget
        )

        # Extract usage metrics if available
        if response.usage:
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            total_tokens = response.usage.total_tokens
        latency_ms = response.latency_ms

        # Emit successful execution event
        orchestrator.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent.id,
                type="llm.execution_recorded",
                payload={
                    "execution_id": execution_id,
                    "attempt_id": attempt_id,
                    "provider_requested": provider,
                    "provider_used": provider_used,
                    "model_requested": model,
                    "model_used": model_used,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "latency_ms": latency_ms,
                    "outcome": outcome,
                },
            )
        )

        # Mark task as completed
        orchestrator.storage.update_task_status(task_id, TaskStatus.COMPLETED.value)
        orchestrator.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent.id,
                type="task_completed",
                payload={"attempt_id": attempt_id, "outcome": outcome},
            )
        )

    except BudgetExceededError as exc:
        # Budget was exceeded - this is a valid outcome to report
        outcome = "blocked"
        error_code = BUDGET_EXCEEDED
        error_message = str(exc)
        failure_category = classify_failure_category(error_code, None)

        orchestrator.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent.id,
                type="llm.budget_exceeded",
                payload={
                    "error_code": error_code,
                    "message": error_message,
                    "provider": provider_used,
                    "model": model_used,
                },
            )
        )

        orchestrator.storage.update_task_status(task_id, TaskStatus.FAILED.value)

    except LLMProviderError as exc:
        # Provider error - capture for diagnostics (without revealing secrets)
        outcome = "failed"
        error_code = exc.error_code or PROVIDER_ERROR
        error_message = str(exc)

        # Log error without revealing secrets like API keys
        if "api" in error_message.lower() or "key" in error_message.lower():
            error_message = f"[{error_code}] Provider credential or configuration issue"

        # Classify failure
        failure_category = classify_failure_category(error_code, None)

        orchestrator.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent.id,
                type="task_failed",
                payload={
                    "attempt_id": attempt_id,
                    "error_code": error_code,
                    "message": error_message,
                    "exception_type": type(exc).__name__,
                    "provider": provider_used,
                    "hint": exc.hint,
                },
            )
        )

        orchestrator.storage.update_task_status(task_id, TaskStatus.FAILED.value)

    except Exception as exc:
        # Unexpected error
        outcome = "failed"
        error_code = UNEXPECTED_ERROR
        error_message = str(exc)[:500]  # Truncate to prevent leaking sensitive data
        failure_category = classify_failure_category(error_code, None)

        orchestrator.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent.id,
                type="task_failed",
                payload={
                    "attempt_id": attempt_id,
                    "error_code": error_code,
                    "message": error_message,
                    "exception_type": type(exc).__name__,
                },
            )
        )

        orchestrator.storage.update_task_status(task_id, TaskStatus.FAILED.value)

    # Step 7: Return smoke result with all relevant details
    return SmokeResult(
        project_id=project_id,
        task_id=task_id,
        attempt_id=attempt_id,
        execution_id=execution_id,
        provider_requested=provider,
        provider_used=provider_used,
        model_requested=model,
        model_used=model_used,
        prompt_text=prompt_text,
        outcome=outcome,
        error_code=error_code,
        error_message=error_message,
        failure_category=failure_category,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
    )
