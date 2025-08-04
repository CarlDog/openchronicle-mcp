"""
Emotional Stability Engine: Gratification Loop Protection

This module ensures characters remain emotionally dynamic and avoid
falling into repetitive patterns like constant flirtation, neediness,
or praise-seeking behaviors. It implements cooldown timers, similarity
detection, and dynamic disruption patterns.

Key Features:
- Emotional history tracking per character
- Repetitive behavior detection and prevention
- Cooldown timers for emotional states
- Anti-loop prompt injection patterns
- Configurable tolerance levels
- Integration with existing character and memory systems
"""

import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Tuple, Union
from difflib import SequenceMatcher
import logging
import re

# Setup logging
logger = logging.getLogger(__name__)

@dataclass
class EmotionalState:
    """Represents a character's emotional state at a point in time."""
    emotion: str  # Primary emotion (flirty, vulnerable, angry, etc.)
    intensity: float  # 0.0 to 1.0
    timestamp: datetime
    context: str  # Brief description of what triggered this state
    duration: Optional[float] = None  # How long this state lasted
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'emotion': self.emotion,
            'intensity': self.intensity,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context,
            'duration': self.duration
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EmotionalState':
        """Create from dictionary."""
        return cls(
            emotion=data['emotion'],
            intensity=data['intensity'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            context=data['context'],
            duration=data.get('duration')
        )

@dataclass
class BehaviorCooldown:
    """Tracks cooldown timers for specific behaviors."""
    behavior: str
    last_occurrence: datetime
    cooldown_minutes: int
    occurrence_count: int = 1
    escalation_threshold: int = 3  # Number of occurrences before escalating cooldown
    
    def is_on_cooldown(self) -> bool:
        """Check if this behavior is still on cooldown."""
        cooldown_duration = timedelta(minutes=self.cooldown_minutes)
        return datetime.now() - self.last_occurrence < cooldown_duration
    
    def get_remaining_cooldown(self) -> Optional[int]:
        """Get remaining cooldown time in minutes."""
        if not self.is_on_cooldown():
            return None
        
        elapsed = datetime.now() - self.last_occurrence
        cooldown_duration = timedelta(minutes=self.cooldown_minutes)
        remaining = cooldown_duration - elapsed
        return int(remaining.total_seconds() / 60)
    
    def trigger_occurrence(self):
        """Register a new occurrence of this behavior."""
        self.last_occurrence = datetime.now()
        self.occurrence_count += 1
        
        # Escalate cooldown if behavior is happening too frequently
        if self.occurrence_count >= self.escalation_threshold:
            self.cooldown_minutes = min(self.cooldown_minutes * 2, 180)  # Max 3 hours
            self.occurrence_count = 0  # Reset counter after escalation
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'behavior': self.behavior,
            'last_occurrence': self.last_occurrence.isoformat(),
            'cooldown_minutes': self.cooldown_minutes,
            'occurrence_count': self.occurrence_count,
            'escalation_threshold': self.escalation_threshold
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BehaviorCooldown':
        """Create from dictionary."""
        return cls(
            behavior=data['behavior'],
            last_occurrence=datetime.fromisoformat(data['last_occurrence']),
            cooldown_minutes=data['cooldown_minutes'],
            occurrence_count=data['occurrence_count'],
            escalation_threshold=data['escalation_threshold']
        )

@dataclass
class LoopDetection:
    """Represents detection of a repetitive loop."""
    loop_type: str  # 'emotional', 'behavioral', 'dialogue'
    pattern: str  # Description of the detected pattern
    confidence: float  # 0.0 to 1.0
    occurrences: List[str]  # Examples of the repetitive content
    suggested_disruption: str  # Suggested way to break the loop
    severity: str = 'medium'  # 'low', 'medium', 'high'

class EmotionalStabilityEngine:
    """
    Manages character emotional states and prevents gratification loops.
    
    This engine tracks emotional history, detects repetitive patterns,
    and implements cooldown mechanisms to maintain dynamic character behavior.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the emotional stability engine."""
        self.config = config or {}
        
        # Configuration parameters
        self.similarity_threshold = self.config.get('similarity_threshold', 0.75)
        self.history_window_hours = self.config.get('history_window_hours', 24)
        self.max_emotional_states = self.config.get('max_emotional_states', 50)
        self.loop_detection_enabled = self.config.get('loop_detection_enabled', True)
        self.auto_disruption_enabled = self.config.get('auto_disruption_enabled', True)
        
        # Data storage
        self.emotional_histories: Dict[str, List[EmotionalState]] = {}
        self.behavior_cooldowns: Dict[str, Dict[str, BehaviorCooldown]] = {}
        self.recent_dialogues: Dict[str, List[Tuple[str, datetime]]] = {}
        
        # Predefined emotional behaviors and their default cooldowns
        self.default_cooldowns = {
            'flirtation': 30,      # 30 minutes
            'vulnerability': 45,    # 45 minutes  
            'praise_seeking': 20,   # 20 minutes
            'confession': 60,       # 1 hour
            'romantic_advance': 90, # 1.5 hours
            'neediness': 25,        # 25 minutes
            'jealousy': 40,         # 40 minutes
            'seduction': 120,       # 2 hours
        }
        
        # Patterns that indicate emotional loops
        self.loop_patterns = {
            'excessive_flirtation': [
                r'you\'?re\s+(so\s+)?(beautiful|gorgeous|stunning|amazing)',
                r'i\s+(can\'t\s+help\s+but\s+)?admire',
                r'your\s+(beautiful|gorgeous|stunning|amazing)?\s*(beauty|eyes|smile)',
                r'blush(es|ing)?',
                r'sultry|seductive|intimate'
            ],
            'praise_seeking': [
                r'do\s+you\s+think\s+i\'?m',
                r'am\s+i\s+(good|pretty|smart|beautiful)',
                r'tell\s+me\s+i\'?m',
                r'i\s+need\s+(to\s+know|your\s+approval)',
                r'validate|reassurance'
            ],
            'neediness': [
                r'don\'?t\s+leave\s+me',
                r'i\s+need\s+you',
                r'can\'?t\s+live\s+without',
                r'please\s+stay',
                r'clingy|desperate|needy'
            ]
        }
        
        # Disruption patterns to break loops
        self.disruption_patterns = {
            'emotional_shift': [
                "Suddenly, {character} catches herself and looks away, embarrassed by her openness.",
                "{character} stiffens slightly, as if remembering something important.",
                "A distant sound breaks {character}'s focus, shifting her attention.",
                "{character} takes a step back, creating some emotional distance."
            ],
            'external_interruption': [
                "A commotion nearby draws {character}'s attention away.",
                "The moment is interrupted by an unexpected noise.",
                "Someone approaches, forcing {character} to compose herself.",
                "A memory suddenly surfaces, changing {character}'s demeanor."
            ],
            'internal_resistance': [
                "{character} fights against the urge to say more.",
                "Something holds {character} back from continuing.",
                "{character} second-guesses herself and changes course.",
                "A flicker of doubt crosses {character}'s mind."
            ]
        }
    
    def track_emotional_state(self, character_id: str, emotion: str, 
                            intensity: float, context: str) -> None:
        """Track a new emotional state for a character."""
        if character_id not in self.emotional_histories:
            self.emotional_histories[character_id] = []
        
        state = EmotionalState(
            emotion=emotion,
            intensity=intensity,
            timestamp=datetime.now(),
            context=context
        )
        
        self.emotional_histories[character_id].append(state)
        
        # Trim history to prevent memory bloat
        if len(self.emotional_histories[character_id]) > self.max_emotional_states:
            self.emotional_histories[character_id] = \
                self.emotional_histories[character_id][-self.max_emotional_states:]
        
        logger.debug(f"Tracked emotional state for {character_id}: {emotion} "
                    f"(intensity: {intensity}) - {context}")
    
    def is_behavior_on_cooldown(self, character_id: str, behavior: str) -> bool:
        """Check if a specific behavior is on cooldown for a character."""
        if character_id not in self.behavior_cooldowns:
            return False
        
        if behavior not in self.behavior_cooldowns[character_id]:
            return False
        
        cooldown = self.behavior_cooldowns[character_id][behavior]
        return cooldown.is_on_cooldown()
    
    def trigger_behavior_cooldown(self, character_id: str, behavior: str, 
                                cooldown_minutes: Optional[int] = None) -> None:
        """Trigger a cooldown for a specific behavior."""
        if character_id not in self.behavior_cooldowns:
            self.behavior_cooldowns[character_id] = {}
        
        if cooldown_minutes is None:
            cooldown_minutes = self.default_cooldowns.get(behavior, 30)
        
        if behavior in self.behavior_cooldowns[character_id]:
            # Update existing cooldown
            self.behavior_cooldowns[character_id][behavior].trigger_occurrence()
        else:
            # Create new cooldown
            self.behavior_cooldowns[character_id][behavior] = BehaviorCooldown(
                behavior=behavior,
                last_occurrence=datetime.now(),
                cooldown_minutes=cooldown_minutes
            )
        
        logger.debug(f"Triggered cooldown for {character_id}: {behavior} "
                    f"({cooldown_minutes} minutes)")
    
    def detect_dialogue_similarity(self, character_id: str, new_dialogue: str) -> float:
        """Detect similarity between new dialogue and recent dialogue."""
        if character_id not in self.recent_dialogues:
            self.recent_dialogues[character_id] = []
        
        # Clean and normalize dialogue for comparison
        normalized_new = self._normalize_text(new_dialogue)
        
        # Check against recent dialogues within the time window
        cutoff_time = datetime.now() - timedelta(hours=self.history_window_hours)
        recent_dialogues = [
            (dialogue, timestamp) for dialogue, timestamp in 
            self.recent_dialogues[character_id] 
            if timestamp > cutoff_time
        ]
        
        max_similarity = 0.0
        for dialogue, _ in recent_dialogues:
            normalized_dialogue = self._normalize_text(dialogue)
            similarity = SequenceMatcher(None, normalized_new, normalized_dialogue).ratio()
            max_similarity = max(max_similarity, similarity)
        
        # Store the new dialogue
        self.recent_dialogues[character_id].append((new_dialogue, datetime.now()))
        
        # Trim old dialogues
        self.recent_dialogues[character_id] = [
            (dialogue, timestamp) for dialogue, timestamp in 
            self.recent_dialogues[character_id]
            if timestamp > cutoff_time
        ]
        
        return max_similarity
    
    def detect_emotional_loops(self, character_id: str, text: str) -> List[LoopDetection]:
        """Detect various types of emotional loops in character behavior."""
        if not self.loop_detection_enabled:
            return []
        
        loops = []
        text_lower = text.lower()
        
        # Check for pattern-based loops
        for loop_type, patterns in self.loop_patterns.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matches.append(pattern)
            
            if matches:
                # Calculate confidence based on number of matching patterns
                confidence = min(len(matches) / len(patterns), 1.0)
                
                # For immediate detection (testing), create loop if patterns match
                # In production, this would check against stored pattern history
                severity = 'high' if len(matches) >= 2 else 'medium'
                
                loop = LoopDetection(
                    loop_type=loop_type,
                    pattern=f"Repetitive {loop_type.replace('_', ' ')} behavior",
                    confidence=confidence,
                    occurrences=[text],  # Current occurrence
                    suggested_disruption=self._get_disruption_suggestion(loop_type),
                    severity=severity
                )
                loops.append(loop)
        
        # Check for dialogue similarity loops
        similarity = self.detect_dialogue_similarity(character_id, text)
        if similarity >= self.similarity_threshold:
            loop = LoopDetection(
                loop_type='dialogue_repetition',
                pattern="Similar dialogue repeated",
                confidence=similarity,
                occurrences=[text],
                suggested_disruption=self._get_disruption_suggestion('dialogue_repetition'),
                severity='high' if similarity >= 0.9 else 'medium'
            )
            loops.append(loop)
        
        return loops
    
    def get_emotional_context(self, character_id: str) -> Dict:
        """Get current emotional context for a character."""
        if character_id not in self.emotional_histories:
            return {'current_state': None, 'recent_emotions': [], 'active_cooldowns': []}
        
        # Get recent emotional history
        cutoff_time = datetime.now() - timedelta(hours=self.history_window_hours)
        recent_states = [
            state for state in self.emotional_histories[character_id]
            if state.timestamp > cutoff_time
        ]
        
        # Get current emotional state (most recent)
        current_state = recent_states[-1] if recent_states else None
        
        # Get active cooldowns
        active_cooldowns = []
        if character_id in self.behavior_cooldowns:
            for behavior, cooldown in self.behavior_cooldowns[character_id].items():
                if cooldown.is_on_cooldown():
                    remaining = cooldown.get_remaining_cooldown()
                    active_cooldowns.append({
                        'behavior': behavior,
                        'remaining_minutes': remaining,
                        'occurrence_count': cooldown.occurrence_count
                    })
        
        return {
            'current_state': current_state.to_dict() if current_state else None,
            'recent_emotions': [state.emotion for state in recent_states[-5:]],
            'active_cooldowns': active_cooldowns,
            'emotional_stability_score': self._calculate_stability_score(character_id)
        }
    
    def generate_anti_loop_prompt(self, character_id: str, detected_loops: List[LoopDetection]) -> str:
        """Generate prompt injection to counter detected loops."""
        if not detected_loops:
            return ""
        
        # Sort loops by severity and confidence
        high_priority_loops = sorted(
            [loop for loop in detected_loops if loop.severity in ['high', 'medium']],
            key=lambda x: (x.severity == 'high', x.confidence),
            reverse=True
        )
        
        if not high_priority_loops:
            return ""
        
        primary_loop = high_priority_loops[0]
        disruption_type = self._determine_disruption_type(primary_loop)
        
        # Get appropriate disruption pattern
        patterns = self.disruption_patterns.get(disruption_type, 
                                               self.disruption_patterns['emotional_shift'])
        
        import random
        disruption_text = random.choice(patterns).format(character=character_id)
        
        # Create anti-loop prompt
        prompt = f"\n[EMOTIONAL_STABILITY_NOTE: {character_id} is showing signs of " \
                f"{primary_loop.loop_type.replace('_', ' ')}. To maintain emotional " \
                f"authenticity: {disruption_text} Consider introducing internal " \
                f"conflict, external distraction, or emotional complexity to avoid " \
                f"repetitive patterns.]\n"
        
        return prompt
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Remove extra whitespace, convert to lowercase
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        # Remove common punctuation that doesn't affect meaning
        normalized = re.sub(r'[.,!?;:"()]+', '', normalized)
        return normalized
    
    def _get_recent_pattern_occurrences(self, character_id: str, pattern_type: str) -> List[str]:
        """Get recent occurrences of a specific pattern type."""
        # This would ideally check against stored pattern history
        # For now, return empty list as we'd need to implement pattern storage
        return []
    
    def _get_disruption_suggestion(self, loop_type: str) -> str:
        """Get an appropriate disruption suggestion for a loop type."""
        suggestions = {
            'excessive_flirtation': 'emotional_shift',
            'praise_seeking': 'internal_resistance', 
            'neediness': 'external_interruption',
            'dialogue_repetition': 'emotional_shift'
        }
        return suggestions.get(loop_type, 'emotional_shift')
    
    def _determine_disruption_type(self, loop: LoopDetection) -> str:
        """Determine the best disruption type for a detected loop."""
        if loop.severity == 'high':
            return 'external_interruption'
        elif 'dialogue' in loop.loop_type:
            return 'emotional_shift'
        else:
            return 'internal_resistance'
    
    def _calculate_stability_score(self, character_id: str) -> float:
        """Calculate an emotional stability score for a character."""
        if character_id not in self.emotional_histories:
            return 1.0
        
        # Get recent emotional states
        cutoff_time = datetime.now() - timedelta(hours=self.history_window_hours)
        recent_states = [
            state for state in self.emotional_histories[character_id]
            if state.timestamp > cutoff_time
        ]
        
        if len(recent_states) < 2:
            return 1.0
        
        # Calculate emotional variance (higher variance = less stable)
        intensities = [state.intensity for state in recent_states]
        mean_intensity = sum(intensities) / len(intensities)
        variance = sum((x - mean_intensity) ** 2 for x in intensities) / len(intensities)
        
        # Calculate emotional diversity (more diverse = more stable)
        unique_emotions = len(set(state.emotion for state in recent_states))
        diversity_score = min(unique_emotions / 5.0, 1.0)  # Normalize to 5 different emotions
        
        # Combine factors (lower variance and higher diversity = higher stability)
        stability_score = diversity_score * (1.0 - min(variance, 1.0))
        
        return max(0.0, min(1.0, stability_score))
    
    def get_cooldown_status(self, character_id: str) -> Dict[str, Dict]:
        """Get status of all cooldowns for a character."""
        if character_id not in self.behavior_cooldowns:
            return {}
        
        status = {}
        for behavior, cooldown in self.behavior_cooldowns[character_id].items():
            status[behavior] = {
                'active': cooldown.is_on_cooldown(),
                'remaining_minutes': cooldown.get_remaining_cooldown(),
                'occurrence_count': cooldown.occurrence_count,
                'last_occurrence': cooldown.last_occurrence.isoformat()
            }
        
        return status
    
    def reset_character_data(self, character_id: str) -> None:
        """Reset all emotional data for a character."""
        if character_id in self.emotional_histories:
            del self.emotional_histories[character_id]
        if character_id in self.behavior_cooldowns:
            del self.behavior_cooldowns[character_id]
        if character_id in self.recent_dialogues:
            del self.recent_dialogues[character_id]
        
        logger.info(f"Reset emotional stability data for character: {character_id}")
    
    def export_character_data(self, character_id: str) -> Dict:
        """Export all emotional data for a character."""
        data = {}
        
        if character_id in self.emotional_histories:
            data['emotional_history'] = [
                state.to_dict() for state in self.emotional_histories[character_id]
            ]
        
        if character_id in self.behavior_cooldowns:
            data['behavior_cooldowns'] = {
                behavior: cooldown.to_dict() 
                for behavior, cooldown in self.behavior_cooldowns[character_id].items()
            }
        
        if character_id in self.recent_dialogues:
            data['recent_dialogues'] = [
                {'dialogue': dialogue, 'timestamp': timestamp.isoformat()}
                for dialogue, timestamp in self.recent_dialogues[character_id]
            ]
        
        return data
    
    def import_character_data(self, character_id: str, data: Dict) -> None:
        """Import emotional data for a character."""
        if 'emotional_history' in data:
            self.emotional_histories[character_id] = [
                EmotionalState.from_dict(state_data)
                for state_data in data['emotional_history']
            ]
        
        if 'behavior_cooldowns' in data:
            if character_id not in self.behavior_cooldowns:
                self.behavior_cooldowns[character_id] = {}
            
            for behavior, cooldown_data in data['behavior_cooldowns'].items():
                self.behavior_cooldowns[character_id][behavior] = \
                    BehaviorCooldown.from_dict(cooldown_data)
        
        if 'recent_dialogues' in data:
            self.recent_dialogues[character_id] = [
                (item['dialogue'], datetime.fromisoformat(item['timestamp']))
                for item in data['recent_dialogues']
            ]
        
        logger.info(f"Imported emotional stability data for character: {character_id}")
    
    def get_engine_stats(self) -> Dict:
        """Get overall engine statistics."""
        total_characters = len(self.emotional_histories)
        total_emotional_states = sum(
            len(history) for history in self.emotional_histories.values()
        )
        total_active_cooldowns = sum(
            len([c for c in cooldowns.values() if c.is_on_cooldown()])
            for cooldowns in self.behavior_cooldowns.values()
        )
        
        avg_stability = 0.0
        if total_characters > 0:
            stability_scores = [
                self._calculate_stability_score(char_id)
                for char_id in self.emotional_histories.keys()
            ]
            avg_stability = sum(stability_scores) / len(stability_scores)
        
        return {
            'total_characters_tracked': total_characters,
            'total_emotional_states': total_emotional_states,
            'total_active_cooldowns': total_active_cooldowns,
            'average_stability_score': round(avg_stability, 3),
            'engine_config': self.config,
            'loop_detection_enabled': self.loop_detection_enabled,
            'auto_disruption_enabled': self.auto_disruption_enabled
        }
