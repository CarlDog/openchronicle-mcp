import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from .scene_logger import get_scene_dir, load_scene, list_scenes
from .memory_manager import restore_memory_from_snapshot, get_memory_dir

def get_rollback_dir(story_id):
    """Get the rollback directory for a story."""
    return os.path.join("storage", story_id, "rollback")

def ensure_rollback_dir(story_id):
    """Ensure rollback directory exists."""
    os.makedirs(get_rollback_dir(story_id), exist_ok=True)

def create_rollback_point(story_id, scene_id, description="Manual rollback point"):
    """Create a rollback point at a specific scene."""
    ensure_rollback_dir(story_id)
    
    # Verify scene exists
    scene_data = load_scene(story_id, scene_id)
    
    rollback_point = {
        "id": scene_id,
        "timestamp": datetime.utcnow().isoformat(),
        "description": description,
        "scene_data": scene_data,
        "created_at": datetime.utcnow().isoformat()
    }
    
    rollback_path = os.path.join(get_rollback_dir(story_id), f"rollback_{scene_id}.json")
    
    with open(rollback_path, "w", encoding="utf-8") as f:
        json.dump(rollback_point, f, indent=2, ensure_ascii=False)
    
    return rollback_point

def list_rollback_points(story_id):
    """List all available rollback points."""
    rollback_dir = get_rollback_dir(story_id)
    
    if not os.path.exists(rollback_dir):
        return []
    
    rollback_points = []
    for filename in os.listdir(rollback_dir):
        if filename.startswith("rollback_") and filename.endswith(".json"):
            filepath = os.path.join(rollback_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                rollback_points.append(json.load(f))
    
    # Sort by timestamp
    rollback_points.sort(key=lambda x: x["timestamp"])
    return rollback_points

def get_scenes_after(story_id, target_scene_id):
    """Get all scenes that come after a target scene."""
    all_scenes = list_scenes(story_id)
    
    try:
        target_index = all_scenes.index(target_scene_id)
        return all_scenes[target_index + 1:]
    except ValueError:
        raise ValueError(f"Scene {target_scene_id} not found in story {story_id}")

def backup_scenes_for_rollback(story_id, scenes_to_backup):
    """Backup scenes before rollback."""
    if not scenes_to_backup:
        return
    
    ensure_rollback_dir(story_id)
    backup_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(get_rollback_dir(story_id), f"backup_{backup_timestamp}")
    os.makedirs(backup_dir, exist_ok=True)
    
    scene_dir = get_scene_dir(story_id)
    
    for scene_id in scenes_to_backup:
        source_path = os.path.join(scene_dir, f"{scene_id}.json")
        backup_path = os.path.join(backup_dir, f"{scene_id}.json")
        
        if os.path.exists(source_path):
            shutil.copy2(source_path, backup_path)
    
    # Save backup metadata
    backup_metadata = {
        "timestamp": datetime.utcnow().isoformat(),
        "backed_up_scenes": scenes_to_backup,
        "reason": "rollback_preparation"
    }
    
    metadata_path = os.path.join(backup_dir, "backup_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(backup_metadata, f, indent=2)

def rollback_to_scene(story_id, target_scene_id, create_backup=True):
    """Rollback story to a specific scene."""
    # Verify target scene exists
    target_scene = load_scene(story_id, target_scene_id)
    
    # Get scenes that will be removed
    scenes_to_remove = get_scenes_after(story_id, target_scene_id)
    
    if not scenes_to_remove:
        return {
            "success": True,
            "message": "Already at target scene",
            "scenes_removed": 0,
            "target_scene": target_scene_id
        }
    
    # Create backup if requested
    if create_backup:
        backup_scenes_for_rollback(story_id, scenes_to_remove)
    
    # Remove scenes after target
    scene_dir = get_scene_dir(story_id)
    removed_count = 0
    
    for scene_id in scenes_to_remove:
        scene_path = os.path.join(scene_dir, f"{scene_id}.json")
        if os.path.exists(scene_path):
            os.remove(scene_path)
            removed_count += 1
    
    # Restore memory state from target scene
    try:
        restore_memory_from_snapshot(story_id, target_scene_id)
        memory_restored = True
    except (FileNotFoundError, ValueError) as e:
        memory_restored = False
        memory_error = str(e)
    
    result = {
        "success": True,
        "message": f"Rolled back to scene {target_scene_id}",
        "scenes_removed": removed_count,
        "target_scene": target_scene_id,
        "memory_restored": memory_restored
    }
    
    if not memory_restored:
        result["memory_error"] = memory_error
    
    return result

def rollback_to_timestamp(story_id, target_timestamp, create_backup=True):
    """Rollback to the scene closest to a specific timestamp."""
    all_scenes = list_scenes(story_id)
    
    if not all_scenes:
        raise ValueError(f"No scenes found for story {story_id}")
    
    # Find the scene closest to the target timestamp
    target_scene_id = None
    target_time = datetime.fromisoformat(target_timestamp.replace('Z', '+00:00'))
    
    for scene_id in all_scenes:
        scene_data = load_scene(story_id, scene_id)
        scene_time = datetime.fromisoformat(scene_data["timestamp"].replace('Z', '+00:00'))
        
        if scene_time <= target_time:
            target_scene_id = scene_id
        else:
            break
    
    if not target_scene_id:
        raise ValueError(f"No scene found before timestamp {target_timestamp}")
    
    return rollback_to_scene(story_id, target_scene_id, create_backup)

def get_rollback_candidates(story_id, limit=10):
    """Get recent scenes that are good rollback candidates."""
    all_scenes = list_scenes(story_id)
    
    if not all_scenes:
        return []
    
    # Get the last N scenes
    recent_scenes = all_scenes[-limit:]
    candidates = []
    
    for scene_id in recent_scenes:
        scene_data = load_scene(story_id, scene_id)
        candidates.append({
            "scene_id": scene_id,
            "timestamp": scene_data["timestamp"],
            "input_preview": scene_data["input"][:100] + "..." if len(scene_data["input"]) > 100 else scene_data["input"],
            "has_flags": bool(scene_data.get("flags", [])),
            "memory_snapshot": bool(scene_data.get("memory", {}))
        })
    
    return candidates

def validate_rollback_integrity(story_id):
    """Validate that rollback data is consistent."""
    issues = []
    
    # Check scene continuity
    all_scenes = list_scenes(story_id)
    if not all_scenes:
        issues.append("No scenes found")
        return issues
    
    # Check for missing scenes in sequence
    for i, scene_id in enumerate(all_scenes[:-1]):
        current_scene = load_scene(story_id, scene_id)
        next_scene_id = all_scenes[i + 1]
        
        current_time = datetime.fromisoformat(current_scene["timestamp"].replace('Z', '+00:00'))
        next_scene = load_scene(story_id, next_scene_id)
        next_time = datetime.fromisoformat(next_scene["timestamp"].replace('Z', '+00:00'))
        
        if current_time >= next_time:
            issues.append(f"Scene {scene_id} timestamp is not before {next_scene_id}")
    
    # Check rollback points
    rollback_points = list_rollback_points(story_id)
    for rollback_point in rollback_points:
        if rollback_point["id"] not in all_scenes:
            issues.append(f"Rollback point {rollback_point['id']} references non-existent scene")
    
    return issues

def cleanup_old_rollback_data(story_id, days_to_keep=30):
    """Clean up old rollback data and backups."""
    rollback_dir = get_rollback_dir(story_id)
    
    if not os.path.exists(rollback_dir):
        return {"cleaned": 0, "message": "No rollback data to clean"}
    
    cutoff_time = datetime.utcnow().timestamp() - (days_to_keep * 24 * 60 * 60)
    cleaned_count = 0
    
    for item in os.listdir(rollback_dir):
        item_path = os.path.join(rollback_dir, item)
        
        # Check if it's a backup directory
        if os.path.isdir(item_path) and item.startswith("backup_"):
            dir_stat = os.stat(item_path)
            if dir_stat.st_mtime < cutoff_time:
                shutil.rmtree(item_path)
                cleaned_count += 1
        
        # Check if it's a rollback point file
        elif item.startswith("rollback_") and item.endswith(".json"):
            file_stat = os.stat(item_path)
            if file_stat.st_mtime < cutoff_time:
                os.remove(item_path)
                cleaned_count += 1
    
    return {
        "cleaned": cleaned_count,
        "message": f"Cleaned {cleaned_count} old rollback items"
    }
