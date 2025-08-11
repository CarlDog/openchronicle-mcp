"""
Character Consistency Component

Specialized component for maintaining character trait consistency, motivation anchoring,
and behavioral validation. Extracted from character_consistency_engine.py.
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Tuple

from ..character_base import CharacterEngineBase, CharacterValidationProvider
from ..character_data import (
    CharacterData,
    CharacterMotivationAnchor,
    CharacterConsistencyViolation,
    CharacterConsistencyProfile,
    CharacterConsistencyLevel,
    CharacterViolationType,
)

logger = logging.getLogger(__name__)


class ConsistencyValidationEngine(CharacterEngineBase, CharacterValidationProvider):
    """
    Maintains character consistency through motivation anchoring, trait locking,
    and behavioral auditing across long narratives.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the consistency validation engine."""
        super().__init__(config)

        # Configuration
        self.strict_mode = self.config.get("strict_mode", False)
        self.violation_threshold = self.config.get("violation_threshold", 3)
        self.consistency_decay_rate = self.config.get("consistency_decay_rate", 0.01)
        self.auto_lock_traits = self.config.get("auto_lock_traits", True)

        # Tracking data
        self.behavioral_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.emotional_states: Dict[str, Dict[str, Any]] = {}

        self.logger.info("Consistency validation engine initialized")

    def initialize_character(
        self, character_id: str, **kwargs
    ) -> CharacterConsistencyProfile:
        """Initialize character consistency profile."""
        if character_id in self.character_data:
            return self.character_data[character_id]

        # Create new consistency profile
        profile = CharacterConsistencyProfile(
            character_id=character_id,
            consistency_level=CharacterConsistencyLevel.MODERATE,
        )

        # Process any provided character data
        character_data = kwargs.get("character_data", {})
        if character_data:
            self._process_character_data(character_id, character_data, profile)

        self.character_data[character_id] = profile
        self.behavioral_patterns[character_id] = []
        self.emotional_states[character_id] = {}

        return profile

    def get_character_data(
        self, character_id: str
    ) -> Optional[CharacterConsistencyProfile]:
        """Get character consistency profile."""
        return self.character_data.get(character_id)

    def load_character_consistency_data(self, story_path: str) -> None:
        """Load character consistency data from story characters."""
        characters_dir = os.path.join(story_path, "characters")

        if not os.path.exists(characters_dir):
            return

        for char_file in os.listdir(characters_dir):
            if char_file.endswith(".json"):
                char_name = char_file[:-5]  # Remove .json
                char_path = os.path.join(characters_dir, char_file)

                try:
                    with open(char_path, "r", encoding="utf-8") as f:
                        char_data = json.load(f)

                    profile = self.get_character_data(char_name)
                    if not profile:
                        profile = self.initialize_character(
                            char_name, character_data=char_data
                        )
                    else:
                        self._process_character_data(char_name, char_data, profile)

                    self.logger.info(f"Loaded consistency data for {char_name}")

                except Exception as e:
                    self.logger.error(
                        f"Failed to load character consistency data for {char_name}: {e}"
                    )

    # =============================================================================
    # Motivation Anchoring
    # =============================================================================

    def add_motivation_anchor(
        self,
        character_id: str,
        motivation_type: str,
        description: str,
        strength: float = 0.8,
        locked: bool = False,
    ) -> str:
        """Add motivation anchor for character."""
        profile = self.get_character_data(character_id)
        if not profile:
            profile = self.initialize_character(character_id)

        anchor = CharacterMotivationAnchor(
            anchor_id=f"{character_id}_{motivation_type}_{len(profile.motivation_anchors)}",
            character_id=character_id,
            motivation_type=motivation_type,
            description=description,
            strength=strength,
            locked=locked,
        )

        profile.motivation_anchors.append(anchor)

        self.logger.info(
            f"Added motivation anchor for {character_id}: {motivation_type}"
        )
        return anchor.anchor_id

    def remove_motivation_anchor(self, character_id: str, anchor_id: str) -> bool:
        """Remove motivation anchor if not locked."""
        profile = self.get_character_data(character_id)
        if not profile:
            return False

        for anchor in profile.motivation_anchors:
            if anchor.anchor_id == anchor_id:
                if anchor.locked:
                    self.logger.warning(f"Cannot remove locked anchor {anchor_id}")
                    return False

                profile.motivation_anchors.remove(anchor)
                return True

        return False

    def get_character_motivations(
        self, character_id: str
    ) -> List[CharacterMotivationAnchor]:
        """Get all motivation anchors for character."""
        profile = self.get_character_data(character_id)
        return profile.motivation_anchors if profile else []

    # =============================================================================
    # Trait Locking
    # =============================================================================

    def lock_trait(self, character_id: str, trait_name: str) -> bool:
        """Lock a character trait to prevent changes."""
        profile = self.get_character_data(character_id)
        if not profile:
            profile = self.initialize_character(character_id)

        profile.locked_traits.add(trait_name)
        self.logger.info(f"Locked trait '{trait_name}' for {character_id}")
        return True

    def unlock_trait(self, character_id: str, trait_name: str) -> bool:
        """Unlock a character trait."""
        profile = self.get_character_data(character_id)
        if not profile:
            return False

        if trait_name in profile.locked_traits:
            profile.locked_traits.remove(trait_name)
            self.logger.info(f"Unlocked trait '{trait_name}' for {character_id}")
            return True

        return False

    def is_trait_locked(self, character_id: str, trait_name: str) -> bool:
        """Check if trait is locked."""
        profile = self.get_character_data(character_id)
        return trait_name in profile.locked_traits if profile else False

    # =============================================================================
    # Violation Tracking
    # =============================================================================

    def record_violation(
        self,
        character_id: str,
        violation_type: CharacterViolationType,
        description: str,
        severity: float = 0.5,
        scene_context: str = "",
    ) -> str:
        """Record a consistency violation."""
        profile = self.get_character_data(character_id)
        if not profile:
            profile = self.initialize_character(character_id)

        violation = CharacterConsistencyViolation(
            violation_id=f"{character_id}_{len(profile.violation_history)}",
            character_id=character_id,
            violation_type=violation_type,
            description=description,
            severity=severity,
            scene_context=scene_context,
        )

        profile.violation_history.append(violation)

        # Update consistency score
        self._update_consistency_score(profile, -severity * 0.1)

        self.logger.warning(f"Recorded violation for {character_id}: {description}")
        return violation.violation_id

    def resolve_violation(self, character_id: str, violation_id: str) -> bool:
        """Mark violation as resolved."""
        profile = self.get_character_data(character_id)
        if not profile:
            return False

        for violation in profile.violation_history:
            if violation.violation_id == violation_id:
                violation.resolved = True
                # Slight consistency score recovery
                self._update_consistency_score(profile, 0.05)
                return True

        return False

    def get_unresolved_violations(
        self, character_id: str
    ) -> List[CharacterConsistencyViolation]:
        """Get unresolved violations for character."""
        profile = self.get_character_data(character_id)
        if not profile:
            return []

        return [v for v in profile.violation_history if not v.resolved]

    # =============================================================================
    # Validation Provider Interface
    # =============================================================================

    def validate_character_action(
        self, character_id: str, action: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate if action is consistent with character."""
        profile = self.get_character_data(character_id)
        if not profile:
            return True, None  # No profile to validate against

        action_type = action.get("type", "")

        # Check trait locks
        if action_type == "trait_change":
            trait_name = action.get("trait_name", "")
            if self.is_trait_locked(character_id, trait_name):
                return False, f"Trait '{trait_name}' is locked and cannot be changed"

        # Check motivation conflicts
        if action_type == "motivation_change":
            return self._validate_motivation_change(profile, action)

        # Check behavioral consistency
        if action_type == "behavior":
            return self._validate_behavioral_consistency(profile, action)

        # Check emotional consistency
        if action_type == "emotion_change":
            return self._validate_emotional_consistency(profile, action)

        return True, None

    def get_consistency_score(self, character_id: str) -> float:
        """Get character consistency score."""
        profile = self.get_character_data(character_id)
        return profile.consistency_score if profile else 1.0

    # =============================================================================
    # Behavioral Pattern Analysis
    # =============================================================================

    def add_behavioral_pattern(
        self, character_id: str, pattern: Dict[str, Any]
    ) -> None:
        """Add behavioral pattern observation."""
        if character_id not in self.behavioral_patterns:
            self.behavioral_patterns[character_id] = []

        pattern["timestamp"] = pattern.get("timestamp", str(datetime.now()))
        self.behavioral_patterns[character_id].append(pattern)

        # Limit pattern history
        if len(self.behavioral_patterns[character_id]) > 100:
            self.behavioral_patterns[character_id] = self.behavioral_patterns[
                character_id
            ][-100:]

    def analyze_behavioral_drift(self, character_id: str) -> Dict[str, Any]:
        """Analyze behavioral drift over time."""
        patterns = self.behavioral_patterns.get(character_id, [])
        if len(patterns) < 2:
            return {"drift_detected": False, "confidence": 0.0}

        # Simple analysis - check for major changes in recent patterns
        recent_patterns = patterns[-10:]  # Last 10 patterns
        older_patterns = patterns[-20:-10] if len(patterns) >= 20 else patterns[:-10]

        if not older_patterns:
            return {"drift_detected": False, "confidence": 0.0}

        # Compare pattern keywords/themes
        recent_themes = self._extract_pattern_themes(recent_patterns)
        older_themes = self._extract_pattern_themes(older_patterns)

        # Calculate similarity
        similarity = self._calculate_theme_similarity(recent_themes, older_themes)
        drift_detected = similarity < 0.6  # Threshold for significant drift

        return {
            "drift_detected": drift_detected,
            "confidence": 1.0 - similarity,
            "recent_themes": recent_themes,
            "older_themes": older_themes,
            "similarity_score": similarity,
        }

    # =============================================================================
    # Data Management
    # =============================================================================

    def export_character_data(self, character_id: str) -> Dict[str, Any]:
        """Export character consistency data."""
        profile = self.get_character_data(character_id)
        if not profile:
            return {}

        return {
            "character_id": character_id,
            "consistency_profile": profile.to_dict(),
            "behavioral_patterns": self.behavioral_patterns.get(character_id, []),
            "emotional_states": self.emotional_states.get(character_id, {}),
            "component": "consistency",
            "version": "1.0",
        }

    def import_character_data(self, character_data: Dict[str, Any]) -> None:
        """Import character consistency data."""
        character_id = character_data.get("character_id")
        if not character_id:
            return

        try:
            # Import consistency profile
            if character_data.get("consistency_profile"):
                profile_data = character_data["consistency_profile"]
                profile = CharacterConsistencyProfile.from_dict(profile_data)
                self.character_data[character_id] = profile

            # Import behavioral patterns
            self.behavioral_patterns[character_id] = character_data.get(
                "behavioral_patterns", []
            )

            # Import emotional states
            self.emotional_states[character_id] = character_data.get(
                "emotional_states", {}
            )

            self.logger.info(f"Imported consistency data for character {character_id}")

        except Exception as e:
            self.logger.error(
                f"Failed to import consistency data for {character_id}: {e}"
            )

    # =============================================================================
    # Private Helper Methods
    # =============================================================================

    def _process_character_data(
        self,
        char_name: str,
        char_data: Dict[str, Any],
        profile: CharacterConsistencyProfile,
    ) -> None:
        """Process character data to extract consistency requirements."""
        # Process emotional profile for anchors
        emotional_profile = char_data.get("emotional_profile", {})
        if emotional_profile:
            self._create_emotional_anchors(char_name, emotional_profile, profile)

        # Process character stats for trait locking
        character_stats = char_data.get("character_stats", {})
        if character_stats:
            self._create_stat_anchors(char_name, character_stats, profile)

        # Process explicit locked traits
        locked_traits = char_data.get("locked_traits", [])
        for trait in locked_traits:
            profile.locked_traits.add(trait)

        # Process motivation anchors from character data
        motivation_data = char_data.get("motivation_anchors", [])
        for anchor_data in motivation_data:
            if isinstance(anchor_data, dict):
                anchor = CharacterMotivationAnchor(
                    anchor_id=anchor_data.get(
                        "anchor_id", f"{char_name}_{len(profile.motivation_anchors)}"
                    ),
                    character_id=char_name,
                    motivation_type=anchor_data.get("motivation_type", "general"),
                    description=anchor_data.get("description", ""),
                    strength=anchor_data.get("strength", 0.8),
                    locked=anchor_data.get("locked", False),
                )
                profile.motivation_anchors.append(anchor)

    def _create_emotional_anchors(
        self,
        char_name: str,
        emotional_profile: Dict[str, Any],
        profile: CharacterConsistencyProfile,
    ) -> None:
        """Create motivation anchors from emotional profile."""
        dominant_emotions = emotional_profile.get("dominant_emotions", [])
        for emotion in dominant_emotions:
            if isinstance(emotion, str):
                self.add_motivation_anchor(
                    char_name,
                    f"emotional_{emotion}",
                    f"Character is emotionally driven by {emotion}",
                    strength=0.7,
                )

    def _create_stat_anchors(
        self,
        char_name: str,
        character_stats: Dict[str, Any],
        profile: CharacterConsistencyProfile,
    ) -> None:
        """Create motivation anchors from character stats."""
        # Auto-lock extreme stats
        if self.auto_lock_traits:
            for stat_name, value in character_stats.items():
                if isinstance(value, (int, float)):
                    if value >= 8 or value <= 2:  # Extreme values
                        profile.locked_traits.add(stat_name)

    def _update_consistency_score(
        self, profile: CharacterConsistencyProfile, change: float
    ) -> None:
        """Update consistency score with bounds checking."""
        profile.consistency_score = max(
            0.0, min(1.0, profile.consistency_score + change)
        )

    def _validate_motivation_change(
        self, profile: CharacterConsistencyProfile, action: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate motivation change against anchors."""
        new_motivation = action.get("new_motivation", "")

        # Check against locked motivation anchors
        for anchor in profile.motivation_anchors:
            if anchor.locked and anchor.strength > 0.8:
                if new_motivation.lower() != anchor.motivation_type.lower():
                    return (
                        False,
                        f"Strong motivation anchor '{anchor.motivation_type}' conflicts with new motivation",
                    )

        return True, None

    def _validate_behavioral_consistency(
        self, profile: CharacterConsistencyProfile, action: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate behavioral action consistency."""
        behavior_type = action.get("behavior_type", "")

        # Check recent behavioral patterns
        recent_violations = [
            v
            for v in profile.violation_history[-5:]
            if v.violation_type == CharacterViolationType.BEHAVIOR_INCONSISTENCY
        ]

        if len(recent_violations) >= 2:
            return False, "Too many recent behavioral inconsistencies"

        return True, None

    def _validate_emotional_consistency(
        self, profile: CharacterConsistencyProfile, action: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate emotional change consistency."""
        new_emotion = action.get("new_emotion", "")
        intensity = action.get("intensity", 0.5)

        # Check against consistency level
        if profile.consistency_level == CharacterConsistencyLevel.STRICT:
            if intensity > 0.8:  # Very intense emotions
                return (
                    False,
                    "Strict consistency mode prevents extreme emotional changes",
                )

        return True, None

    def _extract_pattern_themes(self, patterns: List[Dict[str, Any]]) -> Set[str]:
        """Extract themes from behavioral patterns."""
        themes = set()

        for pattern in patterns:
            # Extract keywords from pattern descriptions
            description = pattern.get("description", "").lower()
            action_type = pattern.get("action_type", "").lower()

            themes.add(action_type)

            # Simple keyword extraction
            keywords = [
                "aggressive",
                "friendly",
                "cautious",
                "bold",
                "analytical",
                "emotional",
            ]
            for keyword in keywords:
                if keyword in description:
                    themes.add(keyword)

        return themes

    def _calculate_theme_similarity(
        self, themes1: Set[str], themes2: Set[str]
    ) -> float:
        """Calculate similarity between two theme sets."""
        if not themes1 and not themes2:
            return 1.0
        if not themes1 or not themes2:
            return 0.0

        intersection = themes1.intersection(themes2)
        union = themes1.union(themes2)

        return len(intersection) / len(union) if union else 0.0
