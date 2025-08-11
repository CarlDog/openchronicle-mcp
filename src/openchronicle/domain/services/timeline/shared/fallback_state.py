"""
Fallback State Manager - Minimal State Management

Provides basic state management when full rollback system is unavailable.
"""

import json
from datetime import UTC
from datetime import datetime
from typing import Any


class FallbackStateManager:
    """Minimal fallback state manager."""

    def __init__(self, story_id: str):
        self.story_id = story_id

    async def create_rollback_point(
        self, scene_id: str, description: str = "Manual rollback point"
    ) -> dict[str, Any]:
        """Create basic rollback point with limited functionality."""
        try:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).parent.parent.parent))
            # from src.openchronicle.infrastructure.persistence import execute_update - REPLACED WITH DEPENDENCY INJECTION
            # from src.openchronicle.infrastructure.persistence import init_database - REPLACED WITH DEPENDENCY INJECTION

            init_database(self.story_id)

            rollback_id = (
                f"fallback_{scene_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            )

            execute_update(
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

        except Exception as e:
            return {
                "error": f"Fallback rollback creation failed: {e}",
                "fallback_mode": True,
            }

    async def list_rollback_points(self) -> list[dict[str, Any]]:
        """List basic rollback points."""
        try:
            import sys
            from pathlib import Path

            sys.path.append(str(Path(__file__).parent.parent.parent))
            # from src.openchronicle.infrastructure.persistence import execute_query - REPLACED WITH DEPENDENCY INJECTION
            # from src.openchronicle.infrastructure.persistence import init_database - REPLACED WITH DEPENDENCY INJECTION

            init_database(self.story_id)

            rows = execute_query(
                self.story_id,
                """
                SELECT rollback_id, scene_id, timestamp, description
                FROM rollback_points ORDER BY timestamp DESC LIMIT 10
            """,
            )

            rollback_points = []
            for row in rows:
                rollback_points.append(
                    {
                        "id": row[0],
                        "scene_id": row[1],
                        "timestamp": row[2],
                        "description": row[3],
                        "fallback_mode": True,
                    }
                )

            return rollback_points

        except Exception:
            return []

    async def rollback_to_point(self, rollback_id: str) -> dict[str, Any]:
        """Basic rollback with limited functionality."""
        return {
            "rollback_id": rollback_id,
            "status": "limited",
            "message": "Fallback mode: Limited rollback functionality available",
            "fallback_mode": True,
            "recommendation": "Use full timeline system for complete rollback capabilities",
        }
