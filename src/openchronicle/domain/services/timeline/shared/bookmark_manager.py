"""
Simple Bookmark Manager for Timeline

Provides a minimal implementation to retrieve bookmarks for a story using the
domain persistence port (IPersistencePort). This avoids infrastructure imports
and keeps hexagonal boundaries intact.
"""

from __future__ import annotations

from typing import Any

from src.openchronicle.domain.ports.persistence_port import IPersistencePort


class SimpleBookmarkManager:
    """Fetches bookmarks from the persistence layer if available."""

    def __init__(self, persistence_port: IPersistencePort):
        self.persistence = persistence_port

    def get_bookmarks(self, story_id: str) -> list[dict[str, Any]]:
        """Return bookmarks for a given story. Gracefully handles missing table."""
        try:
            # Try a simple select; if table doesn't exist, adapter should raise
            rows = self.persistence.execute_query(
                story_id,
                """
                SELECT
                    bookmark_id,
                    scene_id,
                    timestamp,
                    description,
                    bookmark_data
                FROM bookmarks
                WHERE story_id = ?
                ORDER BY timestamp ASC
                LIMIT 200
                """,
                (story_id,),
            )
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        for r in rows:
            # rows are expected to be dict-like based on our in-memory adapter
            results.append(
                {
                    "bookmark_id": r.get("bookmark_id"),
                    "scene_id": r.get("scene_id"),
                    "timestamp": r.get("timestamp"),
                    "description": r.get("description"),
                    "data": r.get("bookmark_data"),
                }
            )
        return results

    def create_bookmark(
        self,
        story_id: str,
        bookmark_id: str,
        scene_id: str,
        timestamp: str,
        description: str = "",
        data: Any | None = None,
    ) -> bool:
        """Create a bookmark record; returns True on success.

        Note: This is a convenience for development and tests; production systems
        may use a dedicated adapter.
        """
        try:
            return self.persistence.execute_update(
                story_id,
                """
                INSERT INTO bookmarks (story_id, bookmark_id, scene_id, timestamp, description, bookmark_data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (story_id, bookmark_id, scene_id, timestamp, description, json_dumps_safe(data)),
            )
        except Exception:
            return False

    def delete_bookmark(self, story_id: str, bookmark_id: str) -> bool:
        """Delete a single bookmark by ID for a story."""
        try:
            return self.persistence.execute_update(
                story_id,
                "DELETE FROM bookmarks WHERE story_id = ? AND bookmark_id = ?",
                (story_id, bookmark_id),
            )
        except Exception:
            return False

    def clear_bookmarks(self, story_id: str) -> bool:
        """Delete all bookmarks for a story."""
        try:
            return self.persistence.execute_update(
                story_id, "DELETE FROM bookmarks WHERE story_id = ?", (story_id,)
            )
        except Exception:
            return False


def json_dumps_safe(data: Any | None) -> str:
    try:
        import json

        return json.dumps(data) if data is not None else ""
    except Exception:
        return ""
