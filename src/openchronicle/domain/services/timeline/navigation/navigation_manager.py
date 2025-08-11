"""
Navigation Manager - Timeline Navigation & History

Handles timeline navigation, history tracking, and scene transitions.
Refactored to use the IPersistencePort (hexagonal architecture, DI) and align
queries with the current scenes schema.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.domain.ports.persistence_inmemory import (
    InMemorySqlitePersistence,
)


class NavigationManager:
    """Handles timeline navigation and history tracking."""

    def __init__(
        self,
        story_id: str,
        *,
        persistence_port: IPersistencePort | None = None,
    ):
        self.story_id = story_id
        # Default to in-memory persistence for local/dev unless injected
        self.persistence: IPersistencePort = (
            persistence_port if persistence_port is not None else InMemorySqlitePersistence()
        )

    async def get_navigation_history(self) -> list[dict[str, Any]]:
        """Retrieve navigation history for timeline."""
        try:
            # Ensure DB initialized for this story
            self.persistence.init_database(self.story_id)

            # Get recent navigation entries (scene_label as title; summary from output)
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT
                    scene_id,
                    scene_label AS scene_title,
                    timestamp,
                    substr(output, 1, 200) AS scene_summary
                FROM scenes
                WHERE story_id = ?
                ORDER BY timestamp DESC
                LIMIT 20
                """,
                (self.story_id,),
            )

            history = []
            for row in rows:
                title = row.get("scene_title") or "Untitled Scene"
                ts = row.get("timestamp")
                history.append(
                    {
                        "scene_id": row.get("scene_id"),
                        "title": title,
                        "timestamp": ts,
                        "summary": row.get("scene_summary"),
                        # Defaults for legacy fields not in schema
                        "navigation_type": "standard",
                        "user_choice": None,
                        "display_time": self._format_display_time(ts),
                    }
                )

            return history

        except Exception as e:
            from openchronicle.shared.logging_system import log_system_event

            log_system_event("error", f"Navigation history retrieval failed: {e}")
            return []

    async def find_scene_by_criteria(
        self,
        title_pattern: str | None = None,
        content_pattern: str | None = None,
        time_range: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find scenes matching navigation criteria."""
        try:
            self.persistence.init_database(self.story_id)

            # Build dynamic query based on criteria
            query_parts = [
                "SELECT scene_id, scene_label AS scene_title, timestamp, substr(output, 1, 200) AS scene_summary FROM scenes WHERE story_id = ?",
            ]
            params: list[Any] = [self.story_id]

            if title_pattern:
                query_parts.append("AND scene_label LIKE ?")
                params.append(f"%{title_pattern}%")

            if content_pattern:
                query_parts.append("AND (output LIKE ? OR scene_label LIKE ?)")
                params.extend([f"%{content_pattern}%", f"%{content_pattern}%"])

            if time_range:
                if time_range.get("start"):
                    query_parts.append("AND timestamp >= ?")
                    params.append(time_range["start"])
                if time_range.get("end"):
                    query_parts.append("AND timestamp <= ?")
                    params.append(time_range["end"])

            query_parts.append("ORDER BY timestamp DESC LIMIT 50")
            query = " ".join(query_parts)

            rows = self.persistence.execute_query(self.story_id, query, tuple(params))

            results = []
            for row in rows:
                results.append(
                    {
                        "scene_id": row.get("scene_id"),
                        "title": (row.get("scene_title") or "Untitled Scene"),
                        "timestamp": row.get("timestamp"),
                        "summary": row.get("scene_summary"),
                        "relevance_score": self._calculate_relevance_score(
                            row, title_pattern, content_pattern
                        ),
                    }
                )

            # Sort by relevance score
            return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            from openchronicle.shared.logging_system import log_system_event

            log_system_event("error", f"Scene search failed: {e}")
            return []

    async def get_scene_context(
        self, scene_id: str, context_window: int = 3
    ) -> dict[str, Any]:
        """Get contextual scenes around target scene."""
        try:
            self.persistence.init_database(self.story_id)

            # Get target scene timestamp
            target_row = self.persistence.execute_query(
                self.story_id,
                """
                SELECT timestamp, scene_label AS scene_title, substr(output, 1, 200) AS scene_summary
                FROM scenes WHERE scene_id = ? AND story_id = ?
                """,
                (scene_id, self.story_id),
            )

            if not target_row:
                return {"error": "Scene not found"}

            target_timestamp = target_row[0]["timestamp"]

            # Get surrounding scenes
            context_rows = self.persistence.execute_query(
                self.story_id,
                """
                (SELECT scene_id, scene_label AS scene_title, timestamp, substr(output, 1, 200) AS scene_summary, 'before' AS position
                 FROM scenes
                 WHERE story_id = ? AND timestamp < ?
                 ORDER BY timestamp DESC
                 LIMIT ?)
                UNION ALL
                (SELECT scene_id, scene_label AS scene_title, timestamp, substr(output, 1, 200) AS scene_summary, 'current' AS position
                 FROM scenes
                 WHERE story_id = ? AND scene_id = ?)
                UNION ALL
                (SELECT scene_id, scene_label AS scene_title, timestamp, substr(output, 1, 200) AS scene_summary, 'after' AS position
                 FROM scenes
                 WHERE story_id = ? AND timestamp > ?
                 ORDER BY timestamp ASC
                 LIMIT ?)
                ORDER BY timestamp ASC
                """,
                (
                    self.story_id,
                    target_timestamp,
                    context_window,
                    self.story_id,
                    scene_id,
                    self.story_id,
                    target_timestamp,
                    context_window,
                ),
            )

            context_scenes = []
            for row in context_rows:
                context_scenes.append(
                    {
                        "scene_id": row.get("scene_id"),
                        "title": (row.get("scene_title") or "Untitled Scene"),
                        "timestamp": row.get("timestamp"),
                        "summary": row.get("scene_summary"),
                        "position": row.get("position"),
                        "is_target": row.get("scene_id") == scene_id,
                    }
                )

            return {
                "target_scene_id": scene_id,
                "context_window": context_window,
                "context_scenes": context_scenes,
                "total_context": len(context_scenes),
            }

        except Exception as e:
            from openchronicle.shared.logging_system import log_system_event

            log_system_event("error", f"Scene context retrieval failed: {e}")
            return {"error": str(e)}

    async def track_navigation_path(
        self, from_scene: str, to_scene: str, navigation_type: str = "manual"
    ) -> bool:
        """Track navigation between scenes."""
        try:
            self.persistence.init_database(self.story_id)

            # Log navigation event
            self.persistence.execute_update(
                self.story_id,
                """
                INSERT INTO navigation_history
                    (from_scene, to_scene, navigation_type, timestamp, story_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    from_scene,
                    to_scene,
                    navigation_type,
                    datetime.now(UTC).isoformat(),
                    self.story_id,
                ),
            )

            from openchronicle.shared.logging_system import log_system_event

            log_system_event(
                "timeline_navigation",
                f"Navigation: {from_scene} -> {to_scene} ({navigation_type})",
            )

            return True

        except Exception as e:
            from openchronicle.shared.logging_system import log_system_event

            log_system_event("error", f"Navigation tracking failed: {e}")
            return False

    async def get_navigation_statistics(self) -> dict[str, Any]:
        """Get navigation pattern statistics."""
        try:
            self.persistence.init_database(self.story_id)

            # Count total scenes
            scene_count_rows = self.persistence.execute_query(
                self.story_id,
                "SELECT COUNT(*) AS count FROM scenes WHERE story_id = ?",
                (self.story_id,),
            )
            scene_count = scene_count_rows[0]["count"] if scene_count_rows else 0

            # Get navigation patterns
            nav_patterns = self.persistence.execute_query(
                self.story_id,
                """
                SELECT navigation_type, COUNT(*) AS count
                FROM navigation_history
                WHERE story_id = ?
                GROUP BY navigation_type
                ORDER BY count DESC
                """,
                (self.story_id,),
            )

            # Get recent activity
            recent_activity_rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT COUNT(*) AS count FROM scenes
                WHERE story_id = ? AND timestamp > datetime('now', '-7 days')
                """,
                (self.story_id,),
            )
            recent_activity = (
                recent_activity_rows[0]["count"] if recent_activity_rows else 0
            )

            return {
                "total_scenes": scene_count,
                "recent_activity": recent_activity,
                "navigation_patterns": [
                    {"type": row[0], "count": row[1]} for row in nav_patterns
                ],
                "statistics_timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            from openchronicle.shared.logging_system import log_system_event

            log_system_event("error", f"Navigation statistics failed: {e}")
            return {"error": str(e)}

    async def navigate(self, navigation_type: str, **kwargs) -> dict[str, Any]:
        """Navigate through timeline with various options."""
        try:
            if navigation_type == "next":
                return await self._navigate_next(kwargs.get("current_scene_id"))
            if navigation_type == "previous":
                return await self._navigate_previous(kwargs.get("current_scene_id"))
            if navigation_type == "jump_to":
                return await self._navigate_jump_to(kwargs.get("target_scene_id"))
            if navigation_type == "search":
                return await self._navigate_search(kwargs.get("search_criteria", {}))
            return {"error": f"Unknown navigation type: {navigation_type}"}
        except Exception as e:
            return {"error": f"Navigation failed: {e!s}"}

    async def build_navigation_structure(
        self, timeline_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build navigation structure from timeline data."""
        try:
            entries = timeline_data.get("entries", [])

            # Build navigation metadata
            navigation_structure = {
                "total_entries": len(entries),
                "scene_entries": len([e for e in entries if e.get("type") == "scene"]),
                "bookmark_entries": len(
                    [e for e in entries if e.get("type") == "bookmark"]
                ),
                "navigation_points": [],
                "current_position": 0,
            }

            # Extract navigation points
            for i, entry in enumerate(entries):
                if entry.get("type") == "scene":
                    navigation_structure["navigation_points"].append(
                        {
                            "index": i,
                            "scene_id": entry.get("scene_id"),
                            "timestamp": entry.get("timestamp"),
                            "label": entry.get("scene_label", f"Scene {i+1}"),
                            "type": "scene",
                        }
                    )
                elif entry.get("type") == "bookmark":
                    bookmark_data = entry.get("bookmark_data", {})
                    navigation_structure["navigation_points"].append(
                        {
                            "index": i,
                            "scene_id": bookmark_data.get("scene_id"),
                            "timestamp": entry.get("timestamp"),
                            "label": bookmark_data.get("description", "Bookmark"),
                            "type": "bookmark",
                        }
                    )

            return navigation_structure

        except Exception as e:
            return {
                "total_entries": 0,
                "scene_entries": 0,
                "bookmark_entries": 0,
                "navigation_points": [],
                "current_position": 0,
                "error": f"Failed to build navigation structure: {e!s}",
            }

    async def _navigate_next(self, current_scene_id: str | None) -> dict[str, Any]:
        """Navigate to next scene in timeline."""
        try:
            self.persistence.init_database(self.story_id)

            if not current_scene_id:
                # Get first scene
                first_scene = self.persistence.execute_query(
                    self.story_id,
                    """
                    SELECT scene_id, scene_label AS scene_title, timestamp FROM scenes
                    WHERE story_id = ?
                    ORDER BY timestamp ASC LIMIT 1
                    """,
                    (self.story_id,),
                )
                if first_scene:
                    return {
                        "target_scene_id": first_scene[0]["scene_id"],
                        "navigation_type": "next",
                        "status": "success",
                    }
                return {"error": "No scenes found"}

            # Find next scene after current
            next_scene = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, scene_label AS scene_title, timestamp FROM scenes
                WHERE story_id = ? AND timestamp > (SELECT timestamp FROM scenes WHERE scene_id = ? AND story_id = ?)
                ORDER BY timestamp ASC LIMIT 1
                """,
                (self.story_id, current_scene_id, self.story_id),
            )

            if next_scene:
                return {
                    "target_scene_id": next_scene[0]["scene_id"],
                    "navigation_type": "next",
                    "status": "success",
                }
            return {"error": "No next scene found"}

        except Exception as e:
            return {"error": f"Next navigation failed: {e!s}"}

    async def _navigate_previous(self, current_scene_id: str | None) -> dict[str, Any]:
        """Navigate to previous scene in timeline."""
        try:
            self.persistence.init_database(self.story_id)

            if not current_scene_id:
                # Get last scene
                last_scene = self.persistence.execute_query(
                    self.story_id,
                    """
                    SELECT scene_id, scene_label AS scene_title, timestamp FROM scenes
                    WHERE story_id = ?
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (self.story_id,),
                )
                if last_scene:
                    return {
                        "target_scene_id": last_scene[0]["scene_id"],
                        "navigation_type": "previous",
                        "status": "success",
                    }
                return {"error": "No scenes found"}

            # Find previous scene before current
            prev_scene = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, scene_label AS scene_title, timestamp FROM scenes
                WHERE story_id = ? AND timestamp < (SELECT timestamp FROM scenes WHERE scene_id = ? AND story_id = ?)
                ORDER BY timestamp DESC LIMIT 1
                """,
                (self.story_id, current_scene_id, self.story_id),
            )

            if prev_scene:
                return {
                    "target_scene_id": prev_scene[0]["scene_id"],
                    "navigation_type": "previous",
                    "status": "success",
                }
            return {"error": "No previous scene found"}

        except Exception as e:
            return {"error": f"Previous navigation failed: {e!s}"}

    async def _navigate_jump_to(self, target_scene_id: str) -> dict[str, Any]:
        """Jump to specific scene."""
        try:
            self.persistence.init_database(self.story_id)

            # Verify scene exists
            scene = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, scene_label AS scene_title, timestamp FROM scenes WHERE story_id = ? AND scene_id = ?
                """,
                (self.story_id, target_scene_id),
            )

            if scene:
                return {
                    "target_scene_id": target_scene_id,
                    "navigation_type": "jump_to",
                    "status": "success",
                }
            return {"error": f"Scene {target_scene_id} not found"}

        except Exception as e:
            return {"error": f"Jump navigation failed: {e!s}"}

    async def _navigate_search(self, search_criteria: dict[str, Any]) -> dict[str, Any]:
        """Search for scenes matching criteria."""
        try:
            results = await self.find_scene_by_criteria(
                title_pattern=search_criteria.get("title"),
                content_pattern=search_criteria.get("content"),
                time_range=search_criteria.get("time_range"),
            )

            if results:
                return {
                    "target_scene_id": results[0]["scene_id"],
                    "navigation_type": "search",
                    "search_results": results,
                    "status": "success",
                }
            return {"error": "No scenes found matching search criteria"}

        except Exception as e:
            return {"error": f"Search navigation failed: {e!s}"}

    def _format_display_time(self, timestamp: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return timestamp

    def _calculate_relevance_score(
        self, row: dict[str, Any], title_pattern: str | None, content_pattern: str | None
    ) -> float:
        """Calculate relevance score for search results."""
        score = 0.0

        title_val = row.get("scene_title")
        if title_pattern and title_val:
            if title_pattern.lower() in title_val.lower():
                score += 10.0

        summary_val = row.get("scene_summary")
        if content_pattern and summary_val:
            if content_pattern.lower() in summary_val.lower():
                score += 5.0

        # Recency bonus (newer scenes get slight boost)
        try:
            timestamp_val = row.get("timestamp")
            dt = datetime.fromisoformat(timestamp_val.replace("Z", "+00:00")) if timestamp_val else None
            if dt is None:
                return score
            days_old = (datetime.now(UTC) - dt).days
            score += max(0, 2.0 - (days_old * 0.1))
        except:
            pass

        return score
