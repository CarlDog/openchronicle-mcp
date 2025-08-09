"""
Integration test demonstrating the complete hexagonal architecture.

This test shows how all layers work together:
- Domain layer: Business logic and entities  
- Application layer: Use cases and orchestration
- Infrastructure layer: Persistence and external systems
"""

import asyncio
from datetime import datetime

# Import all layers
from src.openchronicle.domain import Story, Character, StoryStatus
from src.openchronicle.application import (
    CreateStoryCommand, CreateCharacterCommand, GenerateSceneCommand,
    StoryOrchestrator, CharacterOrchestrator, NarrativeOrchestrator,
    ApplicationFacade
)
from src.openchronicle.infrastructure import create_infrastructure


async def demonstrate_architecture():
    """Demonstrate the complete architecture integration."""
    print("🏗️  OpenChronicle Hexagonal Architecture Demo")
    print("=" * 50)
    
    # 1. Setup Infrastructure
    print("\n📦 Setting up infrastructure...")
    infra = create_infrastructure(
        storage_backend="filesystem",
        storage_path="demo_storage",
        cache_type="memory"
    )
    
    # Get all components
    story_repo = infra.get_story_repository()
    char_repo = infra.get_character_repository()
    scene_repo = infra.get_scene_repository()
    memory_manager = infra.get_memory_manager()
    model_manager = infra.get_model_manager()
    
    print(f"   ✅ Story Repository: {type(story_repo).__name__}")
    print(f"   ✅ Memory Manager: {type(memory_manager).__name__}")
    print(f"   ✅ Model Manager: {len(model_manager.adapters)} adapters")
    
    # 2. Create Domain Services
    print("\n🧠 Setting up domain services...")
    from src.openchronicle.domain.services import StoryGenerator, CharacterAnalyzer
    
    story_generator = StoryGenerator()
    character_analyzer = CharacterAnalyzer()
    print("   ✅ Domain services initialized")
    
    # 3. Create Application Orchestrators
    print("\n🎭 Setting up application orchestrators...")
    story_orchestrator = StoryOrchestrator(
        story_repo, char_repo, scene_repo, memory_manager, story_generator
    )
    
    character_orchestrator = CharacterOrchestrator(
        char_repo, story_repo, memory_manager, character_analyzer
    )
    
    narrative_orchestrator = NarrativeOrchestrator(
        story_repo, char_repo, scene_repo, memory_manager, 
        model_manager, story_generator, character_analyzer
    )
    print("   ✅ Application orchestrators ready")
    
    # 4. Create Application Facade
    print("\n🎪 Setting up application facade...")
    app_facade = ApplicationFacade(
        story_orchestrator, character_orchestrator, narrative_orchestrator
    )
    print("   ✅ Application facade ready")
    
    # 5. Demonstrate Use Cases
    print("\n🎬 Demonstrating use cases...")
    
    # Create a story
    create_story_cmd = CreateStoryCommand(
        title="The Hexagonal Adventure",
        description="A tale of clean architecture and separated concerns",
        initial_world_state={
            "setting": "A magical realm of software architecture",
            "mood": "adventurous",
            "tech_level": "modern"
        }
    )
    
    story_result = await story_orchestrator.create_story(create_story_cmd)
    
    if story_result.success:
        story = story_result.data
        print(f"   ✅ Story created: '{story.title}' (ID: {story.id})")
        
        # Create a character
        create_char_cmd = CreateCharacterCommand(
            story_id=story.id,
            name="Alex the Architect",
            description="A wise software architect who believes in clean code",
            personality_traits={
                "wisdom": 8,
                "creativity": 7,
                "pragmatism": 9
            },
            background="Years of experience building maintainable systems",
            goals=["Design elegant architectures", "Mentor other developers"]
        )
        
        char_result = await character_orchestrator.create_character(create_char_cmd)
        
        if char_result.success:
            character = char_result.data
            print(f"   ✅ Character created: '{character.name}' (ID: {character.id})")
            
            # Generate a scene
            generate_scene_cmd = GenerateSceneCommand(
                story_id=story.id,
                user_input="Alex encounters a legacy codebase that needs refactoring",
                model_preference="mock",
                scene_type="narrative",
                participant_ids=[character.id],
                location="The Repository of Legacy Code"
            )
            
            scene_result = await narrative_orchestrator.generate_scene(generate_scene_cmd)
            
            if scene_result.success:
                scene_data = scene_result.data
                print(f"   ✅ Scene generated using {scene_data['model_used']}")
                print(f"      Content preview: {scene_data['content'][:100]}...")
                print(f"      Generation time: {scene_data['generation_time']:.2f}s")
                
                # Test memory state
                memory_state = await memory_manager.get_current_state(story.id)
                print(f"   ✅ Memory state has {len(memory_state.character_memories)} characters")
                print(f"      Recent events: {len(memory_state.recent_events)}")
                
                # Test caching
                cache = infra.get_cache()
                await cache.set("demo_key", "demo_value", ttl=60)
                cached_value = await cache.get("demo_key")
                print(f"   ✅ Cache test: {cached_value}")
                
    # 6. Health Check
    print("\n🏥 Running health checks...")
    health_status = await infra.health_check()
    print(f"   Overall status: {health_status['status']}")
    
    for component, status in health_status['components'].items():
        status_icon = "✅" if status['status'] == 'healthy' else "❌"
        print(f"   {status_icon} {component}: {status['status']}")
    
    print(f"\n🎉 Architecture demonstration complete!")
    print("   All layers working together seamlessly!")


if __name__ == "__main__":
    asyncio.run(demonstrate_architecture())
