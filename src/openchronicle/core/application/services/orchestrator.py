from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from openchronicle.core.application.policies.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitTimeoutError,
    estimate_tokens,
)
from openchronicle.core.application.policies.retry_controller import RetryController
from openchronicle.core.application.policies.retry_policy import RetryAttempt, RetryConfig, RetryPolicy
from openchronicle.core.application.routing.fallback_executor import FallbackExecutor
from openchronicle.core.application.routing.router_policy import RouteDecision, RouterPolicy
from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
from openchronicle.core.application.services.llm_execution import execute_with_explicit_provider
from openchronicle.core.domain.exceptions import BudgetExceededError
from openchronicle.core.domain.models.execution_record import LLMExecutionRecord
from openchronicle.core.domain.models.project import Agent, Event, Project, Resource, Span, SpanStatus, Task, TaskStatus
from openchronicle.core.domain.models.retry_policy import TaskRetryPolicy
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse
from openchronicle.core.domain.ports.plugin_port import PluginRegistry
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.services.usage_tracker import UsageTracker


@dataclass
class _WorkerRoutingContext:
    """Inter-phase state for _run_worker_summarize pipeline."""

    route_decision: RouteDecision
    messages: list[dict[str, str]]
    input_concat: str
    input_hash: str
    max_tokens: int
    temperature: float
    max_tokens_per_task: int | None
    current_total_tokens: int


class OrchestratorService:
    def __init__(
        self,
        storage: StoragePort,
        llm: LLMPort,
        plugins: PluginRegistry,
        handler_registry: TaskHandlerRegistry,
        emit_event: Callable[[Event], None],
        *,
        rate_limiter: RateLimiter | None = None,
        retry_policy: RetryPolicy | None = None,
        router: RouterPolicy | None = None,
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.plugins = plugins
        self.handler_registry = handler_registry
        self.emit_event = emit_event
        self.usage_tracker = UsageTracker(storage)

        if rate_limiter is not None:
            self.rate_limiter = rate_limiter
        else:
            rpm_limit_str = os.getenv("OC_LLM_RPM_LIMIT")
            tpm_limit_str = os.getenv("OC_LLM_TPM_LIMIT")
            max_wait_ms_str = os.getenv("OC_LLM_MAX_WAIT_MS")
            rate_config = RateLimitConfig(
                rpm_limit=int(rpm_limit_str) if rpm_limit_str else None,
                tpm_limit=int(tpm_limit_str) if tpm_limit_str else None,
                max_wait_ms=int(max_wait_ms_str) if max_wait_ms_str else 5000,
            )
            self.rate_limiter = RateLimiter(rate_config)

        if retry_policy is not None:
            self.retry_policy = retry_policy
        else:
            max_retries_str = os.getenv("OC_LLM_MAX_RETRIES")
            max_retry_sleep_ms_str = os.getenv("OC_LLM_MAX_RETRY_SLEEP_MS")
            retry_config = RetryConfig(
                max_retries=int(max_retries_str) if max_retries_str else 2,
                max_retry_sleep_ms=int(max_retry_sleep_ms_str) if max_retry_sleep_ms_str else 2000,
            )
            self.retry_policy = RetryPolicy(retry_config)

        # Initialize router policy
        self.router = router if router is not None else RouterPolicy()

        # Initialize fallback executor
        self.fallback_executor = FallbackExecutor(
            pool_config=self.router.pool_config,
            emit_event=emit_event,
        )

        self._builtin_handlers = {
            "analysis.summary": self._run_analysis_summary,
            "analysis.worker.summarize": self._run_worker_summarize,
        }

    def create_project(self, name: str, metadata: dict[str, Any] | None = None) -> Project:
        project = Project(name=name, metadata=metadata or {})
        self.storage.add_project(project)
        event = Event(project_id=project.id, type="project_created", payload={"name": name})
        self.emit_event(event)
        return project

    def register_agent(
        self,
        project_id: str,
        name: str,
        role: str = "worker",
        provider: str = "",
        model: str = "",
        tags: list[str] | None = None,
    ) -> Agent:
        agent = Agent(
            project_id=project_id,
            role=role,
            name=name,
            provider=provider,
            model=model,
            tags=tags or [],
        )
        self.storage.add_agent(agent)
        event = Event(
            project_id=project_id, agent_id=agent.id, type="agent_registered", payload={"name": name, "role": role}
        )
        self.emit_event(event)
        return agent

    def list_builtin_handlers(self) -> list[str]:
        return sorted(self._builtin_handlers.keys())

    def list_registered_handlers(self) -> list[str]:
        return self.handler_registry.list_task_types()

    def submit_task(
        self,
        project_id: str,
        task_type: str,
        payload: dict[str, Any],
        parent_task_id: str | None = None,
        agent_id: str | None = None,
    ) -> Task:
        task = Task(
            project_id=project_id, type=task_type, payload=payload, parent_task_id=parent_task_id, agent_id=agent_id
        )
        self.storage.add_task(task)
        event = Event(project_id=project_id, task_id=task.id, type="task_submitted", payload={"task_type": task_type})
        self.emit_event(event)
        return task

    def get_retry_policy(self, task: Task) -> TaskRetryPolicy:
        """Get retry policy for a task (from task payload or default to no retry)."""
        # Check if task payload specifies a retry policy
        retry_config = task.payload.get("retry_policy")
        if retry_config and isinstance(retry_config, dict):
            max_attempts = retry_config.get("max_attempts", 1)
            retry_on_errors = retry_config.get("retry_on_errors")
            backoff_seconds = retry_config.get("backoff_seconds", 0)
            return TaskRetryPolicy(
                max_attempts=max_attempts,
                retry_on_errors=retry_on_errors,
                backoff_seconds=backoff_seconds,
            )
        # Default: retries disabled
        return TaskRetryPolicy.no_retry()

    def _count_prior_attempts(self, task_id: str) -> int:
        """Count number of prior attempts for a task from events."""
        events = self.storage.list_events(task_id)
        return sum(1 for e in events if e.type == "task_started")

    async def execute_task(self, task_id: str, agent_id: str | None = None) -> Any:
        task = self.storage.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        # Generate attempt_id for this execution attempt
        attempt_id = uuid4().hex

        start_event = Event(
            project_id=task.project_id,
            task_id=task.id,
            agent_id=agent_id,
            type="task_started",
            payload={"attempt_id": attempt_id},
        )
        span = Span(
            task_id=task.id,
            agent_id=agent_id,
            name=f"execute.{task.type}",
            start_event_id=start_event.id,
            status=SpanStatus.STARTED,
        )

        handler_error: Exception | None = None
        handler_result: Any | None = None

        # Transaction 1: mark task running + emit start event + open span.
        # Short — no I/O inside.
        with self.storage.transaction():
            self.storage.update_task_status(task.id, TaskStatus.RUNNING.value)
            self.emit_event(start_event)
            self.storage.add_span(span)

        # LLM call — outside any transaction so the write lock is released.
        # If the process crashes here, task stays RUNNING;
        # recover_stale_tasks() (called on startup) will mark it FAILED.
        try:
            handler_result = await self._dispatch_task(task, agent_id, attempt_id)
        except Exception as exc:
            handler_error = exc

        # Transaction 2: record outcome (completion or failure).
        with self.storage.transaction():
            if handler_error is None:
                complete_event = Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="task_completed",
                    payload={"result": handler_result, "attempt_id": attempt_id},
                )
                self.emit_event(complete_event)

                result_json = (
                    json.dumps(handler_result)
                    if isinstance(handler_result, dict)
                    else json.dumps({"value": handler_result})
                )
                self.storage.update_task_result(task.id, result_json, TaskStatus.COMPLETED.value)

                span.end_event_id = complete_event.id
                span.status = SpanStatus.COMPLETED
                span.ended_at = complete_event.created_at
                self.storage.update_span(span)
            else:
                # Extract provider-related context if available
                provider_ctx: dict[str, Any] = {}

                if isinstance(handler_error, LLMProviderError):
                    if handler_error.error_code is not None:
                        provider_ctx["error_code"] = handler_error.error_code
                    if handler_error.provider is not None:
                        provider_ctx["provider"] = handler_error.provider
                    if handler_error.hint is not None:
                        provider_ctx["hint"] = handler_error.hint
                    if handler_error.configured_providers:
                        provider_ctx["configured_providers"] = handler_error.configured_providers

                failed_event = Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="task_failed",
                    payload={
                        "exception_type": type(handler_error).__name__,
                        "message": str(handler_error)[:500],
                        "attempt_id": attempt_id,
                        **provider_ctx,
                    },
                )
                self.emit_event(failed_event)

                error_payload: dict[str, Any] = {
                    "exception_type": type(handler_error).__name__,
                    "message": str(handler_error)[:500],
                    "failed_event_id": failed_event.id,
                }
                # Mirror provider context into persisted error_json
                if provider_ctx:
                    error_payload.update(provider_ctx)

                error_json = json.dumps(error_payload)
                self.storage.update_task_error(task.id, error_json, TaskStatus.FAILED.value)

                span.status = SpanStatus.FAILED
                span.end_event_id = failed_event.id
                span.ended_at = failed_event.created_at
                self.storage.update_span(span)

                # Check retry policy to decide whether to retry
                retry_policy = self.get_retry_policy(task)
                prior_attempts = self._count_prior_attempts(task.id)
                error_code = provider_ctx.get("error_code") if provider_ctx else None

                if RetryController.should_retry(
                    task_id=task.id,
                    attempt_id=attempt_id,
                    error_code=error_code,
                    policy=retry_policy,
                    prior_attempts=prior_attempts,
                ):
                    # Retry allowed: emit task.retry_scheduled event
                    retry_event = Event(
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=agent_id,
                        type="task.retry_scheduled",
                        payload={
                            "task_id": task.id,
                            "failed_attempt_id": attempt_id,
                            "prior_attempts": prior_attempts,
                            "max_attempts": retry_policy.max_attempts,
                            "error_code": error_code,
                            "backoff_seconds": retry_policy.backoff_seconds,
                            "reason": "policy",
                        },
                    )
                    self.emit_event(retry_event)
                    # Note: Actual retry execution will occur naturally via orchestration
                    # (not automatically triggered in this batch)

        if handler_error is not None:
            raise handler_error

        return handler_result

    def record_resource(self, resource: Resource) -> None:
        self.storage.add_resource(resource)
        event = Event(
            project_id=resource.project_id,
            type="resource_added",
            payload={"kind": resource.kind, "path": resource.path},
        )
        self.emit_event(event)

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""

    def _select_workers(self, project_id: str, count: int) -> list[Agent]:
        agents = self.storage.list_agents(project_id)
        workers = [a for a in agents if a.role == "worker"]
        if len(workers) < count:
            raise ValueError("Not enough worker agents registered")
        return workers[:count]

    def _resolve_worker_modes(
        self,
        payload: dict[str, Any],
    ) -> tuple[list[str], str]:
        """Resolve worker modes from task payload (4-way resolution).

        Returns (worker_modes, rationale).
        """
        desired_quality = payload.get("desired_quality")
        worker_modes_raw = payload.get("worker_modes")
        worker_count = payload.get("worker_count", 2)
        mix_strategy = payload.get("mix_strategy")

        if mix_strategy and not worker_modes_raw:
            if worker_count != 2:
                raise ValueError("mix_strategy requires worker_count=2")
            if mix_strategy == "fast_then_quality":
                return ["fast", "quality"], "mix_strategy"
            if mix_strategy == "quality_then_fast":
                return ["quality", "fast"], "mix_strategy"
            raise ValueError(f"Invalid mix_strategy: {mix_strategy}")
        if worker_modes_raw:
            if len(worker_modes_raw) != worker_count:
                raise ValueError(
                    f"worker_modes length ({len(worker_modes_raw)}) must match worker_count ({worker_count})"
                )
            return worker_modes_raw, "explicit_worker_modes"
        if desired_quality:
            return [desired_quality] * worker_count, "desired_quality_replicated"
        default_mode = os.getenv("OC_LLM_DEFAULT_MODE", "fast")
        return [default_mode] * worker_count, "default_mode"

    async def _run_analysis_summary(self, task: Task, agent_id: str | None, attempt_id: str) -> dict[str, Any]:
        text = task.payload.get("text") or ""
        text_hash = self._hash_text(text)
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="supervisor.received_task",
                payload={"text_hash": text_hash, "text_length": len(text)},
            )
        )

        worker_count = task.payload.get("worker_count", 2)
        desired_quality = task.payload.get("desired_quality")
        worker_modes, rationale = self._resolve_worker_modes(task.payload)

        # Emit worker plan event
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="supervisor.worker_plan",
                payload={"worker_count": worker_count, "worker_modes": worker_modes, "rationale": rationale},
            )
        )

        # Emit routing mode selection event for observability
        routing_source = "task_payload" if desired_quality else "default"
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="supervisor.routing_mode_selected",
                payload={"desired_quality": desired_quality, "source": routing_source},
            )
        )

        workers = self._select_workers(task.project_id, worker_count)
        worker_tasks: list[Task] = []
        for idx, (worker, mode) in enumerate(zip(workers, worker_modes, strict=True)):
            child_payload = {"text": text, "worker_index": idx, "desired_quality": mode}
            child_task = self.submit_task(
                task.project_id, "analysis.worker.summarize", child_payload, parent_task_id=task.id, agent_id=worker.id
            )
            worker_tasks.append(child_task)

        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="supervisor.dispatched_workers",
                payload={"worker_task_ids": [t.id for t in worker_tasks], "text_hash": text_hash},
            )
        )

        worker_results: list[str] = []
        for child_task, worker in zip(worker_tasks, workers, strict=False):
            result = await self.execute_task(child_task.id, agent_id=worker.id)
            worker_results.append(result)
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="worker.completed",
                    payload={"worker_task_id": child_task.id, "worker_agent_id": worker.id, "summary": result},
                )
            )

        final_summary = self._merge_summaries(worker_results)
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="supervisor.merged_results",
                payload={"worker_summaries": worker_results, "merge_strategy": "longer_summary"},
            )
        )
        return {"summary": final_summary, "worker_summaries": worker_results}

    async def _run_worker_summarize(self, task: Task, agent_id: str | None, attempt_id: str) -> str:
        ctx = self._worker_setup_routing(task, agent_id)
        max_tokens = self._worker_enforce_budget(task, agent_id, ctx)
        estimated_tokens = self._worker_acquire_rate_limit(
            task,
            agent_id,
            ctx.route_decision.provider,
            ctx.route_decision.model,
            ctx.input_concat,
        )
        response, execution_id, requested_event_id, start_time = await self._worker_execute_llm(
            task,
            agent_id,
            ctx.route_decision,
            ctx.messages,
            max_tokens,
            ctx.temperature,
            ctx.input_concat,
            ctx.input_hash,
            estimated_tokens,
        )
        return self._worker_record_completion(
            task,
            agent_id,
            attempt_id,
            ctx.route_decision,
            response,
            execution_id,
            requested_event_id,
            start_time,
            ctx.input_hash,
        )

    def _worker_setup_routing(
        self,
        task: Task,
        agent_id: str | None,
    ) -> _WorkerRoutingContext:
        """Phase 0: Extract text, route to provider/model, build messages."""
        text = task.payload.get("text") or ""

        # Get agent details for routing
        agent = self.storage.get_agent(agent_id) if agent_id else None
        agent_tags = agent.tags if agent else []
        agent_role = agent.role if agent else "worker"
        agent_provider = agent.provider if agent else None

        # Extract desired_quality hint from task payload if provided
        desired_quality = task.payload.get("desired_quality")

        # Prepare for routing decisions
        max_tokens_per_task_str = os.getenv("OC_MAX_TOKENS_PER_TASK")
        max_tokens_per_task = int(max_tokens_per_task_str) if max_tokens_per_task_str else None
        current_totals = self.usage_tracker.get_task_token_totals(task.id)
        current_total_tokens = current_totals.get("total_tokens") or 0

        # Check if rate limiting was recently triggered
        recent_events = self.storage.list_events(task_id=task.id)
        rate_limit_triggered = any(e.type == "llm.rate_limited" for e in recent_events[-5:] if recent_events)
        rpm_limit_str = os.getenv("OC_LLM_RPM_LIMIT")
        rpm_limit = int(rpm_limit_str) if rpm_limit_str else None

        # Route to provider and model
        route_decision = self.router.route(
            task_type=task.type,
            agent_role=agent_role,
            agent_tags=agent_tags,
            desired_quality=desired_quality,
            provider_preference=agent_provider,
            current_task_tokens=current_total_tokens,
            max_tokens_per_task=max_tokens_per_task,
            rate_limit_triggered=rate_limit_triggered,
            rpm_limit=rpm_limit,
        )

        # Emit routing decision event
        route_payload: dict[str, Any] = {
            "provider_selected": route_decision.provider,
            "model_selected": route_decision.model,
            "mode": route_decision.mode,
            "reasons": route_decision.reasons,
            "task_type": task.type,
            "agent_id": agent_id,
        }
        if route_decision.candidates:
            route_payload["candidates_considered"] = [
                {"provider": p, "model": m, "weight": w} for p, m, w in route_decision.candidates
            ]
            route_payload["weights_used"] = {p: w for p, _, w in route_decision.candidates}

        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="llm.routed",
                payload=route_payload,
            )
        )

        # Build messages
        messages: list[dict[str, str]] = [
            {"role": "system", "content": "Summarize the provided text succinctly."},
            {"role": "user", "content": text},
        ]
        input_concat = "".join(m.get("content", "") for m in messages)
        input_hash = self._hash_text(input_concat)

        return _WorkerRoutingContext(
            route_decision=route_decision,
            messages=messages,
            input_concat=input_concat,
            input_hash=input_hash,
            max_tokens=256,
            temperature=0.2,
            max_tokens_per_task=max_tokens_per_task,
            current_total_tokens=current_total_tokens,
        )

    def _worker_enforce_budget(
        self,
        task: Task,
        agent_id: str | None,
        ctx: _WorkerRoutingContext,
    ) -> int:
        """Phase 1: Check token budget, clamp output tokens. Returns effective max_tokens."""
        max_tokens = ctx.max_tokens

        if ctx.max_tokens_per_task is not None and ctx.current_total_tokens >= ctx.max_tokens_per_task:
            provider = ctx.route_decision.provider
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="llm.budget_exceeded",
                    payload={
                        "limit": ctx.max_tokens_per_task,
                        "current": ctx.current_total_tokens,
                        "provider": provider,
                        "model": ctx.route_decision.model,
                    },
                )
            )
            raise BudgetExceededError(
                ctx.max_tokens_per_task, ctx.current_total_tokens, provider, ctx.route_decision.model
            )

        # Output token clamping
        max_output_tokens_per_call_str = os.getenv("OC_MAX_OUTPUT_TOKENS_PER_CALL")
        if max_output_tokens_per_call_str:
            max_output_tokens_per_call = int(max_output_tokens_per_call_str)
            if max_tokens > max_output_tokens_per_call:
                self.emit_event(
                    Event(
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=agent_id,
                        type="llm.request_clamped",
                        payload={
                            "requested_max_tokens": max_tokens,
                            "clamped_max_tokens": max_output_tokens_per_call,
                        },
                    )
                )
                max_tokens = max_output_tokens_per_call

        return max_tokens

    def _worker_acquire_rate_limit(
        self,
        task: Task,
        agent_id: str | None,
        provider: str,
        model: str,
        input_text: str,
    ) -> int:
        """Phase 2-3: Estimate tokens and acquire rate limiter. Returns estimated_input_tokens."""
        estimated_input_tokens = estimate_tokens(input_text)

        try:
            rate_limit_info = self.rate_limiter.acquire(
                provider=provider,
                model=model,
                estimated_tokens=estimated_input_tokens,
            )
            wait_ms = rate_limit_info.get("wait_ms", 0) or 0
            if wait_ms > 0:
                self.emit_event(
                    Event(
                        project_id=task.project_id,
                        task_id=task.id,
                        agent_id=agent_id,
                        type="llm.rate_limited",
                        payload={
                            "wait_ms": wait_ms,
                            "provider": provider,
                            "model": model,
                            "rpm_limit": rate_limit_info.get("rpm_limit"),
                            "tpm_limit": rate_limit_info.get("tpm_limit"),
                        },
                    )
                )
        except RateLimitTimeoutError as exc:
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="llm.rate_limit_timeout",
                    payload={
                        "max_wait_ms": exc.max_wait_ms,
                        "required_wait_ms": exc.required_wait_ms,
                        "provider": provider,
                        "model": model,
                    },
                )
            )
            raise

        return estimated_input_tokens

    async def _worker_execute_llm(
        self,
        task: Task,
        agent_id: str | None,
        route_decision: RouteDecision,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        input_concat: str,
        input_hash: str,
        estimated_input_tokens: int,
    ) -> tuple[LLMResponse, str, str, float]:
        """Phase 4-5: Generate execution_id, emit llm.requested, call LLM with retry + fallback."""
        execution_id = uuid4().hex
        provider = route_decision.provider
        llm_model = route_decision.model

        requested_event = Event(
            project_id=task.project_id,
            task_id=task.id,
            agent_id=agent_id,
            type="llm.requested",
            payload={
                "execution_id": execution_id,
                "provider_selected": provider,
                "provider": provider,
                "model": llm_model,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "input_chars": len(input_concat),
                "input_hash": input_hash,
                "estimated_input_tokens": estimated_input_tokens,
            },
        )
        self.emit_event(requested_event)

        start = time.perf_counter()

        def on_retry(attempt: RetryAttempt) -> None:
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="llm.retry_scheduled",
                    payload={
                        "attempt": attempt.attempt,
                        "max_retries": attempt.max_retries,
                        "sleep_ms": attempt.sleep_ms,
                        "reason": attempt.reason,
                        "status_code": attempt.status_code,
                        "error_type": attempt.error_type,
                    },
                )
            )

        def on_exhausted(attempts: int, last_error: Exception) -> None:
            status_code = getattr(last_error, "status_code", None) if isinstance(last_error, LLMProviderError) else None
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="llm.retry_exhausted",
                    payload={
                        "attempts": attempts,
                        "last_error_type": type(last_error).__name__,
                        "last_status_code": status_code,
                    },
                )
            )

        async def llm_call_with_provider(provider_name: str, model_name: str) -> Any:
            """Execute LLM call with specific provider and model, including retry logic."""

            async def single_call() -> Any:
                return await execute_with_explicit_provider(
                    llm=self.llm,
                    provider=provider_name,
                    model=model_name,
                    messages=messages,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )

            return await self.retry_policy.execute(single_call, on_retry=on_retry, on_exhausted=on_exhausted)

        try:
            response = await self.fallback_executor.execute_with_fallback(
                primary_decision=route_decision,
                llm_call=llm_call_with_provider,
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                route_reference_id=requested_event.id,
                execution_id=execution_id,
            )
        except Exception:
            raise

        return response, execution_id, requested_event.id, start

    def _worker_record_completion(
        self,
        task: Task,
        agent_id: str | None,
        attempt_id: str,
        route_decision: RouteDecision,
        response: LLMResponse,
        execution_id: str,
        requested_event_id: str,
        start_time: float,
        input_hash: str,
    ) -> str:
        """Phase 6: Compute latency, emit completion events, record usage. Returns summary string."""
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Check for provider mismatch
        if response.provider != route_decision.provider:
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="llm.provider_mismatch",
                    payload={
                        "provider_selected": route_decision.provider,
                        "provider_used": response.provider,
                        "model_selected": route_decision.model,
                        "model_used": response.model,
                    },
                )
            )

        completed_payload = {
            "provider": response.provider,
            "model": response.model,
            "latency_ms": response.latency_ms or latency_ms,
            "finish_reason": response.finish_reason,
            "request_id": response.request_id,
        }
        if response.usage:
            completed_payload["usage"] = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="llm.completed",
                payload=completed_payload,
            )
        )

        # Emit normalized execution record
        usage = response.usage
        record = LLMExecutionRecord(
            task_id=task.id,
            execution_id=execution_id,
            route_reference_id=requested_event_id,
            provider_requested=route_decision.provider,
            provider_used=response.provider,
            model_requested=route_decision.model,
            model=response.model,
            prompt_tokens=usage.input_tokens if usage else None,
            completion_tokens=usage.output_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            outcome="completed",
            error_code=None,
        )
        payload = record.to_payload()
        payload["attempt_id"] = attempt_id
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="llm.execution_recorded",
                payload=payload,
            )
        )

        # Record usage to database
        self.usage_tracker.record_call(
            project_id=task.project_id,
            task_id=task.id,
            agent_id=agent_id or "",
            response=response,
        )

        llm_summary: str = str(response.content)
        self.emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="worker.generated_summary",
                payload={"text_hash": input_hash, "summary": llm_summary},
            )
        )
        return llm_summary

    def _llm_model(self) -> str:
        from typing import cast

        return os.getenv("OPENAI_MODEL") or cast(str, getattr(self.llm, "model", "gpt-4o-mini"))

    async def _dispatch_task(self, task: Task, agent_id: str | None, attempt_id: str) -> Any:
        builtin_handler = self._builtin_handlers.get(task.type)
        if builtin_handler is not None:
            return await builtin_handler(task, agent_id=agent_id, attempt_id=attempt_id)

        if task.type == "plugin.invoke":
            payload = task.payload if isinstance(task.payload, dict) else {}
            handler_name = payload.get("handler")
            input_payload = payload.get("input")
            if not isinstance(handler_name, str) or not handler_name:
                raise ValueError("Missing or invalid payload.handler for plugin.invoke")
            if not isinstance(input_payload, dict):
                raise ValueError("Missing or invalid payload.input for plugin.invoke")

            registry_handler = self.handler_registry.get(handler_name)
            if registry_handler is None:
                raise ValueError(f"Unknown handler: {handler_name}")

            invoke_task = Task(
                id=task.id,
                project_id=task.project_id,
                agent_id=task.agent_id,
                parent_task_id=task.parent_task_id,
                type=task.type,
                payload=input_payload,
                status=task.status,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            return await registry_handler(
                invoke_task,
                {"agent_id": agent_id, "attempt_id": attempt_id, "emit_event": self.emit_event},
            )

        registry_handler = self.handler_registry.get(task.type)
        if registry_handler is not None:
            return await registry_handler(
                task, {"agent_id": agent_id, "attempt_id": attempt_id, "emit_event": self.emit_event}
            )

        # No handler registered for this task type
        raise ValueError(f"No handler registered for task type: {task.type}")

    def _merge_summaries(self, summaries: list[str]) -> str:
        if not summaries:
            return ""
        return max(summaries, key=lambda s: len(s or ""))
