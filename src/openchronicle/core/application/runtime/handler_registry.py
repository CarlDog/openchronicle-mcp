from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from openchronicle.core.domain.models.project import Task

TaskHandlerCallable = Callable[[Task, dict[str, Any] | None], Awaitable[Any]]


class TaskHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandlerCallable] = {}

    def register(self, task_type: str, handler: TaskHandlerCallable) -> None:
        self._handlers[task_type] = handler

    def get(self, task_type: str) -> TaskHandlerCallable | None:
        return self._handlers.get(task_type)

    def list_task_types(self) -> list[str]:
        return sorted(self._handlers.keys())
