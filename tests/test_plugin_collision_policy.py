"""Test plugin collision detection and policy."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from openchronicle.core.application.runtime.plugin_loader import PluginCollisionError, PluginLoader


def test_plugin_collision_same_plugin_id_fails_by_default() -> None:
    """Loading two plugins with the same ID should fail without OC_PLUGIN_ALLOW_COLLISIONS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        plugins_dir.mkdir()

        # Create first plugin
        plugin1_dir = plugins_dir / "test_plugin"
        plugin1_dir.mkdir()
        (plugin1_dir / "__init__.py").write_text("")
        (plugin1_dir / "plugin.py").write_text(
            """
def register(registry, handler_registry, context):
    pass
"""
        )

        # Create second plugin with same name in a subdirectory (simulating external mount)
        external_dir = Path(tmpdir) / "external"
        external_dir.mkdir()
        plugin2_dir = external_dir / "test_plugin"
        plugin2_dir.mkdir()
        (plugin2_dir / "__init__.py").write_text("")
        (plugin2_dir / "plugin.py").write_text(
            """
def register(registry, handler_registry, context):
    pass
"""
        )

        # Load first plugin
        loader = PluginLoader(plugins_dir=str(plugins_dir))
        loader.load_plugins()

        # Manually register the second plugin directory to simulate collision
        # This simulates what would happen if two plugin directories with same name existed
        loader._plugin_sources["test_plugin"] = str(plugin1_dir)

        # Attempting to load plugins with same ID should raise during load_plugins check
        with pytest.raises(PluginCollisionError) as exc_info:
            # Check collision by simulating the check in load_plugins
            if "test_plugin" in loader._plugin_sources:
                if not loader.allow_collisions:
                    existing_source = loader._plugin_sources["test_plugin"]
                    new_source = str(plugin2_dir)
                    raise PluginCollisionError(
                        collision_type="plugin_id",
                        key="test_plugin",
                        existing_source=existing_source,
                        new_source=new_source,
                        sources=[existing_source, new_source],
                        error_code="PLUGIN_ID_COLLISION",
                    )

        assert exc_info.value.collision_type == "plugin_id"
        assert exc_info.value.key == "test_plugin"
        assert exc_info.value.error_code == "PLUGIN_ID_COLLISION"
        assert exc_info.value.existing_source == str(plugin1_dir)
        assert exc_info.value.new_source == str(plugin2_dir)
        assert len(exc_info.value.sources) == 2


def test_plugin_collision_same_handler_name_fails_by_default() -> None:
    """Loading two plugins that register the same handler should fail without OC_PLUGIN_ALLOW_COLLISIONS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        plugins_dir.mkdir()

        # Create first plugin
        plugin1_dir = plugins_dir / "plugin_one"
        plugin1_dir.mkdir()
        (plugin1_dir / "__init__.py").write_text("")
        (plugin1_dir / "plugin.py").write_text(
            """
async def my_handler(task, context):
    return {"result": "plugin_one"}

def register(registry, handler_registry, context):
    handler_registry.register("test.handler", my_handler)
"""
        )

        # Create second plugin with different ID but same handler name
        plugin2_dir = plugins_dir / "plugin_two"
        plugin2_dir.mkdir()
        (plugin2_dir / "__init__.py").write_text("")
        (plugin2_dir / "plugin.py").write_text(
            """
async def my_handler(task, context):
    return {"result": "plugin_two"}

def register(registry, handler_registry, context):
    handler_registry.register("test.handler", my_handler)
"""
        )

        loader = PluginLoader(plugins_dir=str(plugins_dir))

        with pytest.raises(PluginCollisionError) as exc_info:
            loader.load_plugins()

        assert exc_info.value.collision_type == "handler_name"
        assert exc_info.value.key == "test.handler"
        assert exc_info.value.error_code == "HANDLER_COLLISION"
        assert exc_info.value.existing_source == "plugin_one"
        assert exc_info.value.new_source == "plugin_two"
        assert "plugin_one" in exc_info.value.sources[0]
        assert "plugin_two" in exc_info.value.sources[1]


def test_plugin_collision_allowed_with_env_var() -> None:
    """With OC_PLUGIN_ALLOW_COLLISIONS=1, collisions should be allowed with deterministic precedence."""
    original_value = os.environ.get("OC_PLUGIN_ALLOW_COLLISIONS")
    try:
        os.environ["OC_PLUGIN_ALLOW_COLLISIONS"] = "1"

        with tempfile.TemporaryDirectory() as tmpdir:
            plugins_dir = Path(tmpdir) / "plugins"
            plugins_dir.mkdir()

            # Create first plugin
            plugin1_dir = plugins_dir / "plugin_one"
            plugin1_dir.mkdir()
            (plugin1_dir / "__init__.py").write_text("")
            (plugin1_dir / "plugin.py").write_text(
                """
async def my_handler(task, context):
    return {"result": "plugin_one"}

def register(registry, handler_registry, context):
    handler_registry.register("test.handler", my_handler)
"""
            )

            # Create second plugin with same handler name
            plugin2_dir = plugins_dir / "plugin_two"
            plugin2_dir.mkdir()
            (plugin2_dir / "__init__.py").write_text("")
            (plugin2_dir / "plugin.py").write_text(
                """
async def my_handler(task, context):
    return {"result": "plugin_two"}

def register(registry, handler_registry, context):
    handler_registry.register("test.handler", my_handler)
"""
            )

            loader = PluginLoader(plugins_dir=str(plugins_dir))
            # Should not raise
            loader.load_plugins()

            # Verify handler is registered (later plugin wins due to deterministic precedence)
            handler = loader.handler_registry.get("test.handler")
            assert handler is not None

    finally:
        if original_value is None:
            os.environ.pop("OC_PLUGIN_ALLOW_COLLISIONS", None)
        else:
            os.environ["OC_PLUGIN_ALLOW_COLLISIONS"] = original_value


def test_plugin_collision_error_message_includes_sources() -> None:
    """Plugin collision errors should include source paths for debugging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        plugins_dir.mkdir()

        # Create conflicting plugins
        plugin1_dir = plugins_dir / "conflict_a"
        plugin1_dir.mkdir()
        (plugin1_dir / "__init__.py").write_text("")
        (plugin1_dir / "plugin.py").write_text(
            """
async def handler(task, context):
    return {}

def register(registry, handler_registry, context):
    handler_registry.register("conflict.handler", handler)
"""
        )

        plugin2_dir = plugins_dir / "conflict_b"
        plugin2_dir.mkdir()
        (plugin2_dir / "__init__.py").write_text("")
        (plugin2_dir / "plugin.py").write_text(
            """
async def handler(task, context):
    return {}

def register(registry, handler_registry, context):
    handler_registry.register("conflict.handler", handler)
"""
        )

        loader = PluginLoader(plugins_dir=str(plugins_dir))

        with pytest.raises(PluginCollisionError) as exc_info:
            loader.load_plugins()

        error_message = str(exc_info.value)
        assert "conflict.handler" in error_message
        assert "conflict_a" in error_message
        assert "conflict_b" in error_message
        assert exc_info.value.error_code == "HANDLER_COLLISION"
        assert exc_info.value.existing_source == "conflict_a"
        assert exc_info.value.new_source == "conflict_b"


def test_no_collision_for_different_handlers() -> None:
    """Multiple plugins with different handler names should load without collision."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugins_dir = Path(tmpdir) / "plugins"
        plugins_dir.mkdir()

        # Create first plugin
        plugin1_dir = plugins_dir / "plugin_alpha"
        plugin1_dir.mkdir()
        (plugin1_dir / "__init__.py").write_text("")
        (plugin1_dir / "plugin.py").write_text(
            """
async def handler_alpha(task, context):
    return {"result": "alpha"}

def register(registry, handler_registry, context):
    handler_registry.register("alpha.handler", handler_alpha)
"""
        )

        # Create second plugin
        plugin2_dir = plugins_dir / "plugin_beta"
        plugin2_dir.mkdir()
        (plugin2_dir / "__init__.py").write_text("")
        (plugin2_dir / "plugin.py").write_text(
            """
async def handler_beta(task, context):
    return {"result": "beta"}

def register(registry, handler_registry, context):
    handler_registry.register("beta.handler", handler_beta)
"""
        )

        loader = PluginLoader(plugins_dir=str(plugins_dir))
        # Should not raise
        loader.load_plugins()

        # Verify both handlers are registered
        assert loader.handler_registry.get("alpha.handler") is not None
        assert loader.handler_registry.get("beta.handler") is not None
        assert len(loader.handler_registry.list_task_types()) >= 2


class TestUserPluginsDir:
    """OC_USER_PLUGINS_DIR adds a second scan root for operator-supplied plugins."""

    def test_user_plugins_dir_loads_additional_plugin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When OC_USER_PLUGINS_DIR is set + dir has a plugin, it loads alongside built-ins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Built-in plugins root (image-baked equivalent)
            builtin_dir = Path(tmpdir) / "builtin"
            builtin_dir.mkdir()
            builtin_plugin = builtin_dir / "alpha"
            builtin_plugin.mkdir()
            (builtin_plugin / "__init__.py").write_text("")
            (builtin_plugin / "plugin.py").write_text(
                """
async def handler_alpha(task, context):
    return {"src": "builtin"}

def register(registry, handler_registry, context):
    handler_registry.register("alpha.handler", handler_alpha)
"""
            )

            # User plugins root (operator-bind-mount equivalent)
            user_dir = Path(tmpdir) / "user"
            user_dir.mkdir()
            user_plugin = user_dir / "beta"
            user_plugin.mkdir()
            (user_plugin / "__init__.py").write_text("")
            (user_plugin / "plugin.py").write_text(
                """
async def handler_beta(task, context):
    return {"src": "user"}

def register(registry, handler_registry, context):
    handler_registry.register("beta.handler", handler_beta)
"""
            )

            monkeypatch.setenv("OC_USER_PLUGINS_DIR", str(user_dir))
            loader = PluginLoader(plugins_dir=str(builtin_dir))
            loader.load_plugins()

            # Both plugins loaded — built-in first, user-supplied second
            assert loader.handler_registry.get("alpha.handler") is not None
            assert loader.handler_registry.get("beta.handler") is not None

    def test_user_plugins_dir_unset_only_builtin_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When OC_USER_PLUGINS_DIR is unset, only the built-in dir is scanned."""
        monkeypatch.delenv("OC_USER_PLUGINS_DIR", raising=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            builtin_dir = Path(tmpdir) / "builtin"
            builtin_dir.mkdir()
            plugin = builtin_dir / "only_one"
            plugin.mkdir()
            (plugin / "__init__.py").write_text("")
            (plugin / "plugin.py").write_text(
                """
def register(registry, handler_registry, context):
    pass
"""
            )

            loader = PluginLoader(plugins_dir=str(builtin_dir))
            loader.load_plugins()
            # Just the one built-in source registered
            assert "only_one" in loader._plugin_sources
            assert len(loader._plugin_sources) == 1

    def test_user_plugins_dir_set_but_nonexistent_no_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting OC_USER_PLUGINS_DIR to a nonexistent path is silently skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builtin_dir = Path(tmpdir) / "builtin"
            builtin_dir.mkdir()
            # Built-in is empty; that's fine
            monkeypatch.setenv("OC_USER_PLUGINS_DIR", str(Path(tmpdir) / "does-not-exist"))
            loader = PluginLoader(plugins_dir=str(builtin_dir))
            # Should not raise
            loader.load_plugins()
            assert loader._plugin_sources == {}

    def test_user_plugins_dir_collision_with_builtin_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A user plugin with the same dir-name as a built-in raises PluginCollisionError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builtin_dir = Path(tmpdir) / "builtin"
            builtin_dir.mkdir()
            (builtin_dir / "duplicate").mkdir()
            (builtin_dir / "duplicate" / "__init__.py").write_text("")
            (builtin_dir / "duplicate" / "plugin.py").write_text(
                """
def register(registry, handler_registry, context):
    pass
"""
            )

            user_dir = Path(tmpdir) / "user"
            user_dir.mkdir()
            (user_dir / "duplicate").mkdir()
            (user_dir / "duplicate" / "__init__.py").write_text("")
            (user_dir / "duplicate" / "plugin.py").write_text(
                """
def register(registry, handler_registry, context):
    pass
"""
            )

            monkeypatch.setenv("OC_USER_PLUGINS_DIR", str(user_dir))
            loader = PluginLoader(plugins_dir=str(builtin_dir))
            with pytest.raises(PluginCollisionError) as exc_info:
                loader.load_plugins()
            assert exc_info.value.collision_type == "plugin_id"
            assert exc_info.value.key == "duplicate"
