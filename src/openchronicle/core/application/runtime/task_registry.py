from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from openchronicle.core.domain.models.project import Task

TaskHandlerCallable = Callable[[Task, dict[str, Any] | None], Awaitable[Any]]


class HandlerCollisionError(Exception):
    """Raised when attempting to register a handler that already exists."""


class TaskHandlerRegistry:
    def __init__(self, check_collisions: bool = False) -> None:
        self._handlers: dict[str, TaskHandlerCallable] = {}
        self._handler_sources: dict[str, str] = {}  # handler_name -> source (for error messages)
        self._check_collisions = check_collisions
        self._current_source: str | None = None  # Track current plugin being loaded

    def set_current_source(self, source: str | None) -> None:
        """Set the current source (plugin name) for collision tracking."""
        self._current_source = source

    def register(self, task_type: str, handler: TaskHandlerCallable) -> None:
        if self._check_collisions and task_type in self._handlers:
            existing_source = self._handler_sources.get(task_type, "unknown")
            current_source = self._current_source or "unknown"
            raise HandlerCollisionError(
                f"Handler '{task_type}' is already registered by '{existing_source}', "
                f"cannot register again from '{current_source}'"
            )

        self._handlers[task_type] = handler
        if self._current_source:
            self._handler_sources[task_type] = self._current_source

    def get(self, task_type: str) -> TaskHandlerCallable | None:
        return self._handlers.get(task_type)

    def list_task_types(self) -> list[str]:
        return sorted(self._handlers.keys())
