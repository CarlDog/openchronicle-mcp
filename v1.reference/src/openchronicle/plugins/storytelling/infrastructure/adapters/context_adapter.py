"""
Storytelling Context Adapter

Implements the IContextPort interface with storytelling-focused logic,
decoupled from core infrastructure.
"""

from typing import Any

from openchronicle.domain.ports.context_port import IContextPort
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning


class StorytellingContextAdapter(IContextPort):
    """Context adapter specialized for storytelling workflows."""

    def __init__(self) -> None:
        log_info(
            "Initialized storytelling context adapter",
            context_tags=["storytelling", "context", "adapter"],
        )

    async def build_context_with_analysis(self, user_input: str, story_data: dict[str, Any]) -> dict[str, Any]:
        """Build enriched context using lightweight storytelling heuristics."""
        try:
            base = await self.build_basic_context(user_input, story_data)

            # Simple heuristic analysis tailored for narrative inputs
            text = (story_data.get("content") or user_input or "").lower()
            characters = story_data.get("characters") or []
            scenes = story_data.get("scenes") or []

            analysis = {
                "mentions_character": any(c.lower() in text for c in characters)
                if isinstance(characters, list)
                else False,
                "mentions_scene": any((s.get("name", "") or "").lower() in text for s in scenes)
                if isinstance(scenes, list)
                else False,
                "length": len(text),
            }

            base["analysis"] = analysis
            base["context_type"] = "storytelling_enriched"
        except Exception as e:
            log_warning(
                f"build_context_with_analysis fallback due to error: {e}",
                context_tags=["storytelling", "context", "warning"],
            )
            return await self.build_basic_context(user_input, story_data)
        else:
            return base

    async def build_basic_context(self, user_input: str, story_data: dict[str, Any]) -> dict[str, Any]:
        """Return a stable minimal context structure for storytelling."""
        try:
            return {
                "user_input": user_input,
                "story": {
                    "title": story_data.get("title"),
                    "summary": story_data.get("summary"),
                },
                "characters": story_data.get("characters") or [],
                "scenes": story_data.get("scenes") or [],
                "world": story_data.get("world") or {},
                "context_type": "basic",
            }
        except Exception as e:
            log_error(
                f"build_basic_context failed: {e}",
                context_tags=["storytelling", "context", "error"],
            )
            return {
                "user_input": user_input,
                "story": {},
                "characters": [],
                "scenes": [],
                "world": {},
                "context_type": "fallback",
                "error": str(e),
            }

    async def extract_context_metadata(self, context: dict[str, Any]) -> dict[str, Any]:
        """Extract concise metadata from a storytelling context payload."""
        try:
            return {
                "context_size": len(str(context)),
                "character_count": len(context.get("characters") or []),
                "scene_count": len(context.get("scenes") or []),
                "has_title": bool(context.get("story", {}).get("title")),
            }
        except Exception as e:
            log_warning(
                f"extract_context_metadata failed: {e}",
                context_tags=["storytelling", "context", "warning"],
            )
            return {"error": str(e)}
