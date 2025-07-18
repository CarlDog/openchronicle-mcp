"""
Test Character Interaction Dynamics Engine
Tests relationship tracking, multi-character scenes, and interaction management.
"""

import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import tempfile
import time
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.character_interaction_engine import (
    CharacterInteractionEngine,
    RelationshipState,
    CharacterState,
    Interaction,
    SceneState,
    RelationshipType,
    InteractionType
)

class TestCharacterInteractionEngine(unittest.TestCase):
    """Test suite for Character Interaction Dynamics Engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = CharacterInteractionEngine()
        
        # Test characters
        self.test_characters = ["lyra", "kael", "vex"]
        
        # Create a test scene
        self.test_scene_id = "test_scene_001"
        self.test_scene = self.engine.create_scene(
            scene_id=self.test_scene_id,
            characters=self.test_characters,
            scene_focus="confrontation",
            environment_context="tavern"
        )
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = CharacterInteractionEngine()
        self.assertIsInstance(engine.relationships, dict)
        self.assertIsInstance(engine.interaction_history, list)
        self.assertIsInstance(engine.scene_states, dict)
        self.assertIsInstance(engine.character_contexts, dict)
        self.assertTrue(engine.auto_turn_management)
        self.assertTrue(engine.emotional_contagion_enabled)
    
    def test_scene_creation(self):
        """Test creating a new multi-character scene."""
        scene_id = "test_scene_002"
        characters = ["alice", "bob", "charlie"]
        
        scene = self.engine.create_scene(
            scene_id=scene_id,
            characters=characters,
            scene_focus="negotiation",
            environment_context="office"
        )
        
        self.assertEqual(scene.scene_id, scene_id)
        self.assertEqual(scene.active_characters, characters)
        self.assertEqual(len(scene.character_states), 3)
        self.assertEqual(scene.scene_focus, "negotiation")
        self.assertEqual(scene.environment_context, "office")
        self.assertIn(scene_id, self.engine.scene_states)
        
        # Check character states were created
        for char_id in characters:
            self.assertIn(char_id, scene.character_states)
            char_state = scene.character_states[char_id]
            self.assertEqual(char_state.character_id, char_id)
            self.assertEqual(char_state.current_emotion, "neutral")
    
    def test_relationship_creation_and_updates(self):
        """Test creating and updating character relationships."""
        char_a, char_b = "lyra", "kael"
        
        # Create initial relationship
        self.engine.update_relationship(
            char_a, char_b, 
            RelationshipType.TRUST, 
            0.3, 
            "initial meeting"
        )
        
        # Check relationship was created
        rel_state = self.engine.get_relationship_state(char_a, char_b)
        self.assertIsNotNone(rel_state)
        self.assertEqual(rel_state.character_a, char_a)
        self.assertEqual(rel_state.character_b, char_b)
        self.assertEqual(rel_state.relationship_type, RelationshipType.TRUST)
        self.assertAlmostEqual(rel_state.intensity, 0.8, places=1)  # 0.5 + 0.3
        
        # Update relationship
        self.engine.update_relationship(
            char_a, char_b,
            RelationshipType.SUSPICION,
            0.2,
            "suspicious behavior"
        )
        
        # Check update
        rel_state = self.engine.get_relationship_state(char_a, char_b)
        self.assertEqual(rel_state.relationship_type, RelationshipType.SUSPICION)
        self.assertAlmostEqual(rel_state.intensity, 1.0, places=1)  # Capped at 1.0
        self.assertEqual(len(rel_state.history), 2)  # Two updates
    
    def test_interaction_creation_and_tracking(self):
        """Test creating and tracking character interactions."""
        interaction = self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="I don't trust you, Kael.",
            hidden_content="Lyra suspects Kael is hiding something"
        )
        
        self.assertIsNotNone(interaction.interaction_id)
        self.assertEqual(interaction.source_character, "lyra")
        self.assertEqual(interaction.target_characters, ["kael"])
        self.assertEqual(interaction.interaction_type, InteractionType.DIALOGUE)
        self.assertEqual(interaction.content, "I don't trust you, Kael.")
        self.assertEqual(interaction.hidden_content, "Lyra suspects Kael is hiding something")
        self.assertEqual(interaction.scene_context, self.test_scene_id)
        
        # Check it was added to history
        self.assertIn(interaction, self.engine.interaction_history)
        
        # Check character state was updated
        scene = self.engine.scene_states[self.test_scene_id]
        lyra_state = scene.character_states["lyra"]
        self.assertEqual(lyra_state.last_dialogue, "I don't trust you, Kael.")
    
    def test_emotional_impact_processing(self):
        """Test that interactions create appropriate emotional impacts."""
        # Add an angry interaction
        self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="I hate what you've done, you're furious and damned!"
        )
        
        # Check if relationship was affected
        rel_state = self.engine.get_relationship_state("lyra", "kael")
        self.assertIsNotNone(rel_state)
        # Should have detected anger keywords and created/updated relationship
        
        # Add a positive interaction
        self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="kael",
            target_characters=["lyra"],
            interaction_type=InteractionType.DIALOGUE,
            content="Lyra, you're beautiful and wonderful, I love talking with you"
        )
        
        # Check for affection relationship
        rel_state = self.engine.get_relationship_state("kael", "lyra")
        self.assertIsNotNone(rel_state)
    
    def test_turn_management(self):
        """Test automatic turn management in scenes."""
        scene_id = self.test_scene_id
        
        # Test getting next speaker
        next_speaker = self.engine.get_next_speaker(scene_id)
        self.assertIn(next_speaker, self.test_characters)
        
        # Modify speaking priorities
        scene = self.engine.scene_states[scene_id]
        scene.character_states["kael"].speaking_priority = 5
        scene.character_states["vex"].speaking_priority = 1
        
        next_speaker = self.engine.get_next_speaker(scene_id)
        # Kael should be more likely to speak due to higher priority
        self.assertIsNotNone(next_speaker)
    
    def test_interaction_context_generation(self):
        """Test generating context for character interactions."""
        # Add some relationships and interactions first
        self.engine.update_relationship("lyra", "kael", RelationshipType.TRUST, 0.3, "test")
        self.engine.update_relationship("lyra", "vex", RelationshipType.SUSPICION, 0.2, "test")
        
        self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="kael",
            target_characters=["lyra"],
            interaction_type=InteractionType.DIALOGUE,
            content="What do you think about this situation?"
        )
        
        # Generate context for Lyra
        context = self.engine.generate_interaction_context(self.test_scene_id, "lyra")
        
        self.assertEqual(context['scene_focus'], "confrontation")
        self.assertIn('relationships', context)
        self.assertIn('other_characters', context)
        self.assertIn('recent_interactions', context)
        self.assertIn('character_state', context)
        
        # Check relationships are included
        self.assertIn('kael', context['relationships'])
        self.assertIn('vex', context['relationships'])
        self.assertEqual(context['relationships']['kael']['type'], 'trust')
    
    def test_relationship_prompt_generation(self):
        """Test generating relationship-based prompts."""
        # Set up relationships
        self.engine.update_relationship("lyra", "kael", RelationshipType.TRUST, 0.4, "test")
        self.engine.update_relationship("lyra", "vex", RelationshipType.FEAR, 0.6, "test")
        
        # Add hidden thoughts
        self.engine.add_hidden_thought(self.test_scene_id, "lyra", "I wonder if Kael can be trusted")
        self.engine.add_hidden_thought(self.test_scene_id, "lyra", "Vex makes me nervous")
        
        prompt = self.engine.generate_relationship_prompt(self.test_scene_id, "lyra")
        
        self.assertIn("CHARACTER_RELATIONSHIPS", prompt)
        self.assertIn("lyra", prompt)
        self.assertIn("trust", prompt)
        self.assertIn("fear", prompt)
        self.assertIn("private thoughts", prompt)
    
    def test_scene_tension_management(self):
        """Test scene tension tracking and updates."""
        scene_id = self.test_scene_id
        
        # Initial tension should be around 0.3
        scene = self.engine.scene_states[scene_id]
        initial_tension = scene.scene_tension
        
        # Increase tension
        self.engine.update_scene_tension(scene_id, 0.3, "conflict escalates")
        
        updated_scene = self.engine.scene_states[scene_id]
        self.assertGreater(updated_scene.scene_tension, initial_tension)
        
        # Test tension bounds
        self.engine.update_scene_tension(scene_id, 1.0, "maximum tension")
        final_scene = self.engine.scene_states[scene_id]
        self.assertEqual(final_scene.scene_tension, 1.0)  # Should be capped at 1.0
    
    def test_hidden_thoughts_tracking(self):
        """Test tracking character hidden thoughts."""
        scene_id = self.test_scene_id
        character = "lyra"
        
        # Add hidden thoughts
        self.engine.add_hidden_thought(scene_id, character, "I don't trust anyone here")
        self.engine.add_hidden_thought(scene_id, character, "Something feels wrong")
        self.engine.add_hidden_thought(scene_id, character, "Should I make an excuse to leave?")
        
        # Check thoughts were added
        scene = self.engine.scene_states[scene_id]
        char_state = scene.character_states[character]
        
        self.assertEqual(len(char_state.hidden_thoughts), 3)
        self.assertIn("I don't trust anyone here", char_state.hidden_thoughts)
        self.assertIn("Something feels wrong", char_state.hidden_thoughts)
        
        # Test thought limit (should keep only recent 5)
        for i in range(5):
            self.engine.add_hidden_thought(scene_id, character, f"Thought {i}")
        
        char_state = scene.character_states[character]
        self.assertEqual(len(char_state.hidden_thoughts), 5)
    
    def test_emotional_contagion(self):
        """Test emotional contagion between characters."""
        scene_id = self.test_scene_id
        
        # Set up a relationship to modify contagion
        self.engine.update_relationship("kael", "lyra", RelationshipType.AFFECTION, 0.4, "test")
        
        # Set Lyra to high emotional intensity
        scene = self.engine.scene_states[scene_id]
        scene.character_states["lyra"].emotional_intensity = 0.9
        scene.character_states["lyra"].current_emotion = "anger"
        
        # Add an emotional interaction from Lyra
        self.engine.add_interaction(
            scene_id=scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="I can't believe this is happening!"
        )
        
        # Check if emotional contagion affected other characters
        # Vex should be slightly affected (no relationship)
        # The exact values depend on the contagion algorithm
        vex_state = scene.character_states["vex"]
        self.assertIsNotNone(vex_state.emotional_intensity)
    
    def test_scene_summary_generation(self):
        """Test generating comprehensive scene summaries."""
        # Add some data to make the summary interesting
        self.engine.update_relationship("lyra", "kael", RelationshipType.TRUST, 0.3, "test")
        self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="Test dialogue"
        )
        
        summary = self.engine.get_scene_summary(self.test_scene_id)
        
        self.assertIn('scene_state', summary)
        self.assertIn('relationships', summary)
        self.assertIn('recent_interactions', summary)
        self.assertIn('next_speaker', summary)
        self.assertIn('engine_stats', summary)
        
        # Check scene state details
        scene_state = summary['scene_state']
        self.assertEqual(scene_state['scene_id'], self.test_scene_id)
        self.assertEqual(len(scene_state['active_characters']), 3)
    
    def test_data_serialization(self):
        """Test data export and import functionality."""
        # Add some test data
        self.engine.update_relationship("lyra", "kael", RelationshipType.TRUST, 0.3, "test")
        self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="Test content"
        )
        
        # Export scene data
        exported_data = self.engine.export_scene_data(self.test_scene_id)
        
        self.assertIn('scene_state', exported_data)
        self.assertIn('interactions', exported_data)
        self.assertIn('relationships', exported_data)
        
        # Create new engine and import
        new_engine = CharacterInteractionEngine()
        new_engine.import_scene_data(exported_data)
        
        # Check data was imported correctly
        self.assertIn(self.test_scene_id, new_engine.scene_states)
        self.assertTrue(len(new_engine.interaction_history) > 0)
        self.assertTrue(len(new_engine.relationships) > 0)
    
    def test_relationship_state_serialization(self):
        """Test RelationshipState serialization and deserialization."""
        # Create a relationship state
        rel_state = RelationshipState(
            character_a="alice",
            character_b="bob",
            relationship_type=RelationshipType.TRUST,
            intensity=0.7,
            last_updated=datetime.now(),
            context="test relationship"
        )
        
        # Add some history
        rel_state.update_intensity(0.1, "positive interaction")
        
        # Serialize
        rel_dict = rel_state.to_dict()
        
        # Deserialize
        restored_rel = RelationshipState.from_dict(rel_dict)
        
        self.assertEqual(restored_rel.character_a, rel_state.character_a)
        self.assertEqual(restored_rel.character_b, rel_state.character_b)
        self.assertEqual(restored_rel.relationship_type, rel_state.relationship_type)
        self.assertEqual(restored_rel.intensity, rel_state.intensity)
        self.assertEqual(len(restored_rel.history), len(rel_state.history))
    
    def test_character_state_serialization(self):
        """Test CharacterState serialization and deserialization."""
        char_state = CharacterState(
            character_id="test_char",
            current_emotion="excitement",
            emotional_intensity=0.8,
            motivation="discover the truth",
            hidden_thoughts=["This is suspicious", "I need to be careful"],
            active_goals=["find evidence", "protect allies"],
            scene_position="near the door",
            speaking_priority=3
        )
        
        # Serialize
        char_dict = char_state.to_dict()
        
        # Deserialize
        restored_char = CharacterState.from_dict(char_dict)
        
        self.assertEqual(restored_char.character_id, char_state.character_id)
        self.assertEqual(restored_char.current_emotion, char_state.current_emotion)
        self.assertEqual(restored_char.emotional_intensity, char_state.emotional_intensity)
        self.assertEqual(restored_char.motivation, char_state.motivation)
        self.assertEqual(restored_char.hidden_thoughts, char_state.hidden_thoughts)
        self.assertEqual(restored_char.active_goals, char_state.active_goals)
    
    def test_interaction_serialization(self):
        """Test Interaction serialization and deserialization."""
        interaction = Interaction(
            interaction_id="test_interaction_001",
            timestamp=datetime.now(),
            source_character="alice",
            target_characters=["bob", "charlie"],
            interaction_type=InteractionType.DIALOGUE,
            content="Hello everyone!",
            hidden_content="Alice is trying to diffuse tension",
            emotional_impact={"bob": 0.1, "charlie": 0.2},
            scene_context="test_scene"
        )
        
        # Serialize
        interaction_dict = interaction.to_dict()
        
        # Deserialize
        restored_interaction = Interaction.from_dict(interaction_dict)
        
        self.assertEqual(restored_interaction.interaction_id, interaction.interaction_id)
        self.assertEqual(restored_interaction.source_character, interaction.source_character)
        self.assertEqual(restored_interaction.target_characters, interaction.target_characters)
        self.assertEqual(restored_interaction.interaction_type, interaction.interaction_type)
        self.assertEqual(restored_interaction.content, interaction.content)
        self.assertEqual(restored_interaction.hidden_content, interaction.hidden_content)
        self.assertEqual(restored_interaction.emotional_impact, interaction.emotional_impact)
    
    def test_scene_state_serialization(self):
        """Test SceneState serialization and deserialization."""
        # Use the test scene created in setUp
        scene = self.engine.scene_states[self.test_scene_id]
        
        # Add some data to make it more interesting
        scene.character_states["lyra"].hidden_thoughts = ["Test thought"]
        scene.scene_tension = 0.7
        
        # Serialize
        scene_dict = scene.to_dict()
        
        # Deserialize
        restored_scene = SceneState.from_dict(scene_dict)
        
        self.assertEqual(restored_scene.scene_id, scene.scene_id)
        self.assertEqual(restored_scene.active_characters, scene.active_characters)
        self.assertEqual(restored_scene.scene_tension, scene.scene_tension)
        self.assertEqual(restored_scene.scene_focus, scene.scene_focus)
        self.assertEqual(len(restored_scene.character_states), len(scene.character_states))
        
        # Check character states were preserved
        for char_id in scene.active_characters:
            original_state = scene.character_states[char_id]
            restored_state = restored_scene.character_states[char_id]
            self.assertEqual(original_state.character_id, restored_state.character_id)
            self.assertEqual(original_state.hidden_thoughts, restored_state.hidden_thoughts)
    
    def test_engine_stats(self):
        """Test engine statistics generation."""
        # Add some data
        self.engine.update_relationship("lyra", "kael", RelationshipType.TRUST, 0.3, "test")
        self.engine.update_relationship("kael", "vex", RelationshipType.SUSPICION, 0.2, "test")
        
        self.engine.add_interaction(
            scene_id=self.test_scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="Test"
        )
        
        stats = self.engine.get_engine_stats()
        
        self.assertIn('total_scenes', stats)
        self.assertIn('total_interactions', stats)
        self.assertIn('total_relationships', stats)
        self.assertIn('active_relationships', stats)
        self.assertIn('average_scene_tension', stats)
        self.assertIn('interaction_types', stats)
        self.assertIn('relationship_types', stats)
        
        self.assertEqual(stats['total_scenes'], 1)
        self.assertGreaterEqual(stats['total_interactions'], 1)
        self.assertGreaterEqual(stats['total_relationships'], 1)
    
    def test_scene_reset(self):
        """Test resetting scene data."""
        scene_id = self.test_scene_id
        
        # Add some data
        self.engine.add_interaction(
            scene_id=scene_id,
            source_character="lyra",
            target_characters=["kael"],
            interaction_type=InteractionType.DIALOGUE,
            content="Test"
        )
        
        # Verify data exists
        self.assertIn(scene_id, self.engine.scene_states)
        self.assertTrue(any(i.scene_context == scene_id for i in self.engine.interaction_history))
        
        # Reset scene
        self.engine.reset_scene(scene_id)
        
        # Verify data was cleared
        self.assertNotIn(scene_id, self.engine.scene_states)
        self.assertFalse(any(i.scene_context == scene_id for i in self.engine.interaction_history))
    
    def test_multi_character_complex_scene(self):
        """Test a complex multi-character scene with various interactions."""
        # Create a complex scene
        scene_id = "complex_test_scene"
        characters = ["hero", "villain", "ally", "neutral"]
        
        scene = self.engine.create_scene(
            scene_id=scene_id,
            characters=characters,
            scene_focus="final confrontation",
            environment_context="abandoned warehouse"
        )
        
        # Add complex relationships
        self.engine.update_relationship("hero", "villain", RelationshipType.ANGER, 0.8, "long-standing conflict")
        self.engine.update_relationship("hero", "ally", RelationshipType.TRUST, 0.9, "loyal partnership")
        self.engine.update_relationship("ally", "villain", RelationshipType.FEAR, 0.6, "intimidation")
        self.engine.update_relationship("neutral", "hero", RelationshipType.RESPECT, 0.4, "admiration")
        
        # Add a series of interactions
        interactions = [
            ("hero", ["villain"], "You won't get away with this!"),
            ("villain", ["hero", "ally"], "You're too late to stop me now."),
            ("ally", ["hero"], "I've got your back!"),
            ("neutral", ["all"], "This has gone too far."),
            ("villain", ["ally"], "You should have stayed away.")
        ]
        
        for source, targets, content in interactions:
            if targets == ["all"]:
                targets = [c for c in characters if c != source]
            
            self.engine.add_interaction(
                scene_id=scene_id,
                source_character=source,
                target_characters=targets,
                interaction_type=InteractionType.DIALOGUE,
                content=content
            )
        
        # Add hidden thoughts
        self.engine.add_hidden_thought(scene_id, "hero", "I hope the ally stays safe")
        self.engine.add_hidden_thought(scene_id, "villain", "They don't know about my backup plan")
        self.engine.add_hidden_thought(scene_id, "neutral", "I should call for help")
        
        # Update scene tension
        self.engine.update_scene_tension(scene_id, 0.4, "confrontation escalates")
        
        # Get comprehensive summary
        summary = self.engine.get_scene_summary(scene_id)
        
        # Verify complex scene data
        self.assertEqual(len(summary['scene_state']['active_characters']), 4)
        self.assertGreater(len(summary['relationships']), 3)
        self.assertGreater(len(summary['recent_interactions']), 3)
        self.assertGreater(summary['scene_state']['scene_tension'], 0.5)
        
        # Test context generation for each character
        for character in characters:
            context = self.engine.generate_interaction_context(scene_id, character)
            self.assertIn('relationships', context)
            self.assertIn('other_characters', context)
            self.assertIn('recent_interactions', context)
            
            # Each character should have relationships with others
            if character != "neutral":  # Neutral has fewer relationships
                self.assertGreater(len(context['relationships']), 0)

if __name__ == "__main__":
    unittest.main()
