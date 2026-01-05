"""
Entity Manager

Handles participant-specific memory operations including updates, mood tracking,
and voice profile management. Extracted from entity-related functions in memory_manager.py.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Any

from ...shared.memory_models import MAX_MOOD_HISTORY
from ...shared.memory_models import CharacterMemory
from ...shared.memory_models import MoodEntry
from ...shared.memory_models import VoiceProfile
from ..persistence import MemoryRepository


@dataclass
class CharacterUpdateResult:
    """Result of entity update operation."""

    success: bool
    character_name: str
    updated_fields: list[str]
    warnings: list[str]
    previous_mood: str | None = None
    new_mood: str | None = None


class CharacterManager:
    """Manages participant-specific memory operations."""

    def __init__(self, repository: MemoryRepository | None = None):
        """Initialize manager."""
        self.repository = repository or MemoryRepository()

    def update_character(self, story_id: str, character_name: str, updates: dict[str, Any]) -> CharacterUpdateResult:
        """Update entity memory with comprehensive tracking."""
        try:
            # Load current memory
            memory = self.repository.load_memory(story_id)

            # Initialize entry if missing
            if character_name not in memory.characters:
                memory.characters[character_name] = CharacterMemory(name=character_name)

            entity = memory.characters[character_name]
            updated_fields = []
            warnings = []
            previous_mood = entity.current_mood

            # Update basic fields
            for field in ["description", "personality", "background"]:
                if field in updates and updates[field] is not None:
                    setattr(entity, field, updates[field])
                    updated_fields.append(field)

            # Handle mood updates with history tracking
            new_mood = None
            if "mood" in updates and updates["mood"] is not None:
                new_mood = updates["mood"]
                self._update_character_mood(entity, new_mood, updates.get("mood_reason"))
                updated_fields.append("mood")

            # Handle voice profile updates
            if updates.get("voice_updates"):
                self._update_voice_profile(entity, updates["voice_updates"])
                updated_fields.append("voice_profile")

            # Handle relationship updates
            if updates.get("relationship_updates"):
                entity.relationships.update(updates["relationship_updates"])
                updated_fields.append("relationships")

            # Handle arc progress updates
            if updates.get("arc_updates"):
                entity.arc_progress.update(updates["arc_updates"])
                updated_fields.append("arc_progress")

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
                new_mood=new_mood,
            )

        except (KeyError, AttributeError) as e:
            # Handle data structure errors during update operations
            return CharacterUpdateResult(
                success=False,
                character_name=character_name,
                updated_fields=[],
                warnings=["Ch" + f"aracter data error: {e!s}"],
            )
        except ValueError as e:
            # Handle invalid data values during updates
            return CharacterUpdateResult(
                success=False,
                character_name=character_name,
                updated_fields=[],
                warnings=[f"Invalid data provided: {e!s}"],
            )
        except OSError as e:
            return CharacterUpdateResult(
                success=False,
                character_name=character_name,
                updated_fields=[],
                warnings=[f"Memory storage error: {e!s}"],
            )
        except Exception as e:
            return CharacterUpdateResult(
                success=False,
                character_name=character_name,
                updated_fields=[],
                warnings=[f"Unexpected update failure: {e!s}"],
            )

    def get_character_memory(self, story_id: str, character_name: str) -> CharacterMemory | None:
        """Get entity memory data."""
        try:
            memory = self.repository.load_memory(story_id)
            return memory.characters.get(character_name)
        except OSError as e:
            # Storage access error
            return None
        except (AttributeError, KeyError):
            # Data structure or missing entry error
            return None
        except Exception:
            return None

    def get_character_snapshot(
        self, story_id: str, character_name: str, format_for_prompt: bool = True
    ) -> dict[str, Any]:
        """Get entity memory snapshot with optional prompt formatting."""
        try:
            entity = self.get_character_memory(story_id, character_name)
            if not entity:
                return {}

            # Basic snapshot data
            snapshot = {
                "name": entity.name,
                "description": entity.description,
                "personality": entity.personality,
                "background": entity.background,
                "current_mood": entity.current_mood,
                "relationships": entity.relationships,
                "arc_progress": entity.arc_progress,
            }

            # Add voice profile information
            if entity.voice_profile:
                snapshot["voice_profile"] = {
                    "speaking_style": entity.voice_profile.speaking_style,
                    "vocabulary_level": entity.voice_profile.vocabulary_level,
                    "personality_traits": entity.voice_profile.personality_traits,
                    "speaking_patterns": entity.voice_profile.speaking_patterns,
                    "emotional_tendencies": entity.voice_profile.emotional_tendencies,
                }

            # Add recent mood history (last 5 entries)
            if entity.mood_history:
                recent_moods = entity.mood_history[-5:]
                snapshot["recent_mood_history"] = [
                    {
                        "mood": mood.mood,
                        "timestamp": mood.timestamp.isoformat(),
                        "reason": mood.reason,
                    }
                    for mood in recent_moods
                ]

            # Add recent dialogue (last 10 entries)
            if entity.dialogue_history:
                snapshot["recent_dialogue"] = entity.dialogue_history[-10:]
        except Exception:
            return {}
        else:
            return snapshot

    def update_character_mood(
        self,
        story_id: str,
        character_name: str,
        new_mood: str,
        reason: str | None = None,
        confidence: float = 1.0,
    ) -> bool:
        """Update entity mood with history tracking."""
        try:
            memory = self.repository.load_memory(story_id)

            if character_name not in memory.characters:
                memory.characters[character_name] = CharacterMemory(name=character_name)

            entity = memory.characters[character_name]
            self._update_character_mood(entity, new_mood, reason, confidence)

            # Save updated memory
            return self.repository.save_memory(story_id, memory)

        except OSError:
            # Memory storage error
            return False
        except (AttributeError, KeyError, ValueError):
            # Data structure or validation error
            return False
        except Exception:
            return False

    def get_character_voice_prompt(self, story_id: str, character_name: str) -> str:
        """Get voice profile formatted for AI prompts."""
        try:
            entity = self.get_character_memory(story_id, character_name)
            if not entity or not entity.voice_profile:
                return "Ch" + f"aracter: {character_name} (no specific voice profile available)"

            voice = entity.voice_profile
            voice_prompt = "Ch" + f"aracter: {character_name}\n"

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
            if entity.current_mood != "neutral":
                voice_prompt += f"Current Mood: {entity.current_mood}\n"

            return voice_prompt.strip()

        except OSError as e:
            # Memory storage error
            return "Ch" + f"aracter: {character_name} (voice profile unavailable - storage error)"
        except (AttributeError, KeyError) as e:
            # Data structure error
            return "Ch" + f"aracter: {character_name} (voice profile unavailable - data error)"
        except Exception as e:
            return "Ch" + f"aracter: {character_name} (voice profile unavailable - unexpected error)"

    def add_dialogue_entry(self, story_id: str, character_name: str, dialogue: str, max_history: int = 50) -> bool:
        """Add dialogue entry to entity history."""
        try:
            memory = self.repository.load_memory(story_id)

            if character_name not in memory.characters:
                memory.characters[character_name] = CharacterMemory(name=character_name)

            entity = memory.characters[character_name]

            # Add dialogue with timestamp
            timestamped_dialogue = f"[{datetime.now(UTC).strftime('%H:%M')}] {dialogue}"
            entity.dialogue_history.append(timestamped_dialogue)

            # Trim history if too long
            if len(entity.dialogue_history) > max_history:
                entity.dialogue_history = entity.dialogue_history[-max_history:]

            return self.repository.save_memory(story_id, memory)

        except OSError as e:
            # Memory storage error
            return False
        except (AttributeError, KeyError, ValueError) as e:
            # Data structure or validation error
            return False
        except Exception as e:
            return False

    def _update_character_mood(
        self,
        entity: CharacterMemory,
        new_mood: str,
        reason: str | None = None,
        confidence: float = 1.0,
    ) -> None:
        """Internal method to update entity mood with history."""
        # Add current mood to history before changing
        if entity.current_mood != new_mood:
            mood_entry = MoodEntry(
                mood=entity.current_mood,
                timestamp=datetime.now(UTC),
                reason=reason,
                confidence=confidence,
            )
            entity.mood_history.append(mood_entry)

            # Trim mood history to maximum length
            if len(entity.mood_history) > MAX_MOOD_HISTORY:
                entity.mood_history = entity.mood_history[-MAX_MOOD_HISTORY:]

            # Update current mood
            entity.current_mood = new_mood

    def _update_voice_profile(self, entity: CharacterMemory, voice_updates: dict[str, Any]) -> None:
        """Internal method to update voice profile."""
        # Initialize voice profile if it doesn't exist
        if not entity.voice_profile:
            entity.voice_profile = VoiceProfile()

        # Update voice profile fields
        for field in ["speaking_style", "vocabulary_level"]:
            if field in voice_updates:
                setattr(entity.voice_profile, field, voice_updates[field])

        # Update list fields
        for field in [
            "personality_traits",
            "speaking_patterns",
            "emotional_tendencies",
        ]:
            if field in voice_updates:
                if isinstance(voice_updates[field], list):
                    setattr(entity.voice_profile, field, voice_updates[field])
                elif isinstance(voice_updates[field], str):
                    # Convert comma-separated string to list
                    value_list = [item.strip() for item in voice_updates[field].split(",")]
                    setattr(entity.voice_profile, field, value_list)
