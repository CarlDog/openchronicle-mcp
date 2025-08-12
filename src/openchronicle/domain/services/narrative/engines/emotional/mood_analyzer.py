"""
Mood Analyzer Component

Handles mood analysis, dialogue similarity detection, loop detection,
and emotional pattern analysis for the emotional subsystem.
"""

import logging
import re
from collections import Counter
from collections import defaultdict
from collections import deque
from datetime import datetime
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Any

from openchronicle.shared.json_utilities import JSONUtilities


logger = logging.getLogger(__name__)


class LoopDetection:
    """Represents a detected emotional/behavioral loop."""

    def __init__(
        self,
        loop_type: str,
        pattern: str,
        confidence: float,
        occurrences: int,
        first_occurrence: datetime,
        last_occurrence: datetime,
    ):
        self.loop_type = loop_type
        self.pattern = pattern
        self.confidence = confidence
        self.occurrences = occurrences
        self.first_occurrence = first_occurrence
        self.last_occurrence = last_occurrence

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "loop_type": self.loop_type,
            "pattern": self.pattern,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "first_occurrence": self.first_occurrence.isoformat(),
            "last_occurrence": self.last_occurrence.isoformat(),
        }


class MoodAnalyzer:
    """
    Analyzes mood patterns and detects emotional loops.

    Handles dialogue similarity detection, emotional pattern analysis,
    and anti-loop prompt generation for maintaining character variety.
    """

    def __init__(self, config: dict | None = None):
        """Initialize mood analyzer."""
        self.config = config or {}
        self.json_utils = JSONUtilities()

        # Character tracking data
        self.character_dialogue_history = defaultdict(lambda: deque(maxlen=20))
        self.character_emotional_patterns = defaultdict(list)
        self.detected_loops = defaultdict(list)
        self.mood_analysis_cache = defaultdict(dict)

        # Configuration
        self.dialogue_memory_limit = self.config.get("dialogue_memory_limit", 20)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.8)
        self.loop_detection_threshold = self.config.get("loop_detection_threshold", 3)
        self.pattern_window_hours = self.config.get("pattern_window_hours", 24)

        logger.info("MoodAnalyzer initialized")

    def detect_dialogue_similarity(self, character_id: str, new_dialogue: str) -> float:
        """
        Detect similarity with recent dialogue to prevent repetition.

        Args:
            character_id: ID of the character
            new_dialogue: New dialogue to check

        Returns:
            Highest similarity score (0.0 to 1.0)
        """
        try:
            dialogue_history = self.character_dialogue_history[character_id]

            if not dialogue_history:
                # Add to history and return no similarity
                dialogue_history.append(
                    {
                        "dialogue": new_dialogue,
                        "timestamp": datetime.now(),
                        "normalized": self._normalize_text(new_dialogue),
                    }
                )
                return 0.0

            normalized_new = self._normalize_text(new_dialogue)
            max_similarity = 0.0

            # Check similarity against recent dialogue
            for entry in dialogue_history:
                similarity = SequenceMatcher(
                    None, normalized_new, entry["normalized"]
                ).ratio()
                max_similarity = max(max_similarity, similarity)

            # Add new dialogue to history
            dialogue_history.append(
                {
                    "dialogue": new_dialogue,
                    "timestamp": datetime.now(),
                    "normalized": normalized_new,
                }
            )

            return max_similarity

        except Exception as e:
            logger.error(f"Error detecting dialogue similarity: {e}")
            return 0.0

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
        try:
            detected_patterns = []

            # Extract emotional indicators from text
            emotional_indicators = self._extract_emotional_indicators(text)

            # Store pattern for analysis
            pattern_entry = {
                "text": text,
                "emotional_indicators": emotional_indicators,
                "timestamp": datetime.now(),
            }

            self.character_emotional_patterns[character_id].append(pattern_entry)

            # Clean old patterns (keep within time window)
            self._clean_old_patterns(character_id)

            # Analyze for various loop types

            # 1. Emotional phrase loops
            phrase_loops = self._detect_phrase_loops(character_id, text)
            detected_patterns.extend(phrase_loops)

            # 2. Emotional state loops
            state_loops = self._detect_emotional_state_loops(
                character_id, emotional_indicators
            )
            detected_patterns.extend(state_loops)

            # 3. Behavioral pattern loops
            behavior_loops = self._detect_behavioral_loops(character_id, text)
            detected_patterns.extend(behavior_loops)

            # 4. Dialogue structure loops
            structure_loops = self._detect_dialogue_structure_loops(character_id, text)
            detected_patterns.extend(structure_loops)

            # Store detected loops
            for pattern in detected_patterns:
                loop = LoopDetection(
                    loop_type=pattern["type"],
                    pattern=pattern["pattern"],
                    confidence=pattern["confidence"],
                    occurrences=pattern["occurrences"],
                    first_occurrence=pattern["first_occurrence"],
                    last_occurrence=pattern["last_occurrence"],
                )
                self.detected_loops[character_id].append(loop)

            return [pattern for pattern in detected_patterns]

        except Exception as e:
            logger.error(f"Error detecting emotional loops: {e}")
            return []

    def analyze_current_mood(self, character_id: str) -> dict[str, Any]:
        """
        Analyze character's current mood based on recent patterns.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with mood analysis
        """
        try:
            patterns = self.character_emotional_patterns[character_id]

            if not patterns:
                return {"no_data": True, "mood": "neutral"}

            # Analyze recent patterns (last 10)
            recent_patterns = patterns[-10:] if len(patterns) >= 10 else patterns

            # Extract mood indicators
            mood_scores = defaultdict(float)
            total_indicators = 0

            for pattern in recent_patterns:
                for indicator in pattern["emotional_indicators"]:
                    emotion_type = indicator["type"]
                    intensity = indicator["intensity"]
                    mood_scores[emotion_type] += intensity
                    total_indicators += 1

            # Normalize scores
            if total_indicators > 0:
                for emotion in mood_scores:
                    mood_scores[emotion] /= total_indicators

            # Determine dominant mood
            dominant_mood = (
                max(mood_scores.items(), key=lambda x: x[1])
                if mood_scores
                else ("neutral", 0.0)
            )

            # Calculate mood stability
            mood_stability = self._calculate_mood_stability(recent_patterns)

            # Calculate mood intensity
            avg_intensity = (
                sum(mood_scores.values()) / len(mood_scores) if mood_scores else 0.0
            )

            return {
                "dominant_mood": {
                    "emotion": dominant_mood[0],
                    "intensity": dominant_mood[1],
                },
                "mood_distribution": dict(mood_scores),
                "mood_stability": mood_stability,
                "average_intensity": avg_intensity,
                "pattern_count": len(recent_patterns),
                "analysis_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing current mood: {e}")
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
        try:
            if not detected_loops:
                return ""

            prompt_parts = ["[ANTI-LOOP GUIDANCE]"]

            # Group loops by type
            loop_types = defaultdict(list)
            for loop in detected_loops:
                loop_types[loop["type"]].append(loop)

            # Generate guidance for each loop type
            for loop_type, loops in loop_types.items():
                disruption = self._get_disruption_suggestion(loop_type)
                prompt_parts.append(f"- {disruption}")

                # Add specific pattern warnings
                for loop in loops[:2]:  # Limit to top 2 loops per type
                    prompt_parts.append(
                        f"  Avoid repeating: \"{loop['pattern'][:50]}...\""
                    )

            # Add general variety guidance
            prompt_parts.extend(
                [
                    "",
                    "[VARIETY ENHANCEMENT]",
                    "- Introduce unexpected emotional nuances",
                    "- Vary sentence structure and dialogue patterns",
                    "- Express emotions through actions rather than direct statements",
                    "- Consider character growth and adaptation",
                ]
            )

            return "\n".join(prompt_parts)

        except Exception as e:
            logger.error(f"Error generating anti-loop prompt: {e}")
            return "[Error generating anti-loop guidance]"

    def analyze_emotional_patterns(self, character_id: str) -> dict[str, Any]:
        """
        Comprehensive analysis of character's emotional patterns.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with pattern analysis
        """
        try:
            patterns = self.character_emotional_patterns[character_id]
            loops = self.detected_loops[character_id]

            if not patterns:
                return {"no_patterns": True}

            # Pattern frequency analysis
            emotion_frequency = defaultdict(int)
            phrase_frequency = defaultdict(int)

            for pattern in patterns:
                for indicator in pattern["emotional_indicators"]:
                    emotion_frequency[indicator["type"]] += 1

                # Extract common phrases
                phrases = self._extract_phrases(pattern["text"])
                for phrase in phrases:
                    phrase_frequency[phrase] += 1

            # Most common patterns
            most_common_emotions = sorted(
                emotion_frequency.items(), key=lambda x: x[1], reverse=True
            )[:5]

            most_common_phrases = sorted(
                phrase_frequency.items(), key=lambda x: x[1], reverse=True
            )[:5]

            # Loop analysis
            loop_summary = self._summarize_loops(loops)

            # Temporal pattern analysis
            temporal_patterns = self._analyze_temporal_patterns(patterns)

            return {
                "total_patterns_analyzed": len(patterns),
                "emotion_frequency": dict(emotion_frequency),
                "most_common_emotions": most_common_emotions,
                "most_common_phrases": most_common_phrases,
                "loop_summary": loop_summary,
                "temporal_patterns": temporal_patterns,
                "pattern_diversity": len(emotion_frequency),
                "analysis_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing emotional patterns: {e}")
            return {"error": str(e)}

    def get_loop_detection_summary(self, character_id: str) -> dict[str, Any]:
        """
        Get summary of detected loops for character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with loop detection summary
        """
        loops = self.detected_loops[character_id]

        if not loops:
            return {"no_loops_detected": True}

        # Group by loop type
        loop_types = defaultdict(int)
        for loop in loops:
            loop_types[loop.loop_type] += 1

        # Recent loops (last 24 hours)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_loops = [loop for loop in loops if loop.last_occurrence > recent_cutoff]

        # High confidence loops
        high_confidence_loops = [loop for loop in loops if loop.confidence > 0.8]

        return {
            "total_loops_detected": len(loops),
            "loop_types": dict(loop_types),
            "recent_loops_count": len(recent_loops),
            "high_confidence_loops_count": len(high_confidence_loops),
            "most_recent_loop": loops[-1].to_dict() if loops else None,
            "summary_timestamp": datetime.now().isoformat(),
        }

    def reset_character_state(self, character_id: str) -> dict[str, Any]:
        """
        Reset character's mood analysis state.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with reset confirmation
        """
        try:
            # Clear dialogue history
            dialogue_cleared = len(self.character_dialogue_history[character_id])
            self.character_dialogue_history[character_id].clear()

            # Clear emotional patterns
            patterns_cleared = len(self.character_emotional_patterns[character_id])
            self.character_emotional_patterns[character_id].clear()

            # Clear detected loops
            loops_cleared = len(self.detected_loops[character_id])
            self.detected_loops[character_id].clear()

            # Clear analysis cache
            self.mood_analysis_cache[character_id].clear()

            return {
                "character_id": character_id,
                "dialogue_entries_cleared": dialogue_cleared,
                "patterns_cleared": patterns_cleared,
                "loops_cleared": loops_cleared,
                "reset_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error resetting character state: {e}")
            return {"error": str(e)}

    def export_character_data(self, character_id: str) -> dict[str, Any]:
        """Export character's mood analysis data."""
        try:
            dialogue_history = [
                {
                    "dialogue": entry["dialogue"],
                    "timestamp": entry["timestamp"].isoformat(),
                    "normalized": entry["normalized"],
                }
                for entry in self.character_dialogue_history[character_id]
            ]

            patterns = [
                {
                    "text": pattern["text"],
                    "emotional_indicators": pattern["emotional_indicators"],
                    "timestamp": pattern["timestamp"].isoformat(),
                }
                for pattern in self.character_emotional_patterns[character_id]
            ]

            loops = [loop.to_dict() for loop in self.detected_loops[character_id]]

            return {
                "character_id": character_id,
                "export_timestamp": datetime.now().isoformat(),
                "dialogue_history": dialogue_history,
                "emotional_patterns": patterns,
                "detected_loops": loops,
                "mood_analysis_cache": self.mood_analysis_cache[character_id],
            }

        except Exception as e:
            logger.error(f"Error exporting character data: {e}")
            return {"error": str(e)}

    def import_character_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import character's mood analysis data."""
        try:
            character_id = data["character_id"]

            # Import dialogue history
            dialogue_history = deque(maxlen=self.dialogue_memory_limit)
            for entry in data.get("dialogue_history", []):
                dialogue_history.append(
                    {
                        "dialogue": entry["dialogue"],
                        "timestamp": datetime.fromisoformat(entry["timestamp"]),
                        "normalized": entry["normalized"],
                    }
                )
            self.character_dialogue_history[character_id] = dialogue_history

            # Import emotional patterns
            patterns = []
            for pattern in data.get("emotional_patterns", []):
                patterns.append(
                    {
                        "text": pattern["text"],
                        "emotional_indicators": pattern["emotional_indicators"],
                        "timestamp": datetime.fromisoformat(pattern["timestamp"]),
                    }
                )
            self.character_emotional_patterns[character_id] = patterns

            # Import detected loops
            loops = []
            for loop_data in data.get("detected_loops", []):
                loop = LoopDetection(
                    loop_type=loop_data["loop_type"],
                    pattern=loop_data["pattern"],
                    confidence=loop_data["confidence"],
                    occurrences=loop_data["occurrences"],
                    first_occurrence=datetime.fromisoformat(
                        loop_data["first_occurrence"]
                    ),
                    last_occurrence=datetime.fromisoformat(
                        loop_data["last_occurrence"]
                    ),
                )
                loops.append(loop)
            self.detected_loops[character_id] = loops

            # Import analysis cache
            self.mood_analysis_cache[character_id] = data.get("mood_analysis_cache", {})

            return {
                "character_id": character_id,
                "import_timestamp": datetime.now().isoformat(),
                "imported_dialogue_entries": len(dialogue_history),
                "imported_patterns": len(patterns),
                "imported_loops": len(loops),
            }

        except Exception as e:
            logger.error(f"Error importing character data: {e}")
            return {"error": str(e)}

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Convert to lowercase
        normalized = text.lower()

        # Remove punctuation and extra whitespace
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)

        return normalized.strip()

    def _extract_emotional_indicators(self, text: str) -> list[dict[str, Any]]:
        """Extract emotional indicators from text."""
        indicators = []

        # Define emotional patterns
        emotion_patterns = {
            "happiness": [
                "happy",
                "joy",
                "pleased",
                "delighted",
                "cheerful",
                "smile",
                "laugh",
            ],
            "sadness": ["sad", "sorrow", "grief", "melancholy", "cry", "weep", "tears"],
            "anger": ["angry", "rage", "fury", "irritated", "mad", "furious", "livid"],
            "fear": ["afraid", "scared", "terrified", "fearful", "anxious", "worried"],
            "surprise": ["surprised", "shocked", "amazed", "astonished", "stunned"],
            "disgust": ["disgusted", "revolted", "repulsed", "sickened"],
            "love": ["love", "adore", "cherish", "affection", "fond", "dear"],
            "excitement": ["excited", "thrilled", "enthusiastic", "eager", "energetic"],
        }

        # Intensity modifiers
        intensity_modifiers = {
            "very": 1.5,
            "extremely": 2.0,
            "incredibly": 2.0,
            "absolutely": 1.8,
            "quite": 1.2,
            "rather": 1.1,
            "somewhat": 0.8,
            "slightly": 0.6,
            "a bit": 0.7,
            "a little": 0.6,
        }

        text_lower = text.lower()

        for emotion_type, keywords in emotion_patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Base intensity
                    intensity = 1.0

                    # Check for intensity modifiers
                    for modifier, multiplier in intensity_modifiers.items():
                        if modifier in text_lower:
                            intensity *= multiplier

                    # Normalize intensity to 0-1 range
                    intensity = min(intensity, 2.0) / 2.0

                    indicators.append(
                        {
                            "type": emotion_type,
                            "keyword": keyword,
                            "intensity": intensity,
                            "position": text_lower.find(keyword),
                        }
                    )

        return indicators

    def _clean_old_patterns(self, character_id: str) -> None:
        """Clean old patterns outside the time window."""
        cutoff_time = datetime.now() - timedelta(hours=self.pattern_window_hours)

        patterns = self.character_emotional_patterns[character_id]
        self.character_emotional_patterns[character_id] = [
            pattern for pattern in patterns if pattern["timestamp"] > cutoff_time
        ]

        # Also clean old loops
        loops = self.detected_loops[character_id]
        self.detected_loops[character_id] = [
            loop for loop in loops if loop.last_occurrence > cutoff_time
        ]

    def _detect_phrase_loops(
        self, character_id: str, text: str
    ) -> list[dict[str, Any]]:
        """Detect repeated phrase patterns."""
        patterns = self.character_emotional_patterns[character_id]
        loops = []

        # Extract phrases from current text
        current_phrases = self._extract_phrases(text)

        # Check against recent patterns
        for phrase in current_phrases:
            if len(phrase) < 10:  # Skip very short phrases
                continue

            occurrences = []
            for pattern in patterns:
                pattern_phrases = self._extract_phrases(pattern["text"])
                for pattern_phrase in pattern_phrases:
                    similarity = SequenceMatcher(None, phrase, pattern_phrase).ratio()
                    if similarity > self.similarity_threshold:
                        occurrences.append(pattern["timestamp"])

            if len(occurrences) >= self.loop_detection_threshold:
                loops.append(
                    {
                        "type": "phrase_repetition",
                        "pattern": phrase,
                        "confidence": min(len(occurrences) / 5.0, 1.0),
                        "occurrences": len(occurrences),
                        "first_occurrence": min(occurrences),
                        "last_occurrence": max(occurrences),
                    }
                )

        return loops

    def _detect_emotional_state_loops(
        self, character_id: str, current_indicators: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect repeated emotional state patterns."""
        patterns = self.character_emotional_patterns[character_id]
        loops = []

        if not current_indicators:
            return loops

        # Get dominant emotion from current indicators
        emotion_counts = Counter(
            [indicator["type"] for indicator in current_indicators]
        )
        dominant_emotion = emotion_counts.most_common(1)[0][0]

        # Count recent occurrences of this dominant emotion
        recent_occurrences = []
        for pattern in patterns[-10:]:  # Check last 10 patterns
            pattern_emotions = [
                indicator["type"] for indicator in pattern["emotional_indicators"]
            ]
            if dominant_emotion in pattern_emotions:
                recent_occurrences.append(pattern["timestamp"])

        if len(recent_occurrences) >= self.loop_detection_threshold:
            loops.append(
                {
                    "type": "emotional_state_loop",
                    "pattern": f"Repeated {dominant_emotion} expressions",
                    "confidence": min(len(recent_occurrences) / 5.0, 1.0),
                    "occurrences": len(recent_occurrences),
                    "first_occurrence": min(recent_occurrences),
                    "last_occurrence": max(recent_occurrences),
                }
            )

        return loops

    def _detect_behavioral_loops(
        self, character_id: str, text: str
    ) -> list[dict[str, Any]]:
        """Detect repeated behavioral patterns."""
        patterns = self.character_emotional_patterns[character_id]
        loops = []

        # Define behavioral indicators
        behavioral_patterns = {
            "questioning": r"\?",
            "exclaiming": r"!",
            "hesitation": r"\b(um|uh|well|hmm)\b",
            "emphasis": r"[A-Z]{2,}",
            "stuttering": r"\b(\w)\1+\b",
        }

        # Extract behaviors from current text
        current_behaviors = []
        for behavior, pattern in behavioral_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                current_behaviors.append(behavior)

        # Check for behavioral loops
        for behavior in current_behaviors:
            recent_occurrences = []
            for pattern in patterns[-10:]:
                if re.search(
                    behavioral_patterns[behavior], pattern["text"], re.IGNORECASE
                ):
                    recent_occurrences.append(pattern["timestamp"])

            if len(recent_occurrences) >= self.loop_detection_threshold:
                loops.append(
                    {
                        "type": "behavioral_pattern_loop",
                        "pattern": f"Repeated {behavior} behavior",
                        "confidence": min(len(recent_occurrences) / 5.0, 1.0),
                        "occurrences": len(recent_occurrences),
                        "first_occurrence": min(recent_occurrences),
                        "last_occurrence": max(recent_occurrences),
                    }
                )

        return loops

    def _detect_dialogue_structure_loops(
        self, character_id: str, text: str
    ) -> list[dict[str, Any]]:
        """Detect repeated dialogue structure patterns."""
        patterns = self.character_emotional_patterns[character_id]
        loops = []

        # Analyze sentence structure
        current_structure = self._analyze_sentence_structure(text)

        # Check against recent patterns
        structure_matches = []
        for pattern in patterns[-10:]:
            pattern_structure = self._analyze_sentence_structure(pattern["text"])
            similarity = self._calculate_structure_similarity(
                current_structure, pattern_structure
            )

            if similarity > 0.8:
                structure_matches.append(pattern["timestamp"])

        if len(structure_matches) >= self.loop_detection_threshold:
            loops.append(
                {
                    "type": "dialogue_structure_loop",
                    "pattern": f"Repeated sentence structure: {current_structure}",
                    "confidence": min(len(structure_matches) / 5.0, 1.0),
                    "occurrences": len(structure_matches),
                    "first_occurrence": min(structure_matches),
                    "last_occurrence": max(structure_matches),
                }
            )

        return loops

    def _extract_phrases(self, text: str) -> list[str]:
        """Extract meaningful phrases from text."""
        # Split by punctuation and get phrases of reasonable length
        sentences = re.split(r"[.!?]", text)
        phrases = []

        for sentence in sentences:
            sentence = sentence.strip()
            if 10 <= len(sentence) <= 100:  # Reasonable phrase length
                phrases.append(sentence)

        return phrases

    def _analyze_sentence_structure(self, text: str) -> str:
        """Analyze basic sentence structure."""
        # Simple structure analysis based on punctuation and length
        sentence_count = len(re.findall(r"[.!?]", text))
        question_count = text.count("?")
        exclamation_count = text.count("!")
        word_count = len(text.split())

        structure = f"sentences:{sentence_count},questions:{question_count},exclamations:{exclamation_count},words:{word_count}"
        return structure

    def _calculate_structure_similarity(
        self, structure1: str, structure2: str
    ) -> float:
        """Calculate similarity between sentence structures."""
        return SequenceMatcher(None, structure1, structure2).ratio()

    def _calculate_mood_stability(self, patterns: list[dict[str, Any]]) -> float:
        """Calculate mood stability from patterns."""
        if len(patterns) < 2:
            return 1.0

        # Calculate emotional variance across patterns
        emotion_scores = []
        for pattern in patterns:
            if pattern["emotional_indicators"]:
                avg_intensity = sum(
                    indicator["intensity"]
                    for indicator in pattern["emotional_indicators"]
                ) / len(pattern["emotional_indicators"])
                emotion_scores.append(avg_intensity)

        if not emotion_scores:
            return 1.0

        # Calculate variance
        mean_score = sum(emotion_scores) / len(emotion_scores)
        variance = sum((score - mean_score) ** 2 for score in emotion_scores) / len(
            emotion_scores
        )

        # Convert variance to stability (lower variance = higher stability)
        stability = max(0, 1 - variance)
        return stability

    def _summarize_loops(self, loops: list[LoopDetection]) -> dict[str, Any]:
        """Summarize detected loops."""
        if not loops:
            return {"no_loops": True}

        loop_types = Counter([loop.loop_type for loop in loops])
        avg_confidence = sum(loop.confidence for loop in loops) / len(loops)
        total_occurrences = sum(loop.occurrences for loop in loops)

        return {
            "total_loops": len(loops),
            "loop_types": dict(loop_types),
            "average_confidence": avg_confidence,
            "total_occurrences": total_occurrences,
            "most_recent_loop": loops[-1].to_dict() if loops else None,
        }

    def _analyze_temporal_patterns(
        self, patterns: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze temporal patterns in emotional expressions."""
        if len(patterns) < 5:
            return {"insufficient_data": True}

        # Group by hour of day
        hourly_patterns = defaultdict(list)
        for pattern in patterns:
            hour = pattern["timestamp"].hour
            hourly_patterns[hour].extend(pattern["emotional_indicators"])

        # Find peak emotional hours
        hourly_intensity = {}
        for hour, indicators in hourly_patterns.items():
            if indicators:
                avg_intensity = sum(
                    indicator["intensity"] for indicator in indicators
                ) / len(indicators)
                hourly_intensity[hour] = avg_intensity

        peak_hour = (
            max(hourly_intensity.items(), key=lambda x: x[1])
            if hourly_intensity
            else None
        )

        return {
            "hourly_patterns": dict(hourly_intensity),
            "peak_emotional_hour": peak_hour,
            "pattern_time_span": {
                "earliest": min(
                    pattern["timestamp"] for pattern in patterns
                ).isoformat(),
                "latest": max(pattern["timestamp"] for pattern in patterns).isoformat(),
            },
        }

    def _get_disruption_suggestion(self, loop_type: str) -> str:
        """Get disruption suggestion for specific loop type."""
        suggestions = {
            "phrase_repetition": "Vary your expressions and avoid repeating recent phrases",
            "emotional_state_loop": "Introduce subtle emotional shifts or mixed feelings",
            "behavioral_pattern_loop": "Change your behavioral responses and interaction style",
            "dialogue_structure_loop": "Vary sentence length, structure, and conversational approach",
        }

        return suggestions.get(loop_type, "Introduce variety in your responses")

    def get_status(self) -> dict[str, Any]:
        """Get mood analyzer status."""
        return {
            "mood_analyzer": {
                "initialized": True,
                "dialogue_memory_limit": self.dialogue_memory_limit,
                "similarity_threshold": self.similarity_threshold,
                "loop_detection_threshold": self.loop_detection_threshold,
                "pattern_window_hours": self.pattern_window_hours,
                "tracked_characters": len(self.character_dialogue_history),
                "total_dialogue_entries": sum(
                    len(dialogue)
                    for dialogue in self.character_dialogue_history.values()
                ),
                "total_patterns": sum(
                    len(patterns)
                    for patterns in self.character_emotional_patterns.values()
                ),
                "total_detected_loops": sum(
                    len(loops) for loops in self.detected_loops.values()
                ),
            }
        }
