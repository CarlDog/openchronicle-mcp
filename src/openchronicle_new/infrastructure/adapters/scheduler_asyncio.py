"""AsyncIO-based task scheduler."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class AsyncIOScheduler:
    """Schedule asynchronous callables using asyncio."""

    def schedule(self, func: Callable[[], Awaitable[None]], delay: float = 0) -> asyncio.Task:
        async def runner() -> None:
            if delay:
                await asyncio.sleep(delay)
            await func()

        return asyncio.create_task(runner())
