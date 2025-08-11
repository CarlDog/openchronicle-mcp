"""
Scene Models - Data structures for scene systems

Provides standardized data models for scene operations:
- Scene data representation
- Structured tags handling
- Scene metadata management
"""

import json
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from typing import Any


@dataclass
class StructuredTags:
    """Handles structured metadata tags for scenes."""

    def __init__(self, base_tags: dict[str, Any] = None, token_manager: Any = None):
        """Initialize structured tags with optional token tracking."""
        self.tags = base_tags or {}
        self._add_token_information(token_manager)
        self._add_scene_metadata()

    def _add_token_information(self, token_manager: Any) -> None:
        """Add token tracking information if token manager provided."""
        if token_manager and hasattr(token_manager, "get_current_usage"):
            try:
                usage = token_manager.get_current_usage()
                self.tags.update(
                    {
                        "tokens_used": usage.get("tokens_used", 0),
                        "model_used": usage.get("model", "unknown"),
                        "token_cost": usage.get("cost", 0.0),
                        "generation_time": usage.get("generation_time", 0.0),
                    }
                )
            except Exception:
                # If token manager fails, continue without token info
                pass

    def _add_scene_metadata(self) -> None:
        """Add basic scene metadata."""
        if "timestamp" not in self.tags:
            self.tags["timestamp"] = datetime.now(UTC).isoformat()

    def add_character_moods(self, memory_snapshot: dict[str, Any]) -> None:
        """Extract and add character mood information."""
        if memory_snapshot and "characters" in memory_snapshot:
            character_moods = {}
            for char_name, char_data in memory_snapshot["characters"].items():
                mood_state = char_data.get("mood_state", {})
                if mood_state:
                    character_moods[char_name] = {
                        "mood": mood_state.get("current_mood", "neutral"),
                        "stability": mood_state.get("mood_stability", 1.0),
                    }

            if character_moods:
                self.tags["character_moods"] = character_moods

    def add_scene_analysis(self, analysis_data: dict[str, Any]) -> None:
        """Add content analysis information."""
        if analysis_data:
            self.tags.update(
                {
                    "scene_complexity": analysis_data.get("complexity", "medium"),
                    "dialogue_ratio": analysis_data.get("dialogue_ratio", 0.0),
                    "action_density": analysis_data.get("action_density", 0.0),
                    "emotional_intensity": analysis_data.get(
                        "emotional_intensity", 0.0
                    ),
                }
            )

    def get_tags(self) -> dict[str, Any]:
        """Get all structured tags."""
        return self.tags.copy()

    def to_json(self) -> str:
        """Serialize tags to JSON string."""
        return json.dumps(self.tags)


@dataclass
class SceneData:
    """Complete scene data structure."""

    scene_id: str
    timestamp: str
    user_input: str
    model_output: str
    memory_snapshot: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)
    analysis_data: dict[str, Any] | None = None
    scene_label: str | None = None
    model_name: str | None = None
    structured_tags: StructuredTags | None = None

    def __post_init__(self):
        """Post-initialization processing."""
        if self.structured_tags is None:
            self.structured_tags = StructuredTags()

        # Add derived metadata
        self.structured_tags.tags.update(
            {
                "scene_id": self.scene_id,
                "timestamp": self.timestamp,
                "input_length": len(self.user_input),
                "output_length": len(self.model_output),
                "memory_flags_count": len(self.flags),
                "canon_refs_count": len(self.context_refs),
            }
        )

        # Add character moods if available
        self.structured_tags.add_character_moods(self.memory_snapshot)

        # Add analysis data if available
        if self.analysis_data:
            self.structured_tags.add_scene_analysis(self.analysis_data)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scene_id": self.scene_id,
            "timestamp": self.timestamp,
            "input": self.user_input,
            "output": self.model_output,
            "memory_snapshot": json.dumps(self.memory_snapshot),
            "flags": json.dumps(self.flags),
            "canon_refs": json.dumps(self.context_refs),
            "analysis": json.dumps(self.analysis_data) if self.analysis_data else None,
            "scene_label": self.scene_label,
            "model_name": self.model_name,
            "structured_tags": self.structured_tags.to_json(),
        }


@dataclass
class Scene:
    """Simplified scene representation for API responses."""

    scene_id: str
    timestamp: str
    input: str
    output: str
    scene_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_scene_data(cls, scene_data: SceneData) -> "Scene":
        """Create Scene from SceneData."""
        return cls(
            scene_id=scene_data.scene_id,
            timestamp=scene_data.timestamp,
            input=scene_data.user_input,
            output=scene_data.model_output,
            scene_label=scene_data.scene_label,
            metadata=(
                scene_data.structured_tags.get_tags()
                if scene_data.structured_tags
                else {}
            ),
        )


@dataclass
class SceneFilter:
    """Filter criteria for scene queries."""

    mood: str | None = None
    scene_type: str | None = None
    scene_label: str | None = None
    character_name: str | None = None
    date_range: tuple | None = None
    token_range: tuple | None = None
    has_analysis: bool | None = None

    def to_where_clause(self) -> tuple:
        """Convert filter to SQL WHERE clause."""
        conditions = []
        params = []

        if self.mood:
            conditions.append(
                "JSON_EXTRACT(structured_tags, '$.character_moods') LIKE ?"
            )
            params.append(f'%"{self.mood}"%')

        if self.scene_type:
            conditions.append("JSON_EXTRACT(structured_tags, '$.scene_type') = ?")
            params.append(self.scene_type)

        if self.scene_label:
            conditions.append("scene_label = ?")
            params.append(self.scene_label)

        if self.character_name:
            conditions.append(
                "JSON_EXTRACT(structured_tags, '$.character_moods') LIKE ?"
            )
            params.append(f'%"{self.character_name}"%')

        if self.has_analysis is not None:
            if self.has_analysis:
                conditions.append("analysis IS NOT NULL")
            else:
                conditions.append("analysis IS NULL")

        where_clause = " AND ".join(conditions) if conditions else ""
        return where_clause, params
