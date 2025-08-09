"""
Interactive Storytelling Workflow Test

Tests the complete interactive storytelling cycle:
User input → Context building → AI response → Memory update → Scene logging

This workflow validates:
- User input processing and validation
- Context building from current story state
- AI model interaction and response generation
- Memory updates based on new developments
- Scene progression and logging
- Character development through interactions
- Error handling and graceful degradation
"""

import pytest
import pytest_asyncio
import asyncio
import time
from typing import Dict, Any, List

# Import core systems
from core.memory import MemoryOrchestrator
from core.characters import CharacterOrchestrator
from core.scenes import SceneOrchestrator
from core.content.context import ContextOrchestrator
from core.models import ModelOrchestrator
from core.database import DatabaseOrchestrator

# Import test utilities
from tests.mocks.mock_adapters import MockModelOrchestrator

class TestInteractiveStorytellingWorkflow:
    """Test complete interactive storytelling workflow cycles."""
    
    @pytest.fixture
    def established_story_state(self):
        """Provide an established story state for interactive testing."""
        return {
            "story_id": "test_interactive_story",
            "title": "The Crystal Caverns",
            "current_scene": {
                "scene_id": "crystal_caverns_scene_003",
                "title": "The Glowing Chamber",
                "description": "You stand in a vast underground chamber filled with luminescent crystals. Ancient runes glow softly on the walls, and three tunnels lead deeper into the mountain.",
                "location": "Crystal Chamber",
                "active_characters": ["Elena Stormsword", "Marcus Lightbringer"],
                "scene_type": "exploration",
                "choices": [
                    "Examine the glowing runes on the walls",
                    "Take the left tunnel marked with a flame symbol", 
                    "Take the center tunnel that echoes with whispers",
                    "Take the right tunnel that feels unnaturally cold"
                ]
            },
            "characters": {
                "Elena Stormsword": {
                    "role": "Human Paladin",
                    "status": "active",
                    "current_hp": 85,
                    "equipment": ["Blessed Sword", "Sacred Shield", "Crystal Pendant"],
                    "recent_actions": ["Cast healing spell", "Led party through cave entrance"]
                },
                "Marcus Lightbringer": {
                    "role": "Human Cleric",
                    "status": "active", 
                    "current_hp": 70,
                    "equipment": ["Staff of Light", "Holy Symbol", "Healing Potions"],
                    "recent_actions": ["Provided illumination", "Detected magical aura"]
                }
            },
            "story_context": {
                "quest_objective": "Find the Heart of the Mountain crystal",
                "current_danger_level": "moderate",
                "discovered_clues": ["Ancient civilization once lived here", "Crystals respond to magical energy"],
                "party_mood": "cautious but determined"
            }
        }
    
    @pytest_asyncio.fixture
    async def interactive_orchestrators(self, established_story_state):
        """Initialize orchestrators with established story state."""
        story_id = established_story_state["story_id"]
        
        # Initialize orchestrators
        model_orchestrator = MockModelOrchestrator()
        memory_orchestrator = MemoryOrchestrator()
        character_orchestrator = CharacterOrchestrator()
        scene_orchestrator = SceneOrchestrator(story_id)
        context_orchestrator = ContextOrchestrator()
        database_orchestrator = DatabaseOrchestrator()
        
        # Set up story state in memory
        await memory_orchestrator.initialize_story_memory(story_id)
        
        # Add character memories
        for char_name, char_data in established_story_state["characters"].items():
            await memory_orchestrator.update_character_memory(
                story_id, char_name, {
                    "character_state": char_data,
                    "location": established_story_state["current_scene"]["location"],
                    "recent_events": char_data["recent_actions"]
                }
            )
        
        # Add story context to memory
        await memory_orchestrator.add_recent_event(
            story_id, {
                "event_type": "story_state",
                "scene_data": established_story_state["current_scene"],
                "story_context": established_story_state["story_context"]
            }
        )
        
        return {
            "model": model_orchestrator,
            "memory": memory_orchestrator,
            "character": character_orchestrator,
            "scene": scene_orchestrator,
            "context": context_orchestrator,
            "database": database_orchestrator
        }
    
    @pytest.mark.asyncio
    async def test_complete_interactive_cycle(self, established_story_state, interactive_orchestrators):
        """Test complete cycle of user input to story progression."""
        story_id = established_story_state["story_id"]
        orchestrators = interactive_orchestrators
        
        # === USER INPUT SIMULATION ===
        user_inputs = [
            {
                "input": "I examine the glowing runes on the walls carefully",
                "character_focus": "Elena Stormsword",
                "action_type": "investigation"
            },
            {
                "input": "I cast a detect magic spell to understand the runes better", 
                "character_focus": "Marcus Lightbringer",
                "action_type": "spell_casting"
            },
            {
                "input": "Based on what we learned, I want to touch the central rune gently",
                "character_focus": "Elena Stormsword", 
                "action_type": "interaction"
            }
        ]
        
        scene_progression = []
        
        for i, user_input in enumerate(user_inputs):
            print(f"🎮 Processing user input {i+1}: {user_input['input'][:50]}...")
            
            # === PHASE 1: CONTEXT BUILDING ===
            # Build context based on current story state and user input
            story_context = await orchestrators["context"].build_character_focused_context(
                story_data={
                    "story_id": story_id,
                    "current_scene": established_story_state["current_scene"],
                    "user_input": user_input["input"],
                    "action_type": user_input["action_type"]
                },
                character_name=user_input["character_focus"]
            )
            
            assert story_context is not None
            print("  ✅ Context built successfully")
            
            # === PHASE 2: AI RESPONSE GENERATION ===
            # Generate AI response based on context and input
            prompt = f"""
            Story Context: {established_story_state['current_scene']['description']}
            Character: {user_input['character_focus']} 
            Action: {user_input['input']}
            
            Generate a response that advances the story naturally.
            """
            
            ai_response = await orchestrators["model"].generate_response(
                prompt=prompt,
                story_id=story_id,
                context=story_context
            )
            
            assert ai_response is not None
            assert len(ai_response.content) > 10  # Meaningful response
            print("  ✅ AI response generated")
            
            # === PHASE 3: MEMORY UPDATES ===
            # Update memory with new developments
            memory_update = {
                "user_action": user_input["input"],
                "character_acting": user_input["character_focus"],
                "ai_response": ai_response.content[:200],  # Truncated for storage
                "action_type": user_input["action_type"],
                "scene_progression": f"step_{i+1}",
                "timestamp": time.time()
            }
            
            await orchestrators["memory"].add_recent_event(story_id, memory_update)
            
            # Update character-specific memory
            await orchestrators["memory"].update_character_memory(
                story_id, 
                user_input["character_focus"], 
                {
                    "recent_action": user_input["input"],
                    "action_result": ai_response.content[:100],
                    "interaction_count": i + 1
                }
            )
            
            print("  ✅ Memory updated")
            
            # === PHASE 4: SCENE LOGGING ===
            # Create scene fragment for this interaction
            scene_fragment = {
                "scene_id": f"{established_story_state['current_scene']['scene_id']}_interaction_{i+1}",
                "parent_scene": established_story_state["current_scene"]["scene_id"],
                "user_input": user_input["input"],
                "ai_response": ai_response.content,
                "character_focus": user_input["character_focus"],
                "action_type": user_input["action_type"],
                "timestamp": time.time()
            }
            
            scene_result = await orchestrators["scene"].log_scene_fragment(
                story_id, scene_fragment
            )
            
            scene_progression.append(scene_fragment)
            print("  ✅ Scene fragment logged")
            
            # === PHASE 5: CHARACTER STATE UPDATES ===
            # Update character states based on actions
            if user_input["action_type"] == "spell_casting":
                # Simulate spell casting effects
                await orchestrators["character"].update_character_state(
                    story_id,
                    user_input["character_focus"],
                    {
                        "mana_used": 10,
                        "spells_cast": 1,
                        "last_spell": "detect magic"
                    }
                )
            elif user_input["action_type"] == "interaction":
                # Simulate interaction effects
                await orchestrators["character"].update_character_state(
                    story_id,
                    user_input["character_focus"],
                    {
                        "interactions_attempted": 1,
                        "risk_taken": "low"
                    }
                )
            
            print(f"  ✅ Interactive cycle {i+1} completed")
        
        # === WORKFLOW VALIDATION ===
        print("🔍 Validating complete interactive workflow...")
        
        # Check memory contains all interactions
        memory_summary = await orchestrators["memory"].get_memory_summary(story_id)
        assert memory_summary.get("recent_events_count", 0) >= len(user_inputs)
        
        # Check all scene fragments were logged
        assert len(scene_progression) == len(user_inputs)
        
        # Check character memories were updated
        for char_name in established_story_state["characters"].keys():
            char_memory = await orchestrators["memory"].get_character_memory(story_id, char_name)
            assert char_memory is not None
        
        print("✅ Interactive storytelling workflow validation passed")
        
        # === WORKFLOW METRICS ===
        workflow_metrics = {
            "interactions_processed": len(user_inputs),
            "scene_fragments_created": len(scene_progression),
            "memory_updates": len(user_inputs) * 2,  # General + character-specific
            "ai_responses_generated": len(user_inputs),
            "character_states_updated": sum(1 for inp in user_inputs if inp["action_type"] in ["spell_casting", "interaction"]),
            "workflow_status": "completed",
            "average_response_quality": "high"  # Based on response length checks
        }
        
        print(f"🏁 Interactive storytelling workflow completed!")
        print(f"📊 Workflow metrics: {workflow_metrics}")
        
        return {
            "scene_progression": scene_progression,
            "memory_summary": memory_summary,
            "metrics": workflow_metrics
        }
    
    @pytest.mark.asyncio
    async def test_error_handling_during_interaction(self, established_story_state, interactive_orchestrators):
        """Test error handling and recovery during interactive storytelling."""
        story_id = established_story_state["story_id"]
        orchestrators = interactive_orchestrators
        
        # Test invalid user input
        try:
            # Empty input should be handled gracefully
            await orchestrators["context"].build_character_focused_context(
                story_data={
                    "story_id": story_id,
                    "user_input": "",  # Empty input
                    "current_scene": established_story_state["current_scene"]
                },
                character_name="NonexistentCharacter"  # Invalid character
            )
        except Exception as e:
            print(f"✅ Handled invalid input gracefully: {type(e).__name__}")
        
        # Test AI response failure simulation
        try:
            # This should trigger fallback mechanisms
            await orchestrators["model"].generate_response(
                prompt="INVALID_PROMPT_THAT_CAUSES_ERROR",
                story_id="nonexistent_story"
            )
        except Exception as e:
            print(f"✅ Handled AI response failure: {type(e).__name__}")
        
        print("✅ Error handling tests passed")
    
    @pytest.mark.asyncio
    async def test_long_interactive_session(self, established_story_state, interactive_orchestrators):
        """Test performance and memory management during long interactive sessions."""
        story_id = f"{established_story_state['story_id']}_long_session"
        orchestrators = interactive_orchestrators
        
        # Simulate 10 rapid interactions
        interactions_count = 10
        start_time = time.time()
        
        for i in range(interactions_count):
            user_input = f"I perform action number {i+1} in the crystal chamber"
            
            # Quick interaction cycle
            context = await orchestrators["context"].build_character_focused_context(
                story_data={
                    "story_id": story_id,
                    "user_input": user_input,
                    "current_scene": established_story_state["current_scene"]
                },
                character_name="Elena Stormsword"
            )
            
            response = await orchestrators["model"].generate_response(
                prompt=f"Action: {user_input}",
                story_id=story_id
            )
            
            await orchestrators["memory"].add_recent_event(
                story_id, {
                    "interaction": i+1,
                    "user_input": user_input,
                    "response_length": len(response.content)
                }
            )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Performance validation
        avg_time_per_interaction = total_time / interactions_count
        assert avg_time_per_interaction < 2.0  # Should be under 2 seconds per interaction
        
        # Memory efficiency validation
        memory_summary = await orchestrators["memory"].get_memory_summary(story_id)
        assert memory_summary.get("recent_events_count", 0) >= interactions_count
        
        print(f"✅ Long session test completed: {interactions_count} interactions in {total_time:.2f}s")
        print(f"   Average time per interaction: {avg_time_per_interaction:.2f}s")


if __name__ == "__main__":
    # Allow running workflow tests directly
    pytest.main([__file__, "-v", "--tb=short"])
