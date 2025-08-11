"""
Timeline Manager - Core Timeline Building and Management

Handles the primary timeline building functionality extracted from the legacy
timeline_builder.py. Provides scene organization, bookmark integration, and
auto-summary generation in a modular architecture.
"""

import json
import sys
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Database imports from parent core directory
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.openchronicle.infrastructure.persistence import execute_query, init_database
from src.openchronicle.application.services.management.bookmark.bookmark_manager import (
    BookmarkManager,
)
from src.openchronicle.domain.services.scenes.scene_orchestrator import (
    SceneOrchestrator,
)

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent / "utilities"))
from src.openchronicle.shared.logging_system import (
    log_system_event,
    log_info,
    log_warning,
    log_error,
)


class TimelineManager:
    """Manages core timeline building and scene organization."""

    def __init__(self, story_id: str):
        self.story_id = story_id
        self.bookmark_manager = BookmarkManager(story_id)
        init_database(story_id)

    async def build_full_timeline(
        self, include_bookmarks: bool = True, include_summaries: bool = True
    ) -> Dict[str, Any]:
        """Build complete story timeline with scenes and bookmarks."""

        # Get all scenes
        scenes = execute_query(
            self.story_id,
            """
            SELECT scene_id, timestamp, input, output, memory_snapshot, flags, canon_refs, scene_label
            FROM scenes ORDER BY timestamp ASC
        """,
        )

        timeline_entries = []

        # Process scenes
        for scene in scenes:
            entry = {
                "type": "scene",
                "scene_id": scene[0],
                "timestamp": scene[1],
                "input": scene[2],
                "output": scene[3],
                "memory_snapshot": json.loads(scene[4]) if scene[4] else {},
                "flags": json.loads(scene[5]) if scene[5] else [],
                "canon_refs": json.loads(scene[6]) if scene[6] else [],
                "scene_label": scene[7],
            }

            # Add tone analysis if available
            if include_summaries:
                entry["tone_analysis"] = await self._analyze_scene_tone(
                    scene[2], scene[3]
                )

            timeline_entries.append(entry)

        # Add bookmarks if requested
        if include_bookmarks:
            bookmarks = self.bookmark_manager.get_timeline_bookmarks()
            for bookmark in bookmarks:
                timeline_entries.append(
                    {
                        "type": "bookmark",
                        "timestamp": bookmark.get("timestamp", ""),
                        "bookmark_data": bookmark,
                    }
                )

        # Sort by timestamp
        timeline_entries.sort(key=lambda x: x.get("timestamp", ""))

        # Generate auto-summaries if requested
        timeline_data = {
            "entries": timeline_entries,
            "summary_stats": self._calculate_timeline_stats(timeline_entries),
        }

        if include_summaries:
            timeline_data["auto_summaries"] = await self._generate_auto_summaries(
                timeline_entries
            )

        return timeline_data

    async def get_scene_context(
        self, scene_id: str, context_range: int = 3
    ) -> Dict[str, Any]:
        """Get contextual scenes around a specific scene."""

        # Get target scene timestamp
        target_scene = execute_query(
            self.story_id,
            """
            SELECT timestamp FROM scenes WHERE scene_id = ?
        """,
            (scene_id,),
        )

        if not target_scene:
            return {"error": f"Scene {scene_id} not found"}

        target_timestamp = target_scene[0][0]

        # Get scenes before and after
        context_scenes = execute_query(
            self.story_id,
            """
            SELECT scene_id, timestamp, input, output, scene_label
            FROM scenes 
            WHERE ABS(strftime('%s', timestamp) - strftime('%s', ?)) <= ?
            ORDER BY timestamp ASC
        """,
            (target_timestamp, context_range * 3600),
        )  # context_range in hours

        return {
            "target_scene_id": scene_id,
            "context_scenes": [
                {
                    "scene_id": scene[0],
                    "timestamp": scene[1],
                    "input": scene[2],
                    "output": scene[3],
                    "scene_label": scene[4],
                    "is_target": scene[0] == scene_id,
                }
                for scene in context_scenes
            ],
        }

    async def _analyze_scene_tone(
        self, input_text: str, output_text: str
    ) -> Dict[str, Any]:
        """Analyze tone of scene content."""
        # Basic tone analysis - can be enhanced with content analysis integration
        combined_text = f"{input_text} {output_text}".lower()

        tone_indicators = {
            "positive": ["happy", "joy", "excited", "wonderful", "amazing", "great"],
            "negative": ["sad", "angry", "frustrated", "terrible", "awful", "bad"],
            "suspenseful": ["mysterious", "unknown", "hidden", "secret", "danger"],
            "action": ["fight", "run", "chase", "battle", "attack", "escape"],
        }

        tone_scores = {}
        for tone, words in tone_indicators.items():
            score = sum(1 for word in words if word in combined_text)
            tone_scores[tone] = score

        # Determine primary tone
        primary_tone = (
            max(tone_scores, key=tone_scores.get)
            if any(tone_scores.values())
            else "neutral"
        )

        return {
            "primary_tone": primary_tone,
            "tone_scores": tone_scores,
            "confidence": max(tone_scores.values())
            / max(1, len(combined_text.split())),
        }

    async def _generate_auto_summaries(
        self, timeline_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate automatic summaries of timeline segments."""
        scene_entries = [
            entry for entry in timeline_entries if entry["type"] == "scene"
        ]

        if len(scene_entries) < 2:
            return {
                "segments": [],
                "overall_summary": "Insufficient scenes for auto-summary",
            }

        # Create summary segments (every 5 scenes)
        segment_size = 5
        segments = []

        for i in range(0, len(scene_entries), segment_size):
            segment_scenes = scene_entries[i : i + segment_size]

            # Basic summary generation
            segment_summary = {
                "start_scene": segment_scenes[0]["scene_id"],
                "end_scene": segment_scenes[-1]["scene_id"],
                "scene_count": len(segment_scenes),
                "timespan": {
                    "start": segment_scenes[0]["timestamp"],
                    "end": segment_scenes[-1]["timestamp"],
                },
                "key_events": [
                    (
                        scene["input"][:100] + "..."
                        if len(scene["input"]) > 100
                        else scene["input"]
                    )
                    for scene in segment_scenes[:3]  # Top 3 events
                ],
                "dominant_tone": await self._get_segment_tone(segment_scenes),
            }

            segments.append(segment_summary)

        return {
            "segments": segments,
            "overall_summary": f"Timeline contains {len(scene_entries)} scenes across {len(segments)} segments",
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def _get_segment_tone(self, scenes: List[Dict[str, Any]]) -> str:
        """Determine dominant tone for a segment of scenes."""
        tone_counts = {}

        for scene in scenes:
            if "tone_analysis" in scene:
                tone = scene["tone_analysis"]["primary_tone"]
                tone_counts[tone] = tone_counts.get(tone, 0) + 1

        return max(tone_counts, key=tone_counts.get) if tone_counts else "neutral"

    def _calculate_timeline_stats(
        self, timeline_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate basic statistics for the timeline."""
        scene_count = sum(1 for entry in timeline_entries if entry["type"] == "scene")
        bookmark_count = sum(
            1 for entry in timeline_entries if entry["type"] == "bookmark"
        )

        # Calculate timespan
        timestamps = [
            entry["timestamp"] for entry in timeline_entries if entry.get("timestamp")
        ]
        timespan = {
            "start": min(timestamps) if timestamps else "",
            "end": max(timestamps) if timestamps else "",
            "total_entries": len(timeline_entries),
        }

        return {
            "scene_count": scene_count,
            "bookmark_count": bookmark_count,
            "timespan": timespan,
            "entry_types": {"scenes": scene_count, "bookmarks": bookmark_count},
        }
