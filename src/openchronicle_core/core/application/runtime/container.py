from __future__ import annotations

from typing import Any

from openchronicle_core.core.application.runtime.plugin_loader import PluginLoader
from openchronicle_core.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle_core.core.domain.services.orchestrator import OrchestratorService
from openchronicle_core.core.infrastructure.llm.openai_adapter import OpenAIAdapter
from openchronicle_core.core.infrastructure.logging.event_logger import EventLogger
from openchronicle_core.core.infrastructure.persistence.sqlite_store import SqliteStore


class CoreContainer:
    def __init__(self, db_path: str = "data/openchronicle_core.db") -> None:
        self.storage = SqliteStore(db_path=db_path)
        self.storage.init_schema()
        self.event_logger = EventLogger(self.storage)
        self.llm = OpenAIAdapter()
        self.handler_registry = TaskHandlerRegistry()
        self.plugin_loader = PluginLoader(handler_registry=self.handler_registry)
        self.plugin_loader.load_plugins()
        self.orchestrator = OrchestratorService(
            storage=self.storage,
            llm=self.llm,
            plugins=self.plugin_loader.registry_instance(),
            handler_registry=self.plugin_loader.handler_registry_instance(),
            emit_event=self.event_logger.append,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "storage": self.storage,
            "event_logger": self.event_logger,
            "llm": self.llm,
            "plugins": self.plugin_loader.registry_instance(),
            "handler_registry": self.plugin_loader.handler_registry_instance(),
            "orchestrator": self.orchestrator,
        }
