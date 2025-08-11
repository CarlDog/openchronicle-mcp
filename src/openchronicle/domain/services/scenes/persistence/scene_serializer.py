"""
Scene Serializer - Handles scene data serialization and deserialization

Provides consistent serialization for scene data across different contexts:
- API response formatting
- Database storage formatting
- Export/import operations
"""

from datetime import datetime
from typing import Any

from ..shared.scene_models import SceneData


class SceneSerializer:
    """Handles scene data serialization and transformation."""

    def __init__(self):
        """Initialize the serializer."""

    def serialize_scene_for_output(self, scene_data: SceneData) -> dict[str, Any]:
        """
        Serialize scene data for API output/backward compatibility.

        Args:
            scene_data: Scene data to serialize

        Returns:
            Dictionary formatted for legacy API compatibility
        """
        return {
            "scene_id": scene_data.scene_id,
            "timestamp": scene_data.timestamp,
            "input": scene_data.user_input,
            "output": scene_data.model_output,
            "memory_snapshot": scene_data.memory_snapshot,
            "flags": scene_data.flags,
            "canon_refs": scene_data.context_refs,
            "analysis": scene_data.analysis_data,
            "scene_label": scene_data.scene_label,
            "structured_tags": (
                scene_data.structured_tags.get_tags()
                if scene_data.structured_tags
                else {}
            ),
        }

    def serialize_scene_summary(self, scene_data: SceneData) -> dict[str, Any]:
        """
        Serialize scene data for summary views (minimal data).

        Args:
            scene_data: Scene data to serialize

        Returns:
            Dictionary with summary information
        """
        return {
            "scene_id": scene_data.scene_id,
            "timestamp": scene_data.timestamp,
            "scene_label": scene_data.scene_label,
            "input_preview": (
                scene_data.user_input[:100] + "..."
                if len(scene_data.user_input) > 100
                else scene_data.user_input
            ),
            "output_preview": (
                scene_data.model_output[:100] + "..."
                if len(scene_data.model_output) > 100
                else scene_data.model_output
            ),
            "character_count": len(scene_data.memory_snapshot.get("characters", {})),
            "flags_count": len(scene_data.flags),
            "has_analysis": scene_data.analysis_data is not None,
        }

    def serialize_scenes_list(
        self, scenes: list[SceneData], summary: bool = False
    ) -> list[dict[str, Any]]:
        """
        Serialize a list of scenes.

        Args:
            scenes: List of scene data
            summary: If True, use summary format, otherwise full format

        Returns:
            List of serialized scene dictionaries
        """
        if summary:
            return [self.serialize_scene_summary(scene) for scene in scenes]
        return [self.serialize_scene_for_output(scene) for scene in scenes]

    def serialize_for_export(self, scenes: list[SceneData]) -> dict[str, Any]:
        """
        Serialize scenes for export/backup purposes.

        Args:
            scenes: List of scene data

        Returns:
            Export-formatted dictionary
        """
        return {
            "export_metadata": {
                "export_time": datetime.utcnow().isoformat(),
                "scene_count": len(scenes),
                "format_version": "1.0",
            },
            "scenes": [self.serialize_scene_for_output(scene) for scene in scenes],
        }

    def deserialize_from_export(self, export_data: dict[str, Any]) -> list[SceneData]:
        """
        Deserialize scenes from export data.

        Args:
            export_data: Export-formatted dictionary

        Returns:
            List of SceneData objects
        """
        scenes = []

        for scene_dict in export_data.get("scenes", []):
            try:
                scene_data = SceneData(
                    scene_id=scene_dict["scene_id"],
                    timestamp=scene_dict["timestamp"],
                    user_input=scene_dict["input"],
                    model_output=scene_dict["output"],
                    memory_snapshot=scene_dict.get("memory_snapshot", {}),
                    flags=scene_dict.get("flags", []),
                    context_refs=scene_dict.get("canon_refs", []),
                    analysis_data=scene_dict.get("analysis"),
                    scene_label=scene_dict.get("scene_label"),
                    model_name=scene_dict.get("model_name"),
                )
                scenes.append(scene_data)
            except Exception as e:
                # Log error but continue processing other scenes
                print(
                    f"Error deserializing scene {scene_dict.get('scene_id', 'unknown')}: {e}"
                )
                continue

        return scenes

    def serialize_scene_metadata(self, scene_data: SceneData) -> dict[str, Any]:
        """
        Extract just the metadata from a scene.

        Args:
            scene_data: Scene data

        Returns:
            Metadata dictionary
        """
        metadata = {
            "scene_id": scene_data.scene_id,
            "timestamp": scene_data.timestamp,
            "scene_label": scene_data.scene_label,
            "input_length": len(scene_data.user_input),
            "output_length": len(scene_data.model_output),
            "flags_count": len(scene_data.flags),
            "context_refs_count": len(scene_data.context_refs),
            "has_analysis": scene_data.analysis_data is not None,
        }

        # Add structured tags if available
        if scene_data.structured_tags:
            metadata["structured_tags"] = scene_data.structured_tags.get_tags()

        return metadata
