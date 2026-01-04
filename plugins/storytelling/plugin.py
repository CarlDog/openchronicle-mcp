from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from openchronicle_core.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle_core.core.domain.models.project import Event, Task
from openchronicle_core.core.domain.ports.plugin_port import PluginRegistry


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


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
                payload={"text_hash": _hash_text(prompt)},
            )
        )

    draft = f"[storytelling draft] {prompt}"

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
