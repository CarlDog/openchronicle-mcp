"""
Fallback Navigation Manager - Basic Navigation

Provides minimal navigation functionality when full system is unavailable.
"""

from typing import Any



from openchronicle.domain.ports.persistence_port import IPersistencePort
from typing import Optional

class FallbackNavigationManager:
    """Minimal fallback navigation manager."""

    def __init__(self, story_id: str, persistence_port: IPersistencePort):
        self.persistence_port = persistence_port

        self.story_id = story_id

    async def get_navigation_history(self) -> list[dict[str, Any]]:
        """Basic navigation history with limited functionality."""
        try:
            # Infrastructure dependencies replaced with dependency injection

            await self.persistence_port.init_database(self.story_id)

            rows = await self.persistence_port.execute_query(
                self.story_id,
                """
                SELECT scene_id, scene_title, timestamp
                FROM scenes ORDER BY timestamp DESC LIMIT 5
            """,
            )

            history = []
            for row in rows:
                history.append(
                    {
                        "scene_id": row[0],
                        "title": row[1] or "Untitled Scene",
                        "timestamp": row[2],
                        "fallback_mode": True,
                    }
                )

            return history

        except Exception:
            return []

    async def find_scene_by_criteria(self, **kwargs) -> list[dict[str, Any]]:
        """Basic scene search."""
        return [{"message": "Fallback mode: Limited search functionality"}]

    async def get_scene_context(
        self, scene_id: str, context_window: int = 3
    ) -> dict[str, Any]:
        """Basic scene context."""
        return {
            "scene_id": scene_id,
            "message": "Fallback mode: Limited context functionality",
            "fallback_mode": True,
        }

    async def track_navigation_path(
        self, from_scene: str, to_scene: str, navigation_type: str = "manual"
    ) -> bool:
        """Basic navigation tracking."""
        return True

    async def navigate(self, navigation_type: str, **kwargs) -> dict[str, Any]:
        """Main navigation interface with fallback functionality."""
        return {
            "type": navigation_type,
            "message": f"Fallback mode: Limited {navigation_type} functionality",
            "fallback_mode": True,
            "data": {},
        }

    async def get_navigation_statistics(self) -> dict[str, Any]:
        """Basic navigation statistics."""
        return {"message": "Fallback mode: Limited statistics", "fallback_mode": True}
