"""
Timeline Manager - Core Timeline Building and Management

Handles the primary timeline building functionality extracted from the legacy
timeline_builder.py. Provides scene organization, bookmark integration, and
auto-summary generation in a modular architecture.

This manager uses dependency injection following hexagonal architecture principles.
"""

import json
from datetime import UTC
from datetime import datetime
from typing import Any, Optional

# Domain ports only - following hexagonal architecture
from openchronicle.domain.ports.memory_port import IMemoryPort
from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.domain.ports.persistence_inmemory import (
    InMemorySqlitePersistence,
)

# Bookmark management interface (to be injected, not directly imported)
from typing import Protocol


class IBookmarkManager(Protocol):
    """Interface for bookmark management - prevents domain layer violations."""

    def create_bookmark(self, story_id: str, scene_index: int, label: str) -> str:
        """Create a new bookmark."""
        ...

    def get_bookmarks(self, story_id: str) -> list[dict[str, Any]]:
        """Get all bookmarks for a story."""
        ...


class TimelineManager:
    """Manages core timeline building and scene organization using dependency injection."""

    def __init__(
        self,
        story_id: str,
        persistence_port: Optional[IPersistencePort] = None,
        memory_port: Optional[IMemoryPort] = None,
        bookmark_manager: Optional[IBookmarkManager] = None,
    ):
        """
        Initialize timeline manager.

        Args:
            story_id: Story identifier
            persistence_port: Persistence interface implementation (injected)
            memory_port: Memory interface implementation (injected)
        """
        self.story_id = story_id

        # Prefer injected persistence, otherwise use in-memory port for dev/tests
        self.persistence: IPersistencePort = (
            persistence_port if persistence_port is not None else InMemorySqlitePersistence()
        )

        # Memory port is optional for current features; used for future extensions
        self.memory = memory_port

        # Use injected bookmark manager or None (caller responsibility to provide)
        self.bookmark_manager = bookmark_manager
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database for the story."""
        self.persistence.init_database(self.story_id)

    async def build_full_timeline(
        self, include_bookmarks: bool = True, include_summaries: bool = True
    ) -> dict[str, Any]:
        """Build complete story timeline with scenes and optional bookmarks/summaries."""

        # Get all scenes for this story
        scenes = self.persistence.execute_query(
            self.story_id,
            """
            SELECT scene_id, timestamp, input, output, memory_snapshot, flags, canon_refs, analysis, scene_label
            FROM scenes WHERE story_id = ? ORDER BY timestamp ASC
            """,
            (self.story_id,),
        )

        timeline_entries: list[dict[str, Any]] = []

        # Process scenes
        for scene in scenes:
            entry: dict[str, Any] = {
                "type": "scene",
                "scene_id": scene.get("scene_id"),
                "timestamp": scene.get("timestamp"),
                "input": scene.get("input"),
                "output": scene.get("output"),
                "memory_snapshot": self._safe_json_load(scene.get("memory_snapshot"), default={}),
                "flags": self._safe_json_load(scene.get("flags"), default=[]),
                "canon_refs": self._safe_json_load(scene.get("canon_refs"), default=[]),
                "analysis": self._safe_json_load(scene.get("analysis"), default={}),
                "scene_label": scene.get("scene_label"),
            }

            # Add tone analysis if available
            if include_summaries:
                entry["tone_analysis"] = await self._analyze_scene_tone(
                    entry.get("input", ""), entry.get("output", "")
                )

            timeline_entries.append(entry)

        # Add bookmarks if requested
        if include_bookmarks and self.bookmark_manager is not None:
            try:
                bookmarks = self.bookmark_manager.get_bookmarks(self.story_id)
                for bookmark in bookmarks:
                    timeline_entries.append(
                        {
                            "type": "bookmark",
                            "timestamp": bookmark.get("timestamp", ""),
                            "bookmark_data": bookmark,
                        }
                    )
            except Exception:
                # Bookmark system optional; continue without it
                pass

        # Sort by timestamp
        timeline_entries.sort(key=lambda x: x.get("timestamp", ""))

        # Generate auto-summaries if requested
        timeline_data: dict[str, Any] = {
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
    ) -> dict[str, Any]:
        """Get contextual scenes around a specific scene."""

        # Get target scene timestamp
        target_scene = self.persistence.execute_query(
            self.story_id,
            """
            SELECT timestamp FROM scenes WHERE scene_id = ? AND story_id = ?
            """,
            (scene_id, self.story_id),
        )

        if not target_scene:
            return {"error": f"Scene {scene_id} not found"}

        target_timestamp = target_scene[0]["timestamp"]

        # Get scenes before and after
        context_scenes = self.persistence.execute_query(
            self.story_id,
            """
            SELECT scene_id, timestamp, input, output, scene_label
            FROM scenes
            WHERE story_id = ? AND ABS(strftime('%s', timestamp) - strftime('%s', ?)) <= ?
            ORDER BY timestamp ASC
            """,
            (self.story_id, target_timestamp, context_range * 3600),
        )  # context_range in hours

        return {
            "target_scene_id": scene_id,
            "context_scenes": [
                {
                    "scene_id": scene.get("scene_id"),
                    "timestamp": scene.get("timestamp"),
                    "input": scene.get("input"),
                    "output": scene.get("output"),
                    "scene_label": scene.get("scene_label"),
                    "is_target": scene.get("scene_id") == scene_id,
                }
                for scene in context_scenes
            ],
        }

    async def _analyze_scene_tone(
        self, input_text: str, output_text: str
    ) -> dict[str, Any]:
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
        self, timeline_entries: list[dict[str, Any]]
    ) -> dict[str, Any]:
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

    async def _get_segment_tone(self, scenes: list[dict[str, Any]]) -> str:
        """Determine dominant tone for a segment of scenes."""
        tone_counts = {}

        for scene in scenes:
            if "tone_analysis" in scene:
                tone = scene["tone_analysis"]["primary_tone"]
                tone_counts[tone] = tone_counts.get(tone, 0) + 1

        return max(tone_counts, key=tone_counts.get) if tone_counts else "neutral"

    def _calculate_timeline_stats(
        self, timeline_entries: list[dict[str, Any]]
    ) -> dict[str, Any]:
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

    def _safe_json_load(self, raw: Optional[str], *, default: Any) -> Any:
        """Safely parse JSON strings, returning default on error or None."""
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default
