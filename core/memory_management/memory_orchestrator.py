"""
Memory Orchestrator

The main orchestrator that integrates all memory management components,
providing a unified interface to replace the monolithic memory_manager.py.
Maintains 100% backward compatibility while providing enhanced functionality.
"""
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional, Union
import logging

from .persistence import MemoryRepository, MemorySerializer, SnapshotManager
from .character import CharacterManager, MoodTracker, VoiceManager
from .context import ContextBuilder, WorldStateManager, SceneContextManager
from .shared import MemorySnapshot, CharacterMemory


class MemoryOrchestrator:
    """
    Unified memory management orchestrator.
    
    Provides a single interface for all memory operations while delegating
    to specialized components. Maintains backward compatibility with the
    original memory_manager.py functions.
    """
    
    def __init__(self):
        """Initialize the memory orchestrator with all components."""
        # Core components
        self.repository = MemoryRepository()
        self.serializer = MemorySerializer()
        self.snapshot_manager = SnapshotManager(self.repository)
        
        # Character components
        self.character_manager = CharacterManager(self.repository)
        self.mood_tracker = MoodTracker()
        self.voice_manager = VoiceManager()
        
        # Context components
        self.context_builder = ContextBuilder()
        self.world_manager = WorldStateManager()
        self.scene_manager = SceneContextManager()
        
        # Shared utilities
        # self.db_manager = DatabaseManager()  # Not used, removed to avoid schema conflicts
        
        # Setup logging
        self.logger = logging.getLogger('openchronicle.memory')
    
    # ===== CORE MEMORY OPERATIONS =====
    
    def load_current_memory(self, story_id: str) -> Dict[str, Any]:
        """
        Load current memory state for a story.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory_snapshot = self.repository.load_memory(story_id)
            return memory_snapshot.to_dict()
        except Exception as e:
            self.logger.error(f"Error loading memory for story {story_id}: {e}")
            # Return default structure for backward compatibility
            return self.repository.create_default_memory_structure()
    
    def save_current_memory(self, story_id: str, memory_data: Dict[str, Any]) -> bool:
        """
        Save current memory state for a story.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            # Convert dict to MemorySnapshot if needed
            if isinstance(memory_data, dict):
                memory_snapshot = MemorySnapshot.from_dict(memory_data)
            else:
                memory_snapshot = memory_data
            
            return self.repository.save_memory(story_id, memory_snapshot)
        except Exception as e:
            self.logger.error(f"Error saving memory for story {story_id}: {e}")
            return False
    
    def archive_memory_snapshot(self, story_id: str, scene_id: str, 
                              memory_data: Dict[str, Any]) -> bool:
        """
        Archive a memory snapshot for a specific scene.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            if isinstance(memory_data, dict):
                memory_snapshot = MemorySnapshot.from_dict(memory_data)
            else:
                memory_snapshot = memory_data
            
            return self.snapshot_manager.create_snapshot(
                story_id, scene_id, memory_snapshot
            ) is not None
        except Exception as e:
            self.logger.error(f"Error archiving snapshot for {story_id}/{scene_id}: {e}")
            return False
    
    def restore_memory_from_snapshot(self, story_id: str, scene_id: str) -> Dict[str, Any]:
        """
        Restore memory from a historical snapshot.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory_snapshot = self.snapshot_manager.restore_snapshot(story_id, scene_id)
            if memory_snapshot:
                # Save restored memory as current
                self.repository.save_memory(story_id, memory_snapshot)
                return memory_snapshot.to_dict()
            else:
                raise ValueError(f"No memory snapshot found for scene: {scene_id}")
        except Exception as e:
            self.logger.error(f"Error restoring snapshot {story_id}/{scene_id}: {e}")
            raise
    
    # ===== CHARACTER MEMORY OPERATIONS =====
    
    def update_character_memory(self, story_id: str, character_name: str, 
                              updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update character memory with new information.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            # Use the character manager's update_character method
            result = self.character_manager.update_character(story_id, character_name, updates)
            if result.success:
                # Return current memory state
                return self.load_current_memory(story_id)
            else:
                self.logger.error(f"Character update failed: {result.warnings}")
                return self.load_current_memory(story_id)
        except Exception as e:
            self.logger.error(f"Error updating character {character_name} for {story_id}: {e}")
            return self.load_current_memory(story_id)
    
    def get_character_memory_snapshot(self, story_id: str, character_name: str, 
                                    format_for_prompt: bool = True) -> Dict[str, Any]:
        """
        Get a snapshot of character memory.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            snapshot = self.character_manager.get_character_snapshot(
                memory, character_name
            )
            
            if format_for_prompt and snapshot:
                formatted = self.character_manager.format_character_snapshot_for_prompt(snapshot)
                return {"formatted_snapshot": formatted, "raw_snapshot": snapshot.to_dict()}
            
            return snapshot.to_dict() if snapshot else {}
        except Exception as e:
            self.logger.error(f"Error getting character snapshot {character_name} for {story_id}: {e}")
            return {}
    
    def format_character_snapshot_for_prompt(self, snapshot: Dict[str, Any]) -> str:
        """
        Format character snapshot for prompt inclusion.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            if isinstance(snapshot, dict):
                character = CharacterMemory.from_dict(snapshot)
            else:
                character = snapshot
            
            return self.character_manager.format_character_snapshot_for_prompt(character)
        except Exception as e:
            self.logger.error(f"Error formatting character snapshot: {e}")
            return "[Error formatting character snapshot]"
    
    def get_character_voice_prompt(self, story_id: str, character_name: str) -> str:
        """
        Generate voice prompt for character.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            if character_name in memory.characters:
                character = memory.characters[character_name]
                return self.voice_manager.generate_voice_prompt(character)
            return f"Character: {character_name} (no voice profile available)"
        except Exception as e:
            self.logger.error(f"Error getting voice prompt for {character_name}: {e}")
            return f"Character: {character_name} (error loading voice profile)"
    
    def update_character_mood(self, story_id: str, character_name: str, new_mood: str,
                            reasoning: str = "", intensity: float = 1.0) -> Dict[str, Any]:
        """
        Update character mood with tracking.
        
        Enhanced version with mood analysis capabilities.
        """
        try:
            memory = self.repository.load_memory(story_id)
            
            # Use mood tracker for advanced mood management
            if character_name in memory.characters:
                character = memory.characters[character_name]
                updated_character = self.mood_tracker.update_character_mood(
                    character, new_mood, reasoning, intensity
                )
                memory.characters[character_name] = updated_character
                self.repository.save_memory(story_id, memory)
            
            return memory.to_dict()
        except Exception as e:
            self.logger.error(f"Error updating mood for {character_name}: {e}")
            return self.load_current_memory(story_id)
    
    def get_character_memory(self, story_id: str, character_name: str) -> Dict[str, Any]:
        """
        Get character memory data.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            if character_name in memory.characters:
                return memory.characters[character_name].to_dict()
            return {}
        except Exception as e:
            self.logger.error(f"Error getting character memory for {character_name}: {e}")
            return {}
    
    # ===== WORLD STATE OPERATIONS =====
    
    def update_world_state(self, story_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update world state memory.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.update_world_state(
                memory, updates, source="system", 
                description="World state update via orchestrator"
            )
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except Exception as e:
            self.logger.error(f"Error updating world state for {story_id}: {e}")
            return self.load_current_memory(story_id)
    
    def add_memory_flag(self, story_id: str, flag_name: str, 
                       flag_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Add a memory flag.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.add_memory_flag(memory, flag_name, flag_data or {})
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except Exception as e:
            self.logger.error(f"Error adding memory flag {flag_name} for {story_id}: {e}")
            return self.load_current_memory(story_id)
    
    def remove_memory_flag(self, story_id: str, flag_name: str) -> Dict[str, Any]:
        """
        Remove a memory flag by name.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.remove_memory_flag(memory, flag_name)
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except Exception as e:
            self.logger.error(f"Error removing memory flag {flag_name} for {story_id}: {e}")
            return self.load_current_memory(story_id)
    
    def has_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """
        Check if a memory flag exists.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            return self.world_manager.has_memory_flag(memory, flag_name)
        except Exception as e:
            self.logger.error(f"Error checking memory flag {flag_name} for {story_id}: {e}")
            return False
    
    def add_recent_event(self, story_id: str, event_description: str, 
                        event_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Add a recent event to memory.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.add_world_event(
                memory, event_description, event_data=event_data or {}
            )
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except Exception as e:
            self.logger.error(f"Error adding recent event for {story_id}: {e}")
            return self.load_current_memory(story_id)
    
    # ===== CONTEXT AND PROMPT OPERATIONS =====
    
    def get_memory_context_for_prompt(self, story_id: str, 
                                    primary_characters: List[str] = None,
                                    include_full_context: bool = True) -> str:
        """
        Get formatted memory context for LLM prompt injection.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            
            if include_full_context:
                return self.context_builder.build_comprehensive_context(
                    memory, primary_characters
                )
            else:
                return self.context_builder.build_minimal_context(memory)
        except Exception as e:
            self.logger.error(f"Error getting memory context for {story_id}: {e}")
            return "=== MEMORY CONTEXT ===\n[Error loading memory context]"
    
    def get_memory_summary(self, story_id: str) -> str:
        """
        Get a summary of current memory state.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            
            summary_parts = []
            summary_parts.append(f"=== MEMORY SUMMARY FOR {story_id} ===")
            
            # Character count
            char_count = len(memory.characters)
            summary_parts.append(f"Characters: {char_count}")
            
            # World state items
            world_items = len(memory.world_state)
            summary_parts.append(f"World State Items: {world_items}")
            
            # Recent events
            event_count = len(memory.recent_events)
            summary_parts.append(f"Recent Events: {event_count}")
            
            # Active flags
            flag_count = len(memory.flags)
            summary_parts.append(f"Active Flags: {flag_count}")
            
            return "\n".join(summary_parts)
        except Exception as e:
            self.logger.error(f"Error getting memory summary for {story_id}: {e}")
            return f"=== MEMORY SUMMARY FOR {story_id} ===\n[Error loading memory]"
    
    def refresh_memory_after_rollback(self, story_id: str, target_scene_id: str) -> Dict[str, Any]:
        """
        Refresh memory state after rollback operation.
        
        Maintains backward compatibility with original function signature.
        """
        try:
            # Restore from snapshot and make it current
            restored_memory = self.restore_memory_from_snapshot(story_id, target_scene_id)
            
            # Log the rollback event
            self.add_recent_event(
                story_id, 
                f"Story rolled back to scene {target_scene_id}",
                {"rollback_target": target_scene_id, "timestamp": datetime.now(UTC).isoformat()}
            )
            
            return restored_memory
        except Exception as e:
            self.logger.error(f"Error refreshing memory after rollback for {story_id}: {e}")
            return self.load_current_memory(story_id)
    
    # ===== ENHANCED OPERATIONS (NEW CAPABILITIES) =====
    
    def analyze_memory_health(self, story_id: str) -> Dict[str, Any]:
        """
        Analyze memory health and provide recommendations.
        
        NEW: Enhanced capability not in original memory_manager.py
        """
        try:
            memory = self.repository.load_memory(story_id)
            
            analysis = {
                "world_state_analysis": self.world_manager.analyze_world_state(memory),
                "character_count": len(memory.characters),
                "event_count": len(memory.recent_events),
                "flag_count": len(memory.flags),
                "recommendations": []
            }
            
            # Generate recommendations
            if analysis["character_count"] == 0:
                analysis["recommendations"].append("Consider adding character data")
            
            if analysis["event_count"] < 3:
                analysis["recommendations"].append("Consider adding more recent events for context")
            
            world_analysis = analysis["world_state_analysis"]
            if world_analysis.completeness_score < 0.5:
                analysis["recommendations"].append("World state appears incomplete")
            
            return analysis
        except Exception as e:
            self.logger.error(f"Error analyzing memory health for {story_id}: {e}")
            return {"error": str(e), "recommendations": ["Manual review recommended"]}
    
    def create_scene_context(self, story_id: str, scene_id: str, location: str,
                           active_characters: List[str], 
                           scene_type: str = "dialogue") -> Dict[str, Any]:
        """
        Create comprehensive scene context.
        
        NEW: Enhanced capability for scene management.
        """
        try:
            memory = self.repository.load_memory(story_id)
            scene_context = self.scene_manager.create_scene_context(
                memory, scene_id, location, active_characters, scene_type
            )
            return {
                "scene_context": scene_context.__dict__,
                "scene_prompt": self.scene_manager.generate_scene_prompt(scene_context, memory)
            }
        except Exception as e:
            self.logger.error(f"Error creating scene context for {story_id}: {e}")
            return {"error": str(e)}
    
    def get_component_status(self) -> Dict[str, str]:
        """
        Get status of all memory management components.
        
        NEW: Diagnostic capability for system health.
        """
        return {
            "repository": "active" if self.repository else "inactive",
            "serializer": "active" if self.serializer else "inactive", 
            "snapshot_manager": "active" if self.snapshot_manager else "inactive",
            "character_manager": "active" if self.character_manager else "inactive",
            "mood_tracker": "active" if self.mood_tracker else "inactive",
            "voice_manager": "active" if self.voice_manager else "inactive",
            "context_builder": "active" if self.context_builder else "inactive",
            "world_manager": "active" if self.world_manager else "inactive",
            "scene_manager": "active" if self.scene_manager else "inactive"
        }


# Global instance for backward compatibility
_orchestrator_instance = None


def get_memory_orchestrator() -> MemoryOrchestrator:
    """Get the global memory orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = MemoryOrchestrator()
    return _orchestrator_instance


# ===== BACKWARD COMPATIBILITY FUNCTIONS =====
# These functions maintain the exact same interface as the original memory_manager.py

def load_current_memory(story_id: str) -> Dict[str, Any]:
    """Load current memory state for a story."""
    return get_memory_orchestrator().load_current_memory(story_id)


def save_current_memory(story_id: str, memory_data: Dict[str, Any]) -> bool:
    """Save current memory state for a story."""
    return get_memory_orchestrator().save_current_memory(story_id, memory_data)


def archive_memory_snapshot(story_id: str, scene_id: str, memory_data: Dict[str, Any]) -> bool:
    """Archive a memory snapshot for a specific scene."""
    return get_memory_orchestrator().archive_memory_snapshot(story_id, scene_id, memory_data)


def update_character_memory(story_id: str, character_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update character memory with new information."""
    return get_memory_orchestrator().update_character_memory(story_id, character_name, updates)


def get_character_memory_snapshot(story_id: str, character_name: str, format_for_prompt: bool = True) -> Dict[str, Any]:
    """Get a snapshot of character memory."""
    return get_memory_orchestrator().get_character_memory_snapshot(story_id, character_name, format_for_prompt)


def format_character_snapshot_for_prompt(snapshot: Dict[str, Any]) -> str:
    """Format character snapshot for prompt inclusion."""
    return get_memory_orchestrator().format_character_snapshot_for_prompt(snapshot)


def refresh_memory_after_rollback(story_id: str, target_scene_id: str) -> Dict[str, Any]:
    """Refresh memory state after rollback operation."""
    return get_memory_orchestrator().refresh_memory_after_rollback(story_id, target_scene_id)


def get_character_voice_prompt(story_id: str, character_name: str) -> str:
    """Generate voice prompt for character."""
    return get_memory_orchestrator().get_character_voice_prompt(story_id, character_name)


def update_character_mood(story_id: str, character_name: str, new_mood: str, 
                         reasoning: str = "", intensity: float = 1.0) -> Dict[str, Any]:
    """Update character mood with tracking."""
    return get_memory_orchestrator().update_character_mood(story_id, character_name, new_mood, reasoning, intensity)


def update_world_state(story_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update world state memory."""
    return get_memory_orchestrator().update_world_state(story_id, updates)


def add_memory_flag(story_id: str, flag_name: str, flag_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Add a memory flag."""
    return get_memory_orchestrator().add_memory_flag(story_id, flag_name, flag_data)


def remove_memory_flag(story_id: str, flag_name: str) -> Dict[str, Any]:
    """Remove a memory flag by name."""
    return get_memory_orchestrator().remove_memory_flag(story_id, flag_name)


def has_memory_flag(story_id: str, flag_name: str) -> bool:
    """Check if a memory flag exists."""
    return get_memory_orchestrator().has_memory_flag(story_id, flag_name)


def add_recent_event(story_id: str, event_description: str, event_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Add a recent event to memory."""
    return get_memory_orchestrator().add_recent_event(story_id, event_description, event_data)


def get_character_memory(story_id: str, character_name: str) -> Dict[str, Any]:
    """Get character memory data."""
    return get_memory_orchestrator().get_character_memory(story_id, character_name)


def get_memory_summary(story_id: str) -> str:
    """Get a summary of current memory state."""
    return get_memory_orchestrator().get_memory_summary(story_id)


def get_memory_context_for_prompt(story_id: str, primary_characters: List[str] = None, 
                                 include_full_context: bool = True) -> str:
    """Get formatted memory context for LLM prompt injection."""
    return get_memory_orchestrator().get_memory_context_for_prompt(story_id, primary_characters, include_full_context)


def restore_memory_from_snapshot(story_id: str, scene_id: str) -> Dict[str, Any]:
    """Restore memory from a historical snapshot."""
    return get_memory_orchestrator().restore_memory_from_snapshot(story_id, scene_id)
