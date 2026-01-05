"""
Scene Manager - Scene lifecycle and state management

Handles scene management operations:
- Scene rollback functionality
- Scene state management
- Scene lifecycle operations
- Integration with rollback systems

This manager now uses dependency injection following hexagonal architecture principles.
"""

from typing import Any
from typing import Optional

from openchronicle.domain.errors.persistence_errors import RollbackSceneError

# Import domain interfaces (following dependency inversion principle)
from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.shared.logging_system import log_error  # Lightweight logging (Band-Aid removal: replace prints)
from openchronicle.shared.logging_system import log_info  # Lightweight logging (Band-Aid removal: replace prints)
from openchronicle.shared.logging_system import log_warning  # Lightweight logging (Band-Aid removal: replace prints)

from ..persistence.scene_repository import SceneRepository


class SceneManager:
    """Manages scene lifecycle and state operations using dependency injection."""

    def __init__(
        self,
        story_id: str,
        repository: SceneRepository,
        persistence_port: Optional[IPersistencePort] = None,
    ):
        """
        Initialize scene manager.

        Args:
            story_id: Story identifier
            repository: Scene repository instance
            persistence_port: Persistence interface implementation (injected)
        """
        self.story_id = story_id
        self.repository = repository

        # If no persistence port provided, this violates hexagonal architecture
        # The caller should always provide implementations
        if persistence_port is None:
            raise ValueError(
                "SceneManager requires a persistence_port implementation. "
                "This follows hexagonal architecture - domain should not import infrastructure."
            )
        self.persistence = persistence_port

    def rollback_to_scene(self, scene_id: str) -> bool:
        """
        Rollback to a specific scene by removing all scenes after it.

        Args:
            scene_id: Scene ID to rollback to

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, verify the target scene exists
            target_scene = self.repository.load_scene(scene_id)
            if not target_scene:
                log_warning(
                    f"Target scene {scene_id} not found",
                    story_id=self.story_id,
                    scene_id=scene_id,
                    context_tags=["scene", "rollback", "not_found"],
                )
                return False

            # Get the timestamp of the target scene
            target_timestamp = target_scene.timestamp

            # Get all scenes after the target scene for backup
            scenes_to_remove = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp
                FROM scenes
                WHERE timestamp > ? AND story_id = ?
                ORDER BY timestamp ASC
            """,
                [target_timestamp, self.story_id],
            )

            if not scenes_to_remove:
                log_info(
                    f"No scenes to rollback after {scene_id}",
                    story_id=self.story_id,
                    scene_id=scene_id,
                    context_tags=["scene", "rollback", "no_op"],
                )
                return True  # Nothing to rollback, but operation successful

            # Backup scenes before deletion (optional - could be enhanced)
            backup_info = {
                "rollback_timestamp": target_timestamp,
                "scenes_removed": len(scenes_to_remove),
                "scene_ids": [scene["scene_id"] for scene in scenes_to_remove],
            }

            # Delete scenes after the target scene
            success = self.persistence.execute_update(
                self.story_id,
                """
                DELETE FROM scenes
                WHERE timestamp > ? AND story_id = ?
            """,
                [target_timestamp, self.story_id],
            )

            log_info(
                f"Rollback successful: removed {len(scenes_to_remove)} scenes after {scene_id}",
                story_id=self.story_id,
                scene_id=scene_id,
                context_tags=["scene", "rollback", "success"],
            )

        except (RuntimeError, ValueError, KeyError, TypeError) as e:  # narrowed
            log_error(
                f"Error rolling back to scene {scene_id}: {e}",
                story_id=self.story_id,
                scene_id=scene_id,
                context_tags=["scene", "rollback", "error"],
            )
            raise RollbackSceneError(str(e)) from e
        else:
            return True

    def get_rollback_preview(self, scene_id: str) -> dict[str, Any]:
        """
        Preview what would be affected by rolling back to a scene.

        Args:
            scene_id: Scene ID to preview rollback for

        Returns:
            Dictionary with rollback preview information
        """
        try:
            # Get target scene
            target_scene = self.repository.load_scene(scene_id)
            if not target_scene:
                return {"error": f"Scene {scene_id} not found"}

            target_timestamp = target_scene.timestamp

            # Get scenes that would be removed
            scenes_to_remove = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, scene_label,
                       LENGTH(input) as input_length,
                       LENGTH(output) as output_length
                FROM scenes
                WHERE timestamp > ? AND story_id = ?
                ORDER BY timestamp ASC
            """,
                (target_timestamp, self.story_id),
            )

            return {
                "target_scene_id": scene_id,
                "target_timestamp": target_timestamp,
                "scenes_to_remove": len(scenes_to_remove),
                "affected_scenes": [
                    {
                        "scene_id": scene["scene_id"],
                        "timestamp": scene["timestamp"],
                        "scene_label": scene.get("scene_label"),
                        "content_length": scene["input_length"] + scene["output_length"],
                    }
                    for scene in scenes_to_remove
                ],
                "warning": f"This will permanently delete {len(scenes_to_remove)} scenes "
                f"created after the target scene.",
            }

        except (RuntimeError, ValueError, KeyError, TypeError) as e:
            return {"error": f"Error previewing rollback: {e}"}

    def validate_scene_integrity(self) -> dict[str, Any]:
        """
        Validate scene data integrity.

        Returns:
            Dictionary with integrity check results
        """
        try:
            # Check for scenes with missing required data
            issues = []

            # Check for scenes without input/output
            empty_scenes = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp
                FROM scenes
                WHERE (input IS NULL OR input = '') OR (output IS NULL OR output = '')
            """,
            )

            if empty_scenes:
                issues.append(
                    {
                        "type": "empty_content",
                        "count": len(empty_scenes),
                        "scenes": [scene["scene_id"] for scene in empty_scenes[:5]],  # Show first 5
                        "description": "Scenes with missing input or output content",
                    }
                )

            # Check for scenes with invalid timestamps
            invalid_timestamps = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp
                FROM scenes
                WHERE timestamp IS NULL OR timestamp = ''
            """,
            )

            if invalid_timestamps:
                issues.append(
                    {
                        "type": "invalid_timestamps",
                        "count": len(invalid_timestamps),
                        "scenes": [scene["scene_id"] for scene in invalid_timestamps[:5]],
                        "description": "Scenes with missing or invalid timestamps",
                    }
                )

            # Check for duplicate scene IDs (shouldn't happen but good to check)
            duplicates = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, COUNT(*) as count
                FROM scenes
                GROUP BY scene_id
                HAVING COUNT(*) > 1
            """,
            )

            if duplicates:
                issues.append(
                    {
                        "type": "duplicate_scene_ids",
                        "count": len(duplicates),
                        "scenes": [dup["scene_id"] for dup in duplicates],
                        "description": "Duplicate scene IDs found",
                    }
                )

            # Get total scene count for context
            total_scenes = self.persistence.execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as count FROM scenes
            """,
            )[0]["count"]

            return {
                "total_scenes": total_scenes,
                "issues_found": len(issues),
                "issues": issues,
                "status": "healthy" if not issues else "issues_detected",
            }

        except (RuntimeError, ValueError, KeyError, TypeError) as e:
            return {"error": f"Error validating scene integrity: {e}"}

    def compact_scene_data(self) -> dict[str, Any]:
        """
        Compact scene data by removing redundant information (placeholder for future optimization).

        Returns:
            Dictionary with compaction results
        """
        try:
            # For now, just return statistics about potential compaction
            # Future versions could implement actual data compaction

            total_scenes = self.persistence.execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as count FROM scenes
            """,
            )[0]["count"]

            # Estimate potential savings (placeholder logic)

        except (RuntimeError, ValueError, KeyError, TypeError) as e:
            return {"error": f"Error analyzing scene data for compaction: {e}"}
        else:
            return {
                "total_scenes": total_scenes,
                "compaction_performed": False,
                "note": "Scene data compaction is not yet implemented",
                "recommendation": "Scene data is already efficiently stored",
            }

    def get_scene_dependencies(self, scene_id: str) -> dict[str, Any]:
        """
        Get dependencies for a specific scene (scenes that reference it).

        Args:
            scene_id: Scene ID to check dependencies for

        Returns:
            Dictionary with dependency information
        """
        try:
            # Check for scenes that might reference this scene in their content
            # This is a simplified check - could be enhanced with more sophisticated analysis

            referencing_scenes = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, scene_label
                FROM scenes
                WHERE (input LIKE ? OR output LIKE ?) AND scene_id != ?
            """,
                (f"%{scene_id}%", f"%{scene_id}%", scene_id),
            )

            # Check if this scene is referenced in bookmarks (if bookmark table exists)
            try:
                bookmark_references = self.persistence.execute_query(
                    self.story_id,
                    """
                    SELECT bookmark_id, label
                    FROM bookmarks
                    WHERE scene_id = ?
                """,
                    [scene_id],
                )
            except (RuntimeError, ValueError, KeyError, TypeError):
                bookmark_references = []  # Table might not exist

            return {
                "scene_id": scene_id,
                "content_references": len(referencing_scenes),
                "bookmark_references": len(bookmark_references),
                "referencing_scenes": [
                    {
                        "scene_id": scene["scene_id"],
                        "timestamp": scene["timestamp"],
                        "scene_label": scene.get("scene_label"),
                    }
                    for scene in referencing_scenes
                ],
                "bookmarks": [{"bookmark_id": bm["bookmark_id"], "label": bm["label"]} for bm in bookmark_references],
                "has_dependencies": len(referencing_scenes) > 0 or len(bookmark_references) > 0,
            }

        except (RuntimeError, ValueError, KeyError, TypeError) as e:
            return {"error": f"Error checking scene dependencies: {e}"}

    def get_status(self) -> str:
        """
        Get scene manager status.

        Returns:
            Status string
        """
        try:
            integrity = self.validate_scene_integrity()
            if "error" in integrity:
                return "error"

            if integrity["issues_found"] > 0:
                return f"warning ({integrity['issues_found']} issues detected)"
            return f"healthy ({integrity['total_scenes']} scenes)"
        except (RuntimeError, ValueError, KeyError, TypeError):
            return "error"
