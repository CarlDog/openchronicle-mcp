"""
Emotional Orchestrator

Coordinates emotional stability tracking, loop detection, and behavioral
pattern management for character emotional consistency across the system.
"""

import logging
from datetime import datetime
from typing import Any

from src.openchronicle.shared.json_utilities import JSONUtilities

from ..shared.narrative_state import NarrativeStateManager
from .mood_analyzer import MoodAnalyzer
from .stability_tracker import StabilityTracker


logger = logging.getLogger(__name__)


class EmotionalOrchestrator:
    """
    Main orchestrator for emotional stability operations.

    Coordinates emotional state tracking, loop detection, and behavioral
    pattern management to ensure character emotional consistency.
    """

    def __init__(self, config: dict | None = None):
        """Initialize emotional orchestrator with configuration."""
        self.config = config or {}
        self.json_utils = JSONUtilities()

        # Initialize components
        self.stability_tracker = StabilityTracker(config)
        self.mood_analyzer = MoodAnalyzer(config)
        storage_dir = self.config.get("storage_dir", "storage/narrative_emotional")
        self.narrative_state = NarrativeStateManager(storage_dir)

        # Configuration settings
        self.emotion_memory_limit = self.config.get("emotion_memory_limit", 50)
        self.dialogue_memory_limit = self.config.get("dialogue_memory_limit", 20)
        self.behavior_cooldown_duration = self.config.get(
            "behavior_cooldown_duration", 300
        )
        self.similarity_threshold = self.config.get("similarity_threshold", 0.8)
        self.loop_detection_threshold = self.config.get("loop_detection_threshold", 3)

        logger.info("EmotionalOrchestrator initialized")

    def track_emotional_state(
        self, character_id: str, emotion: str, intensity: float, context: str = ""
    ) -> dict[str, Any]:
        """
        Track character's emotional state and detect patterns.

        Args:
            character_id: ID of the character
            emotion: Emotion type (e.g., "happiness", "anger")
            intensity: Emotion intensity (0.0 to 1.0)
            context: Context for the emotion

        Returns:
            Dictionary with tracking results and any detected patterns
        """
        try:
            # Track emotional state
            emotional_state = {
                "emotion": emotion,
                "intensity": intensity,
                "context": context,
                "timestamp": datetime.now(),
            }

            tracking_result = self.stability_tracker.track_emotional_state(
                character_id, emotional_state
            )

            # Analyze for emotional patterns and loops
            loop_analysis = self.mood_analyzer.detect_emotional_loops(
                character_id, emotion, intensity, context
            )

            # Check for instability patterns
            stability_analysis = self.stability_tracker.analyze_stability_patterns(
                character_id
            )

            result = {
                "tracking_result": tracking_result,
                "loop_analysis": loop_analysis,
                "stability_analysis": stability_analysis,
                "emotional_state": (
                    emotional_state.__dict__
                    if hasattr(emotional_state, "__dict__")
                    else emotional_state
                ),
                "timestamp": datetime.now().isoformat(),
            }

            # Generate warnings if needed
            if loop_analysis.get("loops_detected", 0) > 0:
                result["warning"] = "Emotional loops detected - consider intervention"

            if stability_analysis.get("stability_score", 1.0) < 0.5:
                result["warning"] = "Low emotional stability detected"

            return result

        except Exception as e:
            logger.error(f"Error tracking emotional state: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def is_behavior_on_cooldown(self, character_id: str, behavior: str) -> bool:
        """
        Check if a behavior is currently on cooldown.

        Args:
            character_id: ID of the character
            behavior: Behavior to check

        Returns:
            True if behavior is on cooldown, False otherwise
        """
        return self.stability_tracker.is_behavior_on_cooldown(character_id, behavior)

    def trigger_behavior_cooldown(
        self, character_id: str, behavior: str, duration: int | None = None
    ) -> dict[str, Any]:
        """
        Trigger cooldown for a specific behavior.

        Args:
            character_id: ID of the character
            behavior: Behavior to put on cooldown
            duration: Cooldown duration in seconds (optional)

        Returns:
            Dictionary with cooldown information
        """
        cooldown_duration = duration or self.behavior_cooldown_duration

        return self.stability_tracker.trigger_behavior_cooldown(
            character_id, behavior, cooldown_duration
        )

    def detect_dialogue_similarity(self, character_id: str, new_dialogue: str) -> float:
        """
        Detect similarity with recent dialogue to prevent repetition.

        Args:
            character_id: ID of the character
            new_dialogue: New dialogue to check

        Returns:
            Similarity score (0.0 to 1.0)
        """
        return self.mood_analyzer.detect_dialogue_similarity(character_id, new_dialogue)

    def detect_emotional_loops(
        self, character_id: str, text: str
    ) -> list[dict[str, Any]]:
        """
        Detect emotional and behavioral loops in character responses.

        Args:
            character_id: ID of the character
            text: Text to analyze for loops

        Returns:
            List of detected loop patterns
        """
        return self.mood_analyzer.detect_emotional_loops(character_id, text)

    def get_emotional_context(self, character_id: str) -> dict[str, Any]:
        """
        Get current emotional context for character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with emotional context information
        """
        try:
            # Get current emotional state
            current_state = self.stability_tracker.get_current_emotional_state(
                character_id
            )

            # Get recent emotional history
            emotional_history = self.stability_tracker.get_emotional_history(
                character_id, limit=10
            )

            # Get mood analysis
            mood_analysis = self.mood_analyzer.analyze_current_mood(character_id)

            # Get behavioral status
            behavior_status = self.stability_tracker.get_cooldown_status(character_id)

            return {
                "character_id": character_id,
                "current_emotional_state": current_state,
                "recent_emotional_history": emotional_history,
                "mood_analysis": mood_analysis,
                "behavioral_status": behavior_status,
                "context_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting emotional context: {e}")
            return {"error": str(e)}

    def generate_anti_loop_prompt(
        self, character_id: str, detected_loops: list[dict[str, Any]]
    ) -> str:
        """
        Generate prompt to break detected emotional/behavioral loops.

        Args:
            character_id: ID of the character
            detected_loops: List of detected loop patterns

        Returns:
            Anti-loop prompt string
        """
        return self.mood_analyzer.generate_anti_loop_prompt(
            character_id, detected_loops
        )

    def analyze_emotional_stability(self, character_id: str) -> dict[str, Any]:
        """
        Comprehensive analysis of character's emotional stability.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with stability analysis
        """
        try:
            # Get stability metrics
            stability_score = self.stability_tracker.calculate_stability_score(
                character_id
            )

            # Get pattern analysis
            patterns = self.mood_analyzer.analyze_emotional_patterns(character_id)

            # Get loop detection summary
            loops = self.mood_analyzer.get_loop_detection_summary(character_id)

            # Get behavioral analysis
            behaviors = self.stability_tracker.analyze_behavioral_patterns(character_id)

            return {
                "character_id": character_id,
                "stability_score": stability_score,
                "emotional_patterns": patterns,
                "loop_patterns": loops,
                "behavioral_patterns": behaviors,
                "analysis_timestamp": datetime.now().isoformat(),
                "recommendations": self._generate_stability_recommendations(
                    stability_score, patterns, loops, behaviors
                ),
            }

        except Exception as e:
            logger.error(f"Error analyzing emotional stability: {e}")
            return {"error": str(e)}

    def reset_character_emotional_state(self, character_id: str) -> dict[str, Any]:
        """
        Reset character's emotional tracking (for testing/debugging).

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with reset confirmation
        """
        try:
            # Reset stability tracker
            stability_reset = self.stability_tracker.reset_character_state(character_id)

            # Reset mood analyzer
            mood_reset = self.mood_analyzer.reset_character_state(character_id)

            return {
                "character_id": character_id,
                "stability_tracker_reset": stability_reset,
                "mood_analyzer_reset": mood_reset,
                "reset_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error resetting emotional state: {e}")
            return {"error": str(e)}

    def export_emotional_data(self, character_id: str) -> dict[str, Any]:
        """
        Export emotional data for character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with exported emotional data
        """
        try:
            stability_data = self.stability_tracker.export_character_data(character_id)
            mood_data = self.mood_analyzer.export_character_data(character_id)

            return {
                "character_id": character_id,
                "export_timestamp": datetime.now().isoformat(),
                "stability_data": stability_data,
                "mood_data": mood_data,
            }

        except Exception as e:
            logger.error(f"Error exporting emotional data: {e}")
            return {"error": str(e)}

    def import_emotional_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Import emotional data for character.

        Args:
            data: Exported emotional data

        Returns:
            Dictionary with import results
        """
        try:
            character_id = data["character_id"]

            # Import stability data
            if "stability_data" in data:
                stability_result = self.stability_tracker.import_character_data(
                    data["stability_data"]
                )

            # Import mood data
            if "mood_data" in data:
                mood_result = self.mood_analyzer.import_character_data(
                    data["mood_data"]
                )

            return {
                "character_id": character_id,
                "import_timestamp": datetime.now().isoformat(),
                "stability_import": stability_result,
                "mood_import": mood_result,
            }

        except Exception as e:
            logger.error(f"Error importing emotional data: {e}")
            return {"error": str(e)}

    def _generate_stability_recommendations(
        self,
        stability_score: float,
        patterns: dict[str, Any],
        loops: dict[str, Any],
        behaviors: dict[str, Any],
    ) -> list[str]:
        """Generate recommendations for improving emotional stability."""
        recommendations = []

        if stability_score < 0.3:
            recommendations.append(
                "Critical: Consider major narrative intervention to stabilize character"
            )
        elif stability_score < 0.6:
            recommendations.append(
                "Warning: Character showing signs of emotional instability"
            )

        if loops.get("total_loops", 0) > 5:
            recommendations.append(
                "High loop count detected - implement anti-loop measures"
            )

        if patterns.get("emotional_variance", 0) > 0.8:
            recommendations.append(
                "High emotional variance - consider emotional anchoring"
            )

        if behaviors.get("cooldown_violations", 0) > 3:
            recommendations.append(
                "Frequent cooldown violations - adjust behavior timing"
            )

        if not recommendations:
            recommendations.append("Emotional stability within normal parameters")

        return recommendations

    def get_status(self) -> dict[str, Any]:
        """
        Get current status of emotional orchestrator.

        Returns:
            Dictionary with status information
        """
        return {
            "emotional_orchestrator": {
                "initialized": True,
                "emotion_memory_limit": self.emotion_memory_limit,
                "dialogue_memory_limit": self.dialogue_memory_limit,
                "behavior_cooldown_duration": self.behavior_cooldown_duration,
                "similarity_threshold": self.similarity_threshold,
                "loop_detection_threshold": self.loop_detection_threshold,
                "components": {
                    "stability_tracker": self.stability_tracker.get_status(),
                    "mood_analyzer": self.mood_analyzer.get_status(),
                    "narrative_state": self.narrative_state.get_status(),
                },
            }
        }
