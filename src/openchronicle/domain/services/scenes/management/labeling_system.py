"""
Labeling System - Scene labeling and organization

Handles scene labeling operations:
- Scene label management
- Label-based scene querying
- Label organization and validation
"""

import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

# Database imports from parent core directory
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.openchronicle.infrastructure.persistence import execute_query, execute_update

from ..persistence.scene_repository import SceneRepository


class LabelingSystem:
    """Manages scene labeling and organization."""

    def __init__(self, story_id: str, repository: SceneRepository):
        """
        Initialize labeling system.

        Args:
            story_id: Story identifier
            repository: Scene repository instance
        """
        self.story_id = story_id
        self.repository = repository

    def update_scene_label(self, scene_id: str, scene_label: str) -> bool:
        """
        Update label for a specific scene.

        Args:
            scene_id: Scene identifier
            scene_label: New label for the scene

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate label (basic validation)
            if not scene_label or not scene_label.strip():
                print(f"Invalid label provided for scene {scene_id}")
                return False

            # Clean and normalize label
            normalized_label = scene_label.strip()

            # Update through repository
            success = self.repository.update_scene_label(scene_id, normalized_label)

            if success:
                print(f"Scene {scene_id} labeled as '{normalized_label}'")

            return success

        except Exception as e:
            print(f"Error updating scene label for {scene_id}: {e}")
            return False

    def get_scenes_by_label(self, scene_label: str) -> List[Dict[str, Any]]:
        """
        Get all scenes with a specific label.

        Args:
            scene_label: Label to filter by

        Returns:
            List of scenes with the specified label
        """
        try:
            rows = execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output, scene_label,
                       LENGTH(input) as input_length,
                       LENGTH(output) as output_length
                FROM scenes
                WHERE scene_label = ? AND story_id = ?
                ORDER BY timestamp ASC
            """,
                (scene_label, self.story_id),
            )

            results = []
            for row in rows:
                scene_data = {
                    "scene_id": row["scene_id"],
                    "timestamp": row["timestamp"],
                    "scene_label": row["scene_label"],
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
                    "total_length": row["input_length"] + row["output_length"],
                }
                results.append(scene_data)

            return results

        except Exception as e:
            print(f"Error getting scenes by label '{scene_label}': {e}")
            return []

    def get_labeled_scenes(self) -> List[Dict[str, Any]]:
        """
        Get all scenes that have labels.

        Returns:
            List of all labeled scenes
        """
        try:
            rows = execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, scene_label,
                       LENGTH(input) as input_length,
                       LENGTH(output) as output_length,
                       input, output
                FROM scenes
                WHERE scene_label IS NOT NULL AND scene_label != ''
                ORDER BY scene_label ASC, timestamp ASC
            """,
            )

            results = []
            for row in rows:
                scene_data = {
                    "scene_id": row["scene_id"],
                    "timestamp": row["timestamp"],
                    "scene_label": row["scene_label"],
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
                    "total_length": row["input_length"] + row["output_length"],
                }
                results.append(scene_data)

            return results

        except Exception as e:
            print(f"Error getting labeled scenes: {e}")
            return []

    def get_label_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about scene labels.

        Returns:
            Dictionary with label statistics
        """
        try:
            # Get label distribution
            label_counts = execute_query(
                self.story_id,
                """
                SELECT scene_label, COUNT(*) as count
                FROM scenes
                WHERE scene_label IS NOT NULL AND scene_label != ''
                GROUP BY scene_label
                ORDER BY count DESC
            """,
            )

            # Get total scenes and labeled scenes count
            total_stats = execute_query(
                self.story_id,
                """
                SELECT 
                    COUNT(*) as total_scenes,
                    COUNT(scene_label) as labeled_scenes
                FROM scenes
            """,
            )[0]

            # Calculate percentages and additional metrics
            total_scenes = total_stats["total_scenes"]
            labeled_scenes = total_stats["labeled_scenes"]
            unlabeled_scenes = total_scenes - labeled_scenes

            label_distribution = {}
            for row in label_counts:
                label_distribution[row["scene_label"]] = row["count"]

            return {
                "total_scenes": total_scenes,
                "labeled_scenes": labeled_scenes,
                "unlabeled_scenes": unlabeled_scenes,
                "labeling_percentage": (
                    round((labeled_scenes / total_scenes) * 100, 1)
                    if total_scenes > 0
                    else 0
                ),
                "unique_labels": len(label_counts),
                "label_distribution": label_distribution,
                "most_used_label": (
                    label_counts[0]["scene_label"] if label_counts else None
                ),
                "average_scenes_per_label": (
                    round(labeled_scenes / len(label_counts), 1) if label_counts else 0
                ),
            }

        except Exception as e:
            print(f"Error getting label statistics: {e}")
            return {"error": str(e)}

    def suggest_labels(self, scene_id: str) -> List[str]:
        """
        Suggest labels for a scene based on content analysis.

        Args:
            scene_id: Scene ID to suggest labels for

        Returns:
            List of suggested labels
        """
        try:
            # Load scene content
            scene_data = self.repository.load_scene(scene_id)
            if not scene_data:
                return []

            suggestions = []

            # Simple keyword-based suggestions (could be enhanced with ML)
            content = (scene_data.user_input + " " + scene_data.model_output).lower()

            # Common scene type keywords
            if any(word in content for word in ["fight", "battle", "attack", "combat"]):
                suggestions.append("action")

            if any(
                word in content
                for word in ["talk", "conversation", "discuss", "say", "speak"]
            ):
                suggestions.append("dialogue")

            if any(
                word in content for word in ["love", "kiss", "romantic", "intimate"]
            ):
                suggestions.append("romance")

            if any(
                word in content for word in ["mystery", "secret", "hidden", "discover"]
            ):
                suggestions.append("mystery")

            if any(word in content for word in ["travel", "journey", "move", "walk"]):
                suggestions.append("travel")

            if any(word in content for word in ["emotional", "cry", "sad", "tears"]):
                suggestions.append("emotional")

            # Check existing labels for pattern matching
            existing_labels = execute_query(
                self.story_id,
                """
                SELECT DISTINCT scene_label
                FROM scenes
                WHERE scene_label IS NOT NULL AND scene_label != ''
            """,
            )

            # Add existing labels that might be relevant (simple matching)
            for label_row in existing_labels:
                label = label_row["scene_label"].lower()
                if any(word in content for word in label.split()):
                    if label not in [s.lower() for s in suggestions]:
                        suggestions.append(label_row["scene_label"])

            # Limit to top 5 suggestions
            return suggestions[:5]

        except Exception as e:
            print(f"Error suggesting labels for scene {scene_id}: {e}")
            return []

    def rename_label(self, old_label: str, new_label: str) -> Dict[str, Any]:
        """
        Rename all occurrences of a label.

        Args:
            old_label: Current label name
            new_label: New label name

        Returns:
            Dictionary with rename operation results
        """
        try:
            # Check if new label already exists
            existing = execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as count
                FROM scenes
                WHERE scene_label = ?
            """,
                (new_label,),
            )[0]["count"]

            if existing > 0:
                return {
                    "success": False,
                    "error": f"Label '{new_label}' already exists on {existing} scenes",
                }

            # Get scenes with old label
            old_scenes = execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as count
                FROM scenes
                WHERE scene_label = ?
            """,
                (old_label,),
            )[0]["count"]

            if old_scenes == 0:
                return {"success": False, "error": f"Label '{old_label}' not found"}

            # Perform the rename
            execute_update(
                self.story_id,
                """
                UPDATE scenes
                SET scene_label = ?
                WHERE scene_label = ?
            """,
                (new_label, old_label),
            )

            return {
                "success": True,
                "scenes_updated": old_scenes,
                "old_label": old_label,
                "new_label": new_label,
            }

        except Exception as e:
            return {"success": False, "error": f"Error renaming label: {e}"}

    def delete_label(self, label: str) -> Dict[str, Any]:
        """
        Remove label from all scenes (set to NULL).

        Args:
            label: Label to remove

        Returns:
            Dictionary with deletion results
        """
        try:
            # Get count of scenes with this label
            scene_count = execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as count
                FROM scenes
                WHERE scene_label = ?
            """,
                (label,),
            )[0]["count"]

            if scene_count == 0:
                return {"success": False, "error": f"Label '{label}' not found"}

            # Remove the label
            execute_update(
                self.story_id,
                """
                UPDATE scenes
                SET scene_label = NULL
                WHERE scene_label = ?
            """,
                (label,),
            )

            return {
                "success": True,
                "scenes_updated": scene_count,
                "label_removed": label,
            }

        except Exception as e:
            return {"success": False, "error": f"Error deleting label: {e}"}

    def get_status(self) -> str:
        """
        Get labeling system status.

        Returns:
            Status string
        """
        try:
            stats = self.get_label_statistics()
            if "error" in stats:
                return "error"

            return f"active ({stats['labeled_scenes']}/{stats['total_scenes']} scenes labeled, {stats['unique_labels']} unique labels)"
        except Exception:
            return "error"
