from __future__ import annotations

from pathlib import Path

from openchronicle.core.application.runtime.handler_registry import TaskHandlerRegistry
from openchronicle.core.application.runtime.plugin_loader import PluginLoader


def test_storytelling_plugin_registers_handler(tmp_path: Path) -> None:
    registry = TaskHandlerRegistry()
    loader = PluginLoader(plugins_dir="plugins", handler_registry=registry)

    loader.load_plugins(context={"tmp": str(tmp_path)})

    handler = registry.get("story.draft")
    assert handler is not None
