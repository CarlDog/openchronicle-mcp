"""Tests for plugin loader package semantics."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from openchronicle.core.application.runtime.plugin_loader import PluginLoader
from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path


def test_plugin_without_init_py_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Plugins without __init__.py should be rejected with a clear error."""
    plugins_dir = tmp_path / "test_plugins"
    plugins_dir.mkdir()

    # Create a plugin directory without __init__.py
    bad_plugin = plugins_dir / "bad_plugin"
    bad_plugin.mkdir()
    (bad_plugin / "plugin.py").write_text(
        """
def register(registry, handler_registry, context=None):
    pass
"""
    )

    registry = TaskHandlerRegistry()
    loader = PluginLoader(plugins_dir=str(plugins_dir), handler_registry=registry)

    loader.load_plugins()

    captured = capsys.readouterr()
    assert "ERROR: Plugin 'bad_plugin' is missing __init__.py" in captured.err
    assert "Plugins must be packages to support relative imports" in captured.err


def test_storytelling_plugin_uses_relative_imports() -> None:
    """Verify storytelling plugin loads as a package and uses relative imports."""
    registry = TaskHandlerRegistry()
    loader = PluginLoader(plugins_dir="plugins", handler_registry=registry)

    loader.load_plugins()

    # Verify plugin module exists in sys.modules with package structure
    assert "oc_plugins.storytelling" in sys.modules
    assert "oc_plugins.storytelling.plugin" in sys.modules
    assert "oc_plugins.storytelling.helpers" in sys.modules

    # Verify handler was registered
    handler = registry.get("story.draft")
    assert handler is not None


@pytest.mark.asyncio
async def test_storytelling_plugin_handler_works_with_helpers() -> None:
    """Verify the storytelling handler uses helper functions correctly."""
    from openchronicle.core.domain.models.project import Task, TaskStatus

    registry = TaskHandlerRegistry()
    loader = PluginLoader(plugins_dir="plugins", handler_registry=registry)
    loader.load_plugins()

    handler = registry.get("story.draft")
    assert handler is not None

    # Create a test task
    task = Task(
        id="test-task",
        project_id="test-project",
        type="story.draft",
        status=TaskStatus.PENDING,
        payload={"prompt": "Test prompt"},
    )

    result = await handler(task, {})

    # Verify the helpers.format_draft function was used
    assert result == {"draft": "[storytelling draft] Test prompt"}
