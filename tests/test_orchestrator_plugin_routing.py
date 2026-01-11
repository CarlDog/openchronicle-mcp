from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from openchronicle.core.application.runtime.handler_registry import TaskHandlerRegistry
from openchronicle.core.application.runtime.plugin_loader import PluginLoader
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

if TYPE_CHECKING:
    from pathlib import Path


class FakeLLM(LLMPort):
    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        content = " ".join(m.get("content", "") for m in messages)
        return LLMResponse(content=f"llm:{content}", provider="fake", model=model)


@pytest.mark.asyncio
async def test_story_draft_routes_through_plugin_and_emits_events(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(db_path=str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    handler_registry = TaskHandlerRegistry()
    plugin_loader = PluginLoader(plugins_dir="plugins", handler_registry=handler_registry)
    plugin_loader.load_plugins()

    orchestrator = OrchestratorService(
        storage=storage,
        llm=FakeLLM(),
        plugins=plugin_loader.registry_instance(),
        handler_registry=plugin_loader.handler_registry_instance(),
        emit_event=event_logger.append,
    )

    project = orchestrator.create_project("Test")
    task = orchestrator.submit_task(project.id, "story.draft", {"prompt": "Hello"})

    result = await orchestrator.execute_task(task.id)

    assert result == {"draft": "[storytelling draft] Hello"}

    stored_task = storage.get_task(task.id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.COMPLETED

    events = storage.list_events(task.id)
    event_types = [e.type for e in events]
    assert event_types == [
        "task_submitted",
        "task_started",
        "plugin.received_task",
        "plugin.completed_task",
        "task_completed",
    ]


@pytest.mark.asyncio
async def test_orchestrator_routes_only_through_task_handler_registry(tmp_path: Path) -> None:
    """Verify orchestrator uses TaskHandlerRegistry as single source of truth for handlers."""
    db_path = tmp_path / "test.db"
    storage = SqliteStore(db_path=str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    handler_registry = TaskHandlerRegistry()
    plugin_loader = PluginLoader(plugins_dir="plugins", handler_registry=handler_registry)
    plugin_loader.load_plugins()

    orchestrator = OrchestratorService(
        storage=storage,
        llm=FakeLLM(),
        plugins=plugin_loader.registry_instance(),
        handler_registry=plugin_loader.handler_registry_instance(),
        emit_event=event_logger.append,
    )

    # Verify the handler is in TaskHandlerRegistry
    assert handler_registry.get("story.draft") is not None

    # Execute task - should route through TaskHandlerRegistry, not PluginRegistry
    project = orchestrator.create_project("Test")
    task = orchestrator.submit_task(project.id, "story.draft", {"prompt": "Via registry"})
    result = await orchestrator.execute_task(task.id)

    # Verify result came from the handler in TaskHandlerRegistry
    assert result == {"draft": "[storytelling draft] Via registry"}
    assert storage.get_task(task.id).status == TaskStatus.COMPLETED  # type: ignore[union-attr]
