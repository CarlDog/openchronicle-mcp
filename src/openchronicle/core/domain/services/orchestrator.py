from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from typing import Any

from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle.core.domain.models.project import Agent, Event, Project, Resource, Span, SpanStatus, Task, TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError
from openchronicle.core.domain.ports.plugin_port import PluginRegistry
from openchronicle.core.domain.ports.storage_port import StoragePort


class OrchestratorService:
    def __init__(
        self,
        storage: StoragePort,
        llm: LLMPort,
        plugins: PluginRegistry,
        handler_registry: TaskHandlerRegistry,
        emit_event: Callable[[Event], None],
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.plugins = plugins
        self.handler_registry = handler_registry
        self.emit_event = emit_event
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

    async def execute_task(self, task_id: str, agent_id: str | None = None) -> Any:
        task = self.storage.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        start_event = Event(
            project_id=task.project_id, task_id=task.id, agent_id=agent_id, type="task_started", payload={}
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

        with self.storage.transaction():
            self.storage.update_task_status(task.id, TaskStatus.RUNNING.value)
            self.emit_event(start_event)
            self.storage.add_span(span)

            try:
                handler_result = await self._dispatch_task(task, agent_id)
            except Exception as exc:
                handler_error = exc

            if handler_error is None:
                complete_event = Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="task_completed",
                    payload={"result": handler_result},
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
                failed_event = Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="task_failed",
                    payload={
                        "exception_type": type(handler_error).__name__,
                        "message": str(handler_error)[:500],
                    },
                )
                self.emit_event(failed_event)

                error_json = json.dumps(
                    {
                        "exception_type": type(handler_error).__name__,
                        "message": str(handler_error)[:500],
                        "failed_event_id": failed_event.id,
                    }
                )
                self.storage.update_task_error(task.id, error_json, TaskStatus.FAILED.value)

                span.status = SpanStatus.FAILED
                span.end_event_id = failed_event.id
                span.ended_at = failed_event.created_at
                self.storage.update_span(span)

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

    async def _run_analysis_summary(self, task: Task, agent_id: str | None) -> dict[str, Any]:
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

        workers = self._select_workers(task.project_id, 2)
        worker_tasks: list[Task] = []
        for idx, worker in enumerate(workers):
            child_payload = {"text": text, "worker_index": idx}
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

    async def _run_worker_summarize(self, task: Task, agent_id: str | None) -> str:
        text = task.payload.get("text") or ""
        if not self._llm_enabled():
            summary = self._simple_summarize(text)
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="worker.generated_summary",
                    payload={"text_hash": self._hash_text(text), "summary": summary},
                )
            )
            return summary

        messages = [
            {"role": "system", "content": "Summarize the provided text succinctly."},
            {"role": "user", "content": text},
        ]
        input_concat = "".join(m.get("content", "") for m in messages)
        input_hash = self._hash_text(input_concat)
        llm_model = self._llm_model()
        max_tokens = 256
        temperature = 0.2

        requested_event = Event(
            project_id=task.project_id,
            task_id=task.id,
            agent_id=agent_id,
            type="llm.requested",
            payload={
                "provider": "openai",
                "model": llm_model,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "input_chars": len(input_concat),
                "input_hash": input_hash,
            },
        )
        self.emit_event(requested_event)

        start = time.perf_counter()
        try:
            response = await self.llm.complete_async(
                messages,
                model=llm_model,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - start) * 1000)
            error_payload = {
                "provider": "openai",
                "model": llm_model,
                "latency_ms": latency_ms,
                "error_type": type(exc).__name__,
                "message": str(exc)[:500],
            }
            if isinstance(exc, LLMProviderError):
                if exc.status_code is not None:
                    error_payload["status_code"] = exc.status_code
                if exc.error_code is not None:
                    error_payload["error_code"] = exc.error_code
            self.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    agent_id=agent_id,
                    type="llm.failed",
                    payload=error_payload,
                )
            )
            raise

        latency_ms = int((time.perf_counter() - start) * 1000)
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

    def _simple_summarize(self, text: str) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= 160:
            return cleaned
        return cleaned[:150].rsplit(" ", 1)[0] + "..."

    def _llm_enabled(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _llm_model(self) -> str:
        from typing import cast

        return os.getenv("OPENAI_MODEL") or cast(str, getattr(self.llm, "model", "gpt-4o-mini"))

    async def _dispatch_task(self, task: Task, agent_id: str | None) -> Any:
        builtin_handler = self._builtin_handlers.get(task.type)
        if builtin_handler is not None:
            return await builtin_handler(task, agent_id=agent_id)

        registry_handler = self.handler_registry.get(task.type)
        if registry_handler is not None:
            return await registry_handler(task, {"agent_id": agent_id, "emit_event": self.emit_event})

        prompt = task.payload.get("prompt") or task.payload.get("text") or ""
        return await self.llm.generate_async(prompt, model=None, parameters=None)

    def _merge_summaries(self, summaries: list[str]) -> str:
        if not summaries:
            return ""
        return max(summaries, key=lambda s: len(s or ""))
