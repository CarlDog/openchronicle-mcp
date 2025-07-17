import asyncio
import sys
from pathlib import Path
from core.story_loader import load_storypack
from core.context_builder import build_context_with_analysis
from core.memory_manager import (
    load_current_memory, 
    update_character_memory, 
    add_recent_event,
    add_memory_flag,
    get_memory_summary
)
from core.scene_logger import save_scene
from core.rollback_engine import get_rollback_candidates, rollback_to_scene
from core.model_adapter import model_manager
from core.content_analyzer import content_analyzer

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent / "utilities"))
from logging_system import log_model_interaction, log_system_event, log_info, log_error

def print_memory_summary(story_id):
    """Print a summary of current memory state."""
    summary = get_memory_summary(story_id)
    print(f"\n📊 Memory Summary:")
    print(f"   Characters: {summary['character_count']}")
    print(f"   World State: {len(summary['world_state_keys'])} keys")
    print(f"   Active Flags: {len(summary['active_flags'])}")
    print(f"   Recent Events: {summary['recent_events_count']}")
    print(f"   Last Updated: {summary['last_updated']}")

def show_model_info():
    """Show information about available models."""
    print("\n🤖 Available Models:")
    for adapter_name in model_manager.get_available_adapters():
        try:
            info = model_manager.get_adapter_info(adapter_name)
            status = "✅ Ready" if info["initialized"] else "⏳ Not initialized"
            print(f"   {adapter_name}: {info['provider']} - {info['model_name']} ({status})")
        except Exception as e:
            print(f"   {adapter_name}: ❌ Error: {e}")
            log_error(f"Model adapter error for {adapter_name}: {e}")

async def switch_model():
    """Switch the active model adapter."""
    adapters = model_manager.get_available_adapters()
    print("\n🔄 Available Adapters:")
    for i, adapter in enumerate(adapters):
        print(f"{i+1}. {adapter}")
    
    choice = input("Select adapter number (or press Enter to cancel): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(adapters):
        adapter_name = adapters[int(choice)-1]
        try:
            print(f"🔄 Initializing {adapter_name}...")
            success = await model_manager.initialize_adapter(adapter_name)
            if success:
                model_manager.default_adapter = adapter_name
                print(f"✅ Switched to {adapter_name}")
            else:
                print(f"❌ Failed to initialize {adapter_name}")
                log_error(f"Failed to initialize adapter: {adapter_name}")
        except Exception as e:
            print(f"❌ Error switching to {adapter_name}: {e}")
            log_error(f"Error switching to adapter {adapter_name}: {e}")

def show_rollback_options(story_id):
    """Show available rollback options."""
    candidates = get_rollback_candidates(story_id, limit=5)
    if not candidates:
        print("No rollback candidates available.")
        return
    
    print("\n🔄 Recent Rollback Options:")
    for i, candidate in enumerate(candidates):
        print(f"{i+1}. {candidate['scene_id']}: {candidate['input_preview']}")
    
    choice = input("Enter number to rollback (or press Enter to skip): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(candidates):
        scene_id = candidates[int(choice)-1]['scene_id']
        result = rollback_to_scene(story_id, scene_id)
        print(f"✅ {result['message']}")
        print(f"   Scenes removed: {result['scenes_removed']}")

async def run_quick_test():
    """Run a quick test of core functionality without interactive mode."""
    print("🧪 Quick Test Mode - Non-Interactive")
    print("=" * 40)
    
    try:
        # Load story
        print("📚 Loading demo story...")
        story = load_storypack("demo-story")
        story_id = story["id"]
        print(f"✅ Loaded: {story['meta']['title']}")
        
        # Initialize model
        print("🤖 Initializing mock model...")
        await model_manager.initialize_adapter("mock")
        print("✅ Mock model ready")
        
        # Test context building
        print("🏗️ Testing context building...")
        context = await build_context_with_analysis("I look around the room", story)
        print("✅ Context built successfully")
        
        # Test AI response
        print("🤖 Testing AI response...")
        response = await model_manager.generate_response(context["full_context"])
        print(f"✅ Response: {response[:50]}...")
        
        # Test scene logging
        print("📝 Testing scene logging...")
        scene_id = save_scene(story_id, "Test input", response, memory_snapshot=context["memory"])
        print(f"✅ Scene logged: {scene_id}")
        
        # Test memory summary
        print("🧠 Testing memory summary...")
        summary = get_memory_summary(story_id)
        print(f"✅ Memory summary: {summary['character_count']} characters")
        
        print("\n🎉 Quick test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await model_manager.shutdown()

async def main():
    # Check for non-interactive test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        success = await run_quick_test()
        sys.exit(0 if success else 1)
    
    print("🔧 Loading storypack...")
    story = load_storypack("demo-story")
    story_id = story["id"]
    
    print(f"✅ Loaded story: {story['meta']['title']}")
    print_memory_summary(story_id)
    
    # Initialize default model adapter
    print("🤖 Initializing AI model...")
    try:
        await model_manager.initialize_adapter(model_manager.config["default_adapter"])
        print(f"✅ Model ready: {model_manager.default_adapter}")
    except Exception as e:
        print(f"⚠️ Model initialization failed: {e}")
        print("Continuing with mock responses...")
    
    print("\n📖 Commands:")
    print("   - Type your story input normally")
    print("   - Type 'memory' to view memory summary")
    print("   - Type 'rollback' to see rollback options")
    print("   - Type 'models' to see available models")
    print("   - Type 'switch' to switch model")
    print("   - Type 'quit' to exit")
    
    while True:
        user_input = input("\n🧠 You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        elif user_input.lower() == 'memory':
            print_memory_summary(story_id)
            continue
        elif user_input.lower() == 'rollback':
            show_rollback_options(story_id)
            continue
        elif user_input.lower() == 'models':
            show_model_info()
            continue
        elif user_input.lower() == 'switch':
            await switch_model()
            continue
        elif not user_input:
            continue
        
        # Build context using intelligent analysis
        context = await build_context_with_analysis(user_input, story)
        
        # Get routing recommendation from analysis
        routing = context.get("routing", {})
        preferred_adapter = routing.get("adapter", model_manager.default_adapter)
        max_tokens = routing.get("max_tokens", 1024)
        temperature = routing.get("temperature", 0.7)
        
        # Generate AI response using optimized context and routing
        try:
            ai_response = await model_manager.generate_response(
                context["full_context"], 
                adapter_name=preferred_adapter,
                story_id=story_id,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            print(f"⚠️ AI generation failed: {e}")
            ai_response = f"[Error generating response: {e}]"
        
        # Generate content flags from analysis and response
        analysis = context.get("analysis", {})
        if analysis:
            try:
                content_flags = await content_analyzer.generate_content_flags(analysis, ai_response)
                for flag in content_flags:
                    add_memory_flag(story_id, flag["name"], flag["value"])
                print(f"   Generated {len(content_flags)} content flags")
            except Exception as e:
                print(f"⚠️ Flag generation failed: {e}")
        
        # Log the scene
        scene_id = save_scene(
            story_id, 
            user_input, 
            ai_response, 
            memory_snapshot=context["memory"],
            analysis_data=analysis
        )
        
        # Add to recent events
        add_recent_event(story_id, f"User: {user_input}")
        
        print(f"📖 {ai_response}")
        print(f"   Scene logged: {scene_id}")
    
    print("\n👋 Story session ended.")
    await model_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())