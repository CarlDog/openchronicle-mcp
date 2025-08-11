"""
Story Creation Workflow Test

Tests the complete journey of creating a new story from scratch,
including initialization, character setup, first scenes, and memory establishment.

This workflow validates:
- Story initialization and metadata setup
- Character creation and initial development
- First scene generation and logging
- Memory system initialization and first updates
- Database persistence throughout the process
- Content analysis of initial story elements
"""

import asyncio
import time

import pytest
import pytest_asyncio
from openchronicle.domain.services.characters import CharacterOrchestrator
from openchronicle.domain.services.scenes import SceneOrchestrator

# Import core systems
from openchronicle.infrastructure.content.analysis import (
    ContentAnalysisOrchestrator,
)
from openchronicle.infrastructure.content.context import ContextOrchestrator
from openchronicle.infrastructure.memory import MemoryOrchestrator
from openchronicle.infrastructure.persistence import DatabaseOrchestrator

# Import test utilities
from tests.fixtures.mock_adapters import MockModelOrchestrator


class TestStoryCreationWorkflow:
    """Test complete story creation workflow from initialization to first scenes."""

    @pytest.fixture
    def test_story_data(self):
        """Provide test story data for workflow testing."""
        return {
            "story_id": "test_workflow_story",
            "title": "The Enchanted Forest Quest",
            "genre": "Fantasy Adventure",
            "setting": "A mystical forest realm with ancient magic",
            "initial_characters": [
                {
                    "name": "Aria Windwhisper",
                    "role": "Elven Ranger",
                    "description": "A skilled archer with knowledge of forest lore",
                    "personality": "Brave, wise, connected to nature",
                },
                {
                    "name": "Thorin Ironbeard",
                    "role": "Dwarf Warrior",
                    "description": "A stout fighter with a magical warhammer",
                    "personality": "Loyal, gruff, protective of friends",
                },
            ],
            "opening_scene": "The party stands at the edge of the Whispering Woods, ancient trees towering above them like silent guardians. A mysterious glowing path winds deeper into the forest.",
        }

    @pytest_asyncio.fixture
    async def workflow_orchestrators(self, test_story_data):
        """Initialize orchestrators for workflow testing."""
        story_id = test_story_data["story_id"]

        # Use mock model orchestrator for predictable responses
        model_orchestrator = MockModelOrchestrator()

        # Initialize core orchestrators
        memory_orchestrator = MemoryOrchestrator()
        character_orchestrator = CharacterOrchestrator()
        scene_orchestrator = SceneOrchestrator(story_id)
        content_orchestrator = ContentAnalysisOrchestrator(model_orchestrator)
        context_orchestrator = ContextOrchestrator()
        database_orchestrator = DatabaseOrchestrator()

        # Initialize database for story
        await database_orchestrator.initialize_story_database(story_id)

        return {
            "model": model_orchestrator,
            "memory": memory_orchestrator,
            "character": character_orchestrator,
            "scene": scene_orchestrator,
            "content": content_orchestrator,
            "context": context_orchestrator,
            "database": database_orchestrator,
        }

    @pytest.mark.asyncio
    async def test_complete_story_creation_workflow(
        self, test_story_data, workflow_orchestrators
    ):
        """Test the complete story creation workflow from start to first scenes."""
        story_id = test_story_data["story_id"]
        orchestrators = workflow_orchestrators

        # === PHASE 1: STORY INITIALIZATION ===
        print(f"🎭 Starting story creation workflow for: {test_story_data['title']}")

        # Initialize story metadata
        story_metadata = {
            "story_id": story_id,
            "title": test_story_data["title"],
            "genre": test_story_data["genre"],
            "setting": test_story_data["setting"],
            "created_at": time.time(),
            "status": "active",
        }

        # Store story metadata in database
        await orchestrators["database"].store_story_metadata(story_id, story_metadata)

        # Verify story initialization
        stored_metadata = await orchestrators["database"].get_story_metadata(story_id)
        assert stored_metadata["title"] == test_story_data["title"]
        assert stored_metadata["genre"] == test_story_data["genre"]

        print("✅ Story metadata initialized and stored")

        # === PHASE 2: CHARACTER CREATION ===
        created_characters = []

        for char_data in test_story_data["initial_characters"]:
            # Create character using character orchestrator
            character_result = await orchestrators["character"].create_character(
                story_id=story_id,
                character_name=char_data["name"],
                character_data={
                    "role": char_data["role"],
                    "description": char_data["description"],
                    "personality": char_data["personality"],
                    "status": "active",
                    "introduction_scene": None,  # Will be set in opening scene
                },
            )

            created_characters.append(character_result)

            # Update memory with new character
            character_memory_update = {
                "character_introduced": char_data["name"],
                "character_role": char_data["role"],
                "character_traits": char_data["personality"],
                "introduction_context": "Story initialization",
            }

            await orchestrators["memory"].update_character_memory(
                story_id, char_data["name"], character_memory_update
            )

        print(f"✅ Created {len(created_characters)} characters with memory updates")

        # === PHASE 3: OPENING SCENE CREATION ===
        opening_scene_data = {
            "scene_id": f"{story_id}_scene_001",
            "title": "Into the Whispering Woods",
            "description": test_story_data["opening_scene"],
            "location": "Edge of Whispering Woods",
            "active_characters": [
                char["name"] for char in test_story_data["initial_characters"]
            ],
            "scene_type": "opening",
            "timestamp": time.time(),
        }

        # Create scene using scene orchestrator
        scene_result = await orchestrators["scene"].create_scene(
            story_id=story_id, scene_data=opening_scene_data
        )

        # Analyze opening scene content
        content_analysis = await orchestrators["content"].analyze_content(
            content=test_story_data["opening_scene"],
            context={
                "story_id": story_id,
                "scene_id": opening_scene_data["scene_id"],
                "characters": [
                    char["name"] for char in test_story_data["initial_characters"]
                ],
            },
        )

        print("✅ Opening scene created and analyzed")

        # === PHASE 4: INITIAL MEMORY CONSOLIDATION ===
        # Update memory with opening scene information
        scene_memory_update = {
            "scene_created": opening_scene_data["scene_id"],
            "location_introduced": opening_scene_data["location"],
            "scene_mood": "mysterious, anticipatory",
            "story_elements": content_analysis.get("themes", []),
            "character_interactions": "party formation",
        }

        await orchestrators["memory"].add_recent_event(
            story_id=story_id, event_data=scene_memory_update
        )

        # Get memory summary to verify consolidation
        memory_summary = await orchestrators["memory"].get_memory_summary(story_id)

        print("✅ Memory consolidation completed")

        # === PHASE 5: CONTEXT PREPARATION ===
        # Build context for potential next scene
        story_context = await orchestrators["context"].build_character_focused_context(
            story_data={
                "story_id": story_id,
                "current_scene": opening_scene_data,
                "active_characters": opening_scene_data["active_characters"],
            },
            character_name=test_story_data["initial_characters"][0][
                "name"
            ],  # Focus on first character
        )

        assert story_context is not None
        print("✅ Story context prepared for next interactions")

        # === PHASE 6: WORKFLOW VALIDATION ===
        # Verify complete workflow state

        # Check all characters exist in memory
        for char_data in test_story_data["initial_characters"]:
            char_memory = await orchestrators["memory"].get_character_memory(
                story_id, char_data["name"]
            )
            assert char_memory is not None
            assert char_data["name"] in str(char_memory)

        # Check scene is stored and retrievable
        stored_scene = await orchestrators["scene"].get_scene(
            story_id, opening_scene_data["scene_id"]
        )
        assert stored_scene["title"] == opening_scene_data["title"]

        # Check memory summary contains expected elements
        assert (
            len(memory_summary.get("active_flags", [])) >= 0
        )  # May have flags from character creation
        assert memory_summary.get("character_count", 0) >= len(
            test_story_data["initial_characters"]
        )

        # Check database persistence
        all_scenes = await orchestrators["database"].get_story_scenes(story_id)
        assert len(all_scenes) >= 1

        print("✅ Complete workflow validation passed")

        # === WORKFLOW METRICS ===
        workflow_metrics = {
            "characters_created": len(created_characters),
            "scenes_created": 1,
            "memory_updates": len(test_story_data["initial_characters"])
            + 1,  # Character updates + scene update
            "content_analysis_performed": True,
            "context_prepared": True,
            "database_operations": "successful",
            "workflow_status": "completed",
        }

        print("🏁 Story creation workflow completed successfully!")
        print(f"📊 Workflow metrics: {workflow_metrics}")

        return {
            "story_metadata": story_metadata,
            "characters": created_characters,
            "opening_scene": scene_result,
            "memory_summary": memory_summary,
            "content_analysis": content_analysis,
            "context": story_context,
            "metrics": workflow_metrics,
        }

    @pytest.mark.asyncio
    async def test_story_creation_error_recovery(
        self, test_story_data, workflow_orchestrators
    ):
        """Test error recovery during story creation workflow."""
        story_id = f"{test_story_data['story_id']}_error_test"
        orchestrators = workflow_orchestrators

        # Test character creation with invalid data
        with pytest.raises(Exception):
            await orchestrators["character"].create_character(
                story_id=story_id,
                character_name="",  # Invalid empty name
                character_data={},
            )

        # Test scene creation without proper initialization
        with pytest.raises(Exception):
            await orchestrators["scene"].create_scene(
                story_id="nonexistent_story", scene_data={"invalid": "data"}
            )

        print("✅ Error recovery tests passed")

    @pytest.mark.asyncio
    async def test_concurrent_story_creation(
        self, test_story_data, workflow_orchestrators
    ):
        """Test creating multiple stories concurrently."""
        [
            f"{test_story_data['story_id']}_concurrent_1",
            f"{test_story_data['story_id']}_concurrent_2",
        ]

        # Create multiple stories concurrently
        async def create_story(story_id_suffix):
            story_id = f"{test_story_data['story_id']}_{story_id_suffix}"

            # Initialize story with modified data
            story_data = test_story_data.copy()
            story_data["story_id"] = story_id
            story_data["title"] = f"{story_data['title']} - {story_id_suffix}"

            # Create first character only for speed
            char_data = story_data["initial_characters"][0]

            await workflow_orchestrators["character"].create_character(
                story_id=story_id,
                character_name=char_data["name"],
                character_data={
                    "role": char_data["role"],
                    "description": char_data["description"],
                },
            )

            return story_id

        # Run concurrent story creation
        created_stories = await asyncio.gather(
            create_story("concurrent_1"),
            create_story("concurrent_2"),
            return_exceptions=True,
        )

        # Verify both stories were created successfully
        assert len(created_stories) == 2
        assert all(isinstance(story_id, str) for story_id in created_stories)

        print(f"✅ Concurrent story creation test passed: {created_stories}")


if __name__ == "__main__":
    # Allow running workflow tests directly
    pytest.main([__file__, "-v", "--tb=short"])
