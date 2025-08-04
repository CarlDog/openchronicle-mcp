"""
Character Manager

Handles all character-specific memory operations including updates, mood tracking,
and voice profile management. Extracted from character-related functions in memory_manager.py.
"""
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..shared.memory_models import (
    CharacterMemory, CharacterUpdates, MemoryUpdateResult, MoodEntry, VoiceProfile,
    DEFAULT_CHARACTER_TEMPLATE, MAX_MOOD_HISTORY
)
from ..persistence import MemoryRepository


@dataclass
class CharacterUpdateResult:
    """Result of character update operation."""
    success: bool
    character_name: str
    updated_fields: List[str]
    warnings: List[str]
    previous_mood: Optional[str] = None
    new_mood: Optional[str] = None


class CharacterManager:
    """Manages character-specific memory operations."""
    
    def __init__(self, repository: MemoryRepository):
        """Initialize character manager."""
        self.repository = repository
    
    def update_character(self, story_id: str, character_name: str, 
                        updates: Dict[str, Any]) -> CharacterUpdateResult:
        """Update character memory with comprehensive tracking."""
        try:
            # Load current memory
            memory = self.repository.load_memory(story_id)
            
            # Initialize character if doesn't exist
            if character_name not in memory.characters:
                memory.characters[character_name] = CharacterMemory(name=character_name)
            
            character = memory.characters[character_name]
            updated_fields = []
            warnings = []
            previous_mood = character.current_mood
            
            # Update basic fields
            for field in ['description', 'personality', 'background']:
                if field in updates and updates[field] is not None:
                    setattr(character, field, updates[field])
                    updated_fields.append(field)
            
            # Handle mood updates with history tracking
            new_mood = None
            if 'mood' in updates and updates['mood'] is not None:
                new_mood = updates['mood']
                self._update_character_mood(character, new_mood, updates.get('mood_reason'))
                updated_fields.append('mood')
            
            # Handle voice profile updates
            if 'voice_updates' in updates and updates['voice_updates']:
                self._update_voice_profile(character, updates['voice_updates'])
                updated_fields.append('voice_profile')
            
            # Handle relationship updates
            if 'relationship_updates' in updates and updates['relationship_updates']:
                character.relationships.update(updates['relationship_updates'])
                updated_fields.append('relationships')
            
            # Handle arc progress updates
            if 'arc_updates' in updates and updates['arc_updates']:
                character.arc_progress.update(updates['arc_updates'])
                updated_fields.append('arc_progress')
            
            # Update metadata
            memory.metadata.last_updated = datetime.now(UTC)
            memory.metadata.character_count = len(memory.characters)
            
            # Save updated memory
            success = self.repository.save_memory(story_id, memory)
            
            return CharacterUpdateResult(
                success=success,
                character_name=character_name,
                updated_fields=updated_fields,
                warnings=warnings,
                previous_mood=previous_mood,
                new_mood=new_mood
            )
            
        except Exception as e:
            return CharacterUpdateResult(
                success=False,
                character_name=character_name,
                updated_fields=[],
                warnings=[f"Update failed: {str(e)}"]
            )
    
    def get_character_memory(self, story_id: str, character_name: str) -> Optional[CharacterMemory]:
        """Get character memory data."""
        try:
            memory = self.repository.load_memory(story_id)
            return memory.characters.get(character_name)
        except Exception:
            return None
    
    def get_character_snapshot(self, story_id: str, character_name: str, 
                             format_for_prompt: bool = True) -> Dict[str, Any]:
        """Get character memory snapshot with optional prompt formatting."""
        try:
            character = self.get_character_memory(story_id, character_name)
            if not character:
                return {}
            
            # Basic snapshot data
            snapshot = {
                "name": character.name,
                "description": character.description,
                "personality": character.personality,
                "background": character.background,
                "current_mood": character.current_mood,
                "relationships": character.relationships,
                "arc_progress": character.arc_progress
            }
            
            # Add voice profile information
            if character.voice_profile:
                snapshot["voice_profile"] = {
                    "speaking_style": character.voice_profile.speaking_style,
                    "vocabulary_level": character.voice_profile.vocabulary_level,
                    "personality_traits": character.voice_profile.personality_traits,
                    "speaking_patterns": character.voice_profile.speaking_patterns,
                    "emotional_tendencies": character.voice_profile.emotional_tendencies
                }
            
            # Add recent mood history (last 5 entries)
            if character.mood_history:
                recent_moods = character.mood_history[-5:]
                snapshot["recent_mood_history"] = [
                    {
                        "mood": mood.mood,
                        "timestamp": mood.timestamp.isoformat(),
                        "reason": mood.reason
                    } for mood in recent_moods
                ]
            
            # Add recent dialogue (last 10 entries)
            if character.dialogue_history:
                snapshot["recent_dialogue"] = character.dialogue_history[-10:]
            
            return snapshot
            
        except Exception:
            return {}
    
    def update_character_mood(self, story_id: str, character_name: str, 
                            new_mood: str, reason: Optional[str] = None,
                            confidence: float = 1.0) -> bool:
        """Update character mood with history tracking."""
        try:
            memory = self.repository.load_memory(story_id)
            
            if character_name not in memory.characters:
                memory.characters[character_name] = CharacterMemory(name=character_name)
            
            character = memory.characters[character_name]
            self._update_character_mood(character, new_mood, reason, confidence)
            
            # Save updated memory
            return self.repository.save_memory(story_id, memory)
            
        except Exception:
            return False
    
    def get_character_voice_prompt(self, story_id: str, character_name: str) -> str:
        """Get character voice profile formatted for AI prompts."""
        try:
            character = self.get_character_memory(story_id, character_name)
            if not character or not character.voice_profile:
                return f"Character: {character_name} (no specific voice profile available)"
            
            voice = character.voice_profile
            voice_prompt = f"Character: {character_name}\n"
            
            if voice.speaking_style:
                voice_prompt += f"Speaking Style: {voice.speaking_style}\n"
            
            if voice.vocabulary_level:
                voice_prompt += f"Vocabulary Level: {voice.vocabulary_level}\n"
            
            if voice.personality_traits:
                voice_prompt += f"Personality Traits: {', '.join(voice.personality_traits)}\n"
            
            if voice.speaking_patterns:
                voice_prompt += f"Speaking Patterns: {', '.join(voice.speaking_patterns)}\n"
            
            if voice.emotional_tendencies:
                voice_prompt += f"Emotional Tendencies: {', '.join(voice.emotional_tendencies)}\n"
            
            # Add current mood context
            if character.current_mood != "neutral":
                voice_prompt += f"Current Mood: {character.current_mood}\n"
            
            return voice_prompt.strip()
            
        except Exception:
            return f"Character: {character_name} (voice profile unavailable)"
    
    def add_dialogue_entry(self, story_id: str, character_name: str, 
                          dialogue: str, max_history: int = 50) -> bool:
        """Add dialogue entry to character history."""
        try:
            memory = self.repository.load_memory(story_id)
            
            if character_name not in memory.characters:
                memory.characters[character_name] = CharacterMemory(name=character_name)
            
            character = memory.characters[character_name]
            
            # Add dialogue with timestamp
            timestamped_dialogue = f"[{datetime.now(UTC).strftime('%H:%M')}] {dialogue}"
            character.dialogue_history.append(timestamped_dialogue)
            
            # Trim history if too long
            if len(character.dialogue_history) > max_history:
                character.dialogue_history = character.dialogue_history[-max_history:]
            
            return self.repository.save_memory(story_id, memory)
            
        except Exception:
            return False
    
    def _update_character_mood(self, character: CharacterMemory, new_mood: str, 
                             reason: Optional[str] = None, confidence: float = 1.0) -> None:
        """Internal method to update character mood with history."""
        # Add current mood to history before changing
        if character.current_mood != new_mood:
            mood_entry = MoodEntry(
                mood=character.current_mood,
                timestamp=datetime.now(UTC),
                reason=reason,
                confidence=confidence
            )
            character.mood_history.append(mood_entry)
            
            # Trim mood history to maximum length
            if len(character.mood_history) > MAX_MOOD_HISTORY:
                character.mood_history = character.mood_history[-MAX_MOOD_HISTORY:]
            
            # Update current mood
            character.current_mood = new_mood
    
    def _update_voice_profile(self, character: CharacterMemory, 
                            voice_updates: Dict[str, Any]) -> None:
        """Internal method to update character voice profile."""
        # Initialize voice profile if it doesn't exist
        if not character.voice_profile:
            character.voice_profile = VoiceProfile()
        
        # Update voice profile fields
        for field in ['speaking_style', 'vocabulary_level']:
            if field in voice_updates:
                setattr(character.voice_profile, field, voice_updates[field])
        
        # Update list fields
        for field in ['personality_traits', 'speaking_patterns', 'emotional_tendencies']:
            if field in voice_updates:
                if isinstance(voice_updates[field], list):
                    setattr(character.voice_profile, field, voice_updates[field])
                elif isinstance(voice_updates[field], str):
                    # Convert comma-separated string to list
                    value_list = [item.strip() for item in voice_updates[field].split(',')]
                    setattr(character.voice_profile, field, value_list)
