import asyncio
import sys
import argparse
from pathlib import Path

# Add utilities to path for logging system  
sys.path.append(str(Path(__file__).parent / "utilities"))
from logging_system import log_model_interaction, log_system_event, log_info, log_error
from api_key_manager import (
    get_api_key, set_api_key, remove_api_key, list_stored_keys, 
    prompt_and_store_key, get_keyring_info, is_keyring_available
)

# Global flag for emoji display (set by command line argument)
USE_EMOJIS = True

# Lazy imports to avoid full initialization for key management commands
_imports_loaded = False

def load_imports():
    """Load heavy imports only when needed."""
    global _imports_loaded
    if _imports_loaded:
        return
    
    global load_storypack, build_context_with_analysis, load_current_memory
    global update_character_memory, add_recent_event, add_memory_flag, get_memory_summary
    global save_scene, get_rollback_candidates, rollback_to_scene, model_manager
    global ContentAnalyzer, create_image_engine, ImageType
    
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
    from core.content_analyzer import ContentAnalyzer
    from core.image_generation_engine import create_image_engine, ImageType
    
    _imports_loaded = True

def emoji(text):
    """Return emoji text if emojis are enabled, otherwise return empty string."""
    return text if USE_EMOJIS else ""

def status_icon(success=True):
    """Return appropriate status icon based on success and emoji setting."""
    if not USE_EMOJIS:
        return "Ready" if success else "Error"
    return "✅" if success else "❌"

def print_memory_summary(story_id):
    """Print a summary of current memory state."""
    load_imports()  # Ensure imports are loaded
    summary = get_memory_summary(story_id)
    print(f"\n{emoji('📚 ')}Memory Summary:")
    print(f"   Characters: {summary['character_count']}")
    print(f"   World State: {len(summary['world_state_keys'])} keys")
    print(f"   Active Flags: {len(summary['active_flags'])}")
    print(f"   Recent Events: {summary['recent_events_count']}")
    print(f"   Last Updated: {summary['last_updated']}")

def show_model_info():
    """Show information about available models."""
    load_imports()  # Ensure imports are loaded
    print(f"\n{emoji('🤖 ')}Available Models:")
    for adapter_name in model_manager.get_available_adapters():
        try:
            info = model_manager.get_adapter_info(adapter_name)
            status_text = status_icon(info["initialized"]) if USE_EMOJIS else ("Ready" if info["initialized"] else "Not initialized")
            print(f"   {adapter_name}: {info['provider']} - {info['model_name']} ({status_text})")
        except Exception as e:
            error_icon = status_icon(False)
            print(f"   {adapter_name}: {error_icon} Error: {e}")
            log_error(f"Model adapter error for {adapter_name}: {e}")

async def switch_model():
    """Switch the active model adapter."""
    load_imports()  # Ensure imports are loaded
    adapters = model_manager.get_available_adapters()
    print(f"\n{emoji('🔧 ')}Available Adapters:")
    for i, adapter in enumerate(adapters):
        print(f"{i+1}. {adapter}")
    
    choice = input("Select adapter number (or press Enter to cancel): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(adapters):
        adapter_name = adapters[int(choice)-1]
        try:
            print(f"Initializing {adapter_name}...")
            success = await model_manager.initialize_adapter(adapter_name)
            if success:
                model_manager.default_adapter = adapter_name
                print(f"{status_icon(True)} Switched to {adapter_name}")
            else:
                print(f"{status_icon(False)} Failed to initialize {adapter_name}")
                log_error(f"Failed to initialize adapter: {adapter_name}")
        except Exception as e:
            print(f"{status_icon(False)} Error switching to {adapter_name}: {e}")
            log_error(f"Error switching to adapter {adapter_name}: {e}")

def show_rollback_options(story_id):
    """Show available rollback options."""
    candidates = get_rollback_candidates(story_id, limit=5)
    if not candidates:
        print(f"{emoji('⏪ ')}No rollback candidates available.")
        return
    
    print(f"\n{emoji('⏪ ')}Rollback Options:")
    for i, candidate in enumerate(candidates):
        print(f"{i+1}. {candidate['scene_summary']} (Scene {candidate['scene_id']})")
    
    choice = input("Enter number to rollback (or press Enter to skip): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(candidates):
        scene_id = candidates[int(choice)-1]['scene_id']
        result = rollback_to_scene(story_id, scene_id)
        print(f"{status_icon(True)} {result['message']}")
        print(f"   Scenes removed: {result['scenes_removed']}")

async def show_image_commands(story_id):
    """Show and handle image generation commands."""
    print(f"\n{emoji('🎨 ')}Image Generation Commands:")
    print("1. Generate character portrait")
    print("2. Generate scene image")
    print("3. List existing images")
    print("4. View image stats")
    print("5. Back to main menu")
    
    choice = input("Select option (1-5): ").strip()
    
    try:
        image_engine = create_image_engine(story_id)
        
        if choice == "1":
            await generate_character_portrait_cli(image_engine)
        elif choice == "2":
            await generate_scene_image_cli(image_engine)
        elif choice == "3":
            list_existing_images(image_engine)
        elif choice == "4":
            show_image_stats(image_engine)
        elif choice == "5":
            return
        else:
            print(f"{status_icon(False)} Invalid choice. Please select 1-5.")
    except Exception as e:
        print(f"{status_icon(False)} Error accessing image engine: {e}")
        log_error(f"Image engine error: {e}")

async def generate_character_portrait_cli(image_engine):
    """Generate a character portrait via CLI."""
    character_name = input("Character name: ").strip()
    if not character_name:
        print(f"{status_icon(False)} Character name required.")
        return
    
    print("Character description (or press Enter to use default):")
    description = input().strip()
    
    character_data = {}
    if description:
        character_data["description"] = description
    else:
        character_data = {
            "description": f"A character from the story named {character_name}",
            "appearance": {"general": "Detailed character design"},
            "personality": {"demeanor": "Story-appropriate personality"}
        }
    
    print(f"{emoji('🖼️ ')}Generating portrait for {character_name}...")
    
    try:
        image_id = await image_engine.generate_character_portrait(character_name, character_data)
        if image_id:
            print(f"{status_icon(True)} Generated portrait: {image_id}")
            image_path = image_engine.get_image_path(image_id)
            print(f"   Saved to: {image_path}")
        else:
            print(f"{status_icon(False)} Failed to generate portrait (no adapters available)")
    except Exception as e:
        print(f"{status_icon(False)} Error generating portrait: {e}")
        log_error(f"Portrait generation error: {e}")

async def generate_scene_image_cli(image_engine):
    """Generate a scene image via CLI."""
    scene_id = input("Scene ID (optional): ").strip()
    if not scene_id:
        scene_id = f"manual_scene_{int(asyncio.get_event_loop().time())}"
    
    description = input("Scene description: ").strip()
    if not description:
        print(f"{status_icon(False)} Scene description required.")
        return
    
    location = input("Location (optional): ").strip()
    atmosphere = input("Atmosphere/mood (optional): ").strip()
    
    scene_data = {"description": description}
    if location:
        scene_data["location"] = location
    if atmosphere:
        scene_data["atmosphere"] = atmosphere
    
    context = {
        "manual_generation": True,
        "user_requested": True
    }
    
    print(f"{emoji('🎬 ')}Generating scene image for {scene_id}...")
    
    try:
        image_id = await image_engine.generate_scene_image(scene_id, scene_data, context)
        if image_id:
            print(f"{status_icon(True)} Generated scene: {image_id}")
            image_path = image_engine.get_image_path(image_id)
            print(f"   Saved to: {image_path}")
        else:
            print(f"{status_icon(False)} Failed to generate scene (no adapters available)")
    except Exception as e:
        print(f"{status_icon(False)} Error generating scene: {e}")
        log_error(f"Scene generation error: {e}")

def list_existing_images(image_engine):
    """List all existing images."""
    if not image_engine.metadata:
        print(f"{emoji('📷 ')}No images found.")
        return
    
    print(f"\n{emoji('📊 ')}Existing Images ({len(image_engine.metadata)}):")
    
    characters = {}
    scenes = {}
    
    for image_id, metadata in image_engine.metadata.items():
        if metadata.image_type == ImageType.CHARACTER:
            char_name = metadata.character_name or "Unknown"
            if char_name not in characters:
                characters[char_name] = []
            characters[char_name].append(metadata)
        elif metadata.image_type == ImageType.SCENE:
            scene_id = metadata.scene_id or "Unknown"
            if scene_id not in scenes:
                scenes[scene_id] = []
            scenes[scene_id].append(metadata)
    
    if characters:
        print(f"\n{emoji('👥 ')}Character Portraits:")
        for char_name, images in characters.items():
            print(f"   {char_name}: {len(images)} image(s)")
            for img in images:
                print(f"     - {img.image_id} ({img.timestamp})")
    
    if scenes:
        print(f"\n{emoji('🎬 ')}Scene Images:")
        for scene_id, images in scenes.items():
            print(f"   {scene_id}: {len(images)} image(s)")
            for img in images:
                print(f"     - {img.image_id} ({img.timestamp})")

def show_image_stats(image_engine):
    """Show image generation statistics."""
    stats = image_engine.get_engine_stats()
    
    print(f"\n{emoji('📊 ')}Image Generation Stats:")
    print(f"   Images Generated: {stats['images_generated']}")
    print(f"   Total Cost: ${stats['total_cost']:.4f}")
    print(f"   Generation Time: {stats['generation_time']:.2f}s")
    print(f"   Available Adapters: {', '.join(stats['available_adapters'])}")
    
    if stats['providers_used']:
        print(f"   Providers Used: {', '.join(stats['providers_used'])}")
    
    total_images = stats.get('total_images', 0)
    if total_images > 0:
        print(f"   Average Cost per Image: ${stats['total_cost']/total_images:.4f}")
        print(f"   Average Time per Image: {stats['generation_time']/total_images:.2f}s")

async def run_quick_test():
    """Run a quick test of core functionality without interactive mode."""
    print(f"{emoji('🧪 ')}Quick Test Mode - Non-Interactive")
    print("=" * 40)
    
    try:
        # Load story
        print("Loading demo story...")
        story = load_storypack("demo-story")
        story_id = story["id"]
        print(f"{status_icon(True)} Loaded: {story['meta']['title']}")
        
        # Initialize model
        print("Initializing mock model...")
        await model_manager.initialize_adapter("mock")
        print(f"{status_icon(True)} Mock model ready")
        
        # Test context building
        print("Testing context building...")
        context = await build_context_with_analysis("I look around the room", story)
        print(f"{status_icon(True)} Context built successfully")
        
        # Test AI response
        print("Testing AI response...")
        response = await model_manager.generate_response(context["full_context"])
        print(f"{status_icon(True)} Response: {response[:50]}...")
        
        # Test scene logging
        print("Testing scene logging...")
        scene_id = save_scene(story_id, "Test input", response, memory_snapshot=context["memory"])
        print(f"{status_icon(True)} Scene logged: {scene_id}")
        
        # Test memory summary
        print("Testing memory summary...")
        summary = get_memory_summary(story_id)
        print(f"{status_icon(True)} Memory summary: {summary['character_count']} characters")
        
        print(f"\n{emoji('🎉 ')}Quick test completed successfully!")
        return True
        
    except Exception as e:
        print(f"{status_icon(False)} Quick test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await model_manager.shutdown()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='OpenChronicle Interactive Story Engine')
    parser.add_argument('--test', action='store_true', 
                        help='Run quick system test and exit')
    parser.add_argument('--non-interactive', action='store_true',
                        help='Run in non-interactive mode (for testing/automation)')
    parser.add_argument('--story-id', type=str, default='demo-story', metavar='ID',
                        help='Story ID to load (default: demo-story)')
    parser.add_argument('--input', type=str, metavar='TEXT',
                        help='Single input to process in non-interactive mode')
    parser.add_argument('--max-iterations', type=int, default=1, metavar='N',
                        help='Maximum iterations in non-interactive mode (default: 1)')
    parser.add_argument('--no-emojis', action='store_true',
                        help='Disable emoji output for professional/clean display')
    
    # API Key management commands
    parser.add_argument('--set-key', type=str, metavar='PROVIDER',
                        help='Store API key for provider (openai, anthropic, etc.)')
    parser.add_argument('--list-keys', action='store_true',
                        help='List stored API keys')
    parser.add_argument('--remove-key', type=str, metavar='PROVIDER',
                        help='Remove stored API key for provider')
    parser.add_argument('--keyring-info', action='store_true',
                        help='Show keyring backend information')
    
    return parser.parse_args()

async def run_non_interactive_mode(story_id: str, args, story):
    """Run in non-interactive mode for testing/automation."""
    print(f"\nRunning in non-interactive mode...")
    
    # Use provided input or default test input
    test_inputs = []
    if args.input:
        test_inputs = [args.input]
    else:
        test_inputs = [
            "Look around the forest clearing.",
            "Check my equipment.",
            "memory"
        ]
    
    iterations = min(len(test_inputs), args.max_iterations)
    
    for i, test_input in enumerate(test_inputs[:iterations]):
        print(f"\nInput {i+1}: {test_input}")
        
        # Handle special commands
        if test_input.lower() == 'memory':
            print_memory_summary(story_id)
            continue
        elif test_input.lower() in ['models']:
            show_model_info()
            continue
        
        # Process story input
        await process_story_input(story_id, test_input, story)
    
    print(f"\nNon-interactive mode completed ({iterations} iterations)")

async def process_story_input(story_id: str, user_input: str, story):
    """Process a single story input (extracted from main loop)."""
    # Build context with analysis
    print(f"   {emoji('🧠 ')}Analyzing context...")
    context = await build_context_with_analysis(user_input, story)
    
    # Determine the best adapter and parameters for this input
    preferred_adapter = context.get("recommended_adapter", "openai")
    max_tokens = context.get("recommended_max_tokens", 800)
    temperature = context.get("recommended_temperature", 0.7)
    
    print(f"   Using {preferred_adapter} adapter (max_tokens: {max_tokens}, temp: {temperature})")
    
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
        print(f"{status_icon(False)} AI generation failed: {e}")
        ai_response = f"[Error generating response: {e}]"
    
    # Generate content flags from analysis and response
    analysis = context.get("analysis", {})
    if analysis:
        try:
            content_analyzer_instance = ContentAnalyzer(model_manager)
            content_flags = await content_analyzer_instance.generate_content_flags(analysis, ai_response)
            for flag in content_flags:
                add_memory_flag(story_id, flag["name"], flag["value"])
            print(f"   Generated {len(content_flags)} content flags")
        except Exception as e:
            print(f"{status_icon(False)} Flag generation failed: {e}")
    
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
    
    print(f"{ai_response}")
    print(f"   Scene logged: {scene_id}")

async def main():
    global USE_EMOJIS
    args = parse_arguments()
    
    # Set emoji preference from command line
    USE_EMOJIS = not args.no_emojis
    
    # Handle API key management commands first (before heavy imports)
    if handle_key_management_commands(args):
        return  # Exit after handling key commands
    
    # Load heavy imports only after key management check
    load_imports()
    
    # Check for test mode
    if args.test:
        success = await run_quick_test()
        sys.exit(0 if success else 1)
    
    print(f"{emoji('📖 ')}Loading storypack...")
    story = load_storypack(args.story_id)
    story_id = story["id"]
    
    print(f"{status_icon(True)} Loaded story: {story['meta']['title']}")
    print_memory_summary(story_id)
    
    # Initialize default model adapter
    print(f"{emoji('🤖 ')}Initializing AI model...")
    try:
        await model_manager.initialize_adapter(model_manager.config["default_adapter"])
        print(f"{status_icon(True)} Model ready: {model_manager.default_adapter}")
    except Exception as e:
        print(f"{status_icon(False)} Model initialization failed: {e}")
        print(f"{emoji('🚨 ')}CRITICAL WARNING: No real AI models available!")
        print(f"{emoji('⚠️ ')}System will use MOCK responses - NOT suitable for production use!")
        print(f"{emoji('💡 ')}Please configure at least one working AI provider for real functionality.")
        print(f"{emoji('⚠️ ')}Continuing with mock responses for testing purposes only...")
    
    # Handle non-interactive mode
    if args.non_interactive:
        await run_non_interactive_mode(story_id, args, story)
        return
    
    print(f"\n{emoji('📝 ')}Commands:")
    print("   - Type your story input normally")
    print("   - Type 'memory' to view memory summary")
    print("   - Type 'rollback' to see rollback options")
    print("   - Type 'models' to see available models")
    print("   - Type 'switch' to switch model")
    print("   - Type 'images' to access image generation")
    print("   - Type 'keys' to manage API keys")
    print("   - Type 'quit' to exit")
    
    # Interactive mode
    while True:
        user_input = input("\nYou: ").strip()
        
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
        elif user_input.lower() == 'images':
            await show_image_commands(story_id)
            continue
        elif user_input.lower() == 'keys':
            show_interactive_key_commands()
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
            print(f"{status_icon(False)} AI generation failed: {e}")
            ai_response = f"[Error generating response: {e}]"
        
        # Generate content flags from analysis and response
        analysis = context.get("analysis", {})
        if analysis:
            try:
                content_analyzer_instance = ContentAnalyzer(model_manager)
                content_flags = await content_analyzer_instance.generate_content_flags(analysis, ai_response)
                for flag in content_flags:
                    add_memory_flag(story_id, flag["name"], flag["value"])
                print(f"   Generated {len(content_flags)} content flags")
            except Exception as e:
                print(f"{status_icon(False)} Flag generation failed: {e}")
        
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
        
        print(f"{ai_response}")
        print(f"   Scene logged: {scene_id}")
    
    print(f"\n{emoji('👋 ')}Story session ended.")
    await model_manager.shutdown()

def handle_key_management_commands(args):
    """Handle API key management commands."""
    
    if args.keyring_info:
        show_keyring_info()
        return True
    
    if args.list_keys:
        show_stored_keys()
        return True
    
    if args.set_key:
        provider = args.set_key.lower()
        success = prompt_and_store_key(provider)
        if success:
            print(f"\n{status_icon(True)} API key management completed successfully!")
        else:
            print(f"\n{status_icon(False)} API key setup failed.")
        return True
    
    if args.remove_key:
        provider = args.remove_key.lower()
        success = remove_api_key(provider)
        if success:
            print(f"{status_icon(True)} API key removed for {provider}")
        else:
            print(f"{status_icon(False)} Failed to remove API key for {provider}")
        return True
    
    return False

def show_keyring_info():
    """Show keyring backend information."""
    info = get_keyring_info()
    
    print(f"\n{emoji('🔐 ')}Keyring Information:")
    print(f"   Available: {info['available']}")
    
    if info['available']:
        print(f"   Backend: {info['backend']}")
        print(f"   Service: {info['service_name']}")
        print(f"   Supported providers: {', '.join(info['supported_providers'])}")
    else:
        print(f"   Reason: {info['reason']}")
        print(f"   Fix: {info['recommendation']}")

def show_stored_keys():
    """Show stored API keys."""
    if not is_keyring_available():
        print(f"{status_icon(False)} Keyring not available. Install with: pip install keyring")
        return
    
    stored = list_stored_keys()
    
    if not stored:
        print(f"\n{emoji('🔑 ')}No API keys stored in secure storage.")
        print("Use --set-key PROVIDER to store API keys securely.")
        return
    
    print(f"\n{emoji('🗄️ ')}Stored API Keys ({len(stored)}):")
    for provider in sorted(stored):
        print(f"   {emoji('✅ ')}{provider}")
    
    print(f"\nUse --remove-key PROVIDER to remove a key.")

def show_interactive_key_commands():
    """Show and handle interactive API key management."""
    if not is_keyring_available():
        print(f"{status_icon(False)} Secure storage not available.")
        print("Install keyring: pip install keyring")
        return
    
    print(f"\n{emoji('🔐 ')}API Key Management:")
    print("1. Store new API key")
    print("2. List stored keys") 
    print("3. Remove API key")
    print("4. Show keyring info")
    print("5. Back to main menu")
    
    choice = input("Select option (1-5): ").strip()
    
    if choice == "1":
        print("\nSupported providers: openai, anthropic, google, groq, cohere, mistral")
        provider = input("Enter provider name: ").strip().lower()
        if provider:
            prompt_and_store_key(provider)
    elif choice == "2":
        show_stored_keys()
    elif choice == "3":
        stored = list_stored_keys()
        if not stored:
            print("No stored keys to remove.")
            return
        print(f"\nStored providers: {', '.join(stored)}")
        provider = input("Enter provider to remove: ").strip().lower()
        if provider in stored:
            success = remove_api_key(provider)
            if success:
                print(f"{status_icon(True)} Removed API key for {provider}")
            else:
                print(f"{status_icon(False)} Failed to remove key")
        else:
            print(f"{status_icon(False)} Provider not found")
    elif choice == "4":
        show_keyring_info()
    elif choice == "5":
        return
    else:
        print(f"{status_icon(False)} Invalid choice.")

if __name__ == "__main__":
    asyncio.run(main())