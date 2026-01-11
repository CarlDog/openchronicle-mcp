from __future__ import annotations

import asyncio
from typing import Any

from openchronicle.core.application.runtime.handler_registry import TaskHandlerRegistry
from openchronicle.core.domain.models.project import Event, Task
from openchronicle.core.domain.ports.plugin_port import PluginRegistry

from .helpers import format_draft, hash_text


async def _story_draft_handler(task: Task, context: dict[str, Any] | None = None) -> dict[str, str]:
    await asyncio.sleep(0)
    context = context or {}
    emit_event = context.get("emit_event")
    agent_id = context.get("agent_id")

    prompt = task.payload.get("prompt") or "Tell a short story."
    if emit_event:
        emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="plugin.received_task",
                payload={"text_hash": hash_text(prompt)},
            )
        )

    draft = format_draft(prompt)

    if emit_event:
        emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="plugin.completed_task",
                payload={"draft_preview": draft[:80]},
            )
        )

    return {"draft": draft}


def register(
    registry: PluginRegistry, handler_registry: TaskHandlerRegistry, context: dict[str, Any] | None = None
) -> None:
    handler_registry.register("story.draft", _story_draft_handler)
    registry.register_agent_template({"role": "storyteller", "description": "Generates narrative drafts."})
