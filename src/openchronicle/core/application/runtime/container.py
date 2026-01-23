from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openchronicle.core.application.runtime.plugin_loader import PluginLoader
from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.ports.llm_port import LLMPort
from openchronicle.core.infrastructure.llm.provider_facade import create_provider_aware_llm
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


class CoreContainer:
    def __init__(
        self,
        db_path: str | None = None,
        config_dir: str | None = None,
        plugin_dir: str | None = None,
        output_dir: str | None = None,
        llm: LLMPort | None = None,
    ) -> None:
        db_path_str = db_path if db_path is not None else os.getenv("OC_DB_PATH", "data/openchronicle.db")
        config_dir_str = config_dir if config_dir is not None else os.getenv("OC_CONFIG_DIR", "config")
        plugin_dir_str = plugin_dir if plugin_dir is not None else os.getenv("OC_PLUGIN_DIR", "plugins")
        output_dir_str = output_dir if output_dir is not None else os.getenv("OC_OUTPUT_DIR", "output")

        db_path_resolved = Path(db_path_str)
        config_dir_resolved = Path(config_dir_str)
        plugin_dir_resolved = Path(plugin_dir_str)
        output_dir_resolved = Path(output_dir_str)

        db_path_resolved.parent.mkdir(parents=True, exist_ok=True)
        config_dir_resolved.mkdir(parents=True, exist_ok=True)
        plugin_dir_resolved.mkdir(parents=True, exist_ok=True)
        output_dir_resolved.mkdir(parents=True, exist_ok=True)

        self.storage = SqliteStore(db_path=str(db_path_resolved))
        self.storage.init_schema()
        self.event_logger = EventLogger(self.storage)

        # Use provider-aware facade if no explicit LLM provided
        if llm is None:
            # Create facade that can route to multiple providers
            llm = create_provider_aware_llm(config_dir=config_dir_str)

        self.llm = llm
        self.interaction_router = RuleInteractionRouter()
        self.handler_registry = TaskHandlerRegistry()
        self.plugin_loader = PluginLoader(plugins_dir=str(plugin_dir_resolved), handler_registry=self.handler_registry)
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
            "interaction_router": self.interaction_router,
            "plugins": self.plugin_loader.registry_instance(),
            "handler_registry": self.plugin_loader.handler_registry_instance(),
            "orchestrator": self.orchestrator,
        }
