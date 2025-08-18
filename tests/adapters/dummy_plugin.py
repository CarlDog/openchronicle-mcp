"""Dummy plugin for tests."""

from __future__ import annotations

from openchronicle_new.kernel.container import Container


class DummyPlugin:
    id = "dummy"
    version = "0.1"

    def register(self, container: Container) -> object:
        return object()

    def register_cli(self, app: object | None) -> None:
        return None


plugin = DummyPlugin()
