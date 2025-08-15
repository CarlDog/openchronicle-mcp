"""
State Manager - Rollback and State Management

Handles rollback point creation, state snapshots, and restoration functionality
using dependency injection via ports (hexagonal architecture). Provides
versioning and state management with minimal coupling.
"""

import json
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from openchronicle.domain.ports.memory_port import IMemoryPort
from openchronicle.domain.ports.persistence_inmemory import InMemorySqlitePersistence
from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.domain.services.scenes.scene_orchestrator import SceneOrchestrator
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning


class StateManager:
    """Manages rollback points and state restoration."""

    def __init__(
        self,
        story_id: str,
        *,
        persistence_port: IPersistencePort | None = None,
        memory_port: IMemoryPort | None = None,
        scene_orchestrator: SceneOrchestrator | None = None,
    ):
        self.story_id = story_id
        self.persistence: IPersistencePort = (
            persistence_port if persistence_port is not None else InMemorySqlitePersistence()
        )
        self.memory_port = memory_port
        self.scene_orchestrator = (
            scene_orchestrator if scene_orchestrator is not None else
            SceneOrchestrator(story_id, persistence_port=self.persistence)
        )
        self.persistence.init_database(story_id)

    async def create_rollback_point(
        self, scene_id: str, description: str = "Manual rollback point"
    ) -> dict[str, Any]:
        """Create a rollback point at a specific scene."""

        # Verify scene exists
        scene_data = self.scene_orchestrator.load_scene(scene_id)
        if not scene_data:
            raise ValueError(f"Scene {scene_id} not found")

        rollback_id = (
            f"rollback_{scene_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        )

        # Create comprehensive state snapshot
        state_snapshot = await self._create_state_snapshot(scene_id)

        # Store rollback point
        self.persistence.execute_update(
            self.story_id,
            """
            INSERT OR REPLACE INTO rollback_points
                (rollback_id, scene_id, timestamp, description, scene_data, state_snapshot, story_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rollback_id,
                scene_id,
                datetime.now(UTC).isoformat(),
                description,
                json.dumps(scene_data),
                json.dumps(state_snapshot),
                self.story_id,
            ),
        )

        log_info(f"Created rollback point {rollback_id} for scene {scene_id}")

        return {
            "id": rollback_id,
            "scene_id": scene_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "description": description,
            "scene_data": scene_data,
            "state_snapshot": state_snapshot,
            "created_at": datetime.now(UTC).isoformat(),
        }

    async def list_rollback_points(self) -> list[dict[str, Any]]:
        """List all available rollback points."""

        rows = self.persistence.execute_query(
            self.story_id,
            """
            SELECT rollback_id, scene_id, timestamp, description, scene_data, state_snapshot
            FROM rollback_points WHERE story_id = ? ORDER BY timestamp DESC
            """,
            (self.story_id,),
        )

        rollback_points = []
        for row in rows:
            try:
                scene_data = json.loads(row.get("scene_data")) if row.get("scene_data") else {}
                state_snapshot = json.loads(row.get("state_snapshot")) if row.get("state_snapshot") else {}

                rollback_point = {
                    "id": row.get("rollback_id"),
                    "scene_id": row.get("scene_id"),
                    "timestamp": row.get("timestamp"),
                    "description": row.get("description"),
                    "scene_data": scene_data,
                    "state_snapshot": state_snapshot,
                    "age_hours": self._calculate_age_hours(row.get("timestamp")),
                }
                rollback_points.append(rollback_point)

            except json.JSONDecodeError as e:
                log_warning(f"Failed to parse rollback point {row.get('rollback_id')}: {e}")
                continue

        return rollback_points

    async def rollback_to_point(self, rollback_id: str) -> dict[str, Any]:
        """Restore story state to a specific rollback point."""

        # Get rollback point data
        rollback_data = self.persistence.execute_query(
            self.story_id,
            """
            SELECT rollback_id, scene_id, timestamp, description, scene_data, state_snapshot
            FROM rollback_points WHERE rollback_id = ? AND story_id = ?
            """,
            (rollback_id, self.story_id),
        )

        if not rollback_data:
            raise ValueError(f"Rollback point {rollback_id} not found")

        rollback_point = rollback_data[0]
        scene_id = rollback_point.get("scene_id")
        scene_data = (
            json.loads(rollback_point.get("scene_data")) if rollback_point.get("scene_data") else {}
        )
        state_snapshot = (
            json.loads(rollback_point.get("state_snapshot")) if rollback_point.get("state_snapshot") else {}
        )

        # Perform rollback operations
        restoration_results = []

        try:
            # 1. Restore memory state
            if "memory_state" in state_snapshot and state_snapshot["memory_state"] and self.memory_port:
                memory_result = await self._restore_memory_state(state_snapshot["memory_state"])
                restoration_results.append(
                    {
                        "component": "memory",
                        "status": "success",
                        "details": memory_result,
                    }
                )

            # 2. Remove scenes after rollback point
            scenes_removed = await self._remove_scenes_after(scene_id)
            restoration_results.append(
                {
                    "component": "scenes",
                    "status": "success",
                    "details": f"Removed {scenes_removed} scenes",
                }
            )

            # 3. Restore scene state if needed
            scene_result = await self._restore_scene_state(scene_id, scene_data)
            restoration_results.append(
                {"component": "scene", "status": "success", "details": scene_result}
            )

            # 4. Update rollback metadata
            await self._update_rollback_metadata(rollback_id)

            log_info(f"Successfully rolled back to {rollback_id}")

            return {
                "rollback_id": rollback_id,
                "target_scene_id": scene_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "restoration_results": restoration_results,
                "status": "success",
            }

        except Exception as e:
            log_error(f"Rollback to {rollback_id} failed: {e}")
            return {
                "rollback_id": rollback_id,
                "target_scene_id": scene_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "restoration_results": restoration_results,
                "status": "failed",
                "error": str(e),
            }

    async def cleanup_old_rollback_points(
        self, retention_days: int = 30
    ) -> dict[str, Any]:
        """Clean up rollback points older than specified days."""

        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()

        # Get rollback points to remove
        old_points = self.persistence.execute_query(
            self.story_id,
            """
            SELECT rollback_id FROM rollback_points
            WHERE story_id = ? AND timestamp < ? ORDER BY timestamp ASC
            """,
            (self.story_id, cutoff_iso),
        )

        if not old_points:
            return {"removed_count": 0, "message": "No old rollback points found"}

        # Remove old points
        removed_ids = [point.get("rollback_id") for point in old_points]

        self.persistence.execute_update(
            self.story_id,
            """
            DELETE FROM rollback_points WHERE story_id = ? AND timestamp < ?
            """,
            (self.story_id, cutoff_iso),
        )

        log_info(f"Cleaned up {len(removed_ids)} old rollback points")

        return {
            "removed_count": len(removed_ids),
            "removed_ids": removed_ids,
            "cutoff_date": cutoff_iso,
            "retention_days": retention_days,
        }

    async def _create_state_snapshot(self, scene_id: str) -> dict[str, Any]:
        """Create comprehensive state snapshot for rollback."""

        snapshot = {
            "scene_id": scene_id,
            "snapshot_timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            # Capture memory state
            if self.memory_port:
                # Capture all character memories via port
                characters = self.memory_port.list_character_memories(self.story_id)
                memory_state: dict[str, Any] = {}
                for name in characters:
                    data = self.memory_port.retrieve_memory(self.story_id, name)
                    if data is not None:
                        memory_state[name] = data
                snapshot["memory_state"] = memory_state

            # Capture scene count and latest scenes
            recent_scenes = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp FROM scenes
                WHERE story_id = ?
                ORDER BY timestamp DESC LIMIT 5
                """,
                (self.story_id,),
            )

            snapshot["recent_scenes"] = [
                {"scene_id": scene.get("scene_id"), "timestamp": scene.get("timestamp")} for scene in recent_scenes
            ]

            # Capture story metadata
            total_rows = self.persistence.execute_query(
                self.story_id,
                "SELECT COUNT(*) AS count FROM scenes WHERE story_id = ?",
                (self.story_id,),
            )
            total_count = total_rows[0]["count"] if total_rows else 0

            snapshot["story_metadata"] = {
                "total_scenes": total_count,
                "capture_time": datetime.now(UTC).isoformat(),
            }

        except (ValueError, KeyError, TypeError) as e:
            log_warning(f"Invalid state data creating snapshot: {e}")
            snapshot["error"] = str(e)
        except Exception as e:
            log_warning(f"Unexpected error creating complete state snapshot: {e}")
            snapshot["error"] = str(e)

        return snapshot

    async def _restore_memory_state(self, memory_state: dict[str, Any]) -> str:
        """Restore memory state from snapshot."""
        try:
            # Use memory orchestrator to restore state
            for name, data in memory_state.items():
                # Use store_memory to restore; overwrites existing entries
                self.memory_port.store_memory(self.story_id, name, data)
        except Exception as e:
            log_error(f"Failed to restore memory state: {e}")
            return f"Memory restoration failed: {e}"
        else:
            return "Memory state restored via IMemoryPort"

    async def _remove_scenes_after(self, target_scene_id: str) -> int:
        """Remove all scenes that occurred after the target scene."""

        # Get target scene timestamp
        target_scene = self.persistence.execute_query(
            self.story_id,
            """
            SELECT timestamp FROM scenes WHERE scene_id = ? AND story_id = ?
            """,
            (target_scene_id, self.story_id),
        )

        if not target_scene:
            return 0

        target_timestamp = target_scene[0]["timestamp"]

        # Count scenes to remove
        scenes_to_remove = self.persistence.execute_query(
            self.story_id,
            """
            SELECT COUNT(*) AS count FROM scenes WHERE story_id = ? AND timestamp > ?
            """,
            (self.story_id, target_timestamp),
        )

        remove_count = scenes_to_remove[0]["count"] if scenes_to_remove else 0

        # Remove scenes after target
        self.persistence.execute_update(
            self.story_id,
            """
            DELETE FROM scenes WHERE story_id = ? AND timestamp > ?
            """,
            (self.story_id, target_timestamp),
        )

        return remove_count

    async def _restore_scene_state(
        self, scene_id: str, scene_data: dict[str, Any]
    ) -> str:
        """Restore specific scene state if needed."""
        # For now, just verify scene exists
        current_scene = self.scene_orchestrator.load_scene(scene_id)
        if current_scene:
            return f"Scene {scene_id} verified and accessible"
        return f"Warning: Scene {scene_id} not found after rollback"

    async def _update_rollback_metadata(self, rollback_id: str):
        """Update rollback point metadata after use."""
        self.persistence.execute_update(
            self.story_id,
            """
            UPDATE rollback_points
            SET last_used = ?, usage_count = COALESCE(usage_count, 0) + 1
            WHERE rollback_id = ? AND story_id = ?
            """,
            (datetime.now(UTC).isoformat(), rollback_id, self.story_id),
        )

    def _calculate_age_hours(self, timestamp_iso: str) -> float:
        """Calculate age of rollback point in hours."""
        try:
            rollback_time = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            age_delta = datetime.now(UTC) - rollback_time.replace(tzinfo=UTC)
            return age_delta.total_seconds() / 3600
        except (ValueError, TypeError) as e:
            log_warning(f"Invalid timestamp format: {timestamp_iso}, error: {e}")
            return 0.0
        except (AttributeError, OSError) as e:
            log_warning(f"Datetime processing error: {e}")
            return 0.0
        except Exception:
            return 0.0
