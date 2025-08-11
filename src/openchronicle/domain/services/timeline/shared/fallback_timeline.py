"""
Fallback Timeline Manager - Minimal Timeline Functionality

Provides basic timeline functionality when full timeline system is unavailable.
"""

import json
from datetime import datetime, UTC
from typing import Dict, List, Any


class FallbackTimelineManager:
    """Minimal fallback timeline manager."""

    def __init__(self, story_id: str):
        self.story_id = story_id

    async def build_full_timeline(
        self, include_bookmarks: bool = True, include_summaries: bool = True
    ) -> Dict[str, Any]:
        """Build minimal timeline with basic scene data."""
        try:
            # Try to get basic scene data using core database functions
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).parent.parent.parent))
            from src.openchronicle.infrastructure.persistence import (
                execute_query,
                init_database,
            )

            init_database(self.story_id)

            scenes = execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output
                FROM scenes ORDER BY timestamp ASC LIMIT 100
            """,
            )

            timeline_entries = []
            for scene in scenes:
                timeline_entries.append(
                    {
                        "type": "scene",
                        "scene_id": scene[0],
                        "timestamp": scene[1],
                        "input": scene[2][:200] if scene[2] else "",  # Truncated
                        "output": scene[3][:200] if scene[3] else "",  # Truncated
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

        except Exception:
            return {
                "entries": [],
                "summary_stats": {"scene_count": 0, "error": True},
                "metadata": {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "fallback": True,
                    "error": "Failed to load basic timeline data",
                },
            }
