from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from openchronicle.core.domain.models.project import Agent, Event, Project, Resource, Span, Task


class Page(Protocol):
    items: list[Any]
    total: int


class StoragePort(ABC):
    """Persistence operations for the core."""

    @abstractmethod
    def init_schema(self) -> None: ...

    # Projects
    @abstractmethod
    def add_project(self, project: Project) -> None: ...

    @abstractmethod
    def list_projects(self) -> list[Project]: ...

    @abstractmethod
    def get_project(self, project_id: str) -> Project | None: ...

    # Agents
    @abstractmethod
    def add_agent(self, agent: Agent) -> None: ...

    @abstractmethod
    def list_agents(self, project_id: str) -> list[Agent]: ...

    # Tasks
    @abstractmethod
    def add_task(self, task: Task) -> None: ...

    @abstractmethod
    def update_task_status(self, task_id: str, status: str) -> None: ...

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None: ...

    # Events
    @abstractmethod
    def append_event(self, event: Event) -> None: ...

    @abstractmethod
    def list_events(self, task_id: str) -> list[Event]: ...

    # Resources
    @abstractmethod
    def add_resource(self, resource: Resource) -> None: ...

    @abstractmethod
    def list_resources(self, project_id: str) -> list[Resource]: ...

    # Spans
    @abstractmethod
    def add_span(self, span: Span) -> None: ...

    @abstractmethod
    def update_span(self, span: Span) -> None: ...

    @abstractmethod
    def list_spans(self, task_id: str) -> list[Span]: ...

    @abstractmethod
    def get_span(self, span_id: str) -> Span | None: ...
