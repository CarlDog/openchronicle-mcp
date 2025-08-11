"""
Voice Manager

Specialized component for managing character voice profiles and speaking patterns.
Handles voice consistency, style analysis, and prompt generation.
"""

from dataclasses import dataclass
from typing import Any

from ..shared.memory_models import CharacterMemory
from ..shared.memory_models import VoiceProfile


@dataclass
class VoiceAnalysis:
    """Analysis of character voice characteristics."""

    character_name: str
    speaking_style_consistency: float  # 0.0 to 1.0
    vocabulary_complexity: str
    dominant_traits: list[str]
    speaking_patterns_count: int
    voice_completeness: float  # How complete the voice profile is


@dataclass
class VoiceRecommendation:
    """Recommendation for voice profile improvement."""

    field: str
    suggestion: str
    priority: str  # "high", "medium", "low"
    reason: str


class VoiceManager:
    """Advanced voice profile management for characters."""

    def __init__(self):
        """Initialize voice manager."""
        self.vocabulary_levels = {
            "simple": ["basic", "everyday", "common", "plain"],
            "moderate": ["average", "normal", "standard", "typical"],
            "sophisticated": ["advanced", "complex", "refined", "articulate"],
            "archaic": ["old-fashioned", "formal", "classical", "traditional"],
            "technical": ["specialized", "scientific", "professional", "academic"],
        }

        self.common_traits = {
            "personality": [
                "confident",
                "shy",
                "aggressive",
                "gentle",
                "sarcastic",
                "optimistic",
                "pessimistic",
                "humorous",
                "serious",
                "friendly",
            ],
            "speech": [
                "eloquent",
                "rambling",
                "concise",
                "verbose",
                "stuttering",
                "melodic",
                "monotone",
                "expressive",
                "measured",
                "rapid",
            ],
            "social": [
                "formal",
                "casual",
                "respectful",
                "blunt",
                "diplomatic",
                "warm",
                "cold",
                "enthusiastic",
                "reserved",
                "charismatic",
            ],
        }

    def analyze_voice_profile(self, character: CharacterMemory) -> VoiceAnalysis:
        """Perform comprehensive voice profile analysis."""
        try:
            if not character.voice_profile:
                return VoiceAnalysis(
                    character_name=character.name,
                    speaking_style_consistency=0.0,
                    vocabulary_complexity="moderate",
                    dominant_traits=[],
                    speaking_patterns_count=0,
                    voice_completeness=0.0,
                )

            voice = character.voice_profile

            # Calculate voice completeness
            completeness = self._calculate_voice_completeness(voice)

            # Analyze vocabulary complexity
            vocab_complexity = self._analyze_vocabulary_complexity(voice)

            # Get dominant traits
            dominant_traits = self._extract_dominant_traits(voice)

            # Calculate speaking style consistency (based on how well defined it is)
            style_consistency = self._calculate_style_consistency(
                voice, character.dialogue_history
            )

            return VoiceAnalysis(
                character_name=character.name,
                speaking_style_consistency=style_consistency,
                vocabulary_complexity=vocab_complexity,
                dominant_traits=dominant_traits,
                speaking_patterns_count=len(voice.speaking_patterns),
                voice_completeness=completeness,
            )

        except Exception:
            return VoiceAnalysis(
                character_name=character.name,
                speaking_style_consistency=0.0,
                vocabulary_complexity="moderate",
                dominant_traits=[],
                speaking_patterns_count=0,
                voice_completeness=0.0,
            )

    def generate_voice_recommendations(
        self, character: CharacterMemory
    ) -> list[VoiceRecommendation]:
        """Generate recommendations for improving voice profile."""
        recommendations = []

        if not character.voice_profile:
            recommendations.append(
                VoiceRecommendation(
                    field="voice_profile",
                    suggestion="Create a voice profile for this character",
                    priority="high",
                    reason="Character has no voice profile defined",
                )
            )
            return recommendations

        voice = character.voice_profile

        # Check speaking style
        if not voice.speaking_style or len(voice.speaking_style.strip()) < 10:
            recommendations.append(
                VoiceRecommendation(
                    field="speaking_style",
                    suggestion="Add a detailed speaking style description",
                    priority="high",
                    reason="Speaking style is missing or too brief",
                )
            )

        # Check personality traits
        if len(voice.personality_traits) < 3:
            recommendations.append(
                VoiceRecommendation(
                    field="personality_traits",
                    suggestion="Add more personality traits (aim for 3-5)",
                    priority="medium",
                    reason="More traits provide better voice consistency",
                )
            )

        # Check speaking patterns
        if len(voice.speaking_patterns) < 2:
            recommendations.append(
                VoiceRecommendation(
                    field="speaking_patterns",
                    suggestion="Add specific speaking patterns or verbal tics",
                    priority="medium",
                    reason="Patterns help create distinctive speech",
                )
            )

        # Check emotional tendencies
        if len(voice.emotional_tendencies) < 2:
            recommendations.append(
                VoiceRecommendation(
                    field="emotional_tendencies",
                    suggestion="Add emotional tendencies or reaction patterns",
                    priority="low",
                    reason="Emotional patterns enhance voice authenticity",
                )
            )

        # Check for contradictions
        contradictions = self._detect_voice_contradictions(voice)
        for contradiction in contradictions:
            recommendations.append(
                VoiceRecommendation(
                    field="consistency",
                    suggestion=f"Resolve contradiction: {contradiction}",
                    priority="high",
                    reason="Contradictions reduce voice consistency",
                )
            )

        return recommendations

    def generate_voice_prompt(
        self, character: CharacterMemory, context: str = ""
    ) -> str:
        """Generate comprehensive voice prompt for AI generation."""
        if not character.voice_profile:
            return f"Character: {character.name} (no specific voice profile available)"

        voice = character.voice_profile
        prompt_parts = []

        # Character identification
        prompt_parts.append(f"Character: {character.name}")

        # Speaking style
        if voice.speaking_style:
            prompt_parts.append(f"Speaking Style: {voice.speaking_style}")

        # Vocabulary level
        if voice.vocabulary_level:
            prompt_parts.append(f"Vocabulary Level: {voice.vocabulary_level}")

        # Personality traits
        if voice.personality_traits:
            prompt_parts.append(
                f"Personality Traits: {', '.join(voice.personality_traits)}"
            )

        # Speaking patterns
        if voice.speaking_patterns:
            prompt_parts.append(
                f"Speaking Patterns: {', '.join(voice.speaking_patterns)}"
            )

        # Emotional tendencies
        if voice.emotional_tendencies:
            prompt_parts.append(
                f"Emotional Tendencies: {', '.join(voice.emotional_tendencies)}"
            )

        # Current mood context
        if character.current_mood and character.current_mood != "neutral":
            prompt_parts.append(f"Current Mood: {character.current_mood}")

        # Recent dialogue context
        if character.dialogue_history and len(character.dialogue_history) > 0:
            recent_dialogue = character.dialogue_history[-3:]  # Last 3 entries
            prompt_parts.append("Recent dialogue style reference:")
            for dialogue in recent_dialogue:
                # Remove timestamp if present
                clean_dialogue = (
                    dialogue.split("] ", 1)[-1] if "] " in dialogue else dialogue
                )
                prompt_parts.append(f'  "{clean_dialogue}"')

        # Additional context
        if context:
            prompt_parts.append(f"Context: {context}")

        return "\n".join(prompt_parts)

    def update_voice_profile(
        self, character: CharacterMemory, voice_updates: dict[str, Any]
    ) -> bool:
        """Update character voice profile with validation."""
        try:
            # Initialize voice profile if needed
            if not character.voice_profile:
                character.voice_profile = VoiceProfile()

            voice = character.voice_profile

            # Update string fields
            for field in ["speaking_style", "vocabulary_level"]:
                if field in voice_updates and voice_updates[field] is not None:
                    setattr(voice, field, str(voice_updates[field]))

            # Update list fields
            for field in [
                "personality_traits",
                "speaking_patterns",
                "emotional_tendencies",
            ]:
                if field in voice_updates and voice_updates[field] is not None:
                    new_value = voice_updates[field]

                    if isinstance(new_value, list):
                        setattr(voice, field, new_value)
                    elif isinstance(new_value, str):
                        # Handle comma-separated strings
                        value_list = [
                            item.strip()
                            for item in new_value.split(",")
                            if item.strip()
                        ]
                        setattr(voice, field, value_list)

            # Validate vocabulary level
            if voice.vocabulary_level and voice.vocabulary_level not in [
                "simple",
                "moderate",
                "sophisticated",
                "archaic",
                "technical",
            ]:
                voice.vocabulary_level = "moderate"  # Default fallback

            return True

        except Exception:
            return False

    def extract_voice_from_dialogue(
        self, dialogue_history: list[str]
    ) -> dict[str, Any]:
        """Extract voice characteristics from dialogue history."""
        if not dialogue_history:
            return {}

        # This is a simplified extraction - could be enhanced with NLP
        characteristics = {
            "speaking_patterns": [],
            "vocabulary_indicators": [],
            "emotional_indicators": [],
        }

        # Analyze dialogue for patterns
        for dialogue in dialogue_history:
            # Remove timestamps
            clean_dialogue = (
                dialogue.split("] ", 1)[-1] if "] " in dialogue else dialogue
            )

            # Look for speech patterns
            if "..." in clean_dialogue:
                characteristics["speaking_patterns"].append("uses ellipses/pauses")
            if clean_dialogue.count("!") > 1:
                characteristics["emotional_indicators"].append("exclamatory")
            if clean_dialogue.count("?") > 0:
                characteristics["speaking_patterns"].append("inquisitive")

            # Basic vocabulary analysis
            word_count = len(clean_dialogue.split())
            if word_count > 20:
                characteristics["vocabulary_indicators"].append("verbose")
            elif word_count < 5:
                characteristics["vocabulary_indicators"].append("concise")

        # Remove duplicates
        for key in characteristics:
            characteristics[key] = list(set(characteristics[key]))

        return characteristics

    def _calculate_voice_completeness(self, voice: VoiceProfile) -> float:
        """Calculate how complete the voice profile is (0.0 to 1.0)."""
        total_fields = 5
        completed_fields = 0

        # Check each field
        if voice.speaking_style and len(voice.speaking_style.strip()) > 10:
            completed_fields += 1

        if voice.vocabulary_level and voice.vocabulary_level.strip():
            completed_fields += 1

        if voice.personality_traits and len(voice.personality_traits) >= 2:
            completed_fields += 1

        if voice.speaking_patterns and len(voice.speaking_patterns) >= 1:
            completed_fields += 1

        if voice.emotional_tendencies and len(voice.emotional_tendencies) >= 1:
            completed_fields += 1

        return completed_fields / total_fields

    def _analyze_vocabulary_complexity(self, voice: VoiceProfile) -> str:
        """Analyze vocabulary complexity from voice profile."""
        if voice.vocabulary_level:
            return voice.vocabulary_level

        # Infer from other fields
        if voice.speaking_style:
            style_lower = voice.speaking_style.lower()
            for level, indicators in self.vocabulary_levels.items():
                if any(indicator in style_lower for indicator in indicators):
                    return level

        return "moderate"  # Default

    def _extract_dominant_traits(self, voice: VoiceProfile) -> list[str]:
        """Extract dominant personality traits."""
        traits = []

        if voice.personality_traits:
            # Return most significant traits (up to 3)
            traits.extend(voice.personality_traits[:3])

        # Infer traits from speaking style
        if voice.speaking_style:
            style_lower = voice.speaking_style.lower()
            for category, trait_list in self.common_traits.items():
                for trait in trait_list:
                    if trait in style_lower and trait not in traits:
                        traits.append(trait)
                        if len(traits) >= 3:
                            break
                if len(traits) >= 3:
                    break

        return traits[:3]  # Maximum 3 dominant traits

    def _calculate_style_consistency(
        self, voice: VoiceProfile, dialogue_history: list[str]
    ) -> float:
        """Calculate speaking style consistency."""
        if not voice.speaking_style:
            return 0.0

        # Base score on profile completeness
        base_score = self._calculate_voice_completeness(voice)

        # Enhance score if we have dialogue examples
        if dialogue_history and len(dialogue_history) >= 3:
            base_score = min(
                1.0, base_score + 0.2
            )  # Bonus for having dialogue examples

        return base_score

    def _detect_voice_contradictions(self, voice: VoiceProfile) -> list[str]:
        """Detect contradictions in voice profile."""
        contradictions = []

        # Check for contradictory personality traits
        if voice.personality_traits:
            traits_lower = [trait.lower() for trait in voice.personality_traits]

            # Check for obvious contradictions
            contradiction_pairs = [
                ("confident", "shy"),
                ("aggressive", "gentle"),
                ("optimistic", "pessimistic"),
                ("formal", "casual"),
                ("verbose", "concise"),
            ]

            for trait1, trait2 in contradiction_pairs:
                if trait1 in traits_lower and trait2 in traits_lower:
                    contradictions.append(f"Conflicting traits: {trait1} vs {trait2}")

        return contradictions
