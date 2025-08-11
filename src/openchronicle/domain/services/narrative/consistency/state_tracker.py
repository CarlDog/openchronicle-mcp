"""
State Tracker Component

Manages narrative state tracking, character development monitoring,
and consistency metrics for the consistency subsystem.
"""

import logging
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from typing import Any

from openchronicle.shared.json_utilities import JSONUtilities


logger = logging.getLogger(__name__)


class StateTracker:
    """
    Tracks narrative state and character development.

    Monitors character state changes, development progression,
    and provides consistency metrics for narrative management.
    """

    def __init__(self, config: dict | None = None):
        """Initialize state tracker."""
        self.config = config or {}
        self.json_utils = JSONUtilities()

        # Character state tracking
        self.character_states = defaultdict(dict)
        self.character_development = defaultdict(list)
        self.consistency_metrics = defaultdict(dict)

        # Configuration
        self.tracking_window_days = self.config.get("tracking_window_days", 30)
        self.development_threshold = self.config.get("development_threshold", 0.1)

        logger.info("StateTracker initialized")

    def update_character_state(self, character_id: str, memory: dict[str, Any]) -> None:
        """
        Update character state based on new memory.

        Args:
            character_id: ID of the character
            memory: Memory data that affects character state
        """
        try:
            # Update basic state information
            current_state = self.character_states[character_id]

            # Track emotional state changes
            if "emotional_score" in memory:
                self._update_emotional_state(character_id, memory["emotional_score"])

            # Track knowledge/experience accumulation
            if "memory_type" in memory:
                self._update_experience_state(character_id, memory["memory_type"])

            # Track relationship changes if applicable
            if "tags" in memory and any(
                tag in ["social", "relationship"] for tag in memory["tags"]
            ):
                self._update_relationship_state(character_id, memory)

            # Record state change timestamp
            current_state["last_updated"] = datetime.now().isoformat()

            # Update development tracking
            self._track_character_development(character_id, memory)

        except Exception as e:
            logger.error(f"Error updating character state: {e}")

    def get_character_memory_summary(self, character_id: str) -> dict[str, Any]:
        """
        Get comprehensive memory summary for character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with memory summary statistics
        """
        try:
            state = self.character_states.get(character_id, {})
            development = self.character_development.get(character_id, [])

            # Calculate memory statistics
            total_memories = state.get("total_memories", 0)
            memory_types = state.get("memory_types", {})
            emotional_range = state.get("emotional_range", {})

            # Recent activity (last 7 days)
            recent_cutoff = datetime.now() - timedelta(days=7)
            recent_activity = [
                event
                for event in development
                if datetime.fromisoformat(event["timestamp"]) > recent_cutoff
            ]

            # Development metrics
            development_score = self._calculate_development_score(character_id)
            consistency_score = self._calculate_consistency_score(character_id)

            return {
                "character_id": character_id,
                "summary_timestamp": datetime.now().isoformat(),
                "memory_statistics": {
                    "total_memories": total_memories,
                    "memory_types": memory_types,
                    "emotional_range": emotional_range,
                    "recent_activity_count": len(recent_activity),
                },
                "development_metrics": {
                    "development_score": development_score,
                    "consistency_score": consistency_score,
                    "recent_developments": (
                        recent_activity[-5:] if recent_activity else []
                    ),
                },
                "state_information": {
                    "current_emotional_state": state.get(
                        "current_emotional_state", "neutral"
                    ),
                    "dominant_memory_type": self._get_dominant_memory_type(
                        memory_types
                    ),
                    "last_updated": state.get("last_updated", "never"),
                },
            }

        except Exception as e:
            logger.error(f"Error getting memory summary: {e}")
            return {}

    def get_consistency_metrics(
        self, character_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get consistency metrics for character(s).

        Args:
            character_id: Optional specific character ID

        Returns:
            Dictionary with consistency metrics
        """
        try:
            if character_id:
                # Metrics for specific character
                return self._get_character_consistency_metrics(character_id)
            # Aggregate metrics for all characters
            all_metrics = {}
            for char_id in self.character_states.keys():
                all_metrics[char_id] = self._get_character_consistency_metrics(char_id)

            # Calculate system-wide metrics
            all_metrics["system_summary"] = self._calculate_system_consistency_metrics()
            return all_metrics

        except Exception as e:
            logger.error(f"Error getting consistency metrics: {e}")
            return {}

    def track_narrative_event(
        self, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """
        Track system-wide narrative events.

        Args:
            event_type: Type of narrative event
            event_data: Event data
        """
        try:
            # Update system metrics based on event
            if event_type == "memory_conflict":
                self._record_conflict_event(event_data)
            elif event_type == "character_development":
                self._record_development_event(event_data)
            elif event_type == "consistency_check":
                self._record_consistency_event(event_data)

        except Exception as e:
            logger.error(f"Error tracking narrative event: {e}")

    def _update_emotional_state(
        self, character_id: str, emotional_score: float
    ) -> None:
        """Update character's emotional state tracking."""
        state = self.character_states[character_id]

        # Track emotional score history
        if "emotional_history" not in state:
            state["emotional_history"] = []

        state["emotional_history"].append(
            {"score": emotional_score, "timestamp": datetime.now().isoformat()}
        )

        # Keep only recent history (last 50 entries)
        if len(state["emotional_history"]) > 50:
            state["emotional_history"] = state["emotional_history"][-50:]

        # Update current emotional state
        state["current_emotional_state"] = self._interpret_emotional_score(
            emotional_score
        )

        # Update emotional range statistics
        if "emotional_range" not in state:
            state["emotional_range"] = {
                "min": emotional_score,
                "max": emotional_score,
                "avg": emotional_score,
            }
        else:
            scores = [entry["score"] for entry in state["emotional_history"]]
            state["emotional_range"] = {
                "min": min(scores),
                "max": max(scores),
                "avg": sum(scores) / len(scores),
            }

    def _update_experience_state(self, character_id: str, memory_type: str) -> None:
        """Update character's experience and knowledge state."""
        state = self.character_states[character_id]

        # Track memory type counts
        if "memory_types" not in state:
            state["memory_types"] = defaultdict(int)

        state["memory_types"][memory_type] += 1

        # Update total memory count
        state["total_memories"] = sum(state["memory_types"].values())

        # Track experience diversity
        state["experience_diversity"] = len(state["memory_types"])

    def _update_relationship_state(
        self, character_id: str, memory: dict[str, Any]
    ) -> None:
        """Update character's relationship state tracking."""
        state = self.character_states[character_id]

        # Track relationship-related memories
        if "relationship_memories" not in state:
            state["relationship_memories"] = []

        relationship_event = {
            "content": memory.get("content", ""),
            "emotional_impact": memory.get("emotional_score", 0.0),
            "timestamp": memory.get("timestamp", datetime.now().isoformat()),
        }

        state["relationship_memories"].append(relationship_event)

        # Keep only recent relationship history
        if len(state["relationship_memories"]) > 20:
            state["relationship_memories"] = state["relationship_memories"][-20:]

    def _track_character_development(
        self, character_id: str, memory: dict[str, Any]
    ) -> None:
        """Track character development over time."""
        development = self.character_development[character_id]

        # Calculate development indicators
        development_event = {
            "timestamp": datetime.now().isoformat(),
            "memory_type": memory.get("memory_type", "unknown"),
            "emotional_impact": memory.get("emotional_score", 0.0),
            "importance": memory.get("importance", 0.5),
            "development_indicators": self._analyze_development_indicators(memory),
        }

        development.append(development_event)

        # Keep development history within tracking window
        cutoff_date = datetime.now() - timedelta(days=self.tracking_window_days)
        development[:] = [
            event
            for event in development
            if datetime.fromisoformat(event["timestamp"]) > cutoff_date
        ]

    def _analyze_development_indicators(self, memory: dict[str, Any]) -> list[str]:
        """Analyze memory for character development indicators."""
        indicators = []

        content = memory.get("content", "").lower()
        memory_type = memory.get("memory_type", "")
        emotional_score = memory.get("emotional_score", 0.0)

        # Learning indicators
        if any(
            word in content
            for word in ["learned", "discovered", "realized", "understood"]
        ):
            indicators.append("learning")

        # Growth indicators
        if any(
            word in content
            for word in ["overcome", "achieved", "succeeded", "improved"]
        ):
            indicators.append("growth")

        # Relationship indicators
        if any(word in content for word in ["friend", "ally", "trust", "bond"]):
            indicators.append("relationship_building")

        # Conflict indicators
        if any(word in content for word in ["conflict", "fight", "argue", "disagree"]):
            indicators.append("conflict_experience")

        # Emotional development
        if abs(emotional_score) > 0.7:
            indicators.append("emotional_growth")

        # Memory type-specific indicators
        if memory_type in ["action_consequence", "emotional_reaction"]:
            indicators.append("experiential_learning")

        return indicators

    def _calculate_development_score(self, character_id: str) -> float:
        """Calculate character development score."""
        development = self.character_development.get(character_id, [])

        if not development:
            return 0.0

        # Count unique development indicators
        all_indicators = []
        for event in development:
            all_indicators.extend(event.get("development_indicators", []))

        unique_indicators = len(set(all_indicators))
        indicator_diversity = unique_indicators / max(len(all_indicators), 1)

        # Factor in emotional range and memory diversity
        state = self.character_states.get(character_id, {})
        emotional_range = state.get("emotional_range", {})
        emotional_diversity = abs(
            emotional_range.get("max", 0) - emotional_range.get("min", 0)
        )
        experience_diversity = state.get("experience_diversity", 1)

        # Combine factors
        development_score = (
            indicator_diversity * 0.4
            + min(emotional_diversity / 2, 1.0) * 0.3
            + min(experience_diversity / 10, 1.0) * 0.3
        )

        return min(development_score, 1.0)

    def _calculate_consistency_score(self, character_id: str) -> float:
        """Calculate character consistency score."""
        metrics = self.consistency_metrics.get(character_id, {})

        # Base consistency score
        base_score = 1.0

        # Reduce score for conflicts
        conflict_count = metrics.get("total_conflicts", 0)
        conflict_penalty = min(conflict_count * 0.1, 0.5)

        # Reduce score for inconsistent emotional patterns
        emotional_inconsistency = metrics.get("emotional_inconsistency", 0.0)
        emotional_penalty = emotional_inconsistency * 0.3

        # Adjust for memory validation failures
        validation_failures = metrics.get("validation_failures", 0)
        validation_penalty = min(validation_failures * 0.05, 0.3)

        consistency_score = (
            base_score - conflict_penalty - emotional_penalty - validation_penalty
        )

        return max(consistency_score, 0.0)

    def _get_character_consistency_metrics(self, character_id: str) -> dict[str, Any]:
        """Get consistency metrics for specific character."""
        metrics = self.consistency_metrics.get(character_id, {})
        development = self.character_development.get(character_id, [])

        # Recent activity analysis
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_events = [
            event
            for event in development
            if datetime.fromisoformat(event["timestamp"]) > recent_cutoff
        ]

        return {
            "character_id": character_id,
            "consistency_score": self._calculate_consistency_score(character_id),
            "development_score": self._calculate_development_score(character_id),
            "recent_activity": {
                "event_count": len(recent_events),
                "development_indicators": [
                    indicator
                    for event in recent_events
                    for indicator in event.get("development_indicators", [])
                ],
            },
            "conflict_history": {
                "total_conflicts": metrics.get("total_conflicts", 0),
                "recent_conflicts": metrics.get("recent_conflicts", 0),
                "conflict_types": metrics.get("conflict_types", {}),
            },
            "validation_metrics": {
                "total_validations": metrics.get("total_validations", 0),
                "validation_failures": metrics.get("validation_failures", 0),
                "success_rate": self._calculate_validation_success_rate(character_id),
            },
        }

    def _calculate_system_consistency_metrics(self) -> dict[str, Any]:
        """Calculate system-wide consistency metrics."""
        total_characters = len(self.character_states)

        if total_characters == 0:
            return {"total_characters": 0, "system_consistency_score": 1.0}

        # Aggregate scores
        total_consistency = sum(
            self._calculate_consistency_score(char_id)
            for char_id in self.character_states.keys()
        )
        total_development = sum(
            self._calculate_development_score(char_id)
            for char_id in self.character_states.keys()
        )

        avg_consistency = total_consistency / total_characters
        avg_development = total_development / total_characters

        # System-wide conflict analysis
        total_conflicts = sum(
            metrics.get("total_conflicts", 0)
            for metrics in self.consistency_metrics.values()
        )

        return {
            "total_characters": total_characters,
            "system_consistency_score": avg_consistency,
            "average_development_score": avg_development,
            "total_system_conflicts": total_conflicts,
            "characters_with_high_consistency": sum(
                1
                for char_id in self.character_states.keys()
                if self._calculate_consistency_score(char_id) > 0.8
            ),
            "characters_with_active_development": sum(
                1
                for char_id in self.character_states.keys()
                if self._calculate_development_score(char_id) > 0.5
            ),
        }

    def _calculate_validation_success_rate(self, character_id: str) -> float:
        """Calculate validation success rate for character."""
        metrics = self.consistency_metrics.get(character_id, {})
        total = metrics.get("total_validations", 0)
        failures = metrics.get("validation_failures", 0)

        if total == 0:
            return 1.0

        return (total - failures) / total

    def _get_dominant_memory_type(self, memory_types: dict[str, int]) -> str:
        """Get the most common memory type."""
        if not memory_types:
            return "none"

        return max(memory_types.items(), key=lambda x: x[1])[0]

    def _interpret_emotional_score(self, score: float) -> str:
        """Interpret emotional score as state description."""
        if score > 0.7:
            return "very positive"
        if score > 0.3:
            return "positive"
        if score > -0.3:
            return "neutral"
        if score > -0.7:
            return "negative"
        return "very negative"

    def _record_conflict_event(self, event_data: dict[str, Any]) -> None:
        """Record a memory conflict event."""
        character_id = event_data.get("character_id")
        if not character_id:
            return

        metrics = self.consistency_metrics[character_id]
        metrics["total_conflicts"] = metrics.get("total_conflicts", 0) + 1
        metrics["recent_conflicts"] = metrics.get("recent_conflicts", 0) + 1

        # Track conflict type
        conflict_type = event_data.get("conflict_type", "unknown")
        if "conflict_types" not in metrics:
            metrics["conflict_types"] = defaultdict(int)
        metrics["conflict_types"][conflict_type] += 1

    def _record_development_event(self, event_data: dict[str, Any]) -> None:
        """Record a character development event."""
        character_id = event_data.get("character_id")
        if not character_id:
            return

        # Development events are automatically tracked through update_character_state
        # This method can be extended for additional development tracking

    def _record_consistency_event(self, event_data: dict[str, Any]) -> None:
        """Record a consistency check event."""
        character_id = event_data.get("character_id")
        if not character_id:
            return

        metrics = self.consistency_metrics[character_id]
        metrics["total_validations"] = metrics.get("total_validations", 0) + 1

        if not event_data.get("is_consistent", True):
            metrics["validation_failures"] = metrics.get("validation_failures", 0) + 1

    def get_status(self) -> dict[str, Any]:
        """Get state tracker status."""
        return {
            "state_tracker": {
                "initialized": True,
                "tracking_window_days": self.tracking_window_days,
                "development_threshold": self.development_threshold,
                "tracked_characters": len(self.character_states),
                "total_character_events": sum(
                    len(events) for events in self.character_development.values()
                ),
            }
        }
