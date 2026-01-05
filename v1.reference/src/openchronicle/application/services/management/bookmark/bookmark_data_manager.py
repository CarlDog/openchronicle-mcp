"""
Bookmark Management - Core Bookmark Handler

Extracted from bookmark_manager.py
Handles bookmark CRUD operations and data management.
"""

import json
import sqlite3
import sys
from datetime import datetime
from typing import Any, TYPE_CHECKING

from openchronicle.shared.logging_system import log_system_event
from openchronicle.shared.logging_system import log_warning

from ..shared import BookmarkManagerException
from ..shared import BookmarkRecord
from ..shared import BookmarkType

if TYPE_CHECKING:
    from openchronicle.domain.ports.persistence_port import IPersistencePort


class BookmarkDataManager:
    """Handles core bookmark data operations."""

    def __init__(self, story_id: str, persistence_port: "IPersistencePort | None" = None):
        self.story_id = story_id
        self.persistence_port = persistence_port

        # Initialize persistence interface
        if self.persistence_port is not None:
            # Use injected port - set up wrapper methods for compatibility
            self.execute_query = self._execute_query_wrapper
            self.execute_insert = self._execute_insert_wrapper
            self.execute_update = self._execute_update_wrapper
            self.init_database = self._init_database_wrapper
            self.init_database(story_id)
        else:
            # Fallback for backward compatibility and testing
            self._setup_mock_persistence()

    def _setup_mock_persistence(self):
        """Set up mock persistence methods for testing."""
        # For backward compatibility, we still set these attributes
        # but the actual logic will use the wrapper methods
        self.execute_query = self._execute_query_wrapper
        self.execute_insert = self._execute_insert_wrapper
        self.execute_update = self._execute_update_wrapper
        self.init_database = self._init_database_wrapper

    def _execute_query_wrapper(self, story_id: str, query: str, params=None):
        """Wrapper for execute_query that uses persistence port or mock."""
        if self.persistence_port:
            return self.persistence_port.execute_query(story_id, query, params)
        else:
            return self._mock_execute_query(story_id, query, params)

    def _execute_insert_wrapper(self, story_id: str, query: str, params=None):
        """Wrapper for execute_insert that uses persistence port or mock."""
        if self.persistence_port:
            # For inserts, we use execute_update from the port
            success = self.persistence_port.execute_update(story_id, query, params)
            if success:
                # Return a mock ID for compatibility
                import random
                return f"bookmark_{random.randint(1000, 9999)}"
            return None
        else:
            return self._mock_execute_insert(story_id, query, params)

    def _execute_update_wrapper(self, story_id: str, query: str, params=None):
        """Wrapper for execute_update that uses persistence port or mock."""
        if self.persistence_port:
            return self.persistence_port.execute_update(story_id, query, params)
        else:
            return self._mock_execute_update(story_id, query, params)

    def _init_database_wrapper(self, story_id: str):
        """Wrapper for init_database that uses persistence port or mock."""
        if self.persistence_port:
            return self.persistence_port.init_database(story_id)
        else:
            return self._mock_init_database(story_id)

    def _mock_execute_query(self, *args, **kwargs):
        """Mock query function for testing."""
        return []

    def _mock_execute_insert(self, *args, **kwargs):
        """Mock insert function for testing."""
        import random

        return f"bookmark_{random.randint(1000, 9999)}"  # Return string ID for testing

    def _mock_execute_update(self, *args, **kwargs):
        """Mock update function for testing."""
        return True

    def _mock_init_database(self, *args, **kwargs):
        """Mock database init for testing."""
        return True

    def create_bookmark(
        self,
        scene_id: str,
        label: str,
        description: str | None = None,
        bookmark_type: BookmarkType = BookmarkType.USER,
        metadata: dict[str, Any] | None = None,
    ) -> int | str:
        """Create a new bookmark."""
        try:
            # Validate bookmark type
            if not isinstance(bookmark_type, BookmarkType):
                bookmark_type = BookmarkType(bookmark_type)

            # Check for duplicate bookmarks (same scene + label)
            existing = self.execute_query(
                self.story_id,
                """
                SELECT id FROM bookmarks WHERE scene_id = ? AND label = ?
            """,
                (scene_id, label),
            )

            if existing:
                raise BookmarkManagerException(
                    f"Bookmark with label '{label}' already exists for scene {scene_id}"
                )

            # Create the bookmark
            metadata_json = json.dumps(metadata or {})

            cursor = self.execute_insert(
                self.story_id,
                """
                INSERT INTO bookmarks (story_id, scene_id, label, description, bookmark_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    self.story_id,
                    scene_id,
                    label,
                    description,
                    bookmark_type.value,
                    metadata_json,
                ),
            )

            if cursor is None:
                raise BookmarkManagerException("Failed to create bookmark")

            log_system_event(
                "bookmark_created",
                f"Created {bookmark_type.value} bookmark '{label}' for scene {scene_id}",
            )

            return cursor

        except (sqlite3.Error, sqlite3.DatabaseError) as e:
            log_warning(f"Database error creating bookmark: {e}")
            raise BookmarkManagerException(f"Database error creating bookmark: {e}")
        except (ValueError, TypeError) as e:
            log_warning(f"Invalid bookmark data: {e}")
            raise BookmarkManagerException(f"Invalid bookmark data: {e}")
        except Exception as e:
            log_warning(f"Unexpected error creating bookmark: {e}")
            raise BookmarkManagerException(f"Unexpected error creating bookmark: {e}")

    def get_bookmark(self, bookmark_id: int) -> BookmarkRecord | None:
        """Get a bookmark by ID."""
        try:
            rows = self.execute_query(
                self.story_id,
                """
                SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
                FROM bookmarks WHERE id = ?
            """,
                (bookmark_id,),
            )

            if not rows:
                return None

            return self._row_to_bookmark_record(rows[0])

        except (sqlite3.Error, sqlite3.DatabaseError) as e:
            log_warning(f"Database error getting bookmark {bookmark_id}: {e}")
            return None
        except (ValueError, TypeError, AttributeError) as e:
            log_warning(f"Data processing error getting bookmark {bookmark_id}: {e}")
            return None
        except Exception as e:
            log_warning(f"Unexpected error getting bookmark {bookmark_id}: {e}")
            return None
        except Exception as e:
            log_warning(f"Unexpected error getting bookmark {bookmark_id}: {e}")
            return None

    def list_bookmarks(
        self,
        bookmark_type: BookmarkType | None = None,
        scene_id: str | None = None,
        limit: int | None = None,
    ) -> list[BookmarkRecord]:
        """List bookmarks with optional filtering."""
        try:
            query = """
                SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
                FROM bookmarks WHERE story_id = ?
            """
            params: list[str | int] = [self.story_id]

            if bookmark_type:
                query += " AND bookmark_type = ?"
                params.append(bookmark_type.value)

            if scene_id:
                query += " AND scene_id = ?"
                params.append(scene_id)

            query += " ORDER BY created_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            rows = self.execute_query(self.story_id, query, params)
            return [self._row_to_bookmark_record(row) for row in rows]

        except (sqlite3.Error, sqlite3.DatabaseError) as e:
            log_warning(f"Database error listing bookmarks: {e}")
            return []
        except (ValueError, TypeError) as e:
            log_warning(f"Data processing error listing bookmarks: {e}")
            return []
        except Exception as e:
            log_warning(f"Unexpected error listing bookmarks: {e}")
            return []

    def update_bookmark(
        self,
        bookmark_id: int,
        label: str | None = None,
        description: str | None = None,
        bookmark_type: BookmarkType | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update an existing bookmark."""
        try:
            # Get current bookmark
            current = self.get_bookmark(bookmark_id)
            if not current:
                return False

            # Prepare update values
            updates = []
            params = []

            if label is not None:
                updates.append("label = ?")
                params.append(label)

            if description is not None:
                updates.append("description = ?")
                params.append(description)

            if bookmark_type is not None:
                if not isinstance(bookmark_type, BookmarkType):
                    bookmark_type = BookmarkType(bookmark_type)
                updates.append("bookmark_type = ?")
                params.append(bookmark_type.value)

            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))

            if not updates:
                return False

            # Execute update
            params.append(bookmark_id)
            rowcount = self.execute_update(
                self.story_id,
                f"""
                UPDATE bookmarks SET {', '.join(updates)} WHERE id = ?
            """,
                params,
            )

            success = rowcount > 0
            if success:
                log_system_event("bookmark_updated", f"Updated bookmark {bookmark_id}")

            return success

        except (AttributeError, KeyError) as e:
            log_warning(f"Data structure error updating bookmark {bookmark_id}: {e}")
            return False
        except (sqlite3.Error, sqlite3.DatabaseError) as e:
            log_warning(f"Database error updating bookmark {bookmark_id}: {e}")
            return False
        except Exception as e:
            log_warning(f"Unexpected error updating bookmark {bookmark_id}: {e}")
            return False

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID."""
        try:
            rowcount = self.execute_update(
                self.story_id,
                """
                DELETE FROM bookmarks WHERE id = ?
            """,
                (bookmark_id,),
            )

            success = rowcount > 0
            if success:
                log_system_event("bookmark_deleted", f"Deleted bookmark {bookmark_id}")

            return success

        except (AttributeError, KeyError) as e:
            log_warning(f"Data structure error deleting bookmark {bookmark_id}: {e}")
            return False
        except Exception as e:
            log_warning(f"Failed to delete bookmark {bookmark_id}: {e}")
            return False

    def delete_bookmarks_for_scene(self, scene_id: str) -> int:
        """Delete all bookmarks for a specific scene."""
        try:
            rowcount = self.execute_update(
                self.story_id,
                """
                DELETE FROM bookmarks WHERE scene_id = ?
            """,
                (scene_id,),
            )

            if rowcount > 0:
                log_system_event(
                    "bookmarks_deleted",
                    f"Deleted {rowcount} bookmarks for scene {scene_id}",
                )

            return rowcount

        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            log_warning(f"Database error deleting bookmarks for scene {scene_id}: {e}")
            return 0
        except (ValueError, TypeError) as e:
            log_warning(f"Invalid scene ID for bookmark deletion: {e}")
            return 0
        except Exception as e:
            log_warning(f"Unexpected error deleting bookmarks for scene {scene_id}: {e}")
            return 0
            log_warning(f"Failed to delete bookmarks for scene {scene_id}: {e}")
            return 0

    def get_bookmarks_with_scenes(
        self, bookmark_type: BookmarkType | None = None
    ) -> list[dict[str, Any]]:
        """Get bookmarks with their associated scene information."""
        try:
            query = """
                SELECT b.id, b.story_id, b.scene_id, b.label, b.description, b.bookmark_type,
                       b.created_at, b.metadata, s.timestamp, s.input, s.output
                FROM bookmarks b
                JOIN scenes s ON b.scene_id = s.scene_id
                WHERE b.story_id = ?
            """
            params = [self.story_id]

            if bookmark_type:
                query += " AND b.bookmark_type = ?"
                params.append(bookmark_type.value)

            query += " ORDER BY b.created_at DESC"

            rows = self.execute_query(self.story_id, query, params)

            return [
                {
                    "id": row["id"],
                    "story_id": row["story_id"],
                    "scene_id": row["scene_id"],
                    "label": row["label"],
                    "description": row["description"],
                    "bookmark_type": row["bookmark_type"],
                    "created_at": row["created_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "scene_timestamp": row["timestamp"],
                    "scene_input": row["input"],
                    "scene_output": row["output"],
                }
                for row in rows
            ]

        except (AttributeError, KeyError) as e:
            log_warning(f"Data structure error getting bookmarks with scenes: {e}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            log_warning(f"JSON parsing error getting bookmarks with scenes: {e}")
            return []
        except (OSError, IOError) as e:
            log_warning(f"Database error getting bookmarks with scenes: {e}")
            return []
        except Exception as e:
            log_warning(f"Unexpected error getting bookmarks with scenes: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get bookmark statistics."""
        try:
            # Total bookmarks
            total_rows = self.execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as count FROM bookmarks WHERE story_id = ?
            """,
                (self.story_id,),
            )
            total_bookmarks = total_rows[0]["count"]

            # Bookmarks by type
            type_rows = self.execute_query(
                self.story_id,
                """
                SELECT bookmark_type, COUNT(*) as count
                FROM bookmarks WHERE story_id = ?
                GROUP BY bookmark_type
            """,
                (self.story_id,),
            )

            by_type = {row["bookmark_type"]: row["count"] for row in type_rows}

            # Recent bookmarks
            recent_rows = self.execute_query(
                self.story_id,
                """
                SELECT id, label, bookmark_type, created_at
                FROM bookmarks WHERE story_id = ?
                ORDER BY created_at DESC LIMIT 5
            """,
                (self.story_id,),
            )

            recent_bookmarks = [
                {
                    "id": row["id"],
                    "label": row["label"],
                    "bookmark_type": row["bookmark_type"],
                    "created_at": row["created_at"],
                }
                for row in recent_rows
            ]

            return {
                "total_bookmarks": total_bookmarks,
                "by_type": by_type,
                "recent_bookmarks": recent_bookmarks,
            }

        except (OSError, IOError) as e:
            log_warning(f"Database access error while getting bookmark stats: {e}")
            return {"total_bookmarks": 0, "by_type": {}, "recent_bookmarks": []}
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            log_warning(f"Data format error while getting bookmark stats: {e}")
            return {"total_bookmarks": 0, "by_type": {}, "recent_bookmarks": []}
        except Exception as e:
            log_warning(f"Unexpected error while getting bookmark stats: {e}")
            return {"total_bookmarks": 0, "by_type": {}, "recent_bookmarks": []}

    def _row_to_bookmark_record(self, row) -> BookmarkRecord:
        """Convert database row to BookmarkRecord."""
        return BookmarkRecord(
            id=row["id"],
            story_id=row["story_id"],
            scene_id=row["scene_id"],
            label=row["label"],
            description=row["description"],
            bookmark_type=BookmarkType(row["bookmark_type"]),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if isinstance(row["created_at"], str)
                else row["created_at"]
            ),
            metadata=json.loads(row["metadata"] or "{}"),
        )


class BookmarkValidator:
    """Validates bookmark operations and data."""

    @staticmethod
    def validate_bookmark_data(
        scene_id: str,
        label: str,
        bookmark_type: BookmarkType,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate bookmark creation data."""
        errors = []

        # Validate scene_id
        if not scene_id or not isinstance(scene_id, str):
            errors.append("scene_id must be a non-empty string")

        # Validate label
        if not label or not isinstance(label, str):
            errors.append("label must be a non-empty string")
        elif len(label) > 255:
            errors.append("label must be 255 characters or less")

        # Validate bookmark_type
        if not isinstance(bookmark_type, BookmarkType):
            try:
                BookmarkType(bookmark_type)
            except ValueError:
                errors.append(f"Invalid bookmark_type: {bookmark_type}")

        # Validate metadata
        if metadata is not None:
            if not isinstance(metadata, dict):
                errors.append("metadata must be a dictionary")
            else:
                try:
                    json.dumps(metadata)
                except (TypeError, ValueError):
                    errors.append("metadata must be JSON-serializable")

        return {"is_valid": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_search_query(query: str) -> bool:
        """Validate search query."""
        return isinstance(query, str) and len(query.strip()) > 0
