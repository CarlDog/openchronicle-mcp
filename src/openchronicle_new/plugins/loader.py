"""Plugin loader."""

from __future__ import annotations

from importlib import import_module

from ..kernel.container import Container
from .registry import Registry
from .spi import Plugin


def load_from_config(modules: list[str], container: Container, registry: Registry) -> None:
    """Load plugins from module paths."""
    # TODO: support plugin initialization order and better error messages
    for path in modules:
        mod = import_module(path)
        obj = None
        if hasattr(mod, "plugin"):
            obj = getattr(mod, "plugin")
        elif hasattr(mod, "Plugin"):
            obj = getattr(mod, "Plugin")()
        if obj is None:
            continue
        if not isinstance(obj, Plugin):
            continue
        facade = obj.register(container)
        registry.register(obj.id, facade)
        try:
            obj.register_cli(None)
        except Exception:
            pass
