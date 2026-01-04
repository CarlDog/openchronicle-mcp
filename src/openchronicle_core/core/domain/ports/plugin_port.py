from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from openchronicle_core.core.domain.models.project import Task


class TaskHandler(Protocol):
    async def __call__(self, task: Task, *, context: dict[str, Any] | None = None) -> Any: ...


class PluginRegistry(ABC):
    @abstractmethod
    def register_task_handler(self, task_type: str, handler: TaskHandler) -> None: ...

    @abstractmethod
    def get_task_handler(self, task_type: str) -> TaskHandler | None: ...

    @abstractmethod
    def register_agent_template(self, agent: dict[str, Any]) -> None: ...

    @abstractmethod
    def list_agent_templates(self) -> list[dict[str, Any]]: ...


class PluginPort(ABC):
    @abstractmethod
    def load_plugins(self) -> None: ...

    @abstractmethod
    def registry(self) -> PluginRegistry: ...
