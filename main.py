from core.story_loader import load_storypack
from core.context_builder import build_context
from core.memory_manager import (
    load_current_memory, 
    update_character_memory, 
    add_recent_event,
    get_memory_summary
)
from core.scene_logger import save_scene
from core.rollback_engine import get_rollback_candidates, rollback_to_scene

def print_memory_summary(story_id):
    """Print a summary of current memory state."""
    summary = get_memory_summary(story_id)
    print(f"\n📊 Memory Summary:")
    print(f"   Characters: {summary['character_count']}")
    print(f"   World State: {len(summary['world_state_keys'])} keys")
    print(f"   Active Flags: {len(summary['active_flags'])}")
    print(f"   Recent Events: {summary['recent_events_count']}")
    print(f"   Last Updated: {summary['last_updated']}")

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

if __name__ == "__main__":
    print("🔧 Loading storypack...")
    story = load_storypack("demo-story")
    story_id = story["id"]
    
    print(f"✅ Loaded story: {story['meta']['title']}")
    print_memory_summary(story_id)
    
    print("\n📖 Commands:")
    print("   - Type your story input normally")
    print("   - Type 'memory' to view memory summary")
    print("   - Type 'rollback' to see rollback options")
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
        elif not user_input:
            continue
        
        # Build context and process input
        context = build_context(user_input, story)
        
        # Simulate AI response (in real implementation, this would call an LLM)
        ai_response = f"[AI would respond to: {user_input}]"
        
        # Log the scene
        scene_id = save_scene(
            story_id, 
            user_input, 
            ai_response, 
            memory_snapshot=context["memory"]
        )
        
        # Add to recent events
        add_recent_event(story_id, f"User: {user_input}")
        
        print(f"📖 {ai_response}")
        print(f"   Scene logged: {scene_id}")
    
    print("\n👋 Story session ended.")