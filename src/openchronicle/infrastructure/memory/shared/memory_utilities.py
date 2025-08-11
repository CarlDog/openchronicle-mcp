"""
Memory Utilities for Memory Management System
==========================================

Provides utility functions and helper classes for memory management operations.
This module contains common functionality used across memory management components.

Created as part of Phase 5B Memory Management Enhancement
"""

import json
import hashlib
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryMetrics:
    """Container for memory operation metrics."""

    total_memories: int = 0
    character_memories: int = 0
    world_memories: int = 0
    recent_memories: int = 0
    average_importance: float = 0.0
    storage_size_bytes: int = 0


class MemoryUtilities:
    """
    Utility functions for memory management operations.

    Provides common functionality used across memory management components
    including serialization, hashing, filtering, and validation.
    """

    @staticmethod
    def serialize_memory_data(data: Any) -> str:
        """
        Serialize memory data to JSON string.

        Args:
            data: Data to serialize

        Returns:
            JSON string representation
        """
        try:
            if isinstance(data, str):
                return data

            return json.dumps(data, default=str, ensure_ascii=False, indent=None)

        except Exception as e:
            logger.error(f"Error serializing memory data: {e}")
            return "{}"

    @staticmethod
    def deserialize_memory_data(data: str) -> Any:
        """
        Deserialize memory data from JSON string.

        Args:
            data: JSON string to deserialize

        Returns:
            Deserialized data
        """
        try:
            if not data or not isinstance(data, str):
                return {}

            return json.loads(data)

        except Exception as e:
            logger.error(f"Error deserializing memory data: {e}")
            return {}

    @staticmethod
    def generate_memory_hash(content: str, context: Optional[str] = None) -> str:
        """
        Generate a hash for memory content to detect duplicates.

        Args:
            content: Memory content
            context: Optional context for hash generation

        Returns:
            SHA-256 hash string
        """
        hash_input = content
        if context:
            hash_input = f"{content}|{context}"

        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    @staticmethod
    def calculate_importance_score(
        content: str,
        memory_type: str,
        character_mentions: int = 0,
        emotion_intensity: float = 0.0,
    ) -> float:
        """
        Calculate importance score for a memory entry.

        Args:
            content: Memory content
            memory_type: Type of memory
            character_mentions: Number of character mentions
            emotion_intensity: Emotional intensity (0.0 to 1.0)

        Returns:
            Importance score (0.0 to 1.0)
        """
        base_score = 0.5

        # Adjust based on memory type
        type_weights = {
            "dialogue": 0.8,
            "action": 0.7,
            "emotion": 0.9,
            "description": 0.5,
            "event": 0.8,
            "relationship": 0.9,
            "world_event": 0.6,
        }

        type_weight = type_weights.get(memory_type.lower(), 0.5)

        # Adjust based on content length
        content_factor = min(len(content) / 500.0, 1.0)

        # Adjust based on character mentions
        mention_factor = min(character_mentions * 0.1, 0.3)

        # Combine factors
        importance = (
            base_score * type_weight
            + content_factor * 0.2
            + mention_factor
            + emotion_intensity * 0.3
        )

        return min(max(importance, 0.0), 1.0)

    @staticmethod
    def filter_memories_by_relevance(
        memories: List[Dict[str, Any]], query_context: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Filter memories by relevance to a query context.

        Args:
            memories: List of memory dictionaries
            query_context: Context to filter against
            max_results: Maximum number of results to return

        Returns:
            Filtered and sorted list of memories
        """
        if not memories or not query_context:
            return memories[:max_results]

        query_words = set(query_context.lower().split())

        def calculate_relevance(memory: Dict[str, Any]) -> float:
            content = memory.get("content", "").lower()
            content_words = set(content.split())

            # Calculate word overlap
            overlap = len(query_words.intersection(content_words))
            relevance = overlap / max(len(query_words), 1)

            # Boost by importance score
            importance = memory.get("importance_score", 0.0)
            relevance += importance * 0.3

            # Boost recent memories
            timestamp = memory.get("timestamp")
            if timestamp:
                try:
                    mem_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    age_hours = (datetime.now() - mem_time).total_seconds() / 3600
                    recency_boost = max(0, 1 - (age_hours / 168))  # Decay over a week
                    relevance += recency_boost * 0.2
                except Exception:
                    pass

            return relevance

        # Score and sort memories
        scored_memories = [(memory, calculate_relevance(memory)) for memory in memories]
        scored_memories.sort(key=lambda x: x[1], reverse=True)

        return [memory for memory, score in scored_memories[:max_results]]

    @staticmethod
    def merge_similar_memories(
        memories: List[Dict[str, Any]], similarity_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Merge similar memories to reduce redundancy.

        Args:
            memories: List of memory dictionaries
            similarity_threshold: Threshold for considering memories similar

        Returns:
            List of merged memories
        """
        if len(memories) <= 1:
            return memories

        merged = []
        processed = set()

        for i, memory in enumerate(memories):
            if i in processed:
                continue

            similar_memories = [memory]
            content_words = set(memory.get("content", "").lower().split())

            for j, other_memory in enumerate(memories[i + 1 :], start=i + 1):
                if j in processed:
                    continue

                other_words = set(other_memory.get("content", "").lower().split())

                if content_words and other_words:
                    similarity = len(content_words.intersection(other_words)) / len(
                        content_words.union(other_words)
                    )

                    if similarity >= similarity_threshold:
                        similar_memories.append(other_memory)
                        processed.add(j)

            # If we have similar memories, merge them
            if len(similar_memories) > 1:
                merged_memory = MemoryUtilities._merge_memory_group(similar_memories)
            else:
                merged_memory = memory

            merged.append(merged_memory)
            processed.add(i)

        return merged

    @staticmethod
    def _merge_memory_group(memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge a group of similar memories into one.

        Args:
            memories: List of similar memory dictionaries

        Returns:
            Merged memory dictionary
        """
        if not memories:
            return {}

        if len(memories) == 1:
            return memories[0]

        # Use the memory with highest importance as base
        base_memory = max(memories, key=lambda m: m.get("importance_score", 0.0))
        merged = base_memory.copy()

        # Combine content
        all_content = [m.get("content", "") for m in memories if m.get("content")]
        unique_content = []
        seen_content = set()

        for content in all_content:
            content_lower = content.lower().strip()
            if content_lower and content_lower not in seen_content:
                unique_content.append(content)
                seen_content.add(content_lower)

        merged["content"] = " | ".join(unique_content)

        # Update importance to maximum
        merged["importance_score"] = max(
            m.get("importance_score", 0.0) for m in memories
        )

        # Update timestamp to most recent
        timestamps = [m.get("timestamp") for m in memories if m.get("timestamp")]
        if timestamps:
            merged["timestamp"] = max(timestamps)

        # Add merge metadata
        merged["merged_count"] = len(memories)
        merged["merge_timestamp"] = datetime.now().isoformat()

        return merged

    @staticmethod
    def validate_memory_entry(memory: Dict[str, Any]) -> bool:
        """
        Validate a memory entry has required fields.

        Args:
            memory: Memory dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["content", "memory_type"]

        for field in required_fields:
            if field not in memory or not memory[field]:
                logger.warning(f"Memory entry missing required field: {field}")
                return False

        # Validate importance score
        importance = memory.get("importance_score", 0.0)
        if not isinstance(importance, (int, float)) or importance < 0 or importance > 1:
            logger.warning(f"Invalid importance score: {importance}")
            return False

        return True

    @staticmethod
    def clean_memory_content(content: str) -> str:
        """
        Clean and normalize memory content.

        Args:
            content: Raw memory content

        Returns:
            Cleaned content
        """
        if not content or not isinstance(content, str):
            return ""

        # Basic cleaning
        cleaned = content.strip()

        # Remove excessive whitespace
        cleaned = " ".join(cleaned.split())

        # Remove control characters
        cleaned = "".join(char for char in cleaned if ord(char) >= 32)

        return cleaned

    @staticmethod
    def get_memory_metrics(memories: List[Dict[str, Any]]) -> MemoryMetrics:
        """
        Calculate metrics for a collection of memories.

        Args:
            memories: List of memory dictionaries

        Returns:
            MemoryMetrics object with statistics
        """
        if not memories:
            return MemoryMetrics()

        total_memories = len(memories)
        character_memories = sum(1 for m in memories if m.get("character_id"))
        world_memories = sum(
            1 for m in memories if m.get("memory_type") == "world_event"
        )

        # Count recent memories (last 24 hours)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_memories = 0
        importance_scores = []

        for memory in memories:
            # Check recency
            timestamp = memory.get("timestamp")
            if timestamp:
                try:
                    mem_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    if mem_time >= recent_cutoff:
                        recent_memories += 1
                except Exception:
                    pass

            # Collect importance scores
            importance = memory.get("importance_score", 0.0)
            if isinstance(importance, (int, float)):
                importance_scores.append(importance)

        # Calculate average importance
        average_importance = (
            sum(importance_scores) / len(importance_scores)
            if importance_scores
            else 0.0
        )

        # Estimate storage size
        storage_size = sum(
            len(MemoryUtilities.serialize_memory_data(m)) for m in memories
        )

        return MemoryMetrics(
            total_memories=total_memories,
            character_memories=character_memories,
            world_memories=world_memories,
            recent_memories=recent_memories,
            average_importance=round(average_importance, 3),
            storage_size_bytes=storage_size,
        )

    @staticmethod
    def format_memory_for_display(memory: Dict[str, Any], max_length: int = 200) -> str:
        """
        Format a memory entry for display purposes.

        Args:
            memory: Memory dictionary
            max_length: Maximum length of formatted string

        Returns:
            Formatted memory string
        """
        content = memory.get("content", "No content")
        memory_type = memory.get("memory_type", "unknown")
        importance = memory.get("importance_score", 0.0)
        timestamp = memory.get("timestamp", "")

        # Format timestamp
        time_str = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = timestamp[:16]  # Fallback

        # Truncate content if needed
        if len(content) > max_length:
            content = content[: max_length - 3] + "..."

        # Format display string
        parts = [f"[{memory_type}]"]
        if time_str:
            parts.append(f"({time_str})")
        parts.append(f"Score: {importance:.2f}")
        parts.append(f"- {content}")

        return " ".join(parts)


# Convenience functions
def serialize_memory(data: Any) -> str:
    """Serialize memory data to JSON string."""
    return MemoryUtilities.serialize_memory_data(data)


def deserialize_memory(data: str) -> Any:
    """Deserialize memory data from JSON string."""
    return MemoryUtilities.deserialize_memory_data(data)


def calculate_importance(content: str, memory_type: str, **kwargs) -> float:
    """Calculate importance score for memory content."""
    return MemoryUtilities.calculate_importance_score(content, memory_type, **kwargs)


def validate_memory(memory: Dict[str, Any]) -> bool:
    """Validate a memory entry."""
    return MemoryUtilities.validate_memory_entry(memory)
