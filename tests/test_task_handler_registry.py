from __future__ import annotations

from typing import Any

import pytest

from openchronicle_core.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle_core.core.domain.models.project import Task


async def _dummy(task: Task, ctx: dict[str, Any] | None) -> str:
    value: str = task.payload.get("value", "ok")
    return value


def test_register_and_get_handler() -> None:
    registry = TaskHandlerRegistry()
    registry.register("dummy.task", _dummy)

    handler = registry.get("dummy.task")

    assert handler is _dummy
    assert registry.list_task_types() == ["dummy.task"]


@pytest.mark.asyncio
async def test_registered_handler_is_async() -> None:
    registry = TaskHandlerRegistry()
    registry.register("dummy.task", _dummy)

    handler = registry.get("dummy.task")
    assert handler is not None
    result = await handler(Task(payload={"value": "hello"}), None)
    assert result == "hello"


def test_list_task_types_sorted() -> None:
    registry = TaskHandlerRegistry()
    registry.register("b.task", _dummy)
    registry.register("a.task", _dummy)
    assert registry.list_task_types() == ["a.task", "b.task"]
