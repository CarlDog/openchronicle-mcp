"""Tests for plugin loader."""

from __future__ import annotations

from openchronicle_new.kernel import bootstrap
from openchronicle_new.plugins import loader


def test_loader_registers_plugin() -> None:
    bootstrap.reset_core()
    bootstrap.create_core()
    container = bootstrap.get_container()
    registry = bootstrap.get_plugin_registry()
    loader.load_from_config(["tests.adapters.dummy_plugin"], container, registry)
    assert registry.list_all() == ["dummy"]


def test_loader_warns_when_plugin_missing(caplog) -> None:
    bootstrap.reset_core()
    bootstrap.create_core()
    container = bootstrap.get_container()
    registry = bootstrap.get_plugin_registry()
    with caplog.at_level("WARNING"):
        loader.load_from_config(["tests.adapters.no_plugin"], container, registry)
    assert registry.list_all() == []
    assert "no plugin object found" in caplog.text
