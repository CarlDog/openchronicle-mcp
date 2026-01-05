"""
Stability Tracker Component

Manages emotional stability tracking, behavioral cooldowns, and
stability pattern analysis for the emotional subsystem.
"""

import logging
from collections import defaultdict
from collections import deque
from datetime import datetime
from datetime import timedelta
from typing import Any

from openchronicle.shared.json_utilities import JSONUtilities


logger = logging.getLogger(__name__)


class EmotionalState:
    """Represents an emotional state with timing information."""

    def __init__(
        self,
        emotion: str,
        intensity: float,
        context: str = "",
        timestamp: datetime | None = None,
    ):
        self.emotion = emotion
        self.intensity = intensity
        self.context = context
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "emotion": self.emotion,
            "intensity": self.intensity,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionalState":
        """Create from dictionary representation."""
        return cls(
            emotion=data["emotion"],
            intensity=data["intensity"],
            context=data.get("context", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class BehaviorCooldown:
    """Manages cooldown timing for specific behaviors."""

    def __init__(self, behavior: str, duration: int, timestamp: datetime | None = None):
        self.behavior = behavior
        self.duration = duration  # Duration in seconds
        self.start_time = timestamp or datetime.now()
        self.end_time = self.start_time + timedelta(seconds=duration)
        self.triggered_count = 1

    def is_on_cooldown(self) -> bool:
        """Check if behavior is still on cooldown."""
        return datetime.now() < self.end_time

    def get_remaining_cooldown(self) -> int | None:
        """Get remaining cooldown time in seconds."""
        if not self.is_on_cooldown():
            return None

        remaining = (self.end_time - datetime.now()).total_seconds()
        return max(0, int(remaining))

    def trigger_occurrence(self):
        """Record another occurrence of this behavior."""
        self.triggered_count += 1
        # Extend cooldown for repeated behaviors
        extension = min(self.triggered_count * 30, 300)  # Max 5 minute extension
        self.end_time += timedelta(seconds=extension)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "behavior": self.behavior,
            "duration": self.duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "triggered_count": self.triggered_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BehaviorCooldown":
        """Create from dictionary representation."""
        cooldown = cls(
            behavior=data["behavior"],
            duration=data["duration"],
            timestamp=datetime.fromisoformat(data["start_time"]),
        )
        cooldown.end_time = datetime.fromisoformat(data["end_time"])
        cooldown.triggered_count = data["triggered_count"]
        return cooldown


class StabilityTracker:
    """
    Tracks emotional stability and behavioral patterns.

    Manages emotional state history, behavioral cooldowns, and
    provides stability analysis for character emotional consistency.
    """

    def __init__(self, config: dict | None = None):
        """Initialize stability tracker."""
        self.config = config or {}
        self.json_utils = JSONUtilities()

        # Character tracking data
        self.character_emotions = defaultdict(lambda: deque(maxlen=50))
        self.character_behaviors = defaultdict(dict)  # behavior -> BehaviorCooldown
        self.stability_metrics = defaultdict(dict)

        # Configuration
        self.emotion_memory_limit = self.config.get("emotion_memory_limit", 50)
        self.default_cooldown_duration = self.config.get("default_cooldown_duration", 300)
        self.stability_window_hours = self.config.get("stability_window_hours", 24)

        logger.info("StabilityTracker initialized")

    def track_emotional_state(self, character_id: str, emotional_state: dict[str, Any]) -> dict[str, Any]:
        """
        Track character's emotional state.

        Args:
            character_id: ID of the character
            emotional_state: Emotional state data

        Returns:
            Dictionary with tracking results
        """
        try:
            # Create EmotionalState object
            state = EmotionalState(
                emotion=emotional_state["emotion"],
                intensity=emotional_state["intensity"],
                context=emotional_state.get("context", ""),
                timestamp=emotional_state.get("timestamp", datetime.now()),
            )

            # Add to character's emotional history
            self.character_emotions[character_id].append(state)

            # Update stability metrics
            self._update_stability_metrics(character_id)

            # Analyze for patterns
            patterns = self._analyze_emotional_patterns(character_id)

            return {
                "state_tracked": True,
                "current_stability_score": self.calculate_stability_score(character_id),
                "emotional_patterns": patterns,
                "tracking_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception("Error tracking emotional state")
            return {"error": str(e), "state_tracked": False}

    def is_behavior_on_cooldown(self, character_id: str, behavior: str) -> bool:
        """
        Check if a behavior is currently on cooldown.

        Args:
            character_id: ID of the character
            behavior: Behavior to check

        Returns:
            True if behavior is on cooldown, False otherwise
        """
        cooldowns = self.character_behaviors[character_id]

        if behavior not in cooldowns:
            return False

        cooldown = cooldowns[behavior]

        # Clean up expired cooldowns
        if not cooldown.is_on_cooldown():
            del cooldowns[behavior]
            return False

        return True

    def trigger_behavior_cooldown(
        self, character_id: str, behavior: str, duration: int | None = None
    ) -> dict[str, Any]:
        """
        Trigger cooldown for a specific behavior.

        Args:
            character_id: ID of the character
            behavior: Behavior to put on cooldown
            duration: Cooldown duration in seconds

        Returns:
            Dictionary with cooldown information
        """
        try:
            cooldown_duration = duration or self.default_cooldown_duration
            cooldowns = self.character_behaviors[character_id]

            if behavior in cooldowns:
                # Extend existing cooldown
                existing_cooldown = cooldowns[behavior]
                existing_cooldown.trigger_occurrence()

                return {
                    "cooldown_triggered": True,
                    "behavior": behavior,
                    "extended_cooldown": True,
                    "remaining_time": existing_cooldown.get_remaining_cooldown(),
                    "total_triggers": existing_cooldown.triggered_count,
                }
            # Create new cooldown
            new_cooldown = BehaviorCooldown(behavior, cooldown_duration)
            cooldowns[behavior] = new_cooldown

            return {
                "cooldown_triggered": True,
                "behavior": behavior,
                "new_cooldown": True,
                "duration": cooldown_duration,
                "end_time": new_cooldown.end_time.isoformat(),
            }

        except Exception as e:
            logger.exception("Error triggering behavior cooldown")
            return {"error": str(e), "cooldown_triggered": False}

    def get_current_emotional_state(self, character_id: str) -> dict[str, Any] | None:
        """
        Get character's current emotional state.

        Args:
            character_id: ID of the character

        Returns:
            Current emotional state or None
        """
        emotions = self.character_emotions[character_id]

        if not emotions:
            return None

        latest_emotion = emotions[-1]
        return latest_emotion.to_dict()

    def get_emotional_history(self, character_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Get character's emotional history.

        Args:
            character_id: ID of the character
            limit: Maximum number of entries to return

        Returns:
            List of emotional states
        """
        emotions = self.character_emotions[character_id]

        if limit:
            emotions = list(emotions)[-limit:]
        else:
            emotions = list(emotions)

        return [emotion.to_dict() for emotion in emotions]

    def calculate_stability_score(self, character_id: str) -> float:
        """
        Calculate emotional stability score for character.

        Args:
            character_id: ID of the character

        Returns:
            Stability score between 0.0 and 1.0
        """
        emotions = self.character_emotions[character_id]

        if len(emotions) < 3:
            return 1.0  # Not enough data, assume stable

        # Calculate intensity variance (lower variance = more stable)
        intensities = [emotion.intensity for emotion in emotions]
        mean_intensity = sum(intensities) / len(intensities)
        variance = sum((i - mean_intensity) ** 2 for i in intensities) / len(intensities)
        intensity_stability = max(0, 1 - variance)

        # Calculate emotional type consistency
        emotion_types = [emotion.emotion for emotion in emotions]
        unique_emotions = len(set(emotion_types))
        type_stability = max(0, 1 - (unique_emotions / len(emotions)))

        # Calculate temporal stability (recent vs historical patterns)
        recent_emotions = list(emotions)[-10:]  # Last 10 emotions
        if len(recent_emotions) >= 5:
            recent_variance = self._calculate_emotion_variance(recent_emotions)
            historical_variance = self._calculate_emotion_variance(list(emotions)[:-10])
            temporal_stability = max(0, 1 - abs(recent_variance - historical_variance))
        else:
            temporal_stability = 1.0

        # Combine factors
        overall_stability = intensity_stability * 0.4 + type_stability * 0.3 + temporal_stability * 0.3

        return min(max(overall_stability, 0.0), 1.0)

    def analyze_stability_patterns(self, character_id: str) -> dict[str, Any]:
        """
        Analyze stability patterns for character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with pattern analysis
        """
        try:
            emotions = self.character_emotions[character_id]

            if len(emotions) < 5:
                return {"insufficient_data": True, "emotion_count": len(emotions)}

            # Emotional trend analysis
            recent_emotions = list(emotions)[-10:]
            trend = self._analyze_emotional_trend(recent_emotions)

            # Volatility analysis
            volatility = self._calculate_emotional_volatility(list(emotions))

            # Pattern detection
            patterns = self._detect_stability_patterns(list(emotions))

            # Risk assessment
            risk_level = self._assess_stability_risk(character_id)

            return {
                "stability_score": self.calculate_stability_score(character_id),
                "emotional_trend": trend,
                "volatility": volatility,
                "detected_patterns": patterns,
                "risk_level": risk_level,
                "analysis_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception("Error analyzing stability patterns")
            return {"error": str(e)}

    def get_cooldown_status(self, character_id: str) -> dict[str, dict]:
        """
        Get current cooldown status for all behaviors.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with cooldown statuses
        """
        cooldowns = self.character_behaviors[character_id]
        status = {}

        # Clean up expired cooldowns and get status
        expired_behaviors = []
        for behavior, cooldown in cooldowns.items():
            if cooldown.is_on_cooldown():
                status[behavior] = {
                    "on_cooldown": True,
                    "remaining_time": cooldown.get_remaining_cooldown(),
                    "triggered_count": cooldown.triggered_count,
                    "end_time": cooldown.end_time.isoformat(),
                }
            else:
                expired_behaviors.append(behavior)
                status[behavior] = {
                    "on_cooldown": False,
                    "last_triggered": cooldown.start_time.isoformat(),
                    "total_triggers": cooldown.triggered_count,
                }

        # Clean up expired cooldowns
        for behavior in expired_behaviors:
            del cooldowns[behavior]

        return status

    def analyze_behavioral_patterns(self, character_id: str) -> dict[str, Any]:
        """
        Analyze behavioral patterns for character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with behavioral analysis
        """
        cooldowns = self.character_behaviors[character_id]

        if not cooldowns:
            return {"no_behavioral_data": True}

        # Behavior frequency analysis
        behavior_stats = {}
        total_triggers = 0

        for behavior, cooldown in cooldowns.items():
            behavior_stats[behavior] = {
                "total_triggers": cooldown.triggered_count,
                "first_occurrence": cooldown.start_time.isoformat(),
                "currently_on_cooldown": cooldown.is_on_cooldown(),
            }
            total_triggers += cooldown.triggered_count

        # Most frequent behaviors
        most_frequent = sorted(behavior_stats.items(), key=lambda x: x[1]["total_triggers"], reverse=True)[:5]

        return {
            "total_behaviors_tracked": len(behavior_stats),
            "total_behavior_triggers": total_triggers,
            "most_frequent_behaviors": most_frequent,
            "currently_on_cooldown_count": sum(
                1 for stats in behavior_stats.values() if stats["currently_on_cooldown"]
            ),
            "behavior_statistics": behavior_stats,
        }

    def reset_character_state(self, character_id: str) -> dict[str, Any]:
        """
        Reset character's emotional tracking state.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with reset confirmation
        """
        try:
            # Clear emotional history
            emotions_cleared = len(self.character_emotions[character_id])
            self.character_emotions[character_id].clear()

            # Clear behavioral cooldowns
            behaviors_cleared = len(self.character_behaviors[character_id])
            self.character_behaviors[character_id].clear()

            # Clear stability metrics
            self.stability_metrics[character_id].clear()

            return {
                "character_id": character_id,
                "emotions_cleared": emotions_cleared,
                "behaviors_cleared": behaviors_cleared,
                "reset_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception("Error resetting character state")
            return {"error": str(e)}

    def export_character_data(self, character_id: str) -> dict[str, Any]:
        """Export character's stability tracking data."""
        try:
            emotions = [emotion.to_dict() for emotion in self.character_emotions[character_id]]
            behaviors = {
                behavior: cooldown.to_dict() for behavior, cooldown in self.character_behaviors[character_id].items()
            }

            return {
                "character_id": character_id,
                "export_timestamp": datetime.now().isoformat(),
                "emotional_history": emotions,
                "behavioral_cooldowns": behaviors,
                "stability_metrics": self.stability_metrics[character_id],
            }

        except Exception as e:
            logger.exception("Error exporting character data")
            return {"error": str(e)}

    def import_character_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import character's stability tracking data."""
        try:
            character_id = data["character_id"]

            # Import emotional history
            emotions = deque(maxlen=self.emotion_memory_limit)
            for emotion_data in data.get("emotional_history", []):
                emotions.append(EmotionalState.from_dict(emotion_data))
            self.character_emotions[character_id] = emotions

            # Import behavioral cooldowns
            behaviors = {}
            for behavior, cooldown_data in data.get("behavioral_cooldowns", {}).items():
                behaviors[behavior] = BehaviorCooldown.from_dict(cooldown_data)
            self.character_behaviors[character_id] = behaviors

            # Import stability metrics
            self.stability_metrics[character_id] = data.get("stability_metrics", {})

            return {
                "character_id": character_id,
                "import_timestamp": datetime.now().isoformat(),
                "imported_emotions": len(emotions),
                "imported_behaviors": len(behaviors),
            }

        except Exception as e:
            logger.exception("Error importing character data")
            return {"error": str(e)}

    def _update_stability_metrics(self, character_id: str) -> None:
        """Update stability metrics for character."""
        metrics = self.stability_metrics[character_id]

        # Update timestamp
        metrics["last_updated"] = datetime.now().isoformat()

        # Update emotion count
        metrics["total_emotions_tracked"] = len(self.character_emotions[character_id])

        # Update stability score
        metrics["current_stability_score"] = self.calculate_stability_score(character_id)

    def _analyze_emotional_patterns(self, character_id: str) -> dict[str, Any]:
        """Analyze emotional patterns for character."""
        emotions = list(self.character_emotions[character_id])

        if len(emotions) < 3:
            return {"insufficient_data": True}

        # Recent emotion frequency
        recent_emotions = emotions[-10:]
        emotion_counts = {}
        for emotion in recent_emotions:
            emotion_counts[emotion.emotion] = emotion_counts.get(emotion.emotion, 0) + 1

        # Dominant emotion
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1]) if emotion_counts else None

        return {
            "recent_emotion_frequency": emotion_counts,
            "dominant_emotion": dominant_emotion[0] if dominant_emotion else None,
            "emotion_diversity": len(emotion_counts),
            "pattern_analysis_timestamp": datetime.now().isoformat(),
        }

    def _calculate_emotion_variance(self, emotions: list[EmotionalState]) -> float:
        """Calculate variance in emotional intensity."""
        if not emotions:
            return 0.0

        intensities = [emotion.intensity for emotion in emotions]
        mean = sum(intensities) / len(intensities)
        variance = sum((i - mean) ** 2 for i in intensities) / len(intensities)
        return variance

    def _analyze_emotional_trend(self, emotions: list[EmotionalState]) -> str:
        """Analyze trend in recent emotions."""
        if len(emotions) < 3:
            return "insufficient_data"

        intensities = [emotion.intensity for emotion in emotions]

        # Simple trend analysis
        first_half = intensities[: len(intensities) // 2]
        second_half = intensities[len(intensities) // 2 :]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg + 0.1:
            return "improving"
        if second_avg < first_avg - 0.1:
            return "declining"
        return "stable"

    def _calculate_emotional_volatility(self, emotions: list[EmotionalState]) -> float:
        """Calculate emotional volatility."""
        if len(emotions) < 2:
            return 0.0

        # Calculate intensity changes between consecutive emotions
        changes = []
        for i in range(1, len(emotions)):
            change = abs(emotions[i].intensity - emotions[i - 1].intensity)
            changes.append(change)

        return sum(changes) / len(changes) if changes else 0.0

    def _detect_stability_patterns(self, emotions: list[EmotionalState]) -> list[str]:
        """Detect specific stability patterns."""
        patterns = []

        if len(emotions) < 5:
            return patterns

        # Oscillation pattern
        intensities = [emotion.intensity for emotion in emotions[-10:]]
        if self._is_oscillating(intensities):
            patterns.append("oscillating_emotions")

        # Monotonic trends
        if all(intensities[i] <= intensities[i + 1] for i in range(len(intensities) - 1)):
            patterns.append("consistently_improving")
        elif all(intensities[i] >= intensities[i + 1] for i in range(len(intensities) - 1)):
            patterns.append("consistently_declining")

        # High variance
        variance = self._calculate_emotion_variance(emotions[-10:])
        if variance > 0.5:
            patterns.append("high_emotional_variance")

        return patterns

    def _is_oscillating(self, values: list[float]) -> bool:
        """Check if values show oscillating pattern."""
        if len(values) < 4:
            return False

        direction_changes = 0
        for i in range(2, len(values)):
            prev_direction = values[i - 1] - values[i - 2]
            curr_direction = values[i] - values[i - 1]

            if (prev_direction > 0 and curr_direction < 0) or (prev_direction < 0 and curr_direction > 0):
                direction_changes += 1

        # Consider oscillating if more than half the intervals show direction changes
        return direction_changes > len(values) / 2

    def _assess_stability_risk(self, character_id: str) -> str:
        """Assess stability risk level."""
        stability_score = self.calculate_stability_score(character_id)

        if stability_score < 0.3:
            return "high_risk"
        if stability_score < 0.6:
            return "moderate_risk"
        return "low_risk"

    def get_status(self) -> dict[str, Any]:
        """Get stability tracker status."""
        return {
            "stability_tracker": {
                "initialized": True,
                "emotion_memory_limit": self.emotion_memory_limit,
                "default_cooldown_duration": self.default_cooldown_duration,
                "stability_window_hours": self.stability_window_hours,
                "tracked_characters": len(self.character_emotions),
                "total_emotional_states": sum(len(emotions) for emotions in self.character_emotions.values()),
                "active_cooldowns": sum(len(behaviors) for behaviors in self.character_behaviors.values()),
            }
        }
