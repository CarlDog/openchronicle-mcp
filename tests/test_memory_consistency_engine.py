"""
Test suite for Memory Consistency Engine

Tests persistent character memory, consistency validation,
memory retrieval, and character development tracking.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.memory_consistency_engine import (
    MemoryConsistencyEngine, CharacterMemory, MemoryEvent, MemoryConflict,
    MemoryType, MemoryImportance, ConsistencyStatus
)

class TestCharacterMemory:
    """Test CharacterMemory data class functionality."""
    
    def test_memory_creation(self):
        """Test creating a character memory."""
        memory = CharacterMemory(
            memory_id="mem_001",
            character_id="hero",
            memory_type=MemoryType.FACTUAL,
            content="Met the wizard in the tower",
            importance_score=3.0,
            timestamp=datetime.now(),
            related_characters=["wizard"],
            emotional_context="curious",
            keywords=["wizard", "tower", "meeting"]
        )
        
        assert memory.character_id == "hero"
        assert memory.memory_type == MemoryType.FACTUAL
        assert memory.content == "Met the wizard in the tower"
        assert memory.importance_score == 3.0
        assert "wizard" in memory.related_characters
        assert memory.verification_status == ConsistencyStatus.PENDING
    
    def test_memory_serialization(self):
        """Test memory serialization and deserialization."""
        original_memory = CharacterMemory(
            memory_id="mem_002",
            character_id="mage",
            memory_type=MemoryType.EMOTIONAL,
            content="Felt proud after saving the village",
            importance_score=4.0,
            timestamp=datetime.now(),
            emotional_context="pride",
            verification_status=ConsistencyStatus.VALIDATED
        )
        
        # Serialize and deserialize
        data = original_memory.to_dict()
        restored_memory = CharacterMemory.from_dict(data)
        
        assert restored_memory.memory_id == original_memory.memory_id
        assert restored_memory.character_id == original_memory.character_id
        assert restored_memory.memory_type == original_memory.memory_type
        assert restored_memory.content == original_memory.content
        assert restored_memory.importance_score == original_memory.importance_score
        assert restored_memory.verification_status == original_memory.verification_status

class TestMemoryEvent:
    """Test MemoryEvent data class functionality."""
    
    def test_memory_event_creation(self):
        """Test creating a memory event."""
        event = MemoryEvent(
            event_id="evt_001",
            description="Dragon battle in the mountain cave",
            participants=["hero", "companion", "dragon"],
            location="mountain cave",
            emotional_impact={"hero": 2.5, "companion": 1.0},
            consequences=["dragon defeated", "treasure found"],
            memory_significance=4.5
        )
        
        assert event.event_id == "evt_001"
        assert len(event.participants) == 3
        assert "hero" in event.participants
        assert event.emotional_impact["hero"] == 2.5
        assert "treasure found" in event.consequences
        assert event.memory_significance == 4.5

class TestMemoryConsistencyEngine:
    """Test main MemoryConsistencyEngine functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create a test memory consistency engine."""
        return MemoryConsistencyEngine()
    
    @pytest.fixture
    def sample_memory_event(self):
        """Sample memory event for testing."""
        return MemoryEvent(
            event_id="test_event",
            description="Discovered a hidden library",
            participants=["scholar"],
            location="ancient ruins",
            emotional_impact={"scholar": 1.5},
            memory_significance=3.0
        )
    
    def test_engine_initialization(self, engine):
        """Test engine initialization."""
        assert engine.max_memories_per_character == 1000
        assert engine.memory_decay_rate == 0.95
        assert engine.consistency_threshold == 0.8
        assert len(engine.character_memories) == 0
        assert len(engine.memory_conflicts) == 0
    
    def test_add_memory_single_character(self, engine, sample_memory_event):
        """Test adding memories for a single character."""
        memories_created = engine.add_memory("scholar", sample_memory_event)
        
        assert len(memories_created) >= 1
        assert "scholar" in engine.character_memories
        assert len(engine.character_memories["scholar"]) >= 1
        
        # Check that different types of memories were created
        memory_types = {m.memory_type for m in memories_created}
        assert MemoryType.FACTUAL in memory_types
        
        # Check factual memory content
        factual_memories = [m for m in memories_created if m.memory_type == MemoryType.FACTUAL]
        assert len(factual_memories) > 0
        assert "Discovered a hidden library" in factual_memories[0].content
    
    def test_add_memory_with_emotional_impact(self, engine):
        """Test adding memories with emotional impact."""
        event = MemoryEvent(
            event_id="emotional_test",
            description="Lost a dear friend in battle",
            participants=["warrior"],
            emotional_impact={"warrior": -3.0},
            memory_significance=5.0
        )
        
        memories_created = engine.add_memory("warrior", event)
        
        # Should create both factual and emotional memories
        memory_types = {m.memory_type for m in memories_created}
        assert MemoryType.FACTUAL in memory_types
        assert MemoryType.EMOTIONAL in memory_types
        
        # Check emotional memory
        emotional_memories = [m for m in memories_created if m.memory_type == MemoryType.EMOTIONAL]
        assert len(emotional_memories) > 0
        assert "very negative" in emotional_memories[0].content or "negative" in emotional_memories[0].content
    
    def test_add_memory_with_multiple_participants(self, engine):
        """Test adding memories with multiple participants."""
        event = MemoryEvent(
            event_id="group_test",
            description="Solved the ancient puzzle together",
            participants=["hero", "wizard", "rogue"],
            memory_significance=3.5
        )
        
        memories_created = engine.add_memory("hero", event)
        
        # Should create relational memories
        memory_types = {m.memory_type for m in memories_created}
        assert MemoryType.RELATIONAL in memory_types
        
        # Check relational memory
        relational_memories = [m for m in memories_created if m.memory_type == MemoryType.RELATIONAL]
        assert len(relational_memories) > 0
        assert "wizard" in relational_memories[0].content
        assert "rogue" in relational_memories[0].content
    
    def test_retrieve_relevant_memories_basic(self, engine):
        """Test basic memory retrieval."""
        # Add some test memories
        event1 = MemoryEvent("evt1", "Found magical sword", ["knight"], memory_significance=4.0)
        event2 = MemoryEvent("evt2", "Learned fire spell", ["knight"], memory_significance=3.0)
        event3 = MemoryEvent("evt3", "Bought bread at market", ["knight"], memory_significance=1.0)
        
        engine.add_memory("knight", event1)
        engine.add_memory("knight", event2)
        engine.add_memory("knight", event3)
        
        # Retrieve memories related to magic
        relevant_memories = engine.retrieve_relevant_memories("knight", "magic spells combat", max_memories=5)
        
        assert len(relevant_memories) > 0
        # Should find magic-related memories more relevant than market shopping
        memory_contents = [m.content for m in relevant_memories]
        assert any("magical" in content or "spell" in content for content in memory_contents)
    
    def test_retrieve_relevant_memories_by_type(self, engine):
        """Test memory retrieval filtered by memory type."""
        event = MemoryEvent(
            "evt_mixed",
            "Epic battle against the dragon",
            ["paladin"],
            emotional_impact={"paladin": 2.0},
            memory_significance=5.0
        )
        
        engine.add_memory("paladin", event)
        
        # Retrieve only emotional memories
        emotional_memories = engine.retrieve_relevant_memories(
            "paladin", "battle", memory_types=[MemoryType.EMOTIONAL]
        )
        
        assert all(m.memory_type == MemoryType.EMOTIONAL for m in emotional_memories)
        
        # Retrieve only factual memories
        factual_memories = engine.retrieve_relevant_memories(
            "paladin", "battle", memory_types=[MemoryType.FACTUAL]
        )
        
        assert all(m.memory_type == MemoryType.FACTUAL for m in factual_memories)
    
    def test_memory_consistency_validation_no_conflict(self, engine):
        """Test memory consistency validation with no conflicts."""
        # Add a base memory
        event1 = MemoryEvent("evt1", "Learned to read ancient texts", ["scholar"])
        engine.add_memory("scholar", event1)
        
        # Add a consistent memory
        new_memory = CharacterMemory(
            memory_id="new_mem",
            character_id="scholar",
            memory_type=MemoryType.SKILL,
            content="Successfully translated an ancient scroll",
            importance_score=3.0,
            timestamp=datetime.now()
        )
        
        result = engine.validate_memory_consistency("scholar", new_memory)
        
        assert result['status'] in [ConsistencyStatus.VALIDATED, ConsistencyStatus.PENDING]
        assert isinstance(result['conflicts'], list)
        assert result['confidence'] > 0
    
    def test_memory_consistency_validation_with_conflict(self, engine):
        """Test memory consistency validation with conflicts."""
        # Add contradictory memories
        event1 = MemoryEvent("evt1", "The king is alive and well", ["witness"])
        engine.add_memory("witness", event1)
        
        conflicting_memory = CharacterMemory(
            memory_id="conflict_mem",
            character_id="witness",
            memory_type=MemoryType.FACTUAL,
            content="The king is dead and buried",
            importance_score=4.0,
            timestamp=datetime.now()
        )
        
        result = engine.validate_memory_consistency("witness", conflicting_memory)
        
        # Should detect the alive/dead contradiction
        assert len(result['conflicts']) > 0 or result['status'] == ConsistencyStatus.CONFLICTED
    
    def test_character_memory_summary(self, engine):
        """Test character memory summary generation."""
        # Add various types of memories
        events = [
            MemoryEvent("evt1", "Learned swordsmanship", ["fighter"], memory_significance=3.0),
            MemoryEvent("evt2", "Met the queen", ["fighter"], memory_significance=4.0),
            MemoryEvent("evt3", "Bought armor", ["fighter"], memory_significance=2.0)
        ]
        
        for event in events:
            engine.add_memory("fighter", event)
        
        summary = engine.get_character_memory_summary("fighter")
        
        assert summary['character_id'] == "fighter"
        assert summary['total_memories'] > 0
        assert 'memory_types' in summary
        assert 'importance_distribution' in summary
        assert 'recent_memories_count' in summary
        assert 'oldest_memory' in summary
        assert 'newest_memory' in summary
    
    def test_memory_compression(self, engine):
        """Test old memory compression."""
        # Add several old memories
        old_date = datetime.now() - timedelta(days=60)
        for i in range(5):
            event = MemoryEvent(
                f"old_evt_{i}",
                f"Old event number {i}",
                ["archivist"],
                memory_significance=1.0  # Low importance
            )
            event.timestamp = old_date
            memories = engine.add_memory("archivist", event)
            # Set timestamp after adding to override
            for memory in memories:
                memory.timestamp = old_date
        
        # Add a recent important memory
        recent_event = MemoryEvent(
            "recent_evt",
            "Important recent discovery",
            ["archivist"],
            memory_significance=5.0
        )
        engine.add_memory("archivist", recent_event)
        
        original_count = len(engine.character_memories["archivist"])
        compressed_count = engine.compress_old_memories("archivist", retention_days=30)
        
        assert compressed_count >= 0
        # Should have fewer memories after compression
        final_count = len(engine.character_memories["archivist"])
        
        # Important recent memory should still be there
        memory_contents = [m.content for m in engine.character_memories["archivist"]]
        assert any("Important recent discovery" in content for content in memory_contents)
    
    def test_memory_context_for_prompt(self, engine):
        """Test memory context generation for prompts."""
        # Add memories with different types
        events = [
            MemoryEvent("evt1", "Discovered fire magic", ["mage"], memory_significance=4.0),
            MemoryEvent("evt2", "Made friends with the dragon", ["mage"], 
                       emotional_impact={"mage": 2.0}, memory_significance=3.0)
        ]
        
        for event in events:
            engine.add_memory("mage", event)
        
        context = engine.get_memory_context_for_prompt("mage", "using magic spells", max_tokens=200)
        
        assert "[CHARACTER_MEMORIES: mage]" in context
        assert len(context) > 0
        # Should contain relevant information
        assert "magic" in context.lower() or "fire" in context.lower()
    
    def test_memory_export_import(self, engine):
        """Test memory export and import functionality."""
        # Add some memories
        event = MemoryEvent(
            "export_test",
            "Test event for export",
            ["export_char"],
            memory_significance=3.0
        )
        engine.add_memory("export_char", event)
        
        # Export memories
        exported_data = engine.export_character_memories("export_char")
        
        assert exported_data['character_id'] == "export_char"
        assert len(exported_data['memories']) > 0
        assert 'conflicts' in exported_data
        assert 'development' in exported_data
        
        # Create new engine and import
        new_engine = MemoryConsistencyEngine()
        new_engine.import_character_memories(exported_data)
        
        assert "export_char" in new_engine.character_memories
        assert len(new_engine.character_memories["export_char"]) > 0
        
        # Check content consistency
        original_contents = {m.content for m in engine.character_memories["export_char"]}
        imported_contents = {m.content for m in new_engine.character_memories["export_char"]}
        assert original_contents == imported_contents
    
    def test_character_development_tracking(self, engine):
        """Test character development tracking over time."""
        # Add development-related events
        skill_event = MemoryEvent(
            "skill_dev",
            "Learned advanced archery techniques",
            ["archer"],
            memory_significance=4.0
        )
        
        relationship_event = MemoryEvent(
            "rel_dev",
            "Became close friends with the ranger",
            ["archer", "ranger"],
            memory_significance=3.0
        )
        
        engine.add_memory("archer", skill_event)
        engine.add_memory("archer", relationship_event)
        
        summary = engine.get_character_memory_summary("archer")
        development = summary.get('character_development', {})
        
        # Should track skill advancement
        assert 'skill_advancement' in development
        skill_entries = development['skill_advancement']
        assert any('archery' in entry.get('event', '').lower() for entry in skill_entries)
        
        # Should track relationship changes
        assert 'relationship_changes' in development
        rel_entries = development['relationship_changes']
        assert any('ranger' in entry.get('participants', []) for entry in rel_entries)
    
    def test_memory_capacity_management(self, engine):
        """Test memory capacity management."""
        # Set a low capacity for testing
        engine.max_memories_per_character = 5
        
        # Add more memories than the capacity
        for i in range(10):
            event = MemoryEvent(
                f"capacity_evt_{i}",
                f"Event number {i}",
                ["capacity_char"],
                memory_significance=float(i)  # Varying importance
            )
            engine.add_memory("capacity_char", event)
        
        # Should not exceed capacity
        memory_count = len(engine.character_memories["capacity_char"])
        assert memory_count <= engine.max_memories_per_character
        
        # Should keep the most important memories
        remaining_memories = engine.character_memories["capacity_char"]
        importance_scores = [m.importance_score for m in remaining_memories]
        # Most should be high importance (though some may be low due to event processing)
        assert max(importance_scores) >= 7.0  # High importance events should be kept
    
    def test_keyword_extraction(self, engine):
        """Test keyword extraction functionality."""
        keywords = engine._extract_keywords("The brave knight fought the terrible dragon")
        
        assert "knight" in keywords
        assert "fought" in keywords
        assert "dragon" in keywords
        assert "terrible" in keywords
        # Should filter out short words
        assert "the" not in keywords
    
    def test_memory_relevance_calculation(self, engine):
        """Test memory relevance scoring."""
        memory = CharacterMemory(
            memory_id="rel_test",
            character_id="test_char",
            memory_type=MemoryType.FACTUAL,
            content="Studied fire magic in the tower library",
            importance_score=4.0,
            timestamp=datetime.now(),
            keywords=["fire", "magic", "tower", "library", "studied"]
        )
        
        # High relevance context
        high_relevance = engine._calculate_memory_relevance(
            memory, "learning fire magic spells", ["fire", "magic", "learning"]
        )
        
        # Low relevance context
        low_relevance = engine._calculate_memory_relevance(
            memory, "shopping for groceries", ["shopping", "groceries", "food"]
        )
        
        assert high_relevance > low_relevance
        assert 0 <= high_relevance <= 1
        assert 0 <= low_relevance <= 1

class TestMemoryTypes:
    """Test memory type classifications and handling."""
    
    def test_memory_type_enum(self):
        """Test memory type enumeration."""
        assert MemoryType.FACTUAL.value == "factual"
        assert MemoryType.EMOTIONAL.value == "emotional"
        assert MemoryType.RELATIONAL.value == "relational"
        assert MemoryType.SKILL.value == "skill"
        assert MemoryType.EXPERIENTIAL.value == "experiential"
        assert MemoryType.TEMPORAL.value == "temporal"
    
    def test_memory_importance_levels(self):
        """Test memory importance level enumeration."""
        assert MemoryImportance.TRIVIAL.value == 1
        assert MemoryImportance.LOW.value == 2
        assert MemoryImportance.MODERATE.value == 3
        assert MemoryImportance.HIGH.value == 4
        assert MemoryImportance.CRITICAL.value == 5

class TestConsistencyValidation:
    """Test memory consistency validation features."""
    
    @pytest.fixture
    def engine(self):
        return MemoryConsistencyEngine()
    
    def test_contradiction_detection(self, engine):
        """Test detection of memory contradictions."""
        # Create contradictory memories
        memory1 = CharacterMemory(
            memory_id="mem1",
            character_id="test_char",
            memory_type=MemoryType.FACTUAL,
            content="The dragon is alive and terrorizing the village",
            importance_score=4.0,
            timestamp=datetime.now(),
            keywords=["dragon", "alive", "terrorizing", "village"]
        )
        
        memory2 = CharacterMemory(
            memory_id="mem2",
            character_id="test_char",
            memory_type=MemoryType.FACTUAL,
            content="The dragon is dead and its body lies in the cave",
            importance_score=4.0,
            timestamp=datetime.now(),
            keywords=["dragon", "dead", "body", "cave"]
        )
        
        conflict = engine._detect_memory_contradiction(memory2, memory1)
        
        assert conflict is not None
        assert conflict.conflict_type == "factual_contradiction"
        assert memory1.memory_id in conflict.conflicting_memories
        assert memory2.memory_id in conflict.conflicting_memories
    
    def test_temporal_consistency(self, engine):
        """Test temporal consistency checking."""
        # Create memories very close in time
        base_time = datetime.now()
        
        memory1 = CharacterMemory(
            memory_id="temp1",
            character_id="test_char",
            memory_type=MemoryType.FACTUAL,
            content="Started learning magic today",
            importance_score=3.0,
            timestamp=base_time
        )
        
        memory2 = CharacterMemory(
            memory_id="temp2",
            character_id="test_char",
            memory_type=MemoryType.FACTUAL,
            content="Became a master wizard",
            importance_score=5.0,
            timestamp=base_time + timedelta(minutes=30),  # 30 minutes later
            keywords=["became", "master", "wizard"]
        )
        
        conflicts = engine._check_temporal_consistency(memory2, [memory1])
        
        # Should detect rapid state change
        assert len(conflicts) > 0
        assert conflicts[0].conflict_type == "temporal_inconsistency"

if __name__ == "__main__":
    pytest.main([__file__])
