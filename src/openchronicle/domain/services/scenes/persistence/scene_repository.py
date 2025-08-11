"""
Scene Repository - Database operations for scene persistence

Handles all database operations related to scene storage:
- Scene saving and loading
- Scene querying and filtering
- Database schema management
"""

import json
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

# Database imports from parent core directory
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.openchronicle.infrastructure.persistence import (
    execute_query,
    execute_update,
    init_database,
)

# Import shared scene models
from ..shared.scene_models import SceneData, SceneFilter


class SceneRepository:
    """Handles scene data persistence and retrieval."""

    def __init__(self, story_id: str):
        """
        Initialize repository for a specific story.

        Args:
            story_id: Story identifier
        """
        self.story_id = story_id
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database for the story."""
        init_database(self.story_id)

    def save_scene(self, scene_data: SceneData) -> bool:
        """
        Save scene data to database.

        Args:
            scene_data: Scene data to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert scene data to database format
            db_data = scene_data.to_dict()

            execute_update(
                self.story_id,
                """
                INSERT OR REPLACE INTO scenes 
                (scene_id, timestamp, input, output, memory_snapshot, flags, canon_refs, 
                 analysis, scene_label, structured_tags, story_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    db_data["scene_id"],
                    db_data["timestamp"],
                    db_data["input"],
                    db_data["output"],
                    db_data["memory_snapshot"],
                    db_data["flags"],
                    db_data["canon_refs"],
                    db_data["analysis"],
                    db_data["scene_label"],
                    db_data["structured_tags"],
                    self.story_id,
                ),
            )

            return True

        except Exception as e:
            # Add logging system when available
            print(f"Error saving scene {scene_data.scene_id}: {e}")
            return False

    def load_scene(self, scene_id: str) -> Optional[SceneData]:
        """
        Load scene data by ID.

        Args:
            scene_id: Scene identifier

        Returns:
            SceneData if found, None otherwise
        """
        try:
            rows = execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output, memory_snapshot, flags, canon_refs,
                       analysis, scene_label, structured_tags
                FROM scenes
                WHERE scene_id = ?
            """,
                (scene_id,),
            )

            if not rows:
                return None

            row = rows[0]
            return self._row_to_scene_data(row)

        except Exception as e:
            print(f"Error loading scene {scene_id}: {e}")
            return None

    def list_scenes(
        self,
        limit: int = 50,
        offset: int = 0,
        scene_filter: Optional[SceneFilter] = None,
    ) -> List[SceneData]:
        """
        List scenes with optional filtering and pagination.

        Args:
            limit: Maximum number of scenes to return
            offset: Number of scenes to skip
            scene_filter: Optional filter criteria

        Returns:
            List of SceneData objects
        """
        try:
            # Build query with optional filtering
            base_query = """
                SELECT scene_id, timestamp, input, output, memory_snapshot, flags, canon_refs,
                       analysis, scene_label, structured_tags
                FROM scenes
                WHERE story_id = ?
            """

            params = [self.story_id]

            # Add filter conditions if provided
            if scene_filter:
                where_clause, filter_params = scene_filter.to_where_clause()
                if where_clause:
                    base_query += f" AND {where_clause}"
                    params.extend(filter_params)

            # Add ordering and pagination
            base_query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = execute_query(self.story_id, base_query, params)

            return [self._row_to_scene_data(row) for row in rows]

        except Exception as e:
            print(f"Error listing scenes: {e}")
            return []

    def count_scenes(self, scene_filter: Optional[SceneFilter] = None) -> int:
        """
        Count total scenes with optional filtering.

        Args:
            scene_filter: Optional filter criteria

        Returns:
            Total number of scenes matching criteria
        """
        try:
            base_query = "SELECT COUNT(*) as count FROM scenes WHERE story_id = ?"
            params = [self.story_id]

            # Add filter conditions if provided
            if scene_filter:
                where_clause, filter_params = scene_filter.to_where_clause()
                if where_clause:
                    base_query += f" AND {where_clause}"
                    params.extend(filter_params)

            rows = execute_query(self.story_id, base_query, params)
            return rows[0]["count"] if rows else 0

        except Exception as e:
            print(f"Error counting scenes: {e}")
            return 0

    def delete_scene(self, scene_id: str) -> bool:
        """
        Delete a scene by ID.

        Args:
            scene_id: Scene identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            execute_update(
                self.story_id,
                """
                DELETE FROM scenes WHERE scene_id = ? AND story_id = ?
            """,
                (scene_id, self.story_id),
            )

            return True

        except Exception as e:
            print(f"Error deleting scene {scene_id}: {e}")
            return False

    def update_scene_label(self, scene_id: str, scene_label: str) -> bool:
        """
        Update scene label.

        Args:
            scene_id: Scene identifier
            scene_label: New label

        Returns:
            True if successful, False otherwise
        """
        try:
            execute_update(
                self.story_id,
                """
                UPDATE scenes SET scene_label = ? WHERE scene_id = ? AND story_id = ?
            """,
                (scene_label, scene_id, self.story_id),
            )

            return True

        except Exception as e:
            print(f"Error updating scene label for {scene_id}: {e}")
            return False

    def _row_to_scene_data(self, row) -> SceneData:
        """
        Convert database row to SceneData object.

        Args:
            row: Database row (sqlite3.Row or dict)

        Returns:
            SceneData object
        """
        # Convert sqlite3.Row to dict if needed
        if hasattr(row, "keys"):
            row_dict = dict(row)
        else:
            row_dict = row

        # Parse JSON fields
        memory_snapshot = json.loads(row_dict.get("memory_snapshot", "{}"))
        flags = json.loads(row_dict.get("flags", "[]"))
        context_refs = json.loads(row_dict.get("canon_refs", "[]"))
        analysis_data = (
            json.loads(row_dict.get("analysis", "null"))
            if row_dict.get("analysis")
            else None
        )

        return SceneData(
            scene_id=row_dict["scene_id"],
            timestamp=row_dict["timestamp"],
            user_input=row_dict["input"],
            model_output=row_dict["output"],
            memory_snapshot=memory_snapshot,
            flags=flags,
            context_refs=context_refs,
            analysis_data=analysis_data,
            scene_label=row_dict.get("scene_label"),
            model_name=None,  # Not stored in current schema
            structured_tags=None,  # Will be rebuilt from data
        )

    def get_status(self) -> str:
        """
        Get repository status.

        Returns:
            Status string
        """
        try:
            count = self.count_scenes()
            return f"active ({count} scenes)"
        except Exception:
            return "error"
