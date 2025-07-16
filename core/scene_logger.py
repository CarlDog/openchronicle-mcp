import os
import json
from datetime import datetime
from pathlib import Path

def get_scene_dir(story_id):
    return os.path.join("storage", story_id, "scenes")

def get_memory_dir(story_id):
    return os.path.join("storage", story_id, "memory")

def ensure_dirs(story_id):
    os.makedirs(get_scene_dir(story_id), exist_ok=True)
    os.makedirs(get_memory_dir(story_id), exist_ok=True)

def generate_scene_id():
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")

def save_scene(story_id, user_input, model_output, memory_snapshot=None, flags=None, context_refs=None):
    ensure_dirs(story_id)
    
    scene_id = generate_scene_id()
    scene_path = os.path.join(get_scene_dir(story_id), f"{scene_id}.json")

    scene_data = {
        "scene_id": scene_id,
        "timestamp": datetime.utcnow().isoformat(),
        "input": user_input,
        "output": model_output,
        "memory": memory_snapshot or {},
        "flags": flags or [],
        "canon_refs": context_refs or []
    }

    with open(scene_path, "w", encoding="utf-8") as f:
        json.dump(scene_data, f, indent=2)

    return scene_id

def load_scene(story_id, scene_id):
    scene_path = os.path.join(get_scene_dir(story_id), f"{scene_id}.json")
    if not os.path.exists(scene_path):
        raise FileNotFoundError(f"No scene found: {scene_id}")
    with open(scene_path, "r", encoding="utf-8") as f:
        return json.load(f)

def list_scenes(story_id):
    scene_dir = Path(get_scene_dir(story_id))
    return sorted(f.stem for f in scene_dir.glob("*.json"))

def rollback_to_scene(story_id, scene_id):
    """Returns scene input/output/memory to rebuild current state."""
    scene = load_scene(story_id, scene_id)
    return {
        "scene_id": scene["scene_id"],
        "input": scene["input"],
        "output": scene["output"],
        "memory": scene.get("memory", {}),
        "flags": scene.get("flags", [])
    }