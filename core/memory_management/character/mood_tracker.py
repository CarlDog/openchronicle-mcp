"""
Mood Tracker

Specialized component for tracking character mood changes and emotional states.
Provides advanced mood analysis and tracking capabilities.
"""
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from ..shared.memory_models import CharacterMemory, MoodEntry, MAX_MOOD_HISTORY


@dataclass
class MoodAnalysis:
    """Analysis of character mood patterns."""
    character_name: str
    current_mood: str
    dominant_mood: str
    mood_stability: float  # 0.0 to 1.0
    mood_changes_today: int
    emotional_trend: str  # "improving", "declining", "stable"
    recent_triggers: List[str]


@dataclass
class MoodPattern:
    """Identified mood pattern."""
    pattern_type: str  # "cycle", "trigger", "stability"
    description: str
    frequency: int
    confidence: float


class MoodTracker:
    """Advanced mood tracking and analysis for characters."""
    
    def __init__(self):
        """Initialize mood tracker."""
        self.mood_categories = {
            "positive": ["happy", "excited", "content", "confident", "joyful", "optimistic"],
            "negative": ["sad", "angry", "frustrated", "anxious", "depressed", "worried"],
            "neutral": ["neutral", "calm", "focused", "contemplative"],
            "complex": ["conflicted", "bittersweet", "nostalgic", "determined"]
        }
    
    def analyze_character_mood(self, character: CharacterMemory) -> MoodAnalysis:
        """Perform comprehensive mood analysis for character."""
        try:
            if not character.mood_history:
                return MoodAnalysis(
                    character_name=character.name,
                    current_mood=character.current_mood,
                    dominant_mood=character.current_mood,
                    mood_stability=1.0,
                    mood_changes_today=0,
                    emotional_trend="stable",
                    recent_triggers=[]
                )
            
            # Calculate mood stability (less changes = more stable)
            mood_stability = self._calculate_mood_stability(character.mood_history)
            
            # Find dominant mood
            dominant_mood = self._find_dominant_mood(character.mood_history)
            
            # Count mood changes today
            mood_changes_today = self._count_mood_changes_today(character.mood_history)
            
            # Determine emotional trend
            emotional_trend = self._determine_emotional_trend(character.mood_history)
            
            # Extract recent triggers
            recent_triggers = self._extract_recent_triggers(character.mood_history)
            
            return MoodAnalysis(
                character_name=character.name,
                current_mood=character.current_mood,
                dominant_mood=dominant_mood,
                mood_stability=mood_stability,
                mood_changes_today=mood_changes_today,
                emotional_trend=emotional_trend,
                recent_triggers=recent_triggers
            )
            
        except Exception:
            # Return basic analysis on error
            return MoodAnalysis(
                character_name=character.name,
                current_mood=character.current_mood,
                dominant_mood=character.current_mood,
                mood_stability=0.5,
                mood_changes_today=0,
                emotional_trend="unknown",
                recent_triggers=[]
            )
    
    def detect_mood_patterns(self, character: CharacterMemory) -> List[MoodPattern]:
        """Detect patterns in character mood history."""
        patterns = []
        
        if not character.mood_history or len(character.mood_history) < 5:
            return patterns
        
        try:
            # Detect cyclic patterns
            cycle_pattern = self._detect_mood_cycles(character.mood_history)
            if cycle_pattern:
                patterns.append(cycle_pattern)
            
            # Detect trigger patterns
            trigger_patterns = self._detect_trigger_patterns(character.mood_history)
            patterns.extend(trigger_patterns)
            
            # Detect stability patterns
            stability_pattern = self._detect_stability_pattern(character.mood_history)
            if stability_pattern:
                patterns.append(stability_pattern)
            
        except Exception:
            pass  # Return empty patterns on error
        
        return patterns
    
    def get_mood_summary(self, character: CharacterMemory, days: int = 7) -> Dict[str, Any]:
        """Get mood summary for the last N days."""
        try:
            if not character.mood_history:
                return {
                    "character_name": character.name,
                    "current_mood": character.current_mood,
                    "total_entries": 0,
                    "mood_distribution": {},
                    "average_mood_category": "neutral",
                    "most_common_triggers": []
                }
            
            # Filter mood history to last N days
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            recent_moods = [
                mood for mood in character.mood_history 
                if mood.timestamp > cutoff_date
            ]
            
            if not recent_moods:
                recent_moods = character.mood_history[-10:]  # At least last 10 entries
            
            # Calculate mood distribution
            mood_counts = defaultdict(int)
            trigger_counts = defaultdict(int)
            
            for mood in recent_moods:
                mood_counts[mood.mood] += 1
                if mood.reason:
                    trigger_counts[mood.reason] += 1
            
            # Get most common mood
            most_common_mood = max(mood_counts.items(), key=lambda x: x[1])[0] if mood_counts else character.current_mood
            
            # Get average mood category
            avg_mood_category = self._categorize_mood(most_common_mood)
            
            # Get most common triggers
            most_common_triggers = sorted(
                trigger_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            return {
                "character_name": character.name,
                "current_mood": character.current_mood,
                "total_entries": len(recent_moods),
                "mood_distribution": dict(mood_counts),
                "average_mood_category": avg_mood_category,
                "most_common_triggers": [trigger for trigger, count in most_common_triggers]
            }
            
        except Exception:
            return {
                "character_name": character.name,
                "current_mood": character.current_mood,
                "total_entries": 0,
                "mood_distribution": {},
                "average_mood_category": "neutral",
                "most_common_triggers": []
            }
    
    def _calculate_mood_stability(self, mood_history: List[MoodEntry]) -> float:
        """Calculate mood stability score (0.0 to 1.0)."""
        if len(mood_history) < 2:
            return 1.0
        
        # Count mood changes
        changes = 0
        for i in range(1, len(mood_history)):
            if mood_history[i].mood != mood_history[i-1].mood:
                changes += 1
        
        # Stability = 1 - (changes / possible_changes)
        possible_changes = len(mood_history) - 1
        stability = 1.0 - (changes / possible_changes) if possible_changes > 0 else 1.0
        
        return max(0.0, min(1.0, stability))
    
    def _find_dominant_mood(self, mood_history: List[MoodEntry]) -> str:
        """Find the most frequent mood in recent history."""
        if not mood_history:
            return "neutral"
        
        # Count recent moods (last 10 entries)
        recent_moods = mood_history[-10:]
        mood_counts = defaultdict(int)
        
        for mood in recent_moods:
            mood_counts[mood.mood] += 1
        
        return max(mood_counts.items(), key=lambda x: x[1])[0] if mood_counts else "neutral"
    
    def _count_mood_changes_today(self, mood_history: List[MoodEntry]) -> int:
        """Count mood changes that happened today."""
        today = datetime.now(UTC).date()
        today_moods = [
            mood for mood in mood_history 
            if mood.timestamp.date() == today
        ]
        
        changes = 0
        for i in range(1, len(today_moods)):
            if today_moods[i].mood != today_moods[i-1].mood:
                changes += 1
        
        return changes
    
    def _determine_emotional_trend(self, mood_history: List[MoodEntry]) -> str:
        """Determine if emotional state is improving, declining, or stable."""
        if len(mood_history) < 3:
            return "stable"
        
        # Get last 5 mood entries
        recent_moods = mood_history[-5:]
        
        # Score moods (positive = higher score)
        mood_scores = []
        for mood in recent_moods:
            score = self._get_mood_score(mood.mood)
            mood_scores.append(score)
        
        # Calculate trend
        if len(mood_scores) >= 3:
            early_avg = sum(mood_scores[:2]) / 2
            late_avg = sum(mood_scores[-2:]) / 2
            
            diff = late_avg - early_avg
            
            if diff > 0.2:
                return "improving"
            elif diff < -0.2:
                return "declining"
            else:
                return "stable"
        
        return "stable"
    
    def _extract_recent_triggers(self, mood_history: List[MoodEntry]) -> List[str]:
        """Extract recent mood triggers."""
        recent_triggers = []
        
        # Get last 5 mood entries with reasons
        recent_moods = mood_history[-5:]
        for mood in recent_moods:
            if mood.reason and mood.reason not in recent_triggers:
                recent_triggers.append(mood.reason)
        
        return recent_triggers
    
    def _categorize_mood(self, mood: str) -> str:
        """Categorize mood into general category."""
        mood_lower = mood.lower()
        
        for category, moods in self.mood_categories.items():
            if mood_lower in moods:
                return category
        
        return "neutral"
    
    def _get_mood_score(self, mood: str) -> float:
        """Get numerical score for mood (-1.0 to 1.0)."""
        mood_lower = mood.lower()
        
        if mood_lower in self.mood_categories["positive"]:
            return 1.0
        elif mood_lower in self.mood_categories["negative"]:
            return -1.0
        elif mood_lower in self.mood_categories["complex"]:
            return 0.5
        else:  # neutral
            return 0.0
    
    def _detect_mood_cycles(self, mood_history: List[MoodEntry]) -> Optional[MoodPattern]:
        """Detect cyclic patterns in mood history."""
        # Simplified cycle detection - could be enhanced
        if len(mood_history) < 10:
            return None
        
        # Look for repeating sequences
        moods = [mood.mood for mood in mood_history]
        
        # Check for simple alternating patterns
        if len(set(moods[-6:])) == 2:  # Only 2 different moods in last 6 entries
            return MoodPattern(
                pattern_type="cycle",
                description="Alternating mood pattern detected",
                frequency=3,
                confidence=0.7
            )
        
        return None
    
    def _detect_trigger_patterns(self, mood_history: List[MoodEntry]) -> List[MoodPattern]:
        """Detect trigger-based patterns."""
        patterns = []
        
        # Count trigger-mood associations
        trigger_moods = defaultdict(list)
        for mood in mood_history:
            if mood.reason:
                trigger_moods[mood.reason].append(mood.mood)
        
        # Find triggers that consistently cause specific moods
        for trigger, moods in trigger_moods.items():
            if len(moods) >= 3:
                most_common_mood = max(set(moods), key=moods.count)
                if moods.count(most_common_mood) >= len(moods) * 0.7:  # 70% consistency
                    patterns.append(MoodPattern(
                        pattern_type="trigger",
                        description=f"'{trigger}' often leads to '{most_common_mood}' mood",
                        frequency=len(moods),
                        confidence=moods.count(most_common_mood) / len(moods)
                    ))
        
        return patterns
    
    def _detect_stability_pattern(self, mood_history: List[MoodEntry]) -> Optional[MoodPattern]:
        """Detect overall stability pattern."""
        stability = self._calculate_mood_stability(mood_history)
        
        if stability > 0.8:
            return MoodPattern(
                pattern_type="stability",
                description="High mood stability - character maintains consistent emotional state",
                frequency=len(mood_history),
                confidence=stability
            )
        elif stability < 0.3:
            return MoodPattern(
                pattern_type="instability",
                description="High mood volatility - character experiences frequent emotional changes",
                frequency=len(mood_history),
                confidence=1.0 - stability
            )
        
        return None
