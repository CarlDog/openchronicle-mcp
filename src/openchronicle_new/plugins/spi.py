"""Plugin service provider interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..kernel.container import Container


@runtime_checkable
class Plugin(Protocol):
    """Protocol that plugin implementations must follow."""

    id: str
    version: str

    def register(self, container: Container) -> Any:  # pragma: no cover - protocol definition
        """Register services and return optional facade."""

    def register_cli(self, app: Any | None) -> None:  # pragma: no cover - protocol definition
        """Register CLI commands if needed."""
