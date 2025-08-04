"""
Memory Consistency Engine: Persistent Character Memory System

This module implements a sophisticated memory consistency system that maintains
coherent character memories across story sessions, prevents contradictions,
and ensures character development persistence.

Key Features:
- Persistent character memory tracking across sessions
- Memory consistency validation and contradiction detection
- Intelligent memory retrieval with relevance scoring
- Character development tracking and arc consistency
- Cross-engine integration for memory-guided story generation
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import math
import re

# Setup logging
logger = logging.getLogger(__name__)

class MemoryType(Enum):
    """Types of character memories."""
    FACTUAL = "factual"           # Objective information and events
    EMOTIONAL = "emotional"       # Feelings and emotional responses
    RELATIONAL = "relational"     # Character relationships and interactions
    SKILL = "skill"              # Learned abilities and knowledge
    EXPERIENTIAL = "experiential" # Personal experiences and adventures
    TEMPORAL = "temporal"         # Time-based memories and sequences

class MemoryImportance(Enum):
    """Memory importance levels for retention and retrieval."""
    TRIVIAL = 1      # Forgettable details
    LOW = 2          # Minor events
    MODERATE = 3     # Notable events
    HIGH = 4         # Important developments
    CRITICAL = 5     # Life-changing events

class ConsistencyStatus(Enum):
    """Memory consistency validation status."""
    VALIDATED = "validated"
    PENDING = "pending"
    CONFLICTED = "conflicted"
    RESOLVED = "resolved"

@dataclass
class CharacterMemory:
    """Individual character memory entry."""
    memory_id: str
    character_id: str
    memory_type: MemoryType
    content: str
    importance_score: float
    timestamp: datetime
    related_characters: List[str] = field(default_factory=list)
    emotional_context: str = ""
    verification_status: ConsistencyStatus = ConsistencyStatus.PENDING
    keywords: List[str] = field(default_factory=list)
    location: str = ""
    consequences: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'memory_id': self.memory_id,
            'character_id': self.character_id,
            'memory_type': self.memory_type.value,
            'content': self.content,
            'importance_score': self.importance_score,
            'timestamp': self.timestamp.isoformat(),
            'related_characters': self.related_characters,
            'emotional_context': self.emotional_context,
            'verification_status': self.verification_status.value,
            'keywords': self.keywords,
            'location': self.location,
            'consequences': self.consequences
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CharacterMemory':
        """Create from dictionary."""
        return cls(
            memory_id=data['memory_id'],
            character_id=data['character_id'],
            memory_type=MemoryType(data['memory_type']),
            content=data['content'],
            importance_score=data['importance_score'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            related_characters=data.get('related_characters', []),
            emotional_context=data.get('emotional_context', ''),
            verification_status=ConsistencyStatus(data.get('verification_status', 'pending')),
            keywords=data.get('keywords', []),
            location=data.get('location', ''),
            consequences=data.get('consequences', [])
        )

@dataclass
class MemoryEvent:
    """Structured event for creating character memories."""
    event_id: str
    description: str
    participants: List[str]
    location: str = ""
    emotional_impact: Dict[str, float] = field(default_factory=dict)
    consequences: List[str] = field(default_factory=list)
    memory_significance: float = 3.0
    event_type: str = "general"
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class MemoryConflict:
    """Represents a detected memory consistency conflict."""
    conflict_id: str
    character_id: str
    conflicting_memories: List[str]  # Memory IDs
    conflict_type: str
    severity: str
    description: str
    suggested_resolution: str
    timestamp: datetime = field(default_factory=datetime.now)

class MemoryConsistencyEngine:
    """
    Manages character memory consistency, persistence, and intelligent retrieval.
    
    This engine ensures characters maintain coherent memories across story sessions,
    detects contradictions, and provides context-aware memory retrieval.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the memory consistency engine."""
        self.config = config or {}
        
        # Memory storage
        self.character_memories: Dict[str, List[CharacterMemory]] = {}
        self.memory_conflicts: List[MemoryConflict] = []
        self.character_development: Dict[str, Dict[str, Any]] = {}
        
        # Configuration settings
        self.max_memories_per_character = self.config.get('max_memories_per_character', 1000)
        self.memory_decay_rate = self.config.get('memory_decay_rate', 0.95)  # Per week
        self.consistency_threshold = self.config.get('consistency_threshold', 0.8)
        self.relevance_threshold = self.config.get('relevance_threshold', 0.2)  # Lowered from 0.3
        
        # Memory keywords for context matching
        self.emotional_keywords = {
            'positive': ['happy', 'joy', 'love', 'excited', 'proud', 'confident', 'satisfied'],
            'negative': ['sad', 'angry', 'fear', 'worried', 'disappointed', 'frustrated', 'ashamed'],
            'neutral': ['calm', 'focused', 'curious', 'thoughtful', 'determined']
        }
        
        # Character development tracking
        self.development_categories = [
            'personality_growth', 'skill_advancement', 'relationship_changes',
            'knowledge_gained', 'emotional_maturity', 'goal_evolution'
        ]
    
    def add_memory(self, character_id: str, memory_event: MemoryEvent) -> List[CharacterMemory]:
        """Add a new memory event for a character, creating individual memories."""
        if character_id not in self.character_memories:
            self.character_memories[character_id] = []
        
        memories_created = []
        
        # Create different types of memories from the event
        memories_to_create = self._generate_memories_from_event(character_id, memory_event)
        
        for memory_data in memories_to_create:
            memory = CharacterMemory(
                memory_id=self._generate_memory_id(character_id, memory_data['content']),
                character_id=character_id,
                memory_type=memory_data['type'],
                content=memory_data['content'],
                importance_score=memory_data['importance'],
                timestamp=memory_event.timestamp,
                related_characters=[p for p in memory_event.participants if p != character_id],
                emotional_context=memory_data.get('emotional_context', ''),
                keywords=self._extract_keywords(memory_data['content']),
                location=memory_event.location,
                consequences=memory_event.consequences
            )
            
            # Validate consistency before adding
            consistency_result = self.validate_memory_consistency(character_id, memory)
            memory.verification_status = consistency_result['status']
            
            self.character_memories[character_id].append(memory)
            memories_created.append(memory)
            
            # Log conflicts if found
            if consistency_result['conflicts']:
                for conflict in consistency_result['conflicts']:
                    self.memory_conflicts.append(conflict)
                    logger.warning(f"Memory conflict detected for {character_id}: {conflict.description}")
        
        # Update character development tracking
        self._update_character_development(character_id, memory_event)
        
        # Manage memory capacity
        self._manage_memory_capacity(character_id)
        
        logger.info(f"Added {len(memories_created)} memories for {character_id}")
        return memories_created
    
    def retrieve_relevant_memories(self, character_id: str, context: str, 
                                 max_memories: int = 10, memory_types: Optional[List[MemoryType]] = None) -> List[CharacterMemory]:
        """Retrieve the most relevant memories for a given context."""
        if character_id not in self.character_memories:
            return []
        
        character_memories = self.character_memories[character_id]
        
        # Filter by memory types if specified
        if memory_types:
            character_memories = [m for m in character_memories if m.memory_type in memory_types]
        
        # Filter by verification status (exclude conflicted memories)
        character_memories = [m for m in character_memories if m.verification_status != ConsistencyStatus.CONFLICTED]
        
        # Calculate relevance scores
        scored_memories = []
        context_keywords = self._extract_keywords(context.lower())
        
        for memory in character_memories:
            relevance_score = self._calculate_memory_relevance(memory, context, context_keywords)
            if relevance_score >= self.relevance_threshold:
                scored_memories.append((memory, relevance_score))
        
        # Sort by relevance score (descending)
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        
        # Return top memories
        return [memory for memory, score in scored_memories[:max_memories]]
    
    def validate_memory_consistency(self, character_id: str, new_memory: CharacterMemory) -> Dict[str, Any]:
        """Validate if a new memory is consistent with existing character memories."""
        if character_id not in self.character_memories:
            return {'status': ConsistencyStatus.VALIDATED, 'conflicts': []}
        
        existing_memories = self.character_memories[character_id]
        conflicts = []
        
        # Check for direct contradictions
        for existing_memory in existing_memories:
            conflict = self._detect_memory_contradiction(new_memory, existing_memory)
            if conflict:
                conflicts.append(conflict)
        
        # Check temporal consistency
        temporal_conflicts = self._check_temporal_consistency(new_memory, existing_memories)
        conflicts.extend(temporal_conflicts)
        
        # Check character knowledge consistency
        knowledge_conflicts = self._check_knowledge_consistency(new_memory, existing_memories)
        conflicts.extend(knowledge_conflicts)
        
        # Determine overall status
        if not conflicts:
            status = ConsistencyStatus.VALIDATED
        elif any(c.severity == 'high' for c in conflicts):
            status = ConsistencyStatus.CONFLICTED
        else:
            status = ConsistencyStatus.PENDING
        
        return {
            'status': status,
            'conflicts': conflicts,
            'confidence': self._calculate_consistency_confidence(new_memory, existing_memories)
        }
    
    def get_character_memory_summary(self, character_id: str) -> Dict[str, Any]:
        """Get a comprehensive summary of a character's memory state."""
        if character_id not in self.character_memories:
            return {'character_id': character_id, 'total_memories': 0}
        
        memories = self.character_memories[character_id]
        
        # Count by memory type
        type_counts = {}
        for memory_type in MemoryType:
            type_counts[memory_type.value] = sum(1 for m in memories if m.memory_type == memory_type)
        
        # Count by importance
        importance_distribution = {}
        for i in range(1, 6):
            importance_distribution[f'level_{i}'] = sum(1 for m in memories if int(m.importance_score) == i)
        
        # Recent memories (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_memories = [m for m in memories if m.timestamp > week_ago]
        
        # Memory conflicts
        character_conflicts = [c for c in self.memory_conflicts if c.character_id == character_id]
        
        return {
            'character_id': character_id,
            'total_memories': len(memories),
            'memory_types': type_counts,
            'importance_distribution': importance_distribution,
            'recent_memories_count': len(recent_memories),
            'conflicts_count': len(character_conflicts),
            'oldest_memory': min(memories, key=lambda m: m.timestamp).timestamp.isoformat() if memories else None,
            'newest_memory': max(memories, key=lambda m: m.timestamp).timestamp.isoformat() if memories else None,
            'character_development': self.character_development.get(character_id, {})
        }
    
    def compress_old_memories(self, character_id: str, retention_days: int = 30) -> int:
        """Compress or remove old, low-importance memories to manage capacity."""
        if character_id not in self.character_memories:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        memories = self.character_memories[character_id]
        
        # Separate memories into keep and compress categories
        memories_to_keep = []
        memories_to_compress = []
        
        for memory in memories:
            if (memory.timestamp > cutoff_date or 
                memory.importance_score >= 4 or  # Keep important memories
                memory.verification_status == ConsistencyStatus.VALIDATED):
                memories_to_keep.append(memory)
            else:
                memories_to_compress.append(memory)
        
        # Create compressed summary of old memories
        if memories_to_compress:
            compressed_memory = self._create_compressed_memory(character_id, memories_to_compress)
            memories_to_keep.append(compressed_memory)
        
        original_count = len(memories)
        self.character_memories[character_id] = memories_to_keep
        
        compressed_count = original_count - len(memories_to_keep) + (1 if memories_to_compress else 0)
        
        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} old memories for {character_id}")
        
        return compressed_count
    
    def get_memory_context_for_prompt(self, character_id: str, current_context: str, 
                                    max_tokens: int = 500) -> str:
        """Generate memory context snippet for inclusion in story prompts."""
        relevant_memories = self.retrieve_relevant_memories(character_id, current_context, max_memories=10)
        
        if not relevant_memories:
            return ""
        
        # Group memories by type for better organization
        memory_groups = {}
        for memory in relevant_memories:
            memory_type = memory.memory_type.value
            if memory_type not in memory_groups:
                memory_groups[memory_type] = []
            memory_groups[memory_type].append(memory)
        
        # Build context string
        context_parts = [f"[CHARACTER_MEMORIES: {character_id}]"]
        
        for memory_type, memories in memory_groups.items():
            if memories:
                context_parts.append(f"\n{memory_type.upper()}:")
                for memory in memories[:3]:  # Limit to top 3 per type
                    # Truncate long memories
                    content = memory.content[:100] + "..." if len(memory.content) > 100 else memory.content
                    context_parts.append(f"- {content}")
        
        context_string = "\n".join(context_parts)
        
        # Ensure we don't exceed token limit (rough estimation)
        if len(context_string) > max_tokens * 4:  # ~4 chars per token
            context_string = context_string[:max_tokens * 4] + "..."
        
        return context_string
    
    def export_character_memories(self, character_id: str) -> Dict[str, Any]:
        """Export all memories for a character."""
        if character_id not in self.character_memories:
            return {'character_id': character_id, 'memories': []}
        
        return {
            'character_id': character_id,
            'memories': [memory.to_dict() for memory in self.character_memories[character_id]],
            'conflicts': [
                {
                    'conflict_id': c.conflict_id,
                    'conflict_type': c.conflict_type,
                    'severity': c.severity,
                    'description': c.description,
                    'timestamp': c.timestamp.isoformat()
                }
                for c in self.memory_conflicts if c.character_id == character_id
            ],
            'development': self.character_development.get(character_id, {})
        }
    
    def import_character_memories(self, data: Dict[str, Any]) -> None:
        """Import memories for a character from exported data."""
        character_id = data['character_id']
        
        # Import memories
        memories = []
        for memory_data in data.get('memories', []):
            memory = CharacterMemory.from_dict(memory_data)
            memories.append(memory)
        
        self.character_memories[character_id] = memories
        
        # Import development data
        if 'development' in data:
            self.character_development[character_id] = data['development']
        
        logger.info(f"Imported {len(memories)} memories for {character_id}")
    
    # Private helper methods
    
    def _generate_memory_id(self, character_id: str, content: str) -> str:
        """Generate unique memory ID based on character and content."""
        hash_input = f"{character_id}_{content}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def _generate_memories_from_event(self, character_id: str, event: MemoryEvent) -> List[Dict[str, Any]]:
        """Generate different types of memories from an event."""
        memories = []
        
        # Factual memory of the event
        memories.append({
            'type': MemoryType.FACTUAL,
            'content': f"Event: {event.description}",
            'importance': event.memory_significance,
            'emotional_context': ''
        })
        
        # Emotional memory if there's emotional impact
        if character_id in event.emotional_impact:
            emotional_score = event.emotional_impact[character_id]
            emotional_context = self._interpret_emotional_score(emotional_score)
            
            memories.append({
                'type': MemoryType.EMOTIONAL,
                'content': f"Felt {emotional_context} during: {event.description}",
                'importance': min(5, event.memory_significance + abs(emotional_score)),
                'emotional_context': emotional_context
            })
        
        # Relational memories for other participants
        if len(event.participants) > 1:
            other_participants = [p for p in event.participants if p != character_id]
            if other_participants:
                memories.append({
                    'type': MemoryType.RELATIONAL,
                    'content': f"Interacted with {', '.join(other_participants)} during: {event.description}",
                    'importance': event.memory_significance,
                    'emotional_context': ''
                })
        
        return memories
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text for memory matching."""
        # Simple keyword extraction - can be enhanced with NLP
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out common words and keep meaningful terms
        stop_words = {'the', 'and', 'but', 'for', 'are', 'was', 'were', 'has', 'had', 'will', 'would', 'could', 'should'}
        keywords = [word for word in words if word not in stop_words and len(word) >= 3]  # Changed from > 3 to >= 3
        
        # Return unique keywords, limited to reasonable number
        return list(set(keywords))[:20]
    
    def _calculate_memory_relevance(self, memory: CharacterMemory, context: str, context_keywords: List[str]) -> float:
        """Calculate how relevant a memory is to the current context."""
        relevance_score = 0.0
        
        # Keyword matching
        memory_keywords = set(memory.keywords)
        context_keywords_set = set(context_keywords)
        keyword_overlap = len(memory_keywords.intersection(context_keywords_set))
        keyword_score = keyword_overlap / max(len(context_keywords_set), 1) * 0.4
        
        # Content similarity (simple approach)
        content_words = set(self._extract_keywords(memory.content))
        content_overlap = len(content_words.intersection(context_keywords_set))
        content_score = content_overlap / max(len(context_keywords_set), 1) * 0.3
        
        # Importance boost
        importance_score = (memory.importance_score / 5.0) * 0.2
        
        # Recency boost (more recent memories are more relevant)
        days_old = (datetime.now() - memory.timestamp).days
        recency_score = max(0, (30 - days_old) / 30) * 0.1
        
        relevance_score = keyword_score + content_score + importance_score + recency_score
        
        # Give a minimum relevance for any keyword match
        if keyword_overlap > 0 or content_overlap > 0:
            relevance_score = max(relevance_score, 0.4)  # Ensure minimum relevance for matches
        
        return min(1.0, relevance_score)
    
    def _detect_memory_contradiction(self, new_memory: CharacterMemory, existing_memory: CharacterMemory) -> Optional[MemoryConflict]:
        """Detect if two memories contradict each other."""
        # Simple contradiction detection - can be enhanced
        
        # Check for direct contradictions in factual memories
        if (new_memory.memory_type == MemoryType.FACTUAL and 
            existing_memory.memory_type == MemoryType.FACTUAL):
            
            # Look for contradictory phrases
            contradictory_pairs = [
                ('alive', 'dead'), ('yes', 'no'), ('true', 'false'),
                ('love', 'hate'), ('friend', 'enemy'), ('success', 'failure')
            ]
            
            new_words = set(self._extract_keywords(new_memory.content))
            existing_words = set(self._extract_keywords(existing_memory.content))
            
            for word1, word2 in contradictory_pairs:
                if ((word1 in new_words and word2 in existing_words) or
                    (word2 in new_words and word1 in existing_words)):
                    
                    return MemoryConflict(
                        conflict_id=f"conflict_{new_memory.memory_id}_{existing_memory.memory_id}",
                        character_id=new_memory.character_id,
                        conflicting_memories=[new_memory.memory_id, existing_memory.memory_id],
                        conflict_type="factual_contradiction",
                        severity="medium",
                        description=f"Contradictory information about {word1}/{word2}",
                        suggested_resolution="Review both memories for accuracy"
                    )
        
        return None
    
    def _check_temporal_consistency(self, new_memory: CharacterMemory, existing_memories: List[CharacterMemory]) -> List[MemoryConflict]:
        """Check for temporal consistency issues."""
        conflicts = []
        
        # Check if events are in logical temporal order
        for existing_memory in existing_memories:
            time_diff = new_memory.timestamp - existing_memory.timestamp
            
            # Flag if memories are very close in time but suggest different states
            if abs(time_diff.total_seconds()) < 3600:  # Within 1 hour
                if (new_memory.memory_type == MemoryType.FACTUAL and 
                    existing_memory.memory_type == MemoryType.FACTUAL):
                    
                    # Simple check for state changes that seem too fast
                    state_changes = ['learned', 'forgot', 'became', 'stopped']
                    new_words = self._extract_keywords(new_memory.content)
                    
                    if any(change in new_words for change in state_changes):
                        conflicts.append(MemoryConflict(
                            conflict_id=f"temporal_{new_memory.memory_id}_{existing_memory.memory_id}",
                            character_id=new_memory.character_id,
                            conflicting_memories=[new_memory.memory_id, existing_memory.memory_id],
                            conflict_type="temporal_inconsistency",
                            severity="low",
                            description="Rapid state change detected",
                            suggested_resolution="Verify timing of events"
                        ))
        
        return conflicts
    
    def _check_knowledge_consistency(self, new_memory: CharacterMemory, existing_memories: List[CharacterMemory]) -> List[MemoryConflict]:
        """Check if new memory is consistent with character's knowledge state."""
        conflicts = []
        
        # Check if character suddenly knows something they shouldn't
        if new_memory.memory_type == MemoryType.SKILL:
            skill_memories = [m for m in existing_memories if m.memory_type == MemoryType.SKILL]
            
            # Simple check for skill progression consistency
            if 'mastered' in new_memory.content.lower():
                has_learning_memory = any('learning' in m.content.lower() or 'practicing' in m.content.lower() 
                                        for m in skill_memories)
                
                if not has_learning_memory:
                    conflicts.append(MemoryConflict(
                        conflict_id=f"knowledge_{new_memory.memory_id}",
                        character_id=new_memory.character_id,
                        conflicting_memories=[new_memory.memory_id],
                        conflict_type="knowledge_inconsistency",
                        severity="medium",
                        description="Skill mastery without learning progression",
                        suggested_resolution="Add learning progression memories"
                    ))
        
        return conflicts
    
    def _calculate_consistency_confidence(self, new_memory: CharacterMemory, existing_memories: List[CharacterMemory]) -> float:
        """Calculate confidence score for memory consistency."""
        if not existing_memories:
            return 1.0
        
        # Simple confidence calculation based on memory alignment
        related_memories = [m for m in existing_memories 
                          if any(keyword in m.keywords for keyword in new_memory.keywords)]
        
        if not related_memories:
            return 0.8  # Neutral confidence for unrelated memories
        
        # Check for supporting vs. conflicting evidence
        supporting_count = 0
        for memory in related_memories:
            if memory.verification_status == ConsistencyStatus.VALIDATED:
                supporting_count += 1
        
        confidence = supporting_count / len(related_memories)
        return max(0.1, min(1.0, confidence))
    
    def _interpret_emotional_score(self, score: float) -> str:
        """Convert numerical emotional score to descriptive text."""
        if score > 2:
            return "very positive"
        elif score > 0.5:
            return "positive"
        elif score > -0.5:
            return "neutral"
        elif score > -2:
            return "negative"
        else:
            return "very negative"
    
    def _update_character_development(self, character_id: str, event: MemoryEvent) -> None:
        """Update character development tracking based on new event."""
        if character_id not in self.character_development:
            self.character_development[character_id] = {
                'personality_growth': [],
                'skill_advancement': [],
                'relationship_changes': [],
                'knowledge_gained': [],
                'emotional_maturity': [],
                'goal_evolution': []
            }
        
        development = self.character_development[character_id]
        
        # Analyze event for development indicators
        event_lower = event.description.lower()
        
        # Skill advancement
        if any(word in event_lower for word in ['learned', 'practiced', 'improved', 'mastered']):
            development['skill_advancement'].append({
                'event': event.description,
                'timestamp': event.timestamp.isoformat(),
                'significance': event.memory_significance
            })
        
        # Relationship changes
        if len(event.participants) > 1:
            development['relationship_changes'].append({
                'event': event.description,
                'participants': event.participants,
                'timestamp': event.timestamp.isoformat()
            })
        
        # Keep only recent development entries (last 50)
        for category in development:
            if len(development[category]) > 50:
                development[category] = development[category][-50:]
    
    def _manage_memory_capacity(self, character_id: str) -> None:
        """Manage memory capacity to prevent unlimited growth."""
        memories = self.character_memories[character_id]
        
        if len(memories) > self.max_memories_per_character:
            # Sort by importance and recency
            memories.sort(key=lambda m: (m.importance_score, m.timestamp), reverse=True)
            
            # Keep the most important and recent memories
            self.character_memories[character_id] = memories[:self.max_memories_per_character]
            
            logger.info(f"Trimmed memories for {character_id} to {self.max_memories_per_character}")
    
    def _create_compressed_memory(self, character_id: str, memories_to_compress: List[CharacterMemory]) -> CharacterMemory:
        """Create a compressed summary memory from multiple old memories."""
        # Group memories by type
        type_groups = {}
        for memory in memories_to_compress:
            memory_type = memory.memory_type
            if memory_type not in type_groups:
                type_groups[memory_type] = []
            type_groups[memory_type].append(memory)
        
        # Create summary
        summary_parts = []
        for memory_type, memories in type_groups.items():
            summary_parts.append(f"{memory_type.value}: {len(memories)} events")
        
        compressed_content = f"Compressed memory summary: {', '.join(summary_parts)}"
        
        return CharacterMemory(
            memory_id=self._generate_memory_id(character_id, compressed_content),
            character_id=character_id,
            memory_type=MemoryType.FACTUAL,
            content=compressed_content,
            importance_score=2.0,  # Low importance for compressed memories
            timestamp=datetime.now(),
            keywords=['compressed', 'summary'],
            verification_status=ConsistencyStatus.VALIDATED
        )
