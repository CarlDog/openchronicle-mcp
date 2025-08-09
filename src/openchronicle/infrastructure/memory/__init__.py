"""
Infrastructure layer memory management for OpenChronicle.

This module provides concrete implementations for managing story memory,
character states, and narrative context across sessions.
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
from dataclasses import asdict

from ...domain import MemoryState, Character
from ...application.orchestrators import MemoryManager


class FileSystemMemoryManager(MemoryManager):
    """File-based memory manager implementation."""
    
    def __init__(self, storage_path: str = "storage/memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, MemoryState] = {}
    
    async def get_current_state(self, story_id: str) -> MemoryState:
        """Get current memory state for a story."""
        # Check cache first
        if story_id in self._memory_cache:
            return self._memory_cache[story_id]
        
        # Load from file
        memory_file = self.storage_path / f"{story_id}_memory.json"
        
        if not memory_file.exists():
            # Create new memory state
            memory_state = MemoryState(
                story_id=story_id,
                timestamp=datetime.now(),
                character_memories={},
                world_state={},
                active_flags={},
                recent_events=[]
            )
            await self._save_memory_state(story_id, memory_state)
            return memory_state
        
        try:
            async with aiofiles.open(memory_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                memory_data = json.loads(content)
            
            memory_state = MemoryState(
                story_id=memory_data["story_id"],
                timestamp=datetime.fromisoformat(memory_data["last_updated"]),
                character_memories=memory_data.get("character_memories", {}),
                world_state=memory_data.get("world_state", {}),
                active_flags=memory_data.get("flags", {}),
                recent_events=memory_data.get("recent_events", [])
            )
            
            # Cache the loaded state
            self._memory_cache[story_id] = memory_state
            return memory_state
            
        except Exception as e:
            print(f"Error loading memory for story {story_id}: {e}")
            # Return empty memory state on error
            return MemoryState(
                story_id=story_id,
                timestamp=datetime.now(),
                character_memories={},
                world_state={},
                active_flags={},
                recent_events=[]
            )
    
    async def update_memory(self, story_id: str, updates: Dict[str, Any]) -> bool:
        """Update memory state with new information."""
        try:
            current_state = await self.get_current_state(story_id)
            
            # Create mutable copies for updates
            character_memories = current_state.character_memories.copy()
            world_state = current_state.world_state.copy()
            recent_events = current_state.recent_events.copy()
            active_flags = current_state.active_flags.copy()
            
            # Apply character updates
            if "characters" in updates:
                for char_id, char_updates in updates["characters"].items():
                    if char_id not in character_memories:
                        character_memories[char_id] = {}
                    character_memories[char_id].update(char_updates)
            
            # Apply world state updates
            if "world_state" in updates:
                world_state.update(updates["world_state"])
            
            # Add new events
            if "events" in updates:
                new_events = updates["events"]
                if isinstance(new_events, list):
                    recent_events.extend(new_events)
                else:
                    recent_events.append(new_events)
                
                # Keep only recent events (last 50)
                if len(recent_events) > 50:
                    recent_events = recent_events[-50:]
            
            # Update flags
            if "add_flags" in updates:
                active_flags.update(updates["add_flags"])
            
            if "remove_flags" in updates:
                for flag_name in updates["remove_flags"]:
                    active_flags.pop(flag_name, None)
            
            # Create new memory state
            updated_state = MemoryState(
                story_id=story_id,
                timestamp=datetime.now(),
                character_memories=character_memories,
                world_state=world_state,
                active_flags=active_flags,
                recent_events=recent_events,
                version=current_state.version + 1,
                checksum=current_state.checksum
            )
            
            # Save updated state
            await self._save_memory_state(story_id, updated_state)
            
            # Update cache
            self._memory_cache[story_id] = updated_state
            
            return True
            
        except Exception as e:
            print(f"Error updating memory for story {story_id}: {e}")
            return False
    
    async def _save_memory_state(self, story_id: str, memory_state: MemoryState):
        """Save memory state to file."""
        memory_file = self.storage_path / f"{story_id}_memory.json"
        
        memory_data = {
            "story_id": memory_state.story_id,
            "character_memories": memory_state.character_memories,
            "world_state": memory_state.world_state,
            "recent_events": memory_state.recent_events,
            "flags": memory_state.active_flags,
            "last_updated": memory_state.timestamp.isoformat()
        }
        
        async with aiofiles.open(memory_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(memory_data, indent=2, ensure_ascii=False))
    
    async def search_memory(
        self, 
        story_id: str, 
        search_term: str, 
        search_scope: List[str] = None
    ) -> Dict[str, List[Any]]:
        """Search memory content for a term."""
        if search_scope is None:
            search_scope = ["characters", "events", "world_state"]
        
        memory_state = await self.get_current_state(story_id)
        results = {}
        
        search_term_lower = search_term.lower()
        
        # Search character memories
        if "characters" in search_scope:
            char_results = []
            for char_id, char_memory in memory_state.character_memories.items():
                char_str = json.dumps(char_memory, default=str).lower()
                if search_term_lower in char_str:
                    char_results.append({
                        "character_id": char_id,
                        "memory": char_memory
                    })
            results["characters"] = char_results
        
        # Search events
        if "events" in search_scope:
            event_results = []
            for i, event in enumerate(memory_state.recent_events):
                event_str = json.dumps(event, default=str).lower()
                if search_term_lower in event_str:
                    event_results.append({
                        "index": i,
                        "event": event
                    })
            results["events"] = event_results
        
        # Search world state
        if "world_state" in search_scope:
            world_results = []
            world_str = json.dumps(memory_state.world_state, default=str).lower()
            if search_term_lower in world_str:
                for key, value in memory_state.world_state.items():
                    value_str = json.dumps(value, default=str).lower()
                    if search_term_lower in value_str:
                        world_results.append({
                            "key": key,
                            "value": value
                        })
            results["world_state"] = world_results
        
        return results
    
    async def get_character_memory_profile(self, story_id: str, character_id: str) -> Dict[str, Any]:
        """Get detailed memory profile for a specific character."""
        memory_state = await self.get_current_state(story_id)
        
        if character_id not in memory_state.character_memories:
            return {}
        
        char_memory = memory_state.character_memories[character_id]
        
        # Enhanced profile with analysis
        profile = {
            "basic_info": char_memory.copy(),
            "interaction_count": 0,
            "recent_interactions": [],
            "emotional_progression": [],
            "relationship_changes": []
        }
        
        # Analyze recent events for character involvement
        for event in memory_state.recent_events:
            if isinstance(event, dict):
                # Check if character was involved
                participants = event.get("participants", [])
                if character_id in participants:
                    profile["interaction_count"] += 1
                    profile["recent_interactions"].append(event)
                
                # Track emotional state changes
                if "emotional_state" in event and character_id in event.get("character_updates", {}):
                    profile["emotional_progression"].append({
                        "timestamp": event.get("timestamp"),
                        "state": event["emotional_state"]
                    })
        
        return profile
    
    async def cleanup_old_memories(self, days_to_keep: int = 30):
        """Clean up old memory files."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for memory_file in self.storage_path.glob("*_memory.json"):
            try:
                if memory_file.stat().st_mtime < cutoff_date.timestamp():
                    memory_file.unlink()
                    # Remove from cache if present
                    story_id = memory_file.stem.replace("_memory", "")
                    self._memory_cache.pop(story_id, None)
            except Exception as e:
                print(f"Error cleaning up memory file {memory_file}: {e}")


class InMemoryManager(MemoryManager):
    """In-memory implementation for testing and development."""
    
    def __init__(self):
        self._memory_states: Dict[str, MemoryState] = {}
    
    async def get_current_state(self, story_id: str) -> MemoryState:
        """Get current memory state for a story."""
        if story_id not in self._memory_states:
            self._memory_states[story_id] = MemoryState(
                story_id=story_id,
                character_memories={},
                world_state={},
                recent_events=[],
                flags={},
                last_updated=datetime.now()
            )
        
        return self._memory_states[story_id]
    
    async def update_memory(self, story_id: str, updates: Dict[str, Any]) -> bool:
        """Update memory state with new information."""
        try:
            current_state = await self.get_current_state(story_id)
            
            # Apply updates (same logic as FileSystemMemoryManager)
            if "characters" in updates:
                for char_id, char_updates in updates["characters"].items():
                    if char_id not in current_state.character_memories:
                        current_state.character_memories[char_id] = {}
                    current_state.character_memories[char_id].update(char_updates)
            
            if "world_state" in updates:
                current_state.world_state.update(updates["world_state"])
            
            if "events" in updates:
                new_events = updates["events"]
                if isinstance(new_events, list):
                    current_state.recent_events.extend(new_events)
                else:
                    current_state.recent_events.append(new_events)
                
                if len(current_state.recent_events) > 50:
                    current_state.recent_events = current_state.recent_events[-50:]
            
            if "add_flags" in updates:
                current_state.flags.update(updates["add_flags"])
            
            if "remove_flags" in updates:
                for flag_name in updates["remove_flags"]:
                    current_state.flags.pop(flag_name, None)
            
            current_state.last_updated = datetime.now()
            return True
            
        except Exception as e:
            print(f"Error updating memory for story {story_id}: {e}")
            return False


# Export memory manager implementations
__all__ = [
    "FileSystemMemoryManager",
    "InMemoryManager"
]
