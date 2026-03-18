from __future__ import annotations

import asyncio
import logging
from typing import Any

from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
from openchronicle.core.domain.models.project import Event, Task
from openchronicle.core.domain.ports.plugin_port import PluginRegistry

from .application.scene_handler import generate_scene
from .domain.modes import EngagementMode
from .helpers import format_draft, hash_text
from .importer import import_project

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handler: story.draft (demo)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Handler: story.import
# ---------------------------------------------------------------------------


async def _story_import_handler(task: Task, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Import a storytelling project from a directory of text files."""
    await asyncio.sleep(0)
    ctx = context or {}
    memory_save = ctx.get("memory_save")
    emit_event = ctx.get("emit_event")
    agent_id = ctx.get("agent_id")

    payload = task.payload if isinstance(task.payload, dict) else {}
    source_dir: str = payload.get("source_dir", "")
    project_name: str = payload.get("project_name", "Unnamed Project")
    dry_run: bool = payload.get("dry_run", False)

    if not source_dir:
        raise ValueError("source_dir is required in task payload")
    if memory_save is None:
        raise RuntimeError("memory_save not available in handler context")

    if emit_event:
        emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="plugin.received_task",
                payload={"source_dir": source_dir, "project_name": project_name},
            )
        )

    result = import_project(
        source_dir=source_dir,
        project_name=project_name,
        memory_save=memory_save,
        dry_run=dry_run,
    )

    if emit_event:
        emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="plugin.completed_task",
                payload={
                    "project_name": result.project_name,
                    "imported": result.imported,
                    "skipped": result.skipped,
                },
            )
        )

    return {
        "project_name": result.project_name,
        "imported": result.imported,
        "assets_uploaded": result.assets_uploaded,
        "skipped": result.skipped,
        "warnings": result.warnings,
    }


# ---------------------------------------------------------------------------
# Handler: story.scene
# ---------------------------------------------------------------------------


async def _story_scene_handler(task: Task, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate a storytelling scene using assembled context and LLM."""
    ctx = context or {}
    memory_search = ctx.get("memory_search")
    memory_save = ctx.get("memory_save")
    llm_complete = ctx.get("llm_complete")
    emit_event = ctx.get("emit_event")
    agent_id = ctx.get("agent_id")

    if memory_search is None:
        raise RuntimeError("memory_search not available in handler context")
    if memory_save is None:
        raise RuntimeError("memory_save not available in handler context")
    if llm_complete is None:
        raise RuntimeError("llm_complete not available in handler context")

    payload = task.payload if isinstance(task.payload, dict) else {}
    user_prompt: str = payload.get("prompt", "")
    mode_str: str = payload.get("mode", "director")
    canon: bool = payload.get("canon", True)
    player_character: str | None = payload.get("player_character")
    location: str | None = payload.get("location")
    save_scene: bool = payload.get("save_scene", False)
    max_output_tokens: int = payload.get("max_output_tokens", 2048)
    temperature: float = payload.get("temperature", 0.8)

    if not user_prompt:
        raise ValueError("prompt is required in task payload")

    # Resolve engagement mode
    try:
        mode = EngagementMode(mode_str.lower())
    except ValueError:
        valid = ", ".join(m.value for m in EngagementMode)
        raise ValueError(f"Invalid mode '{mode_str}'. Valid modes: {valid}") from None

    if emit_event:
        emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="plugin.received_task",
                payload={
                    "handler": "story.scene",
                    "mode": mode.value,
                    "canon": canon,
                    "prompt_len": len(user_prompt),
                },
            )
        )

    result = await generate_scene(
        memory_search=memory_search,
        memory_save=memory_save,
        llm_complete=llm_complete,
        user_prompt=user_prompt,
        mode=mode,
        canon=canon,
        player_character=player_character,
        location=location,
        save_scene=save_scene,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )

    if emit_event:
        emit_event(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=agent_id,
                type="plugin.completed_task",
                payload={
                    "handler": "story.scene",
                    "mode": result.mode,
                    "canon": result.canon,
                    "scene_len": len(result.scene_text),
                    "characters_used": result.characters_used,
                    "scene_id": result.scene_id,
                },
            )
        )

    return {
        "scene_text": result.scene_text,
        "mode": result.mode,
        "canon": result.canon,
        "player_character": result.player_character,
        "location": result.location,
        "characters_used": result.characters_used,
        "scene_id": result.scene_id,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(
    registry: PluginRegistry, handler_registry: TaskHandlerRegistry, context: dict[str, Any] | None = None
) -> None:
    handler_registry.register("story.draft", _story_draft_handler)
    handler_registry.register("story.import", _story_import_handler)
    handler_registry.register("story.scene", _story_scene_handler)
    registry.register_agent_template(
        {"role": "storyteller", "description": "Imports and manages narrative content, generates scenes."}
    )
