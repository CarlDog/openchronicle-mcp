"""
Fallback State Manager - Minimal State Management

Provides basic state management when full rollback system is unavailable.
"""

import json
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Optional

from openchronicle.domain.ports.persistence_port import IPersistencePort


class FallbackStateManager:
    """Minimal fallback state manager."""

    def __init__(self, story_id: str, persistence_port: IPersistencePort):
        self.persistence_port = persistence_port

        self.story_id = story_id

    async def create_rollback_point(
        self, scene_id: str, description: str = "Manual rollback point"
    ) -> dict[str, Any]:
        """Create basic rollback point with limited functionality."""
        try:
            self.persistence_port.init_database(self.story_id)

            rollback_id = (
                f"fallback_{scene_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            )

            self.persistence_port.execute_update(
                self.story_id,
                """
                INSERT OR REPLACE INTO rollback_points
                (rollback_id, scene_id, timestamp, description, scene_data)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    rollback_id,
                    scene_id,
                    datetime.now(UTC).isoformat(),
                    f"[FALLBACK] {description}",
                    json.dumps({"fallback_mode": True, "scene_id": scene_id}),
                ),
            )

            return {
                "id": rollback_id,
                "scene_id": scene_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "description": description,
                "fallback_mode": True,
                "limited_functionality": True,
            }
        except (RuntimeError, ValueError, KeyError, TypeError, OSError) as e:
            return {
                "error": f"Fallback rollback creation failed: {e}",
                "fallback_mode": True,
            }

    async def list_rollback_points(self) -> list[dict[str, Any]]:
        """List basic rollback points."""
        try:
            self.persistence_port.init_database(self.story_id)

            rows = self.persistence_port.execute_query(
                self.story_id,
                """
                SELECT rollback_id, scene_id, timestamp, description
                FROM rollback_points
                WHERE story_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """,
                (self.story_id,),
            )

            rollback_points = []
            for row in rows:
                rollback_points.append(
                    {
                        "id": row.get("rollback_id") if hasattr(row, "get") else None,
                        "scene_id": row.get("scene_id") if hasattr(row, "get") else None,
                        "timestamp": row.get("timestamp") if hasattr(row, "get") else None,
                        "description": row.get("description") if hasattr(row, "get") else None,
                        "fallback_mode": True,
                    }
                )

        except (RuntimeError, ValueError, KeyError, TypeError, OSError):
            return []
        else:
            return rollback_points

    async def rollback_to_point(self, rollback_id: str) -> dict[str, Any]:
        """Basic rollback with limited functionality."""
        return {
            "rollback_id": rollback_id,
            "status": "limited",
            "message": "Fallback mode: Limited rollback functionality available",
            "fallback_mode": True,
            "recommendation": "Use full timeline system for complete rollback capabilities",
        }
