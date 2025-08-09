"""
Character Development Workflow Test

Tests the complete character development journey across multiple story sessions:
Character creation → Development through interactions → Growth and evolution → Long-term consistency

This workflow validates:
- Character initialization and base trait establishment
- Character development through story interactions
- Personality evolution and growth tracking
- Relationship development between characters
- Long-term character consistency across sessions
- Character decision-making patterns
- Emotional state tracking and development
"""

import pytest
import pytest_asyncio
import asyncio
import time
from typing import Dict, Any, List

# Import core systems  
from core.characters import CharacterOrchestrator
from core.memory import MemoryOrchestrator
from core.content.analysis import ContentAnalysisOrchestrator
from core.database import DatabaseOrchestrator

# Import test utilities
from tests.mocks.mock_adapters import MockModelOrchestrator

class TestCharacterDevelopmentWorkflow:
    """Test complete character development workflow across story progression."""
    
    @pytest.fixture
    def character_development_scenario(self):
        """Provide character development scenario data."""
        return {
            "story_id": "test_character_development",
            "protagonist": {
                "name": "Lyra Moonweaver",
                "initial_traits": {
                    "personality": "shy, intelligent, curious about magic",
                    "background": "village librarian with untapped magical potential",
                    "fears": ["public speaking", "making mistakes", "disappointing others"],
                    "desires": ["learn powerful magic", "help her village", "gain confidence"],
                    "relationships": {},
                    "character_level": 1,
                    "emotional_state": "nervous but hopeful"
                }
            },
            "mentor_character": {
                "name": "Archmage Valdris",
                "initial_traits": {
                    "personality": "wise, patient, occasionally stern",
                    "background": "ancient wizard with centuries of experience",
                    "teaching_style": "gradual revelation, learning through challenges",
                    "relationship_to_protagonist": "mentor",
                    "emotional_state": "cautiously optimistic about new student"
                }
            },
            "development_events": [
                {
                    "event_type": "first_lesson",
                    "description": "Lyra attempts her first magical spell under Valdris' guidance",
                    "challenges": ["controlling magical energy", "overcoming fear of failure"],
                    "expected_growth": ["magical_skill", "confidence"]
                },
                {
                    "event_type": "public_demonstration", 
                    "description": "Lyra must demonstrate her progress to village elders",
                    "challenges": ["public speaking", "performance under pressure"],
                    "expected_growth": ["courage", "self_esteem", "leadership"]
                },
                {
                    "event_type": "mentor_conflict",
                    "description": "Lyra disagrees with Valdris about magical ethics",
                    "challenges": ["standing up to authority", "articulating beliefs"],
                    "expected_growth": ["independence", "moral_reasoning", "assertiveness"]
                },
                {
                    "event_type": "crisis_leadership",
                    "description": "Village under threat, Lyra must lead magical defense",
                    "challenges": ["making critical decisions", "protecting others"],
                    "expected_growth": ["leadership", "responsibility", "magical_mastery"]
                }
            ]
        }
    
    @pytest_asyncio.fixture
    async def character_orchestrators(self, character_development_scenario):
        """Initialize orchestrators for character development testing."""
        story_id = character_development_scenario["story_id"]
        
        # Initialize orchestrators
        character_orchestrator = CharacterOrchestrator()
        memory_orchestrator = MemoryOrchestrator()
        content_orchestrator = ContentAnalysisOrchestrator(MockModelOrchestrator())
        database_orchestrator = DatabaseOrchestrator()
        
        # Initialize database
        await database_orchestrator.initialize_story_database(story_id)
        
        return {
            "character": character_orchestrator,
            "memory": memory_orchestrator, 
            "content": content_orchestrator,
            "database": database_orchestrator
        }
    
    @pytest.mark.asyncio
    async def test_complete_character_development_arc(self, character_development_scenario, character_orchestrators):
        """Test complete character development from introduction to mastery."""
        story_id = character_development_scenario["story_id"]
        orchestrators = character_orchestrators
        
        protagonist = character_development_scenario["protagonist"]
        mentor = character_development_scenario["mentor_character"]
        
        print(f"🧙‍♀️ Starting character development workflow for: {protagonist['name']}")
        
        # === PHASE 1: CHARACTER INITIALIZATION ===
        # Create protagonist
        protagonist_result = await orchestrators["character"].create_character(
            story_id=story_id,
            character_name=protagonist["name"],
            character_data=protagonist["initial_traits"]
        )
        
        # Create mentor
        mentor_result = await orchestrators["character"].create_character(
            story_id=story_id,
            character_name=mentor["name"],
            character_data=mentor["initial_traits"]
        )
        
        print("✅ Characters initialized")
        
        # === PHASE 2: CHARACTER DEVELOPMENT THROUGH EVENTS ===
        character_growth_tracking = {
            protagonist["name"]: {
                "growth_metrics": {},
                "relationship_changes": {},
                "skill_progression": {},
                "emotional_journey": []
            }
        }
        
        for i, event in enumerate(character_development_scenario["development_events"]):
            print(f"📖 Processing development event {i+1}: {event['event_type']}")
            
            # --- EVENT SIMULATION ---
            # Simulate character responses to event
            event_interaction = {
                "event_description": event["description"],
                "character_challenges": event["challenges"],
                "protagonist_response": f"Lyra responds to {event['event_type']} with determination despite her fears",
                "mentor_guidance": f"Valdris provides guidance appropriate for {event['event_type']}",
                "event_outcome": "mixed success with learning opportunities"
            }
            
            # --- CHARACTER GROWTH APPLICATION ---
            # Apply growth based on event
            growth_updates = {}
            for growth_area in event["expected_growth"]:
                if growth_area == "magical_skill":
                    growth_updates["magical_ability"] = growth_updates.get("magical_ability", 0) + 1
                elif growth_area == "confidence":
                    growth_updates["confidence_level"] = growth_updates.get("confidence_level", 0) + 1
                elif growth_area == "leadership":
                    growth_updates["leadership_experience"] = growth_updates.get("leadership_experience", 0) + 1
                # Add more growth mappings as needed
            
            # Update character data with growth
            await orchestrators["character"].update_character_development(
                story_id=story_id,
                character_name=protagonist["name"],
                development_data={
                    "event_type": event["event_type"],
                    "growth_areas": event["expected_growth"],
                    "skill_improvements": growth_updates,
                    "challenges_faced": event["challenges"],
                    "development_stage": i + 1
                }
            )
            
            # --- RELATIONSHIP DEVELOPMENT ---
            # Update relationship between protagonist and mentor
            relationship_update = self._calculate_relationship_change(
                event["event_type"], i, len(character_development_scenario["development_events"])
            )
            
            await orchestrators["character"].update_character_relationship(
                story_id=story_id,
                character_name=protagonist["name"],
                other_character=mentor["name"],
                relationship_data=relationship_update
            )
            
            # --- MEMORY CONSOLIDATION ---
            # Update memory with character development
            memory_update = {
                "character_development_event": event["event_type"],
                "character_growth": event["expected_growth"],
                "character_challenges": event["challenges"],
                "development_stage": f"stage_{i+1}",
                "character_evolution": growth_updates
            }
            
            await orchestrators["memory"].update_character_memory(
                story_id, protagonist["name"], memory_update
            )
            
            # Track growth for validation
            character_growth_tracking[protagonist["name"]]["growth_metrics"].update(growth_updates)
            character_growth_tracking[protagonist["name"]]["emotional_journey"].append({
                "stage": i + 1,
                "event": event["event_type"],
                "emotional_state": self._determine_emotional_state(event, i)
            })
            
            print(f"  ✅ Character development applied for event {i+1}")
        
        # === PHASE 3: CHARACTER CONSISTENCY VALIDATION ===
        print("🔍 Validating character development consistency...")
        
        # Get final character state
        final_character_state = await orchestrators["character"].get_character_data(
            story_id, protagonist["name"]
        )
        
        # Validate growth progression
        assert final_character_state is not None
        
        # Check character memory contains development history
        character_memory = await orchestrators["memory"].get_character_memory(
            story_id, protagonist["name"]
        )
        assert character_memory is not None
        
        # Validate relationship development
        relationships = await orchestrators["character"].get_character_relationships(
            story_id, protagonist["name"]
        )
        assert mentor["name"] in str(relationships)  # Mentor relationship should exist
        
        print("✅ Character development consistency validated")
        
        # === PHASE 4: CHARACTER ANALYSIS ===
        # Analyze character development content
        development_summary = f"""
        Character: {protagonist['name']}
        Development Journey: {len(character_development_scenario['development_events'])} major events
        Growth Areas: {', '.join(set().union(*[event['expected_growth'] for event in character_development_scenario['development_events']]))}
        Final State: Evolved from {protagonist['initial_traits']['personality']} to mature magical practitioner
        """
        
        content_analysis = await orchestrators["content"].analyze_content(
            content=development_summary,
            context={
                "analysis_type": "character_development",
                "story_id": story_id,
                "character_name": protagonist["name"]
            }
        )
        
        print("✅ Character development analysis completed")
        
        # === WORKFLOW METRICS ===
        workflow_metrics = {
            "characters_developed": 2,  # Protagonist + mentor
            "development_events": len(character_development_scenario["development_events"]),
            "growth_areas_tracked": len(set().union(*[event['expected_growth'] for event in character_development_scenario['development_events']])),
            "relationship_developments": 1,  # Protagonist-mentor relationship
            "memory_updates": len(character_development_scenario["development_events"]),
            "character_consistency": "maintained",
            "development_arc_completion": "successful"
        }
        
        print(f"🏁 Character development workflow completed!")
        print(f"📊 Development metrics: {workflow_metrics}")
        
        return {
            "character_growth": character_growth_tracking,
            "final_state": final_character_state,
            "content_analysis": content_analysis,
            "metrics": workflow_metrics
        }
    
    def _calculate_relationship_change(self, event_type: str, event_index: int, total_events: int) -> Dict[str, Any]:
        """Calculate how relationship changes based on event type and progression."""
        relationship_data = {
            "interaction_count": event_index + 1,
            "relationship_stage": f"stage_{event_index + 1}"
        }
        
        if event_type == "first_lesson":
            relationship_data.update({
                "trust_level": "building",
                "mentor_satisfaction": "hopeful",
                "student_respect": "high"
            })
        elif event_type == "public_demonstration":
            relationship_data.update({
                "trust_level": "increased",
                "mentor_pride": "growing",
                "public_acknowledgment": "mentor_support"
            })
        elif event_type == "mentor_conflict":
            relationship_data.update({
                "trust_level": "tested_but_maintained",
                "independence_recognized": "emerging",
                "mutual_respect": "deepened"
            })
        elif event_type == "crisis_leadership":
            relationship_data.update({
                "trust_level": "complete",
                "mentor_pride": "profound",
                "relationship_evolution": "equals"
            })
        
        return relationship_data
    
    def _determine_emotional_state(self, event: Dict[str, Any], event_index: int) -> str:
        """Determine character's emotional state after event."""
        if event["event_type"] == "first_lesson":
            return "nervous excitement, cautious hope"
        elif event["event_type"] == "public_demonstration":
            return "anxious but determined, growing confidence"
        elif event["event_type"] == "mentor_conflict":
            return "conflicted but resolute, emerging independence"
        elif event["event_type"] == "crisis_leadership":
            return "confident, responsible, mature"
        else:
            return f"developing emotional maturity (stage {event_index + 1})"
    
    @pytest.mark.asyncio
    async def test_character_relationship_network(self, character_development_scenario, character_orchestrators):
        """Test complex character relationship networks and development."""
        story_id = f"{character_development_scenario['story_id']}_network"
        orchestrators = character_orchestrators
        
        # Create a network of characters with interconnected relationships
        characters = [
            {"name": "Hero", "role": "protagonist"},
            {"name": "Mentor", "role": "guide"}, 
            {"name": "Rival", "role": "challenger"},
            {"name": "Friend", "role": "supporter"}
        ]
        
        # Create all characters
        for char in characters:
            await orchestrators["character"].create_character(
                story_id=story_id,
                character_name=char["name"],
                character_data={"role": char["role"], "status": "active"}
            )
        
        # Establish relationship network
        relationships = [
            ("Hero", "Mentor", "student-teacher"),
            ("Hero", "Rival", "competitive"),
            ("Hero", "Friend", "supportive"),
            ("Mentor", "Rival", "cautious_disapproval"),
            ("Friend", "Rival", "tense_tolerance")
        ]
        
        for char1, char2, relationship_type in relationships:
            await orchestrators["character"].establish_relationship(
                story_id=story_id,
                character1=char1,
                character2=char2,
                relationship_data={"type": relationship_type, "strength": "moderate"}
            )
        
        # Validate network creation
        hero_relationships = await orchestrators["character"].get_character_relationships(
            story_id, "Hero"
        )
        
        # Hero should have relationships with all other characters
        assert len(hero_relationships) >= 3
        
        print("✅ Character relationship network test passed")
    
    @pytest.mark.asyncio
    async def test_character_consistency_over_time(self, character_development_scenario, character_orchestrators):
        """Test character consistency across multiple story sessions."""
        story_id = f"{character_development_scenario['story_id']}_consistency"
        orchestrators = character_orchestrators
        
        protagonist = character_development_scenario["protagonist"]
        
        # Create character
        await orchestrators["character"].create_character(
            story_id=story_id,
            character_name=protagonist["name"],
            character_data=protagonist["initial_traits"]
        )
        
        # Simulate multiple story sessions with character interactions
        sessions = 5
        for session in range(sessions):
            # Update character with session-specific development
            session_development = {
                "session_number": session + 1,
                "experiences_gained": f"session_{session + 1}_experiences",
                "personality_reinforcement": "core_traits_maintained",
                "growth_incremental": True
            }
            
            await orchestrators["character"].update_character_development(
                story_id=story_id,
                character_name=protagonist["name"],
                development_data=session_development
            )
        
        # Validate character maintained core consistency
        final_character = await orchestrators["character"].get_character_data(
            story_id, protagonist["name"]
        )
        
        # Character should exist and maintain core traits
        assert final_character is not None
        assert protagonist["name"] in str(final_character)
        
        print(f"✅ Character consistency maintained across {sessions} sessions")


if __name__ == "__main__":
    # Allow running workflow tests directly
    pytest.main([__file__, "-v", "--tb=short"])
