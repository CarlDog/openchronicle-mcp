"""
Character Interaction Dynamics Engine

This module enables dynamic, believable conversations and emotional interactions
between multiple characters in OpenChronicle stories. It tracks relationships,
manages multi-character scenes, and coordinates character interactions.

Key Features:
- Relationship tracking matrix between characters
- Multi-character conversation flow management
- Dynamic relationship state updates (trust, suspicion, etc.)
- Hidden thoughts and motivations separate from dialogue
- Interaction history logging for context building
- Scene controller for orchestrating character turns
- Emotional state synchronization between characters
"""

import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from enum import Enum
import logging
import uuid

# Setup logging
logger = logging.getLogger(__name__)

class RelationshipType(Enum):
    """Types of relationships between characters."""
    TRUST = "trust"
    SUSPICION = "suspicion"
    FEAR = "fear"
    AFFECTION = "affection"
    ANGER = "anger"
    RESPECT = "respect"
    CONTEMPT = "contempt"
    LOYALTY = "loyalty"
    BETRAYAL = "betrayal"
    ROMANTIC = "romantic"
    RIVALRY = "rivalry"
    FRIENDSHIP = "friendship"

class InteractionType(Enum):
    """Types of character interactions."""
    DIALOGUE = "dialogue"
    ACTION = "action"
    THOUGHT = "thought"
    WHISPER = "whisper"
    REACTION = "reaction"
    INTERNAL_MONOLOGUE = "internal_monologue"

@dataclass
class RelationshipState:
    """Represents the relationship state between two characters."""
    character_a: str
    character_b: str
    relationship_type: RelationshipType
    intensity: float  # 0.0 to 1.0
    last_updated: datetime
    history: List[Dict[str, Any]] = field(default_factory=list)
    context: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'character_a': self.character_a,
            'character_b': self.character_b,
            'relationship_type': self.relationship_type.value,
            'intensity': self.intensity,
            'last_updated': self.last_updated.isoformat(),
            'history': self.history,
            'context': self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RelationshipState':
        """Create from dictionary."""
        return cls(
            character_a=data['character_a'],
            character_b=data['character_b'],
            relationship_type=RelationshipType(data['relationship_type']),
            intensity=data['intensity'],
            last_updated=datetime.fromisoformat(data['last_updated']),
            history=data.get('history', []),
            context=data.get('context', '')
        )
    
    def update_intensity(self, delta: float, reason: str) -> None:
        """Update relationship intensity with reasoning."""
        old_intensity = self.intensity
        self.intensity = max(0.0, min(1.0, self.intensity + delta))
        self.last_updated = datetime.now()
        
        # Record the change
        self.history.append({
            'timestamp': self.last_updated.isoformat(),
            'old_intensity': old_intensity,
            'new_intensity': self.intensity,
            'delta': delta,
            'reason': reason
        })
        
        logger.debug(f"Updated {self.character_a}->{self.character_b} "
                    f"{self.relationship_type.value}: {old_intensity:.2f} -> "
                    f"{self.intensity:.2f} ({reason})")

@dataclass
class CharacterState:
    """Represents a character's current state in a scene."""
    character_id: str
    current_emotion: str
    emotional_intensity: float  # 0.0 to 1.0
    motivation: str
    hidden_thoughts: List[str] = field(default_factory=list)
    active_goals: List[str] = field(default_factory=list)
    scene_position: str = ""  # Where they are in the scene
    speaking_priority: int = 0  # Higher = more likely to speak next
    last_action: Optional[str] = None
    last_dialogue: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'character_id': self.character_id,
            'current_emotion': self.current_emotion,
            'emotional_intensity': self.emotional_intensity,
            'motivation': self.motivation,
            'hidden_thoughts': self.hidden_thoughts,
            'active_goals': self.active_goals,
            'scene_position': self.scene_position,
            'speaking_priority': self.speaking_priority,
            'last_action': self.last_action,
            'last_dialogue': self.last_dialogue
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CharacterState':
        """Create from dictionary."""
        return cls(
            character_id=data['character_id'],
            current_emotion=data['current_emotion'],
            emotional_intensity=data['emotional_intensity'],
            motivation=data['motivation'],
            hidden_thoughts=data.get('hidden_thoughts', []),
            active_goals=data.get('active_goals', []),
            scene_position=data.get('scene_position', ''),
            speaking_priority=data.get('speaking_priority', 0),
            last_action=data.get('last_action'),
            last_dialogue=data.get('last_dialogue')
        )

@dataclass
class Interaction:
    """Represents a single character interaction."""
    interaction_id: str
    timestamp: datetime
    source_character: str
    target_characters: List[str]  # Can be multiple for group interactions
    interaction_type: InteractionType
    content: str
    hidden_content: Optional[str] = None  # Private thoughts/motivations
    emotional_impact: Dict[str, float] = field(default_factory=dict)  # Impact on each character
    scene_context: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'interaction_id': self.interaction_id,
            'timestamp': self.timestamp.isoformat(),
            'source_character': self.source_character,
            'target_characters': self.target_characters,
            'interaction_type': self.interaction_type.value,
            'content': self.content,
            'hidden_content': self.hidden_content,
            'emotional_impact': self.emotional_impact,
            'scene_context': self.scene_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Interaction':
        """Create from dictionary."""
        return cls(
            interaction_id=data['interaction_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            source_character=data['source_character'],
            target_characters=data['target_characters'],
            interaction_type=InteractionType(data['interaction_type']),
            content=data['content'],
            hidden_content=data.get('hidden_content'),
            emotional_impact=data.get('emotional_impact', {}),
            scene_context=data.get('scene_context', '')
        )

@dataclass
class SceneState:
    """Represents the overall state of a multi-character scene."""
    scene_id: str
    active_characters: List[str]
    character_states: Dict[str, CharacterState]
    turn_order: List[str]
    current_speaker: Optional[str]
    scene_tension: float  # 0.0 to 1.0
    scene_focus: str  # Main focus of the scene
    environment_context: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'scene_id': self.scene_id,
            'active_characters': self.active_characters,
            'character_states': {k: v.to_dict() for k, v in self.character_states.items()},
            'turn_order': self.turn_order,
            'current_speaker': self.current_speaker,
            'scene_tension': self.scene_tension,
            'scene_focus': self.scene_focus,
            'environment_context': self.environment_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SceneState':
        """Create from dictionary."""
        character_states = {
            k: CharacterState.from_dict(v) 
            for k, v in data['character_states'].items()
        }
        
        return cls(
            scene_id=data['scene_id'],
            active_characters=data['active_characters'],
            character_states=character_states,
            turn_order=data['turn_order'],
            current_speaker=data.get('current_speaker'),
            scene_tension=data['scene_tension'],
            scene_focus=data['scene_focus'],
            environment_context=data.get('environment_context', '')
        )

class CharacterInteractionEngine:
    """
    Manages character interactions, relationships, and multi-character scenes.
    
    This engine tracks relationship dynamics, orchestrates character conversations,
    and maintains individual character states within complex multi-character scenes.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the character interaction engine."""
        self.config = config or {}
        
        # Configuration parameters
        self.max_scene_history = self.config.get('max_scene_history', 100)
        self.relationship_decay_rate = self.config.get('relationship_decay_rate', 0.01)
        self.interaction_window_hours = self.config.get('interaction_window_hours', 24)
        self.auto_turn_management = self.config.get('auto_turn_management', True)
        self.emotional_contagion_enabled = self.config.get('emotional_contagion_enabled', True)
        
        # Data storage
        self.relationships: Dict[str, RelationshipState] = {}  # Key: "char_a:char_b"
        self.interaction_history: List[Interaction] = []
        self.scene_states: Dict[str, SceneState] = {}
        self.character_contexts: Dict[str, Dict[str, Any]] = {}
        
        # Turn management
        self.speaking_patterns = {
            'balanced': [1, 1, 1],  # Everyone speaks equally
            'leader_focused': [3, 1, 1],  # One character dominates
            'dialogue_heavy': [2, 2, 1],  # Two characters focus
            'round_robin': [1, 1, 1]  # Strict rotation
        }
    
    def create_scene(self, scene_id: str, characters: List[str], 
                    scene_focus: str, environment_context: str = "") -> SceneState:
        """Create a new multi-character scene."""
        character_states = {}
        
        for char_id in characters:
            character_states[char_id] = CharacterState(
                character_id=char_id,
                current_emotion="neutral",
                emotional_intensity=0.5,
                motivation="participate in scene",
                scene_position=environment_context
            )
        
        scene_state = SceneState(
            scene_id=scene_id,
            active_characters=characters,
            character_states=character_states,
            turn_order=characters.copy(),
            current_speaker=characters[0] if characters else None,
            scene_tension=0.3,
            scene_focus=scene_focus,
            environment_context=environment_context
        )
        
        self.scene_states[scene_id] = scene_state
        
        logger.info(f"Created scene '{scene_id}' with {len(characters)} characters: "
                   f"{', '.join(characters)}")
        
        return scene_state
    
    def add_interaction(self, scene_id: str, source_character: str, 
                       target_characters: List[str], interaction_type: InteractionType,
                       content: str, hidden_content: Optional[str] = None) -> Interaction:
        """Add a new character interaction to the scene."""
        interaction = Interaction(
            interaction_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            source_character=source_character,
            target_characters=target_characters,
            interaction_type=interaction_type,
            content=content,
            hidden_content=hidden_content,
            scene_context=scene_id
        )
        
        self.interaction_history.append(interaction)
        
        # Update character states based on interaction
        if scene_id in self.scene_states:
            scene = self.scene_states[scene_id]
            
            # Update source character's last action/dialogue
            if source_character in scene.character_states:
                char_state = scene.character_states[source_character]
                if interaction_type == InteractionType.DIALOGUE:
                    char_state.last_dialogue = content
                else:
                    char_state.last_action = content
        
        # Process emotional impacts and relationship changes
        self._process_interaction_effects(interaction)
        
        logger.debug(f"Added {interaction_type.value} interaction from {source_character} "
                    f"to {target_characters} in scene {scene_id}")
        
        return interaction
    
    def update_relationship(self, char_a: str, char_b: str, 
                          relationship_type: RelationshipType, 
                          intensity_delta: float, reason: str) -> None:
        """Update the relationship between two characters."""
        relationship_key = f"{char_a}:{char_b}"
        
        if relationship_key not in self.relationships:
            # Create new relationship
            self.relationships[relationship_key] = RelationshipState(
                character_a=char_a,
                character_b=char_b,
                relationship_type=relationship_type,
                intensity=0.5,  # Start neutral
                last_updated=datetime.now(),
                context=reason
            )
        
        relationship = self.relationships[relationship_key]
        
        # Update the relationship type if it's changed significantly
        if relationship.relationship_type != relationship_type:
            # Check if this is a stronger emotion
            intensity_threshold = 0.7
            if intensity_delta > 0 and (relationship.intensity + intensity_delta) > intensity_threshold:
                relationship.relationship_type = relationship_type
                logger.info(f"Relationship {char_a}->{char_b} changed to {relationship_type.value}")
        
        relationship.update_intensity(intensity_delta, reason)
    
    def get_relationship_state(self, char_a: str, char_b: str) -> Optional[RelationshipState]:
        """Get the current relationship state between two characters."""
        relationship_key = f"{char_a}:{char_b}"
        return self.relationships.get(relationship_key)
    
    def get_next_speaker(self, scene_id: str, pattern: str = 'balanced') -> Optional[str]:
        """Determine who should speak next in a scene."""
        if scene_id not in self.scene_states:
            return None
        
        scene = self.scene_states[scene_id]
        
        if not scene.active_characters:
            return None
        
        if not self.auto_turn_management:
            return scene.current_speaker
        
        # Use speaking priority to determine next speaker
        candidates = []
        for char_id in scene.active_characters:
            char_state = scene.character_states.get(char_id)
            if char_state:
                priority = char_state.speaking_priority
                
                # Boost priority based on emotional intensity
                priority += char_state.emotional_intensity * 2
                
                # Reduce priority if they just spoke
                if char_id == scene.current_speaker:
                    priority -= 1
                
                candidates.append((char_id, priority))
        
        # Sort by priority and select highest
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if candidates:
            next_speaker = candidates[0][0]
            scene.current_speaker = next_speaker
            return next_speaker
        
        return None
    
    def generate_interaction_context(self, scene_id: str, character_id: str) -> Dict[str, Any]:
        """Generate context for a character's next interaction in a scene."""
        if scene_id not in self.scene_states:
            return {}
        
        scene = self.scene_states[scene_id]
        char_state = scene.character_states.get(character_id)
        
        if not char_state:
            return {}
        
        # Get recent interactions in this scene
        recent_interactions = [
            interaction for interaction in self.interaction_history[-10:]
            if interaction.scene_context == scene_id
        ]
        
        # Get relationships with other characters in scene
        relationships = {}
        for other_char in scene.active_characters:
            if other_char != character_id:
                # Check relationship in both directions
                rel_state = self.get_relationship_state(character_id, other_char)
                if rel_state:
                    relationships[other_char] = {
                        'type': rel_state.relationship_type.value,
                        'intensity': rel_state.intensity,
                        'direction': 'outgoing'
                    }
                else:
                    # Check reverse direction
                    rel_state = self.get_relationship_state(other_char, character_id)
                    if rel_state:
                        relationships[other_char] = {
                            'type': rel_state.relationship_type.value,
                            'intensity': rel_state.intensity,
                            'direction': 'incoming'
                        }
        
        # Get other characters' states
        other_character_states = {
            char_id: state.to_dict() 
            for char_id, state in scene.character_states.items()
            if char_id != character_id
        }
        
        context = {
            'scene_focus': scene.scene_focus,
            'scene_tension': scene.scene_tension,
            'environment': scene.environment_context,
            'character_state': char_state.to_dict(),
            'relationships': relationships,
            'other_characters': other_character_states,
            'recent_interactions': [interaction.to_dict() for interaction in recent_interactions[-3:]],
            'hidden_thoughts': char_state.hidden_thoughts,
            'motivations': char_state.active_goals
        }
        
        return context
    
    def generate_relationship_prompt(self, scene_id: str, character_id: str) -> str:
        """Generate a prompt snippet for character relationships in a scene."""
        context = self.generate_interaction_context(scene_id, character_id)
        
        if not context.get('relationships'):
            return ""
        
        prompt_parts = [f"\n[CHARACTER_RELATIONSHIPS for {character_id}:"]
        
        for other_char, rel_data in context['relationships'].items():
            rel_type = rel_data['type']
            intensity = rel_data['intensity']
            intensity_desc = "weakly" if intensity < 0.3 else "moderately" if intensity < 0.7 else "strongly"
            
            prompt_parts.append(f"- {character_id} {intensity_desc} {rel_type}s {other_char}")
        
        # Add hidden thoughts if any
        if context.get('hidden_thoughts'):
            prompt_parts.append(f"- {character_id}'s private thoughts: {'; '.join(context['hidden_thoughts'][-2:])}")
        
        prompt_parts.append("Consider these relationships in your response.]\n")
        
        return " ".join(prompt_parts)
    
    def update_scene_tension(self, scene_id: str, tension_delta: float, reason: str) -> None:
        """Update the overall tension level of a scene."""
        if scene_id not in self.scene_states:
            return
        
        scene = self.scene_states[scene_id]
        old_tension = scene.scene_tension
        scene.scene_tension = max(0.0, min(1.0, scene.scene_tension + tension_delta))
        
        logger.debug(f"Scene {scene_id} tension: {old_tension:.2f} -> "
                    f"{scene.scene_tension:.2f} ({reason})")
    
    def add_hidden_thought(self, scene_id: str, character_id: str, thought: str) -> None:
        """Add a hidden thought for a character."""
        if scene_id not in self.scene_states:
            return
        
        scene = self.scene_states[scene_id]
        if character_id in scene.character_states:
            char_state = scene.character_states[character_id]
            char_state.hidden_thoughts.append(thought)
            
            # Keep only recent thoughts
            if len(char_state.hidden_thoughts) > 5:
                char_state.hidden_thoughts = char_state.hidden_thoughts[-5:]
            
            logger.debug(f"Added hidden thought for {character_id}: {thought[:50]}...")
    
    def _process_interaction_effects(self, interaction: Interaction) -> None:
        """Process the emotional and relationship effects of an interaction."""
        source = interaction.source_character
        targets = interaction.target_characters
        content = interaction.content.lower()
        
        # Analyze content for emotional impact
        emotional_indicators = {
            'anger': ['angry', 'furious', 'rage', 'hate', 'damn', 'hell'],
            'affection': ['love', 'dear', 'sweet', 'beautiful', 'wonderful'],
            'fear': ['afraid', 'scared', 'terrified', 'worried', 'anxious'],
            'trust': ['trust', 'believe', 'faith', 'honest', 'reliable'],
            'suspicion': ['suspicious', 'doubt', 'unsure', 'questionable', 'lie']
        }
        
        # Detect emotional content
        detected_emotions = []
        for emotion, keywords in emotional_indicators.items():
            if any(keyword in content for keyword in keywords):
                detected_emotions.append(emotion)
        
        # Update relationships based on detected emotions
        for target in targets:
            for emotion in detected_emotions:
                if emotion == 'anger':
                    # Negative emotions
                    self.update_relationship(
                        source, target, 
                        RelationshipType.ANGER, 
                        0.1, 
                        f"Interaction: {interaction.content[:50]}..."
                    )
                elif emotion == 'suspicion':
                    self.update_relationship(
                        source, target, 
                        RelationshipType.SUSPICION, 
                        0.1, 
                        f"Interaction: {interaction.content[:50]}..."
                    )
                elif emotion == 'affection':
                    # Positive emotions
                    self.update_relationship(
                        source, target,
                        RelationshipType.AFFECTION,
                        0.1,
                        f"Interaction: {interaction.content[:50]}..."
                    )
                elif emotion == 'trust':
                    self.update_relationship(
                        source, target,
                        RelationshipType.TRUST,
                        0.1,
                        f"Interaction: {interaction.content[:50]}..."
                    )
        
        # Apply emotional contagion if enabled
        if self.emotional_contagion_enabled and interaction.scene_context in self.scene_states:
            self._apply_emotional_contagion(interaction)
    
    def _apply_emotional_contagion(self, interaction: Interaction) -> None:
        """Apply emotional contagion effects to nearby characters."""
        scene_id = interaction.scene_context
        scene = self.scene_states[scene_id]
        
        # Get source character's emotional state
        source_state = scene.character_states.get(interaction.source_character)
        if not source_state:
            return
        
        # Apply reduced emotional impact to other characters in scene
        contagion_factor = 0.3  # How much emotion spreads
        
        for char_id in scene.active_characters:
            if char_id != interaction.source_character and char_id not in interaction.target_characters:
                char_state = scene.character_states[char_id]
                
                # Get relationship strength as modifier
                rel_state = self.get_relationship_state(char_id, interaction.source_character)
                relationship_modifier = 1.0
                if rel_state:
                    relationship_modifier = rel_state.intensity
                
                # Apply emotional contagion
                emotion_impact = source_state.emotional_intensity * contagion_factor * relationship_modifier
                char_state.emotional_intensity = min(1.0, char_state.emotional_intensity + emotion_impact * 0.1)
    
    def get_scene_summary(self, scene_id: str) -> Dict[str, Any]:
        """Get a comprehensive summary of a scene's current state."""
        if scene_id not in self.scene_states:
            return {}
        
        scene = self.scene_states[scene_id]
        
        # Get recent interactions
        recent_interactions = [
            interaction.to_dict() for interaction in self.interaction_history[-10:]
            if interaction.scene_context == scene_id
        ]
        
        # Get all relationships in this scene
        scene_relationships = {}
        for char_a in scene.active_characters:
            for char_b in scene.active_characters:
                if char_a != char_b:
                    rel_state = self.get_relationship_state(char_a, char_b)
                    if rel_state:
                        scene_relationships[f"{char_a}->{char_b}"] = rel_state.to_dict()
        
        return {
            'scene_state': scene.to_dict(),
            'relationships': scene_relationships,
            'recent_interactions': recent_interactions,
            'next_speaker': self.get_next_speaker(scene_id),
            'engine_stats': self.get_engine_stats()
        }
    
    def export_scene_data(self, scene_id: str) -> Dict[str, Any]:
        """Export all data for a specific scene."""
        if scene_id not in self.scene_states:
            return {}
        
        scene_interactions = [
            interaction.to_dict() for interaction in self.interaction_history
            if interaction.scene_context == scene_id
        ]
        
        scene_relationships = {}
        scene = self.scene_states[scene_id]
        for char_a in scene.active_characters:
            for char_b in scene.active_characters:
                if char_a != char_b:
                    rel_state = self.get_relationship_state(char_a, char_b)
                    if rel_state:
                        scene_relationships[f"{char_a}:{char_b}"] = rel_state.to_dict()
        
        return {
            'scene_state': scene.to_dict(),
            'interactions': scene_interactions,
            'relationships': scene_relationships,
            'character_contexts': {
                char_id: self.character_contexts.get(char_id, {})
                for char_id in scene.active_characters
            }
        }
    
    def import_scene_data(self, scene_data: Dict[str, Any]) -> None:
        """Import scene data from external source."""
        if 'scene_state' in scene_data:
            scene_state = SceneState.from_dict(scene_data['scene_state'])
            self.scene_states[scene_state.scene_id] = scene_state
        
        if 'interactions' in scene_data:
            for interaction_data in scene_data['interactions']:
                interaction = Interaction.from_dict(interaction_data)
                self.interaction_history.append(interaction)
        
        if 'relationships' in scene_data:
            for rel_key, rel_data in scene_data['relationships'].items():
                self.relationships[rel_key] = RelationshipState.from_dict(rel_data)
        
        if 'character_contexts' in scene_data:
            self.character_contexts.update(scene_data['character_contexts'])
        
        logger.info("Imported scene data successfully")
    
    def reset_scene(self, scene_id: str) -> None:
        """Reset all data for a specific scene."""
        if scene_id in self.scene_states:
            del self.scene_states[scene_id]
        
        # Remove scene interactions
        self.interaction_history = [
            interaction for interaction in self.interaction_history
            if interaction.scene_context != scene_id
        ]
        
        logger.info(f"Reset scene data for: {scene_id}")
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics."""
        total_scenes = len(self.scene_states)
        total_interactions = len(self.interaction_history)
        total_relationships = len(self.relationships)
        
        # Calculate average scene tension
        avg_scene_tension = 0.0
        if total_scenes > 0:
            avg_scene_tension = sum(
                scene.scene_tension for scene in self.scene_states.values()
            ) / total_scenes
        
        # Count active relationships
        active_relationships = sum(
            1 for rel in self.relationships.values()
            if rel.intensity > 0.1
        )
        
        return {
            'total_scenes': total_scenes,
            'total_interactions': total_interactions,
            'total_relationships': total_relationships,
            'active_relationships': active_relationships,
            'average_scene_tension': round(avg_scene_tension, 3),
            'interaction_types': self._count_interaction_types(),
            'relationship_types': self._count_relationship_types(),
            'engine_config': self.config
        }
    
    def _count_interaction_types(self) -> Dict[str, int]:
        """Count interactions by type."""
        type_counts = {}
        for interaction in self.interaction_history:
            interaction_type = interaction.interaction_type.value
            type_counts[interaction_type] = type_counts.get(interaction_type, 0) + 1
        return type_counts
    
    def _count_relationship_types(self) -> Dict[str, int]:
        """Count relationships by type."""
        type_counts = {}
        for relationship in self.relationships.values():
            rel_type = relationship.relationship_type.value
            type_counts[rel_type] = type_counts.get(rel_type, 0) + 1
        return type_counts
