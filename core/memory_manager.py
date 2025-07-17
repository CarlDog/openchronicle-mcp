import os
import json
from datetime import datetime
from pathlib import Path

def get_memory_dir(story_id):
    """Get the memory directory for a story."""
    return os.path.join("storage", story_id, "memory")

def ensure_memory_dir(story_id):
    """Ensure memory directory exists."""
    os.makedirs(get_memory_dir(story_id), exist_ok=True)

def get_current_memory_path(story_id):
    """Get path to current memory file."""
    return os.path.join(get_memory_dir(story_id), "current_memory.json")

def get_memory_history_path(story_id):
    """Get path to memory history file."""
    return os.path.join(get_memory_dir(story_id), "memory_history.json")

def load_current_memory(story_id):
    """Load the current memory state for a story."""
    ensure_memory_dir(story_id)
    memory_path = get_current_memory_path(story_id)
    
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Return default memory structure
    return {
        "characters": {},
        "world_state": {},
        "flags": [],
        "recent_events": [],
        "metadata": {
            "created": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat()
        }
    }

def save_current_memory(story_id, memory_data):
    """Save the current memory state."""
    ensure_memory_dir(story_id)
    memory_path = get_current_memory_path(story_id)
    
    # Update metadata
    memory_data["metadata"]["last_updated"] = datetime.utcnow().isoformat()
    
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2, ensure_ascii=False)

def archive_memory_snapshot(story_id, scene_id, memory_data):
    """Archive a memory snapshot linked to a scene."""
    ensure_memory_dir(story_id)
    history_path = get_memory_history_path(story_id)
    
    # Load existing history
    history = []
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    
    # Add new snapshot
    snapshot = {
        "scene_id": scene_id,
        "timestamp": datetime.utcnow().isoformat(),
        "memory": memory_data.copy()
    }
    history.append(snapshot)
    
    # Keep only last 50 snapshots to prevent bloat
    history = history[-50:]
    
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def update_character_memory(story_id, character_name, updates):
    """Update memory for a specific character."""
    memory = load_current_memory(story_id)
    
    if character_name not in memory["characters"]:
        memory["characters"][character_name] = {
            "traits": {},
            "relationships": {},
            "history": [],
            "current_state": {}
        }
    
    character = memory["characters"][character_name]
    
    # Apply updates
    for key, value in updates.items():
        if key == "traits":
            character["traits"].update(value)
        elif key == "relationships":
            character["relationships"].update(value)
        elif key == "history":
            if isinstance(value, list):
                character["history"].extend(value)
            else:
                character["history"].append(value)
        elif key == "current_state":
            character["current_state"].update(value)
    
    save_current_memory(story_id, memory)
    return memory

def update_world_state(story_id, updates):
    """Update world state memory."""
    memory = load_current_memory(story_id)
    memory["world_state"].update(updates)
    save_current_memory(story_id, memory)
    return memory

def add_memory_flag(story_id, flag_name, flag_data=None):
    """Add a memory flag."""
    memory = load_current_memory(story_id)
    
    flag_entry = {
        "name": flag_name,
        "timestamp": datetime.utcnow().isoformat(),
        "data": flag_data or {}
    }
    
    memory["flags"].append(flag_entry)
    save_current_memory(story_id, memory)
    return memory

def remove_memory_flag(story_id, flag_name):
    """Remove a memory flag by name."""
    memory = load_current_memory(story_id)
    memory["flags"] = [f for f in memory["flags"] if f["name"] != flag_name]
    save_current_memory(story_id, memory)
    return memory

def has_memory_flag(story_id, flag_name):
    """Check if a memory flag exists."""
    memory = load_current_memory(story_id)
    return any(f["name"] == flag_name for f in memory["flags"])

def add_recent_event(story_id, event_description, event_data=None):
    """Add a recent event to memory."""
    memory = load_current_memory(story_id)
    
    event = {
        "description": event_description,
        "timestamp": datetime.utcnow().isoformat(),
        "data": event_data or {}
    }
    
    memory["recent_events"].append(event)
    
    # Keep only last 20 events
    memory["recent_events"] = memory["recent_events"][-20:]
    
    save_current_memory(story_id, memory)
    return memory

def get_character_memory(story_id, character_name):
    """Get memory for a specific character."""
    memory = load_current_memory(story_id)
    return memory["characters"].get(character_name, {})

def get_memory_summary(story_id):
    """Get a summary of current memory state."""
    memory = load_current_memory(story_id)
    
    return {
        "character_count": len(memory["characters"]),
        "world_state_keys": list(memory["world_state"].keys()),
        "active_flags": [f["name"] for f in memory["flags"]],
        "recent_events_count": len(memory["recent_events"]),
        "last_updated": memory["metadata"]["last_updated"]
    }

def restore_memory_from_snapshot(story_id, scene_id):
    """Restore memory from a historical snapshot."""
    history_path = get_memory_history_path(story_id)
    
    if not os.path.exists(history_path):
        raise FileNotFoundError(f"No memory history found for story: {story_id}")
    
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    # Find the snapshot
    snapshot = None
    for snap in history:
        if snap["scene_id"] == scene_id:
            snapshot = snap
            break
    
    if not snapshot:
        raise ValueError(f"No memory snapshot found for scene: {scene_id}")
    
    # Restore memory
    memory_data = snapshot["memory"]
    save_current_memory(story_id, memory_data)
    
    return memory_data
