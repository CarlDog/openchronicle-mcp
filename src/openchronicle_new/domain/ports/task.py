"""Task scheduling port."""

from __future__ import annotations

from typing import Awaitable, Callable, Protocol


class Scheduler(Protocol):
    """Abstract scheduler for asynchronous tasks."""

    def schedule(self, func: Callable[[], Awaitable[None]], delay: float = 0) -> None:
        """Schedule a coroutine to run after an optional delay."""
