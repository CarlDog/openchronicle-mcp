"""Fallback execution wrapper for multi-provider LLM calls with constraint-driven fallback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openchronicle.core.application.routing.error_classifier import ErrorClass, classify_error
from openchronicle.core.application.routing.pool_config import PoolConfig
from openchronicle.core.domain.models.llm_execution_record import LLMExecutionRecord
from openchronicle.core.domain.ports.llm_port import LLMResponse


class FallbackExecutor:
    """
    Executes LLM calls with fallback logic for multi-provider routing.

    Handles fallback to alternate providers based on:
    - Error classification (constraint/transient/refusal/permanent)
    - Pool configuration and fallback settings
    - Maximum fallback attempts
    """

    def __init__(
        self,
        pool_config: PoolConfig,
        emit_event: Callable[[Any], None],  # Event type from domain.models
    ) -> None:
        """
        Initialize fallback executor.

        Args:
            pool_config: Provider pool configuration
            emit_event: Callback to emit events
        """
        self.pool_config = pool_config
        self.emit_event = emit_event

    async def execute_with_fallback(
        self,
        primary_decision: Any,  # RouteDecision from router_policy
        llm_call: Callable[[str, str], Any],  # (provider, model) -> LLMResponse
        project_id: str,
        task_id: str,
        agent_id: str | None,
    ) -> LLMResponse:
        """
        Execute LLM call with fallback support.

        Args:
            primary_decision: Primary routing decision with candidate list
            llm_call: Async callable that takes (provider, model) and returns LLMResponse
            project_id: Project ID for event emission
            task_id: Task ID for event emission
            agent_id: Agent ID for event emission

        Returns:
            LLMResponse from successful call

        Raises:
            Exception: If all attempts (primary + fallbacks) fail
        """
        # Track tried providers to avoid retrying same one
        tried: set[tuple[str, str]] = set()

        # Get candidate list from routing decision
        candidates = primary_decision.candidates or [
            (primary_decision.provider, primary_decision.model, 100),
        ]

        # Start with primary
        current_provider = primary_decision.provider
        current_model = primary_decision.model
        fallback_count = 0

        while True:
            tried.add((current_provider, current_model))

            try:
                # Attempt the call
                response: LLMResponse = await llm_call(current_provider, current_model)
                return response

            except Exception as exc:
                # Classify the error
                error_class = classify_error(exc)

                # Check if fallback is allowed
                fallback_allowed = self._should_fallback(error_class, fallback_count)

                if not fallback_allowed:
                    # No fallback allowed or exhausted - emit final failure and re-raise
                    self._emit_final_failure(
                        exc,
                        error_class,
                        current_provider,
                        current_model,
                        project_id,
                        task_id,
                        agent_id,
                    )
                    # Emit normalized execution record for final failure/refusal
                    self._emit_execution_record(
                        task_id=task_id,
                        route_provider=primary_decision.provider,
                        provider_used=current_provider,
                        model_used=current_model,
                        outcome="refused" if error_class == "refusal" else "failed",
                        error_code=getattr(exc, "error_code", None),
                        project_id=project_id,
                        agent_id=agent_id,
                    )
                    raise

                # Try to find next candidate
                next_candidate = self._get_next_candidate(candidates, tried)

                if next_candidate is None:
                    # No more candidates - emit final failure and re-raise
                    self._emit_final_failure(
                        exc,
                        error_class,
                        current_provider,
                        current_model,
                        project_id,
                        task_id,
                        agent_id,
                    )
                    # Emit normalized execution record for final failure/refusal
                    self._emit_execution_record(
                        task_id=task_id,
                        route_provider=primary_decision.provider,
                        provider_used=current_provider,
                        model_used=current_model,
                        outcome="refused" if error_class == "refusal" else "failed",
                        error_code=getattr(exc, "error_code", None),
                        project_id=project_id,
                        agent_id=agent_id,
                    )
                    raise

                # Fallback to next candidate
                next_provider, next_model = next_candidate
                self._emit_fallback_selected(
                    error_class,
                    exc,
                    current_provider,
                    current_model,
                    next_provider,
                    next_model,
                    project_id,
                    task_id,
                    agent_id,
                )

                # Emit attempt-level failure (non-terminal)
                self._emit_attempt_failure(
                    exc,
                    error_class,
                    current_provider,
                    current_model,
                    project_id,
                    task_id,
                    agent_id,
                )

                # Update for next iteration
                current_provider = next_provider
                current_model = next_model
                fallback_count += 1

    def _should_fallback(self, error_class: ErrorClass, fallback_count: int) -> bool:
        """Determine if fallback is allowed based on error class and config."""
        # Check attempt limit
        if fallback_count >= self.pool_config.max_fallbacks:
            return False

        # Check error-class-specific flags
        if error_class == "constraint":
            return self.pool_config.fallback_on_constraint
        if error_class == "transient":
            return self.pool_config.fallback_on_transient
        if error_class == "refusal":
            return self.pool_config.fallback_on_refusal

        # Permanent errors never fallback
        return False

    def _get_next_candidate(
        self,
        candidates: list[tuple[str, str, int]],
        tried: set[tuple[str, str]],
    ) -> tuple[str, str] | None:
        """Find next untried candidate from the list."""
        for provider, model, _weight in candidates:
            if (provider, model) not in tried:
                return (provider, model)
        return None

    def _emit_fallback_selected(
        self,
        error_class: ErrorClass,
        exc: Exception,
        from_provider: str,
        from_model: str,
        to_provider: str,
        to_model: str,
        project_id: str,
        task_id: str,
        agent_id: str | None,
    ) -> None:
        """Emit event when fallback is selected."""
        from openchronicle.core.domain.models.project import Event
        from openchronicle.core.domain.ports.llm_port import LLMProviderError

        payload: dict[str, Any] = {
            "from_provider": from_provider,
            "from_model": from_model,
            "to_provider": to_provider,
            "to_model": to_model,
            "reason_class": error_class,
            "error_type": type(exc).__name__,
        }

        if isinstance(exc, LLMProviderError):
            if exc.status_code is not None:
                payload["status_code"] = exc.status_code
            if exc.error_code is not None:
                payload["error_code"] = exc.error_code

        self.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                type="llm.fallback_selected",
                payload=payload,
            )
        )

    def _emit_attempt_failure(
        self,
        exc: Exception,
        error_class: ErrorClass,
        provider: str,
        model: str,
        project_id: str,
        task_id: str,
        agent_id: str | None,
    ) -> None:
        """Emit attempt-level failure (non-terminal)."""
        from openchronicle.core.domain.models.project import Event
        from openchronicle.core.domain.ports.llm_port import LLMProviderError

        payload: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "error_class": error_class,
            "error_type": type(exc).__name__,
            "message": str(exc)[:500],
        }

        if isinstance(exc, LLMProviderError):
            if exc.status_code is not None:
                payload["status_code"] = exc.status_code
            if exc.error_code is not None:
                payload["error_code"] = exc.error_code

        self.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                type="llm.attempt_failed",
                payload=payload,
            )
        )

    def _emit_final_failure(
        self,
        exc: Exception,
        error_class: ErrorClass,
        provider: str,
        model: str,
        project_id: str,
        task_id: str,
        agent_id: str | None,
    ) -> None:
        """Emit final failure event (terminal)."""
        from openchronicle.core.domain.models.project import Event
        from openchronicle.core.domain.ports.llm_port import LLMProviderError

        payload: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "error_class": error_class,
            "error_type": type(exc).__name__,
            "message": str(exc)[:500],
        }

        if isinstance(exc, LLMProviderError):
            if exc.status_code is not None:
                payload["status_code"] = exc.status_code
            if exc.error_code is not None:
                payload["error_code"] = exc.error_code

        # Emit as llm.failed (or llm.refused for refusals)
        event_type = "llm.refused" if error_class == "refusal" else "llm.failed"

        self.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                type=event_type,
                payload=payload,
            )
        )

    def _emit_execution_record(
        self,
        *,
        task_id: str,
        route_provider: str,
        provider_used: str,
        model_used: str,
        outcome: str,
        error_code: str | None,
        project_id: str,
        agent_id: str | None,
    ) -> None:
        """Emit llm.execution_recorded with normalized failure/refusal details."""
        from openchronicle.core.domain.models.project import Event

        record = LLMExecutionRecord(
            task_id=task_id,
            route_reference_id=None,
            provider_requested=route_provider,
            provider_used=provider_used,
            model=model_used,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            outcome=outcome,
            error_code=error_code,
        )

        self.emit_event(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                type="llm.execution_recorded",
                payload={
                    "task_id": record.task_id,
                    "route_reference_id": record.route_reference_id,
                    "provider_requested": record.provider_requested,
                    "provider_used": record.provider_used,
                    "model": record.model,
                    "prompt_tokens": record.prompt_tokens,
                    "completion_tokens": record.completion_tokens,
                    "total_tokens": record.total_tokens,
                    "outcome": record.outcome,
                    "error_code": record.error_code,
                    "created_at": record.created_at.isoformat(),
                },
            )
        )
