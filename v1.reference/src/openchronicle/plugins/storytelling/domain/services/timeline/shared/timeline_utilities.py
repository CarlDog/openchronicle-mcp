"""
Shared Timeline Utilities - Common Temporal State Management

Provides shared utilities, validation patterns, and common functionality
for timeline and state management operations.
"""

from datetime import UTC
from datetime import datetime
from typing import Any


class TimelineUtilities:
    """Core timeline utility functions for navigation and state management."""

    @staticmethod
    def build_timeline_from_scenes(
        scenes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build timeline entries from scene data."""
        timeline = []
        for scene in scenes:
            timeline.append(
                {
                    "type": "scene",
                    "scene_id": scene.get("scene_id"),
                    "timestamp": scene.get("timestamp", datetime.now(UTC).isoformat()),
                    "description": scene.get("scene_label", "Scene"),
                    "data": scene,
                }
            )
        return sorted(timeline, key=lambda x: x["timestamp"])

    @staticmethod
    def find_scene_by_id(timeline: list[dict[str, Any]], scene_id: str) -> dict[str, Any] | None:
        """Find a specific scene in timeline."""
        for entry in timeline:
            if entry.get("type") == "scene" and entry.get("scene_id") == scene_id:
                return entry
        return None

    @staticmethod
    def get_scenes_in_range(timeline: list[dict[str, Any]], start_time: str, end_time: str) -> list[dict[str, Any]]:
        """Get scenes within a time range."""
        scenes = []
        for entry in timeline:
            if entry.get("type") == "scene":
                entry_time = entry.get("timestamp", "")
                if start_time <= entry_time <= end_time:
                    scenes.append(entry)
        return scenes

    @staticmethod
    def create_rollback_point(timeline: list[dict[str, Any]], description: str = None) -> dict[str, Any]:
        """Create a rollback point from current timeline state."""
        return {
            "type": "rollback_point",
            "timestamp": datetime.now(UTC).isoformat(),
            "description": description or "Manual rollback point",
            "timeline_snapshot": timeline.copy(),
            "scene_count": len([e for e in timeline if e.get("type") == "scene"]),
        }


class TemporalStateManager:
    """Shared temporal state management utilities."""

    @staticmethod
    def validate_timeline_entry(entry: dict[str, Any]) -> bool:
        """Validate timeline entry structure."""
        required_fields = ["type", "timestamp"]
        return all(field in entry for field in required_fields)

    @staticmethod
    def normalize_timestamp(timestamp: str) -> str:
        """Normalize timestamp to ISO format."""
        try:
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            dt = datetime.fromisoformat(timestamp)
            return dt.isoformat()
        except (ValueError, TypeError):
            return datetime.now(UTC).isoformat()
        except (AttributeError, OSError):
            return datetime.now(UTC).isoformat()
        except Exception:
            return datetime.now(UTC).isoformat()

    @staticmethod
    def calculate_timeline_gaps(entries: list[dict[str, Any]], max_gap_hours: int = 24) -> list[dict[str, Any]]:
        """Identify significant gaps in timeline."""
        if len(entries) < 2:
            return []

        gaps = []
        for i in range(1, len(entries)):
            prev_entry = entries[i - 1]
            curr_entry = entries[i]

            try:
                prev_time = datetime.fromisoformat(prev_entry["timestamp"])
                curr_time = datetime.fromisoformat(curr_entry["timestamp"])
                gap_hours = (curr_time - prev_time).total_seconds() / 3600

                if gap_hours > max_gap_hours:
                    gaps.append(
                        {
                            "start_entry": prev_entry,
                            "end_entry": curr_entry,
                            "gap_hours": gap_hours,
                            "gap_type": "significant" if gap_hours > 72 else "moderate",
                        }
                    )
            except (ValueError, TypeError):
                continue
            except (KeyError, AttributeError):
                continue
            except Exception:
                continue

        return gaps


class CheckpointPatterns:
    """Common checkpoint and rollback patterns."""

    @staticmethod
    def should_auto_checkpoint(scene_count: int, interval: int = 10) -> bool:
        """Determine if automatic checkpoint should be created."""
        return scene_count > 0 and scene_count % interval == 0

    @staticmethod
    def generate_checkpoint_description(scene_data: dict[str, Any]) -> str:
        """Generate automatic description for checkpoint."""
        scene_input = scene_data.get("input", "")
        if len(scene_input) > 50:
            return f"Auto-checkpoint: {scene_input[:50]}..."
        return f"Auto-checkpoint: {scene_input}"

    @staticmethod
    def prioritize_checkpoints(
        checkpoints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Prioritize checkpoints by importance for retention."""
        # Sort by age and usage patterns
        return sorted(
            checkpoints,
            key=lambda x: (
                x.get("usage_count", 0),
                -x.get("age_hours", 0),  # Negative to prefer recent
            ),
            reverse=True,
        )


class HistoryUtilities:
    """History tracking and analysis utilities."""

    @staticmethod
    def extract_narrative_arc(timeline_entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract basic narrative arc from timeline."""
        scene_entries = [e for e in timeline_entries if e.get("type") == "scene"]

        if len(scene_entries) < 3:
            return {"arc_type": "insufficient_data", "scenes": len(scene_entries)}

        # Simple arc analysis
        beginning = scene_entries[: len(scene_entries) // 3]
        middle = scene_entries[len(scene_entries) // 3 : 2 * len(scene_entries) // 3]
        end = scene_entries[2 * len(scene_entries) // 3 :]

        return {
            "arc_type": "three_act",
            "beginning": {
                "scene_count": len(beginning),
                "start_time": beginning[0]["timestamp"] if beginning else None,
            },
            "middle": {
                "scene_count": len(middle),
                "complexity": len(middle) / len(scene_entries),
            },
            "end": {
                "scene_count": len(end),
                "end_time": end[-1]["timestamp"] if end else None,
            },
            "total_scenes": len(scene_entries),
        }

    @staticmethod
    def detect_story_phases(
        timeline_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect distinct phases in story progression."""
        scene_entries = [e for e in timeline_entries if e.get("type") == "scene"]

        phases = []
        phase_size = max(3, len(scene_entries) // 5)  # At least 3 scenes per phase

        for i in range(0, len(scene_entries), phase_size):
            phase_scenes = scene_entries[i : i + phase_size]
            if phase_scenes:
                phases.append(
                    {
                        "phase_number": len(phases) + 1,
                        "start_scene": phase_scenes[0]["scene_id"],
                        "end_scene": phase_scenes[-1]["scene_id"],
                        "scene_count": len(phase_scenes),
                        "timespan": {
                            "start": phase_scenes[0]["timestamp"],
                            "end": phase_scenes[-1]["timestamp"],
                        },
                    }
                )

        return phases
