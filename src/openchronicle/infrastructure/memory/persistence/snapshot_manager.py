"""
Snapshot Manager

Handles memory snapshot creation, restoration, and rollback functionality.
Extracted from archive_memory_snapshot and refresh_memory_after_rollback functions.
"""

from dataclasses import dataclass
from typing import Any

from ..shared.memory_models import MemoryState
from .memory_repository import MemoryRepository


@dataclass
class RollbackResult:
    """Result of rollback operation."""

    success: bool
    message: str
    restored_scene_id: str
    changes_detected: list[str]
    warnings: list[str]


class SnapshotManager:
    """Manages memory snapshots and rollback functionality."""

    def __init__(self, repository: MemoryRepository):
        """Initialize snapshot manager."""
        self.repository = repository
        self.max_snapshots = 50

    def create_snapshot(self, story_id: str, scene_id: str) -> str:
        """Create memory snapshot for current scene."""
        current_memory = self.repository.load_memory(story_id)
        snapshot_id = self.repository.create_snapshot(
            story_id, scene_id, current_memory
        )

        if snapshot_id:
            return snapshot_id
        return ""

    def restore_from_snapshot(self, story_id: str, scene_id: str) -> RollbackResult:
        """Restore memory from specific snapshot with detailed results."""
        try:
            # Load current memory for comparison
            current_memory = self.repository.load_memory(story_id)

            # Restore from snapshot
            restored_memory = self.repository.restore_from_snapshot(story_id, scene_id)

            if not restored_memory:
                return RollbackResult(
                    success=False,
                    message=f"No snapshot found for scene {scene_id}",
                    restored_scene_id="",
                    changes_detected=[],
                    warnings=[],
                )

            # Detect changes between current and restored memory
            changes = self._detect_changes(current_memory, restored_memory)

            # Save restored memory as current
            success = self.repository.save_memory(story_id, restored_memory)

            if success:
                return RollbackResult(
                    success=True,
                    message=f"Successfully restored memory from scene {scene_id}",
                    restored_scene_id=scene_id,
                    changes_detected=changes,
                    warnings=[],
                )
            return RollbackResult(
                success=False,
                message="Failed to save restored memory",
                restored_scene_id=scene_id,
                changes_detected=changes,
                warnings=["Memory restoration succeeded but save failed"],
            )

        except Exception as e:
            return RollbackResult(
                success=False,
                message=f"Rollback failed: {e!s}",
                restored_scene_id="",
                changes_detected=[],
                warnings=[],
            )

    def get_available_snapshots(self, story_id: str) -> list[dict[str, Any]]:
        """Get list of available snapshots with metadata."""
        return self.repository.get_snapshot_metadata(story_id)

    def cleanup_old_snapshots(self, story_id: str) -> int:
        """Clean up old snapshots and return count removed."""
        try:
            snapshots = self.get_available_snapshots(story_id)
            if len(snapshots) <= self.max_snapshots:
                return 0

            # This is handled by the repository during snapshot creation
            # But we can provide stats on how many would be cleaned
            return len(snapshots) - self.max_snapshots

        except Exception:
            return 0

    def _detect_changes(self, current: MemoryState, restored: MemoryState) -> list[str]:
        """Detect changes between current and restored memory states."""
        changes = []

        # Character changes
        current_chars = set(current.characters.keys())
        restored_chars = set(restored.characters.keys())

        # New characters in current that will be lost
        new_chars = current_chars - restored_chars
        if new_chars:
            changes.append(f"Characters removed: {', '.join(new_chars)}")

        # Characters restored that weren't in current
        restored_chars_only = restored_chars - current_chars
        if restored_chars_only:
            changes.append(f"Characters restored: {', '.join(restored_chars_only)}")

        # Character modifications
        for char_name in current_chars & restored_chars:
            current_char = current.characters[char_name]
            restored_char = restored.characters[char_name]

            if current_char.description != restored_char.description:
                changes.append(f"Character {char_name}: description changed")
            if current_char.current_mood != restored_char.current_mood:
                changes.append(
                    f"Character {char_name}: mood {current_char.current_mood} → {restored_char.current_mood}"
                )
            if len(current_char.mood_history) != len(restored_char.mood_history):
                changes.append(f"Character {char_name}: mood history length changed")

        # World state changes
        current_world_keys = set(current.world_state.keys())
        restored_world_keys = set(restored.world_state.keys())

        new_world_keys = current_world_keys - restored_world_keys
        if new_world_keys:
            changes.append(f"World state removed: {', '.join(new_world_keys)}")

        restored_world_keys_only = restored_world_keys - current_world_keys
        if restored_world_keys_only:
            changes.append(
                f"World state restored: {', '.join(restored_world_keys_only)}"
            )

        # Flag changes
        current_flags = {flag.name for flag in current.flags}
        restored_flags = {flag.name for flag in restored.flags}

        if current_flags != restored_flags:
            new_flags = current_flags - restored_flags
            restored_flags_only = restored_flags - current_flags

            if new_flags:
                changes.append(f"Flags removed: {', '.join(new_flags)}")
            if restored_flags_only:
                changes.append(f"Flags restored: {', '.join(restored_flags_only)}")

        # Event changes
        if len(current.recent_events) != len(restored.recent_events):
            changes.append(
                f"Recent events count: {len(current.recent_events)} → {len(restored.recent_events)}"
            )

        return changes
