"""
Character Consistency Engine
Implements motivation anchoring, trait locking, and behavior auditing for character consistency.
"""

import json
import os
import sys
import time
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error

class ConsistencyViolationType(Enum):
    """Types of consistency violations that can be detected."""
    EMOTIONAL_CONTRADICTION = "emotional_contradiction"
    TRAIT_VIOLATION = "trait_violation"
    MOTIVATION_CONFLICT = "motivation_conflict"
    BEHAVIORAL_INCONSISTENCY = "behavioral_inconsistency"
    TONE_MISMATCH = "tone_mismatch"

@dataclass
class ConsistencyViolation:
    """Represents a character consistency violation."""
    violation_type: ConsistencyViolationType
    character_name: str
    scene_id: str
    description: str
    severity: float  # 0.0-1.0, where 1.0 is most severe
    expected_behavior: str
    actual_behavior: str
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['violation_type'] = self.violation_type.value
        return result

@dataclass
class MotivationAnchor:
    """Represents a locked character motivation that must persist."""
    trait_name: str
    value: Any
    description: str
    locked: bool = True
    priority: int = 1  # 1=highest, lower numbers = higher priority
    context_requirement: Optional[str] = None  # When this anchor should be emphasized
    
class CharacterConsistencyEngine:
    """
    Maintains character consistency through motivation anchoring, trait locking,
    and behavioral auditing across long narratives.
    """
    
    def __init__(self, character_style_manager=None):
        self.character_style_manager = character_style_manager
        self.motivation_anchors: Dict[str, List[MotivationAnchor]] = {}
        self.locked_traits: Dict[str, Set[str]] = {}
        self.violation_history: Dict[str, List[ConsistencyViolation]] = {}
        self.behavioral_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.emotional_states: Dict[str, Dict[str, Any]] = {}
        self.consistency_scores: Dict[str, float] = {}
        
    def load_character_consistency_data(self, story_path: str) -> None:
        """Load character consistency data from story characters."""
        characters_dir = os.path.join(story_path, "characters")
        
        if not os.path.exists(characters_dir):
            return
            
        for char_file in os.listdir(characters_dir):
            if char_file.endswith('.json'):
                char_name = char_file[:-5]  # Remove .json
                char_path = os.path.join(characters_dir, char_file)
                
                try:
                    with open(char_path, 'r', encoding='utf-8') as f:
                        char_data = json.load(f)
                    
                    self._process_character_data(char_name, char_data)
                    log_info(f"Loaded consistency data for {char_name}")
                    
                except Exception as e:
                    log_error(f"Failed to load character consistency data for {char_name}: {e}")
    
    def _process_character_data(self, char_name: str, char_data: Dict[str, Any]) -> None:
        """Process character data to extract consistency requirements."""
        # Initialize character tracking
        self.motivation_anchors[char_name] = []
        self.locked_traits[char_name] = set()
        self.violation_history[char_name] = []
        self.behavioral_patterns[char_name] = []
        self.emotional_states[char_name] = {}
        self.consistency_scores[char_name] = 1.0
        
        # Process emotional profile for anchors
        emotional_profile = char_data.get('emotional_profile', {})
        if emotional_profile:
            self._create_emotional_anchors(char_name, emotional_profile)
        
        # Process character stats for trait locking
        character_stats = char_data.get('character_stats', {})
        if character_stats:
            self._create_stat_anchors(char_name, character_stats)
        
        # Process explicit locked traits
        locked_traits = char_data.get('locked_traits', [])
        for trait in locked_traits:
            self.locked_traits[char_name].add(trait)
        
        # Process motivation anchors from character data
        motivation_data = char_data.get('motivation_anchors', [])
        for anchor_data in motivation_data:
            anchor = MotivationAnchor(**anchor_data)
            self.motivation_anchors[char_name].append(anchor)
    
    def _create_emotional_anchors(self, char_name: str, emotional_profile: Dict[str, Any]) -> None:
        """Create motivation anchors from emotional profile."""
        anchors = []
        
        # Volatility anchor
        volatility = emotional_profile.get('volatility', 0.5)
        if volatility < 0.3:
            anchors.append(MotivationAnchor(
                trait_name="emotional_control",
                value="stoic",
                description="Character maintains emotional control and rarely shows extreme reactions",
                priority=1
            ))
        elif volatility > 0.7:
            anchors.append(MotivationAnchor(
                trait_name="emotional_volatility", 
                value="explosive",
                description="Character has intense emotional reactions and mood swings",
                priority=1
            ))
        
        # Gratification drive anchor
        gratification = emotional_profile.get('gratification_drive', 0.5)
        if gratification < 0.3:
            anchors.append(MotivationAnchor(
                trait_name="independence",
                value="self_sufficient",
                description="Character is self-reliant and doesn't seek approval from others",
                priority=1
            ))
        elif gratification > 0.7:
            anchors.append(MotivationAnchor(
                trait_name="validation_seeking",
                value="approval_seeking", 
                description="Character needs validation and approval from others",
                priority=2
            ))
        
        # Boundaries anchor
        if emotional_profile.get('boundaries_enabled', True):
            anchors.append(MotivationAnchor(
                trait_name="personal_boundaries",
                value="enabled",
                description="Character can resist advances and say no when uncomfortable",
                priority=1
            ))
        
        self.motivation_anchors[char_name].extend(anchors)
    
    def _create_stat_anchors(self, char_name: str, character_stats: Dict[str, Any]) -> None:
        """Create motivation anchors from character stats."""
        anchors = []
        
        # High/low stat anchors
        for stat_name, value in character_stats.items():
            if isinstance(value, (int, float)):
                if value >= 8:  # High stat
                    anchors.append(MotivationAnchor(
                        trait_name=f"high_{stat_name}",
                        value=value,
                        description=f"Character has exceptionally high {stat_name} ({value}/10)",
                        priority=2
                    ))
                elif value <= 3:  # Low stat (changed from 2 to 3 for more realistic threshold)
                    anchors.append(MotivationAnchor(
                        trait_name=f"low_{stat_name}",
                        value=value,
                        description=f"Character has very low {stat_name} ({value}/10)",
                        priority=2
                    ))
        
        self.motivation_anchors[char_name].extend(anchors)
    
    def get_motivation_prompt(self, char_name: str, context_type: Optional[str] = None) -> str:
        """Generate motivation anchoring prompt for character consistency."""
        if char_name not in self.motivation_anchors:
            return ""
        
        anchors = self.motivation_anchors[char_name]
        if not anchors:
            return ""
        
        # Filter anchors by context if specified
        relevant_anchors = []
        for anchor in anchors:
            if context_type and anchor.context_requirement:
                if context_type == anchor.context_requirement:
                    relevant_anchors.append(anchor)
            else:
                relevant_anchors.append(anchor)
        
        # Sort by priority
        relevant_anchors.sort(key=lambda x: x.priority)
        
        # Build prompt
        prompt_parts = [f"=== {char_name.upper()} MOTIVATION ANCHORS ==="]
        
        for anchor in relevant_anchors[:5]:  # Limit to top 5 anchors
            prompt_parts.append(f"- {anchor.trait_name}: {anchor.description}")
        
        locked_traits = self.locked_traits.get(char_name, set())
        if locked_traits:
            prompt_parts.append("")
            prompt_parts.append("LOCKED TRAITS (cannot be changed):")
            for trait in sorted(locked_traits):
                prompt_parts.append(f"- {trait}")
        
        prompt_parts.append("")
        prompt_parts.append("The character MUST maintain consistency with these core motivations and traits.")
        
        return "\\n".join(prompt_parts)
    
    def analyze_behavioral_consistency(self, char_name: str, scene_output: str, 
                                     scene_id: str, context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Analyze scene output for behavioral consistency violations."""
        violations = []
        
        if char_name not in self.motivation_anchors:
            return violations
        
        # Check against motivation anchors
        violations.extend(self._check_motivation_violations(char_name, scene_output, scene_id, context))
        
        # Check against locked traits
        violations.extend(self._check_trait_violations(char_name, scene_output, scene_id, context))
        
        # Check for emotional contradictions
        violations.extend(self._check_emotional_contradictions(char_name, scene_output, scene_id, context))
        
        # Store violations
        if violations:
            if char_name not in self.violation_history:
                self.violation_history[char_name] = []
            self.violation_history[char_name].extend(violations)
            
            # Update consistency score
            self._update_consistency_score(char_name, violations)
            
            # Log violations
            for violation in violations:
                log_warning(f"Consistency violation for {char_name}: {violation.description}")
        
        return violations
    
    def _check_motivation_violations(self, char_name: str, scene_output: str, 
                                   scene_id: str, context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Check for violations against motivation anchors."""
        violations = []
        anchors = self.motivation_anchors.get(char_name, [])
        
        for anchor in anchors:
            violation = self._check_anchor_violation(char_name, anchor, scene_output, scene_id, context)
            if violation:
                violations.append(violation)
        
        return violations
    
    def _check_anchor_violation(self, char_name: str, anchor: MotivationAnchor, 
                              scene_output: str, scene_id: str, context: Optional[Dict[str, Any]] = None) -> Optional[ConsistencyViolation]:
        """Check if scene output violates a specific motivation anchor."""
        output_lower = scene_output.lower()
        
        # Specific checks based on anchor type
        if anchor.trait_name == "emotional_control" and anchor.value == "stoic":
            # Check for excessive emotional displays
            emotional_indicators = [
                "screaming", "sobbing", "hysterical", "raging", "furious",
                "ecstatic", "overwhelmed", "devastated", "exploded"
            ]
            for indicator in emotional_indicators:
                if indicator in output_lower:
                    return ConsistencyViolation(
                        violation_type=ConsistencyViolationType.TRAIT_VIOLATION,
                        character_name=char_name,
                        scene_id=scene_id,
                        description=f"Character showed excessive emotion ('{indicator}') despite stoic nature",
                        severity=0.7,
                        expected_behavior="Maintain emotional control",
                        actual_behavior=f"Displayed emotional reaction: {indicator}",
                        timestamp=time.time()
                    )
        
        elif anchor.trait_name == "independence" and anchor.value == "self_sufficient":
            # Check for approval-seeking behavior
            approval_seeking = [
                "do you like me", "am i good enough", "please approve", 
                "tell me i'm", "what do you think of me", "am i pretty"
            ]
            for phrase in approval_seeking:
                if phrase in output_lower:
                    return ConsistencyViolation(
                        violation_type=ConsistencyViolationType.MOTIVATION_CONFLICT,
                        character_name=char_name,
                        scene_id=scene_id,
                        description=f"Character sought approval despite independent nature",
                        severity=0.8,
                        expected_behavior="Self-sufficient behavior",
                        actual_behavior=f"Seeking approval: '{phrase}'",
                        timestamp=time.time()
                    )
        
        elif anchor.trait_name == "personal_boundaries" and anchor.value == "enabled":
            # Check that character maintains boundaries
            boundary_violations = [
                "i can't say no", "whatever you want", "i have to please",
                "i don't matter", "use me however"
            ]
            for phrase in boundary_violations:
                if phrase in output_lower:
                    return ConsistencyViolation(
                        violation_type=ConsistencyViolationType.TRAIT_VIOLATION,
                        character_name=char_name,
                        scene_id=scene_id,
                        description=f"Character failed to maintain personal boundaries",
                        severity=0.9,
                        expected_behavior="Maintain personal boundaries",
                        actual_behavior=f"Boundary violation: '{phrase}'",
                        timestamp=time.time()
                    )
        
        return None
    
    def _check_trait_violations(self, char_name: str, scene_output: str, 
                              scene_id: str, context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Check for violations against locked traits."""
        violations = []
        locked_traits = self.locked_traits.get(char_name, set())
        
        # Define trait violation patterns
        trait_patterns = {
            "pacifist": [
                "kill", "murder", "destroy", "attack", "fight", "violence",
                "blood", "weapon", "strike", "hurt"
            ],
            "honest": [
                "lie", "deceive", "trick", "manipulate", "false", "dishonest",
                "betray", "cheat"
            ],
            "coward": [
                "brave", "courageous", "fearless", "bold", "heroic", "charge",
                "face danger", "stand up to"
            ],
            "loyal": [
                "betray", "abandon", "leave behind", "turn against", "desert",
                "forsake", "unfaithful"
            ]
        }
        
        output_lower = scene_output.lower()
        
        for trait in locked_traits:
            if trait in trait_patterns:
                patterns = trait_patterns[trait]
                for pattern in patterns:
                    if pattern in output_lower:
                        violations.append(ConsistencyViolation(
                            violation_type=ConsistencyViolationType.TRAIT_VIOLATION,
                            character_name=char_name,
                            scene_id=scene_id,
                            description=f"Character violated locked trait '{trait}' with '{pattern}'",
                            severity=0.8,
                            expected_behavior=f"Maintain {trait} trait",
                            actual_behavior=f"Displayed behavior: {pattern}",
                            timestamp=time.time()
                        ))
        
        return violations
    
    def _check_emotional_contradictions(self, char_name: str, scene_output: str, 
                                      scene_id: str, context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Check for emotional contradictions within the scene."""
        violations = []
        
        # Look for emotional contradiction patterns
        contradiction_patterns = [
            (["happy", "joyful", "excited"], ["sad", "depressed", "miserable"]),
            (["angry", "furious", "rage"], ["calm", "peaceful", "serene"]),
            (["confident", "sure", "certain"], ["doubt", "uncertain", "confused"]),
            (["love", "adore", "cherish"], ["hate", "despise", "loathe"])
        ]
        
        output_lower = scene_output.lower()
        
        for positive_emotions, negative_emotions in contradiction_patterns:
            found_positive = any(emotion in output_lower for emotion in positive_emotions)
            found_negative = any(emotion in output_lower for emotion in negative_emotions)
            
            if found_positive and found_negative:
                violations.append(ConsistencyViolation(
                    violation_type=ConsistencyViolationType.EMOTIONAL_CONTRADICTION,
                    character_name=char_name,
                    scene_id=scene_id,
                    description="Character displayed contradictory emotions in same scene",
                    severity=0.6,
                    expected_behavior="Consistent emotional state",
                    actual_behavior="Mixed contradictory emotions",
                    timestamp=time.time()
                ))
        
        return violations
    
    def _update_consistency_score(self, char_name: str, violations: List[ConsistencyViolation]) -> None:
        """Update character consistency score based on violations."""
        if not violations:
            return
        
        current_score = self.consistency_scores.get(char_name, 1.0)
        
        # Calculate penalty based on violations
        total_penalty = 0
        for violation in violations:
            total_penalty += violation.severity * 0.1  # Max 10% penalty per violation
        
        # Apply penalty with dampening
        new_score = max(0.0, current_score - (total_penalty * 0.5))
        self.consistency_scores[char_name] = new_score
        
        log_info(f"Updated consistency score for {char_name}: {new_score:.2f}")
    
    def get_consistency_score(self, char_name: str) -> float:
        """Get current consistency score for character."""
        return self.consistency_scores.get(char_name, 1.0)
    
    def get_consistency_report(self, char_name: str) -> Dict[str, Any]:
        """Generate comprehensive consistency report for character."""
        if char_name not in self.motivation_anchors:
            return {"error": f"No consistency data for character {char_name}"}
        
        violations = self.violation_history.get(char_name, [])
        recent_violations = [v for v in violations if time.time() - v.timestamp < 3600]  # Last hour
        
        # Group violations by type
        violation_counts = {}
        for violation in violations:
            vtype = violation.violation_type.value
            violation_counts[vtype] = violation_counts.get(vtype, 0) + 1
        
        return {
            "character_name": char_name,
            "consistency_score": self.get_consistency_score(char_name),
            "motivation_anchors": len(self.motivation_anchors.get(char_name, [])),
            "locked_traits": list(self.locked_traits.get(char_name, set())),
            "total_violations": len(violations),
            "recent_violations": len(recent_violations),
            "violation_types": violation_counts,
            "recent_violation_details": [v.to_dict() for v in recent_violations[-5:]]
        }
    
    def add_motivation_anchor(self, char_name: str, anchor: MotivationAnchor) -> None:
        """Add a new motivation anchor for character."""
        if char_name not in self.motivation_anchors:
            self.motivation_anchors[char_name] = []
        
        self.motivation_anchors[char_name].append(anchor)
        log_info(f"Added motivation anchor '{anchor.trait_name}' for {char_name}")
    
    def lock_trait(self, char_name: str, trait_name: str) -> None:
        """Lock a trait for character (cannot be violated)."""
        if char_name not in self.locked_traits:
            self.locked_traits[char_name] = set()
        
        self.locked_traits[char_name].add(trait_name)
        log_info(f"Locked trait '{trait_name}' for {char_name}")
    
    def get_fallback_prompt(self, char_name: str, max_tokens: int = 200) -> str:
        """Generate fallback motivation prompt when token budget is limited."""
        if char_name not in self.motivation_anchors:
            return ""
        
        # Get highest priority anchors
        anchors = sorted(self.motivation_anchors[char_name], key=lambda x: x.priority)
        
        # Build minimal prompt
        essential_traits = []
        for anchor in anchors[:3]:  # Top 3 only
            essential_traits.append(f"{anchor.trait_name}: {anchor.value}")
        
        locked_traits = list(self.locked_traits.get(char_name, set()))[:2]  # Top 2 locked traits
        
        prompt = f"{char_name} core traits: {', '.join(essential_traits)}"
        if locked_traits:
            prompt += f" | Locked: {', '.join(locked_traits)}"
        
        # Ensure we stay under token limit
        if len(prompt) > max_tokens:
            prompt = prompt[:max_tokens-3] + "..."
        
        return prompt
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall consistency engine statistics."""
        total_characters = len(self.motivation_anchors)
        total_violations = sum(len(violations) for violations in self.violation_history.values())
        
        avg_consistency = 0.0
        if self.consistency_scores:
            avg_consistency = sum(self.consistency_scores.values()) / len(self.consistency_scores)
        
        return {
            "total_characters": total_characters,
            "total_violations": total_violations,
            "average_consistency_score": avg_consistency,
            "characters_with_anchors": len([c for c in self.motivation_anchors.values() if c]),
            "characters_with_locked_traits": len([c for c in self.locked_traits.values() if c])
        }
