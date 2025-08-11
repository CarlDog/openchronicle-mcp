"""
Mood Analyzer - Scene mood and type analysis

Provides mood and scene type analysis capabilities:
- Character mood tracking
- Scene type classification
- Mood timeline analysis
- Emotional trend detection

This analyzer now uses dependency injection following hexagonal architecture principles.
"""

import json
from datetime import datetime
from typing import Any
from typing import Optional

# Import domain interfaces (following dependency inversion principle)
from src.openchronicle.domain.ports.persistence_port import IPersistencePort


class MoodAnalyzer:
    """Handles mood analysis and scene type classification using dependency injection."""

    def __init__(
        self, story_id: str, persistence_port: Optional[IPersistencePort] = None
    ):
        """
        Initialize mood analyzer for a specific story.

        Args:
            story_id: Story identifier
            persistence_port: Persistence interface implementation (injected)
        """
        self.story_id = story_id

        # If no persistence port provided, this violates hexagonal architecture
        # The caller should always provide implementations
        if persistence_port is None:
            raise ValueError(
                "MoodAnalyzer requires a persistence_port implementation. "
                "This follows hexagonal architecture - domain should not import infrastructure."
            )
        self.persistence = persistence_port

        # Define mood categories for analysis
        self.mood_categories = {
            "positive": [
                "happy",
                "joyful",
                "excited",
                "content",
                "pleased",
                "cheerful",
                "optimistic",
            ],
            "negative": [
                "sad",
                "angry",
                "frustrated",
                "depressed",
                "melancholy",
                "anxious",
                "worried",
            ],
            "neutral": ["neutral", "calm", "focused", "thoughtful", "serious"],
            "intense": ["passionate", "determined", "fierce", "intense", "dramatic"],
        }

        # Scene type categories
        self.scene_types = {
            "dialogue": ["conversation", "discussion", "dialogue", "talking"],
            "action": ["fight", "chase", "battle", "conflict", "action"],
            "exposition": ["description", "exposition", "explanation", "narrative"],
            "emotional": ["emotional", "intimate", "personal", "relationship"],
        }

    def get_scenes_by_mood(self, mood: str) -> list[dict[str, Any]]:
        """
        Get scenes filtered by character mood.

        Args:
            mood: Mood to filter by

        Returns:
            List of scenes with the specified mood
        """
        try:
            # Query scenes with structured tags containing mood information
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output, scene_label, structured_tags,
                       LENGTH(input) as input_length,
                       LENGTH(output) as output_length
                FROM scenes
                WHERE structured_tags LIKE ?
                ORDER BY timestamp DESC
            """,
                [f'%"{mood}"%'],
            )

            results = []
            for row in rows:
                # Parse structured tags to get mood details
                mood_info = self._extract_mood_info(row.get("structured_tags"), mood)

                scene_data = {
                    "scene_id": row["scene_id"],
                    "timestamp": row["timestamp"],
                    "scene_label": row.get("scene_label"),
                    "input_preview": (
                        row["input"][:200] + "..."
                        if len(row["input"]) > 200
                        else row["input"]
                    ),
                    "output_preview": (
                        row["output"][:200] + "..."
                        if len(row["output"]) > 200
                        else row["output"]
                    ),
                    "input_length": row["input_length"],
                    "output_length": row["output_length"],
                    "mood_details": mood_info,
                }

                results.append(scene_data)

            return results

        except Exception as e:
            print(f"Error getting scenes by mood '{mood}': {e}")
            return []

    def get_scenes_by_type(self, scene_type: str) -> list[dict[str, Any]]:
        """
        Get scenes filtered by scene type.

        Args:
            scene_type: Scene type to filter by

        Returns:
            List of scenes with the specified type
        """
        try:
            # Query scenes with structured tags containing scene type information
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output, scene_label, structured_tags,
                       LENGTH(input) as input_length,
                       LENGTH(output) as output_length
                FROM scenes
                WHERE structured_tags LIKE ?
                ORDER BY timestamp DESC
            """,
                [f'%"scene_type":"{scene_type}"%'],
            )

            results = []
            for row in rows:
                scene_data = {
                    "scene_id": row["scene_id"],
                    "timestamp": row["timestamp"],
                    "scene_label": row.get("scene_label"),
                    "scene_type": scene_type,
                    "input_preview": (
                        row["input"][:200] + "..."
                        if len(row["input"]) > 200
                        else row["input"]
                    ),
                    "output_preview": (
                        row["output"][:200] + "..."
                        if len(row["output"]) > 200
                        else row["output"]
                    ),
                    "input_length": row["input_length"],
                    "output_length": row["output_length"],
                }

                # Add additional scene type analysis if available
                type_info = self._extract_scene_type_info(row.get("structured_tags"))
                if type_info:
                    scene_data["type_analysis"] = type_info

                results.append(scene_data)

            return results

        except Exception as e:
            print(f"Error getting scenes by type '{scene_type}': {e}")
            return []

    def get_character_mood_timeline(self, character_name: str) -> list[dict[str, Any]]:
        """
        Get mood timeline for a specific character.

        Args:
            character_name: Name of character to analyze

        Returns:
            List of mood data points over time
        """
        try:
            # Query scenes with character mood information
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, structured_tags
                FROM scenes
                WHERE structured_tags LIKE ?
                ORDER BY timestamp ASC
            """,
                [f'%"{character_name}"%'],
            )

            timeline = []
            for row in rows:
                mood_data = self._extract_character_mood(
                    row.get("structured_tags"), character_name
                )

                if mood_data:
                    timeline_entry = {
                        "scene_id": row["scene_id"],
                        "timestamp": row["timestamp"],
                        "character_name": character_name,
                        "mood": mood_data.get("mood", "neutral"),
                        "stability": mood_data.get("stability", 1.0),
                        "mood_category": self._categorize_mood(
                            mood_data.get("mood", "neutral")
                        ),
                    }
                    timeline.append(timeline_entry)

            # Add trend analysis
            timeline_with_trends = self._add_mood_trends(timeline)

            return timeline_with_trends

        except Exception as e:
            print(f"Error getting character mood timeline for '{character_name}': {e}")
            return []

    def get_mood_distribution(self) -> dict[str, Any]:
        """
        Get overall mood distribution across all scenes.

        Returns:
            Dictionary with mood distribution statistics
        """
        try:
            # Get all scenes with mood information
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT structured_tags
                FROM scenes
                WHERE structured_tags IS NOT NULL
            """,
            )

            mood_counts = {}
            character_mood_counts = {}
            total_scenes_with_moods = 0

            for row in rows:
                try:
                    tags = json.loads(row["structured_tags"])
                    character_moods = tags.get("character_moods", {})

                    if character_moods:
                        total_scenes_with_moods += 1

                        for char_name, mood_data in character_moods.items():
                            mood = mood_data.get("mood", "neutral")

                            # Count overall moods
                            if mood in mood_counts:
                                mood_counts[mood] += 1
                            else:
                                mood_counts[mood] = 1

                            # Count per-character moods
                            if char_name not in character_mood_counts:
                                character_mood_counts[char_name] = {}

                            if mood in character_mood_counts[char_name]:
                                character_mood_counts[char_name][mood] += 1
                            else:
                                character_mood_counts[char_name][mood] = 1

                except (json.JSONDecodeError, TypeError):
                    continue

            # Categorize moods
            categorized_moods = {}
            for category, moods in self.mood_categories.items():
                categorized_moods[category] = sum(
                    mood_counts.get(mood, 0) for mood in moods
                )

            return {
                "total_scenes_with_moods": total_scenes_with_moods,
                "mood_distribution": mood_counts,
                "mood_categories": categorized_moods,
                "character_mood_breakdown": character_mood_counts,
                "most_common_mood": (
                    max(mood_counts.items(), key=lambda x: x[1])[0]
                    if mood_counts
                    else "neutral"
                ),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"Error getting mood distribution: {e}")
            return {"error": str(e)}

    def _extract_mood_info(
        self, structured_tags: str | None, target_mood: str
    ) -> dict[str, Any]:
        """Extract mood information from structured tags."""
        if not structured_tags:
            return {}

        try:
            tags = json.loads(structured_tags)
            character_moods = tags.get("character_moods", {})

            mood_info = {"characters_with_mood": [], "mood_details": {}}

            for char_name, mood_data in character_moods.items():
                if mood_data.get("mood") == target_mood:
                    mood_info["characters_with_mood"].append(char_name)
                    mood_info["mood_details"][char_name] = mood_data

            return mood_info

        except (json.JSONDecodeError, TypeError):
            return {}

    def _extract_scene_type_info(self, structured_tags: str | None) -> dict[str, Any]:
        """Extract scene type information from structured tags."""
        if not structured_tags:
            return {}

        try:
            tags = json.loads(structured_tags)
            return {
                "scene_complexity": tags.get("scene_complexity", "medium"),
                "dialogue_ratio": tags.get("dialogue_ratio", 0.0),
                "action_density": tags.get("action_density", 0.0),
                "emotional_intensity": tags.get("emotional_intensity", 0.0),
            }

        except (json.JSONDecodeError, TypeError):
            return {}

    def _extract_character_mood(
        self, structured_tags: str | None, character_name: str
    ) -> dict[str, Any] | None:
        """Extract mood data for a specific character."""
        if not structured_tags:
            return None

        try:
            tags = json.loads(structured_tags)
            character_moods = tags.get("character_moods", {})
            return character_moods.get(character_name)

        except (json.JSONDecodeError, TypeError):
            return None

    def _categorize_mood(self, mood: str) -> str:
        """Categorize a mood into broader categories."""
        for category, moods in self.mood_categories.items():
            if mood in moods:
                return category
        return "neutral"

    def _add_mood_trends(self, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add trend analysis to mood timeline."""
        if len(timeline) < 2:
            return timeline

        for i, entry in enumerate(timeline):
            if i == 0:
                entry["trend"] = "initial"
            else:
                prev_mood = timeline[i - 1]["mood"]
                curr_mood = entry["mood"]

                if prev_mood == curr_mood:
                    entry["trend"] = "stable"
                else:
                    prev_category = self._categorize_mood(prev_mood)
                    curr_category = self._categorize_mood(curr_mood)

                    if prev_category == "negative" and curr_category == "positive":
                        entry["trend"] = "improving"
                    elif prev_category == "positive" and curr_category == "negative":
                        entry["trend"] = "declining"
                    else:
                        entry["trend"] = "changing"

        return timeline

    def get_status(self) -> str:
        """
        Get mood analyzer status.

        Returns:
            Status string
        """
        try:
            distribution = self.get_mood_distribution()
            if "error" in distribution:
                return "error"
            return f"active ({distribution['total_scenes_with_moods']} scenes with mood data)"
        except Exception:
            return "error"
