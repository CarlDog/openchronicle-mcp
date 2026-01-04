from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openchronicle_core.core.application.runtime.plugin_loader import PluginLoader
from openchronicle_core.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle_core.core.domain.models.project import TaskStatus
from openchronicle_core.core.domain.ports.llm_port import LLMPort
from openchronicle_core.core.domain.services.orchestrator import OrchestratorService
from openchronicle_core.core.infrastructure.logging.event_logger import EventLogger
from openchronicle_core.core.infrastructure.persistence.sqlite_store import SqliteStore


class FakeLLM(LLMPort):
    async def generate_async(
        self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None
    ) -> str:
        return f"llm:{prompt}"

    def generate(self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None) -> str:
        return f"llm:{prompt}"


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
