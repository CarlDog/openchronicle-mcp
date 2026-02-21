from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PluginRegistry(ABC):
    @abstractmethod
    def register_agent_template(self, agent: dict[str, Any]) -> None: ...

    @abstractmethod
    def list_agent_templates(self) -> list[dict[str, Any]]: ...


class PluginPort(ABC):
    @abstractmethod
    def load_plugins(self) -> None: ...

    @abstractmethod
    def registry(self) -> PluginRegistry: ...
