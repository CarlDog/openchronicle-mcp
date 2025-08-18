"""Plugin loader."""

from __future__ import annotations

import logging
from importlib import import_module

from ..kernel.container import Container
from .registry import Registry
from .spi import Plugin

logger = logging.getLogger(__name__)


def load_from_config(modules: list[str], container: Container, registry: Registry) -> None:
    """Load plugins from module paths."""
    # TODO: support plugin initialization order
    for path in modules:
        try:
            mod = import_module(path)
        except Exception as exc:  # pragma: no cover - import failure path
            logger.warning("failed to import %s: %s", path, exc)
            continue
        obj = getattr(mod, "plugin", None)
        if obj is None and hasattr(mod, "Plugin"):
            try:
                obj = getattr(mod, "Plugin")()
            except Exception as exc:  # pragma: no cover - instantiation failure path
                logger.warning("failed to instantiate Plugin class in %s: %s", path, exc)
                continue
        if obj is None:
            logger.warning("no plugin object found in %s", path)
            continue
        if not isinstance(obj, Plugin):
            logger.warning("object %r in %s is not a Plugin instance", obj, path)
            continue
        try:
            facade = obj.register(container)
        except Exception as exc:  # pragma: no cover - plugin register failure
            logger.warning("plugin %s failed to register: %s", obj.id, exc)
            continue
        registry.register(obj.id, facade)
        try:
            obj.register_cli(None)
        except Exception:  # pragma: no cover - optional CLI registration
            logger.debug("plugin %s has no CLI registration", obj.id)
