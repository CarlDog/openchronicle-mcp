"""
Fallback Timeline Manager - Minimal Timeline Functionality

Provides basic timeline functionality when full timeline system is unavailable.
"""

from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Optional

from openchronicle.domain.ports.persistence_port import IPersistencePort


class FallbackTimelineManager:
    """Minimal fallback timeline manager."""

    def __init__(self, story_id: str, persistence_port: IPersistencePort):
        self.persistence_port = persistence_port

        self.story_id = story_id

    async def build_full_timeline(
        self, include_bookmarks: bool = True, include_summaries: bool = True
    ) -> dict[str, Any]:
        """Build minimal timeline with basic scene data."""
        try:
            # Basic scene data via injected persistence port
            self.persistence_port.init_database(self.story_id)

            scenes = self.persistence_port.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output
                FROM scenes
                WHERE story_id = ?
                ORDER BY timestamp ASC
                LIMIT 100
            """,
                (self.story_id,),
            )

            timeline_entries = []
            for scene in scenes:
                timeline_entries.append(
                    {
                        "type": "scene",
                        "scene_id": scene.get("scene_id") if hasattr(scene, "get") else None,
                        "timestamp": scene.get("timestamp") if hasattr(scene, "get") else None,
                        "input": (scene.get("input")[:200] if hasattr(scene, "get") and scene.get("input") else ""),
                        "output": (scene.get("output")[:200] if hasattr(scene, "get") and scene.get("output") else ""),
                        "fallback_mode": True,
                    }
                )

            return {
                "entries": timeline_entries,
                "summary_stats": {
                    "scene_count": len(timeline_entries),
                    "fallback_mode": True,
                    "limited_data": True,
                },
                "metadata": {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "fallback": True,
                },
            }

        except (RuntimeError, ValueError, KeyError, TypeError, OSError):
            return {
                "entries": [],
                "summary_stats": {"scene_count": 0, "error": True},
                "metadata": {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "fallback": True,
                    "error": "Failed to load basic timeline data",
                },
            }
