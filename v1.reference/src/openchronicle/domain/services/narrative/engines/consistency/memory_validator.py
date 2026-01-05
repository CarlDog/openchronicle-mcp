"""
Memory Validator Component

Handles memory validation, conflict detection, consistency checking,
and memory lifecycle management for the consistency subsystem.
"""

import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from typing import Any

from openchronicle.domain.models.memory_models import CharacterMemory as DomainCharacterMemory
from openchronicle.domain.models.memory_models import MemoryState
from openchronicle.domain.ports.memory_port import IMemoryPort
from openchronicle.shared.json_utilities import JSONUtilities


logger = logging.getLogger(__name__)


class MemoryEvent:
    """Represents a memory event that generates character memories."""

    def __init__(
        self,
        event_type: str,
        content: str,
        timestamp: datetime,
        characters_involved: list[str],
        emotional_impact: float = 0.0,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ):
        self.event_type = event_type
        self.content = content
        self.timestamp = timestamp
        self.characters_involved = characters_involved
        self.emotional_impact = emotional_impact
        self.importance = importance
        self.tags = tags or []


class CharacterMemory:
    """Represents a character's memory."""

    def __init__(
        self,
        character_id: str,
        content: str,
        memory_type: str,
        emotional_score: float,
        importance: float,
        timestamp: datetime,
        tags: list[str],
    ):
        self.character_id = character_id
        self.content = content
        self.memory_type = memory_type
        self.emotional_score = emotional_score
        self.importance = importance
        self.timestamp = timestamp
        self.tags = tags
        self.memory_id = self._generate_memory_id()

    def _generate_memory_id(self) -> str:
        """Generate unique memory ID."""
        content_hash = hashlib.sha256(f"{self.character_id}_{self.content}_{self.timestamp}".encode()).hexdigest()
        return f"mem_{content_hash[:16]}"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "character_id": self.character_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "emotional_score": self.emotional_score,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterMemory":
        """Create from dictionary."""
        return cls(
            character_id=data["character_id"],
            content=data["content"],
            memory_type=data["memory_type"],
            emotional_score=data["emotional_score"],
            importance=data["importance"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tags=data["tags"],
        )


class MemoryConflict:
    """Represents a memory consistency conflict."""

    def __init__(
        self,
        conflict_type: str,
        severity: float,
        description: str,
        conflicting_memories: list[str],
    ):
        self.conflict_type = conflict_type
        self.severity = severity
        self.description = description
        self.conflicting_memories = conflicting_memories


class MemoryValidator:
    """
    Validates memory consistency and manages memory lifecycle.

    Handles memory generation, validation, conflict detection,
    and consistency checking for character memories.
    """

    def __init__(self, memory_port: IMemoryPort, config: dict | None = None):
        """Initialize memory validator."""
        self.config = config or {}
        self.json_utils = JSONUtilities()
        self.memory_port = memory_port

        # Configuration
        self.consistency_threshold = self.config.get("consistency_threshold", 0.8)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.9)
        self.max_memory_age_days = self.config.get("max_memory_age_days", 365)

        logger.info("MemoryValidator initialized")

    def generate_memories_from_event(self, character_id: str, event: MemoryEvent) -> list[dict[str, Any]]:
        """
        Generate character memories from a memory event.

        Args:
            character_id: ID of the character
            event: Memory event to process

        Returns:
            List of generated memories
        """
        try:
            memories = []

            # Generate primary memory for the event
            primary_memory = {
                "character_id": character_id,
                "content": event.content,
                "memory_type": f"{event.event_type}_primary",
                "emotional_score": event.emotional_impact,
                "importance": event.importance,
                "timestamp": event.timestamp,
                "tags": event.tags + [event.event_type],
            }
            memories.append(primary_memory)

            # Generate contextual memories based on event type
            if event.event_type == "dialogue":
                # Create memory about the conversation
                contextual_memory = {
                    "character_id": character_id,
                    "content": f"Had a conversation involving: {event.content[:100]}...",
                    "memory_type": "dialogue_context",
                    "emotional_score": event.emotional_impact * 0.7,
                    "importance": event.importance * 0.8,
                    "timestamp": event.timestamp,
                    "tags": event.tags + ["conversation", "social"],
                }
                memories.append(contextual_memory)

            elif event.event_type == "action":
                # Create memory about the action's consequences
                contextual_memory = {
                    "character_id": character_id,
                    "content": f"Performed action with outcome: {event.content[:100]}...",
                    "memory_type": "action_consequence",
                    "emotional_score": event.emotional_impact * 0.6,
                    "importance": event.importance * 0.9,
                    "timestamp": event.timestamp,
                    "tags": event.tags + ["action", "consequence"],
                }
                memories.append(contextual_memory)

            # Generate emotional memory if significant impact
            if abs(event.emotional_impact) > 0.5:
                emotional_memory = {
                    "character_id": character_id,
                    "content": (
                        f"Felt {self._interpret_emotional_score(event.emotional_impact)} "
                        f"about: {event.content[:50]}..."
                    ),
                    "memory_type": "emotional_reaction",
                    "emotional_score": event.emotional_impact,
                    "importance": abs(event.emotional_impact),
                    "timestamp": event.timestamp,
                    "tags": event.tags + ["emotion", "feeling"],
                }
                memories.append(emotional_memory)

        except (AttributeError, KeyError):
            logger.exception("Event data structure error generating memories")
            return []
        except (ValueError, TypeError):
            logger.exception("Event parameter error generating memories")
            return []
        else:
            return memories

    def validate_memory_consistency(
        self, character_id: str, new_memory: dict[str, Any], story_id: str = "default"
    ) -> dict[str, Any]:
        """
        Validate consistency of new memory against existing memories.

        Args:
            character_id: ID of the character
            new_memory: Memory to validate
            story_id: ID of the story context

        Returns:
            Dictionary with validation results
        """
        try:
            # Get existing memories for character
            existing_memories = self._get_character_memories(character_id, story_id)

            # Convert to CharacterMemory object
            memory_obj = CharacterMemory.from_dict(new_memory)

            # Check for conflicts
            conflicts = []

            # Temporal consistency check
            temporal_conflicts = self._check_temporal_consistency(memory_obj, existing_memories)
            conflicts.extend(temporal_conflicts)

            # Knowledge consistency check
            knowledge_conflicts = self._check_knowledge_consistency(memory_obj, existing_memories)
            conflicts.extend(knowledge_conflicts)

            # Calculate overall consistency confidence
            confidence = self._calculate_consistency_confidence(memory_obj, existing_memories)

            is_consistent = len(conflicts) == 0 and confidence >= self.consistency_threshold

            return {
                "is_consistent": is_consistent,
                "confidence": confidence,
                "conflicts": [conflict.__dict__ for conflict in conflicts],
                "validation_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception("Error validating memory consistency")
            return {
                "is_consistent": False,
                "confidence": 0.0,
                "conflicts": [],
                "error": str(e),
            }

    def retrieve_relevant_memories(
        self, character_id: str, context: str, max_memories: int = 5, story_id: str = "default"
    ) -> list[dict[str, Any]]:
        """
        Retrieve memories relevant to current context.

        Args:
            character_id: ID of the character
            context: Current context
            max_memories: Maximum memories to return
            story_id: ID of the story context

        Returns:
            List of relevant memories
        """
        try:
            # Get all memories for character
            memories = self._get_character_memories(character_id, story_id)

            # Extract keywords from context
            context_keywords = self._extract_keywords(context)

            # Calculate relevance scores
            scored_memories = []
            for memory in memories:
                relevance = self._calculate_memory_relevance(memory, context, context_keywords)
                scored_memories.append((memory, relevance))

            # Sort by relevance and return top results
            scored_memories.sort(key=lambda x: x[1], reverse=True)

            return [memory.to_dict() for memory, _ in scored_memories[:max_memories]]

        except (AttributeError, KeyError) as e:
            logger.exception("Memory data structure error retrieving relevant memories")
            return []
        except (ValueError, TypeError) as e:
            logger.exception("Memory parameter error retrieving relevant memories")
            return []
        except Exception as e:
            logger.exception("Error retrieving relevant memories")
            return []

    def compress_old_memories(self, character_id: str, retention_days: int = 30, story_id: str = "default") -> int:
        """
        Compress old memories to save storage.

        Args:
            character_id: ID of the character
            retention_days: Days to retain detailed memories
            story_id: ID of the story context

        Returns:
            Number of memories compressed
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            # Get old memories
            old_memories = self._get_memories_before_date(character_id, cutoff_date, story_id)

            # Group by week and create summaries
            compressed_count = 0
            weekly_groups = defaultdict(list)

            for memory in old_memories:
                week_key = memory.timestamp.strftime("%Y-W%U")
                weekly_groups[week_key].append(memory)

            # Create compressed summaries
            for week, memories in weekly_groups.items():
                if len(memories) > 5:  # Only compress if enough memories
                    summary = self._create_memory_summary(memories)
                    self._save_compressed_memory(character_id, summary, week, story_id)
                    self._delete_old_memories([m.memory_id for m in memories], character_id, story_id)
                    compressed_count += len(memories)
        except (AttributeError, KeyError) as e:
            logger.exception("Memory data structure error compressing memories")
            return 0
        except (OSError, IOError) as e:
            logger.exception("Storage error compressing memories")
            return 0
        except Exception as e:
            logger.exception("Error compressing memories")
            return 0
        else:
            return compressed_count

    def get_memory_context_for_prompt(
        self, character_id: str, current_context: str, max_tokens: int = 500, story_id: str = "default"
    ) -> str:
        """
        Generate memory context for prompt.

        Args:
            character_id: ID of the character
            current_context: Current context
            max_tokens: Maximum tokens
            story_id: ID of the story context

        Returns:
            Formatted memory context
        """
        try:
            # Get relevant memories
            relevant_memories = self.retrieve_relevant_memories(
                character_id, current_context, max_memories=10, story_id=story_id
            )

            # Format for prompt
            context_parts = []
            token_count = 0

            for memory in relevant_memories:
                memory_text = f"Memory: {memory['content']} (Importance: {memory['importance']:.1f})"
                # Rough token estimation (4 chars per token)
                estimated_tokens = len(memory_text) // 4

                if token_count + estimated_tokens <= max_tokens:
                    context_parts.append(memory_text)
                    token_count += estimated_tokens
                else:
                    break

            return "\n".join(context_parts)

        except (AttributeError, KeyError) as e:
            logger.exception("Memory data structure error generating context")
            return ""
        except (ValueError, TypeError) as e:
            logger.exception("Memory parameter error generating context")
            return ""
        except Exception as e:
            logger.exception("Error generating memory context")
            return ""

    def export_character_memories(self, character_id: str, story_id: str = "default") -> dict[str, Any]:
        """Export character memories."""
        try:
            memories = self._get_character_memories(character_id, story_id)
            return {
                "character_id": character_id,
                "export_timestamp": datetime.now().isoformat(),
                "memory_count": len(memories),
                "memories": [memory.to_dict() for memory in memories],
            }
        except (KeyError, AttributeError) as e:
            logger.exception("Memory data structure error exporting memories")
            return {}
        except (ValueError, TypeError) as e:
            logger.exception("Memory parameter error exporting memories")
            return {}
        except Exception as e:
            logger.exception("Error exporting memories")
            return {}

    def import_character_memories(self, data: dict[str, Any], story_id: str = "default") -> None:
        """Import character memories."""
        try:
            character_id = data["character_id"]
            memories = data["memories"]

            for memory_data in memories:
                memory = CharacterMemory.from_dict(memory_data)
                self._save_memory(memory, story_id)

            logger.info(f"Imported {len(memories)} memories for character {character_id}")

        except (KeyError, AttributeError) as e:
            logger.exception("Memory import data structure error")
            raise
        except (ValueError, TypeError) as e:
            logger.exception("Memory import parameter error")
            raise
        except Exception as e:
            logger.exception("Error importing memories")
            raise

    def _get_character_memories(self, character_id: str, story_id: str = "default") -> list[CharacterMemory]:
        """Get all memories for a character from the repository."""
        try:
            # Load memory state from repository
            memory_state = self.memory_port.load_memory(story_id)

            # Extract character memories
            if character_id in memory_state.characters:
                character = memory_state.characters[character_id]
                # Convert repository CharacterMemory to local CharacterMemory format
                # Note: This adapts between infrastructure and domain models
                memories = []

                # Convert dialogue history to CharacterMemory objects
                for dialogue in character.dialogue_history:
                    memory = CharacterMemory(
                        character_id=character_id,
                        content=dialogue.get("content", ""),
                        memory_type="dialogue",
                        emotional_score=dialogue.get("emotional_score", 0.0),
                        importance=dialogue.get("importance", 0.5),
                        timestamp=datetime.fromisoformat(dialogue.get("timestamp", datetime.now().isoformat())),
                        tags=dialogue.get("tags", []),
                    )
                    memories.append(memory)

                result_memories = memories
            else:
                result_memories = []
        except (AttributeError, KeyError) as e:
            logger.exception("Error accessing character memory data")
            return []
        except (ValueError, TypeError) as e:
            logger.exception("Error with character memory parameters")
            return []
        except Exception as e:
            logger.exception("Error getting character memories")
            return []
        else:
            return result_memories

    def _get_memories_before_date(
        self, character_id: str, date: datetime, story_id: str = "default"
    ) -> list[CharacterMemory]:
        """Get memories before specified date from the repository."""
        try:
            # Get all character memories first
            all_memories = self._get_character_memories(character_id, story_id)

            # Filter by date
            filtered_memories = [memory for memory in all_memories if memory.timestamp < date]
        except (AttributeError, KeyError) as e:
            logger.exception("Error accessing memory date data")
            return []
        except (ValueError, TypeError) as e:
            logger.exception("Error with memory date parameters")
            return []
        except Exception as e:
            logger.exception("Error getting memories before date")
            return []
        else:
            return filtered_memories

    def _save_memory(self, memory: CharacterMemory, story_id: str = "default") -> None:
        """Save memory to repository."""
        try:
            # Load current memory state
            memory_state = self.memory_port.load_memory(story_id)

            # Ensure character exists in memory state
            if memory.character_id not in memory_state.characters:
                # Use domain CharacterMemory model
                memory_state.characters[memory.character_id] = DomainCharacterMemory(name=memory.character_id)

            # Convert domain memory to infrastructure format and add to dialogue history
            character = memory_state.characters[memory.character_id]
            dialogue_entry = {
                "content": memory.content,
                "memory_type": memory.memory_type,
                "emotional_score": memory.emotional_score,
                "importance": memory.importance,
                "timestamp": memory.timestamp.isoformat(),
                "tags": memory.tags,
            }

            # Add to dialogue history
            character.dialogue_history.append(dialogue_entry)

            # Save updated memory state
            success = self.memory_port.save_memory(story_id, memory_state)

            if not success:
                logger.warning(f"Failed to save memory for character {memory.character_id}")

        except (AttributeError, KeyError) as e:
            logger.exception("Error accessing memory save data")
            raise
        except (ValueError, TypeError) as e:
            logger.exception("Error with memory save parameters")
            raise
        except Exception as e:
            logger.exception("Error saving memory")
            raise

    def _save_compressed_memory(self, character_id: str, summary: str, week: str, story_id: str = "default") -> None:
        """Save compressed memory summary to repository."""
        try:
            # Load current memory state
            memory_state = self.memory_port.load_memory(story_id)

            # Ensure character exists
            if character_id not in memory_state.characters:
                memory_state.characters[character_id] = DomainCharacterMemory(name=character_id)

            # Add compressed summary to character's background or create summary section
            character = memory_state.characters[character_id]

            # Add to background or create a summary tracking system
            summary_entry = f"Week {week} Summary: {summary}"
            if character.background:
                character.background += f"\n\n{summary_entry}"
            else:
                character.background = summary_entry

            # Save updated memory state
            success = self.memory_port.save_memory(story_id, memory_state)

            if not success:
                logger.warning(f"Failed to save compressed memory for character {character_id}")

        except (AttributeError, KeyError) as e:
            logger.exception("Error accessing compressed memory data")
            raise
        except (ValueError, TypeError) as e:
            logger.exception("Error with compressed memory parameters")
            raise
        except Exception as e:
            logger.exception("Error saving compressed memory")
            raise

    def _delete_old_memories(self, memory_ids: list[str], character_id: str, story_id: str = "default") -> None:
        """Delete old memories from repository based on memory content or index."""
        try:
            # Load current memory state
            memory_state = self.memory_port.load_memory(story_id)

            if character_id not in memory_state.characters:
                logger.warning(f"Character {character_id} not found in memory state")
                return

            character = memory_state.characters[character_id]

            # Since we don't have direct memory IDs in the current structure,
            # we'll remove the oldest memories based on the count in memory_ids
            # This is a practical implementation that maintains memory bounds

            if len(character.dialogue_history) > len(memory_ids):
                # Remove the oldest entries
                memories_to_remove = len(memory_ids)
                character.dialogue_history = character.dialogue_history[memories_to_remove:]

                logger.info(f"Removed {memories_to_remove} old memories for character {character_id}")

            # Save updated memory state
            success = self.memory_port.save_memory(story_id, memory_state)

            if not success:
                logger.warning(f"Failed to delete old memories for character {character_id}")

        except (AttributeError, KeyError) as e:
            logger.exception("Error accessing memory deletion data")
            raise
        except (ValueError, TypeError) as e:
            logger.exception("Error with memory deletion parameters")
            raise
        except Exception as e:
            logger.exception("Error deleting old memories")
            raise

    def _create_memory_summary(self, memories: list[CharacterMemory]) -> str:
        """Create summary of multiple memories."""
        # Extract key themes and events
        content_parts = [memory.content for memory in memories]
        combined_content = " ".join(content_parts)

        # Simple summarization (could be enhanced with AI)
        return f"Weekly summary: {combined_content[:200]}..."

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text."""
        # Simple keyword extraction
        words = re.findall(r"\b\w+\b", text.lower())
        # Filter out common words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return list(set(keywords))

    def _calculate_memory_relevance(self, memory: CharacterMemory, context: str, context_keywords: list[str]) -> float:
        """Calculate relevance score for memory."""
        relevance = 0.0

        # Keyword matching
        memory_keywords = self._extract_keywords(memory.content)
        common_keywords = set(memory_keywords) & set(context_keywords)
        keyword_score = len(common_keywords) / max(len(context_keywords), 1)
        relevance += keyword_score * 0.4

        # Importance factor
        relevance += memory.importance * 0.3

        # Recency factor (more recent = more relevant)
        days_ago = (datetime.now() - memory.timestamp).days
        recency_score = max(0, 1 - (days_ago / 365))  # Decay over year
        relevance += recency_score * 0.2

        # Emotional significance
        relevance += abs(memory.emotional_score) * 0.1

        return min(relevance, 1.0)

    def _check_temporal_consistency(
        self, new_memory: CharacterMemory, existing_memories: list[CharacterMemory]
    ) -> list[MemoryConflict]:
        """Check for temporal inconsistencies."""
        conflicts = []

        for existing in existing_memories:
            # Check for impossible temporal sequences
            if new_memory.timestamp < existing.timestamp:
                # Check if new memory contradicts later events
                if self._detect_temporal_contradiction(new_memory, existing):
                    conflict = MemoryConflict(
                        conflict_type="temporal_inconsistency",
                        severity=0.8,
                        description="New memory occurs before conflicting later memory",
                        conflicting_memories=[new_memory.memory_id, existing.memory_id],
                    )
                    conflicts.append(conflict)

        return conflicts

    def _check_knowledge_consistency(
        self, new_memory: CharacterMemory, existing_memories: list[CharacterMemory]
    ) -> list[MemoryConflict]:
        """Check for knowledge inconsistencies."""
        conflicts = []

        for existing in existing_memories:
            contradiction = self._detect_memory_contradiction(new_memory, existing)
            if contradiction:
                conflicts.append(contradiction)

        return conflicts

    def _detect_memory_contradiction(
        self, new_memory: CharacterMemory, existing_memory: CharacterMemory
    ) -> MemoryConflict | None:
        """Detect contradiction between memories."""
        # Simple contradiction detection based on opposing keywords
        opposing_pairs = [
            (["love", "like", "enjoy"], ["hate", "dislike", "despise"]),
            (["friend", "ally"], ["enemy", "foe"]),
            (["trust", "believe"], ["distrust", "doubt"]),
            (["alive", "living"], ["dead", "deceased"]),
        ]

        new_keywords = self._extract_keywords(new_memory.content)
        existing_keywords = self._extract_keywords(existing_memory.content)

        for positive_words, negative_words in opposing_pairs:
            new_has_positive = any(word in new_keywords for word in positive_words)
            new_has_negative = any(word in new_keywords for word in negative_words)
            existing_has_positive = any(word in existing_keywords for word in positive_words)
            existing_has_negative = any(word in existing_keywords for word in negative_words)

            if (new_has_positive and existing_has_negative) or (new_has_negative and existing_has_positive):
                return MemoryConflict(
                    conflict_type="knowledge_contradiction",
                    severity=0.7,
                    description="Contradicting emotional/factual content detected",
                    conflicting_memories=[
                        new_memory.memory_id,
                        existing_memory.memory_id,
                    ],
                )

        return None

    def _detect_temporal_contradiction(self, new_memory: CharacterMemory, existing_memory: CharacterMemory) -> bool:
        """Detect temporal contradiction between memories."""
        # Simple temporal contradiction detection
        # This would be enhanced with more sophisticated logic
        return False

    def _calculate_consistency_confidence(
        self, new_memory: CharacterMemory, existing_memories: list[CharacterMemory]
    ) -> float:
        """Calculate confidence in memory consistency."""
        if not existing_memories:
            return 1.0

        # Calculate based on similarity to existing memories
        similarities = []
        for existing in existing_memories:
            similarity = self._calculate_memory_similarity(new_memory, existing)
            similarities.append(similarity)

        # High similarity to existing memories suggests consistency
        avg_similarity = sum(similarities) / len(similarities)
        return min(avg_similarity + 0.3, 1.0)  # Boost confidence slightly

    def _calculate_memory_similarity(self, memory1: CharacterMemory, memory2: CharacterMemory) -> float:
        """Calculate similarity between two memories."""
        # Simple similarity based on keyword overlap
        keywords1 = set(self._extract_keywords(memory1.content))
        keywords2 = set(self._extract_keywords(memory2.content))

        if not keywords1 or not keywords2:
            return 0.0

        intersection = keywords1 & keywords2
        union = keywords1 | keywords2

        return len(intersection) / len(union)

    def _interpret_emotional_score(self, score: float) -> str:
        """Interpret emotional score as text."""
        if score > 0.7:
            return "very positive"
        if score > 0.3:
            return "positive"
        if score > -0.3:
            return "neutral"
        if score > -0.7:
            return "negative"
        return "very negative"

    def get_status(self) -> dict[str, Any]:
        """Get validator status."""
        return {
            "memory_validator": {
                "initialized": True,
                "consistency_threshold": self.consistency_threshold,
                "similarity_threshold": self.similarity_threshold,
                "max_memory_age_days": self.max_memory_age_days,
            }
        }
