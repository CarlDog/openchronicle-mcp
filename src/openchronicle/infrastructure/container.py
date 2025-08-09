"""
Infrastructure Container - Dependency Injection Container

This container provides all infrastructure dependencies including:
- Domain services (Story, Character, Scene, Memory)  
- Infrastructure services (Logging, Cache)
- Repository implementations
- Adapter implementations

This is a compatibility layer that bridges to the legacy systems
during the migration process.
"""

from typing import Optional
import sys
from pathlib import Path

from .config import InfrastructureConfig
from openchronicle.domain.services import (
    StoryService, CharacterService, SceneService, MemoryService
)


class InfrastructureContainer:
    """Dependency injection container for infrastructure layer."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
        self._story_service: Optional[StoryService] = None
        self._character_service: Optional[CharacterService] = None
        self._scene_service: Optional[SceneService] = None
        self._memory_service: Optional[MemoryService] = None
        self._logging_service: Optional['LoggingService'] = None
        self._cache_service: Optional['CacheService'] = None
    
    def story_service(self) -> StoryService:
        """Get story service instance."""
        if self._story_service is None:
            self._story_service = LegacyStoryService(self.config)
        return self._story_service
    
    def character_service(self) -> CharacterService:
        """Get character service instance."""
        if self._character_service is None:
            self._character_service = LegacyCharacterService(self.config)
        return self._character_service
    
    def scene_service(self) -> SceneService:
        """Get scene service instance."""
        if self._scene_service is None:
            self._scene_service = LegacySceneService(self.config)
        return self._scene_service
    
    def memory_service(self) -> MemoryService:
        """Get memory service instance."""
        if self._memory_service is None:
            self._memory_service = LegacyMemoryService(self.config)
        return self._memory_service
    
    def logging_service(self) -> 'LoggingService':
        """Get logging service instance."""
        if self._logging_service is None:
            self._logging_service = LegacyLoggingService(self.config)
        return self._logging_service
    
    def cache_service(self) -> 'CacheService':
        """Get cache service instance.""" 
        if self._cache_service is None:
            self._cache_service = LegacyCacheService(self.config)
        return self._cache_service


# Legacy compatibility services - these bridge to the existing system
# during migration

class LegacyStoryService(StoryService):
    """Legacy compatibility story service."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
    
    async def get_story(self, story_id: str):
        """Get story by ID using legacy system."""
        try:
            # Add legacy path
            sys.path.append(str(Path(__file__).parent.parent.parent.parent))
            from core.story_loader import load_storypack
            
            story_data = load_storypack(story_id)
            
            # Convert to our domain entity
            from openchronicle.domain.entities import Story
            return Story(
                id=story_data["id"],
                title=story_data["meta"]["title"],
                description=story_data["meta"].get("description", ""),
                world_state=story_data.get("world_state", {})
            )
            
        except Exception as e:
            print(f"Error loading story {story_id}: {e}")
            return None
    
    async def save_story(self, story) -> bool:
        """Save story (not implemented in legacy compatibility)."""
        return False


class LegacyCharacterService(CharacterService):
    """Legacy compatibility character service."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
    
    async def get_character(self, story_id: str, character_id: str):
        """Get character (not implemented in legacy compatibility)."""
        return None
    
    async def save_character(self, story_id: str, character) -> bool:
        """Save character (not implemented in legacy compatibility)."""
        return False


class LegacySceneService(SceneService):
    """Legacy compatibility scene service."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
    
    async def get_scene(self, story_id: str, scene_id: str):
        """Get scene (not implemented in legacy compatibility)."""
        return None
    
    async def save_scene(self, story_id: str, scene) -> bool:
        """Save scene (not implemented in legacy compatibility)."""
        return False


class LegacyMemoryService(MemoryService):
    """Legacy compatibility memory service."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
    
    async def get_memory_summary(self, story_id: str):
        """Get memory summary using legacy system."""
        try:
            # Add legacy path
            sys.path.append(str(Path(__file__).parent.parent.parent.parent))
            from core.memory import MemoryOrchestrator
            
            memory_orchestrator = MemoryOrchestrator()
            return memory_orchestrator.get_memory_summary(story_id)  # Remove await, it's not async
            
        except Exception as e:
            print(f"Error getting memory summary for {story_id}: {e}")
            return {"character_count": 0, "world_state_keys": [], "active_flags": [], 
                   "recent_events_count": 0, "last_updated": "Unknown"}
    
    async def add_recent_event(self, story_id: str, description: str, importance: float = 1.0):
        """Add recent event using legacy system."""
        try:
            # For now, just log the event - will implement properly later
            print(f"Adding recent event to {story_id}: {description}")
            return True
            
        except Exception as e:
            print(f"Error adding recent event: {e}")
            return None
    
    async def add_memory_flag(self, story_id: str, flag_name: str, description: str, flag_type: str = "general"):
        """Add memory flag using legacy system."""
        try:
            # For now, just log the flag - will implement properly later
            print(f"Adding memory flag to {story_id}: {flag_name} = {description}")
            return True
            
        except Exception as e:
            print(f"Error adding memory flag: {e}")
            return None


class LegacyLoggingService:
    """Legacy compatibility logging service."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
    
    async def log_info(self, message: str):
        """Log info message."""
        try:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
            from core.shared.logging_system import log_info
            log_info(message)
        except Exception:
            print(f"INFO: {message}")
    
    async def log_error(self, message: str):
        """Log error message."""
        try:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
            from core.shared.logging_system import log_error
            log_error(message)
        except Exception:
            print(f"ERROR: {message}")
    
    async def log_warning(self, message: str):
        """Log warning message."""
        try:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
            from core.shared.logging_system import log_warning
            log_warning(message)
        except Exception:
            print(f"WARNING: {message}")


class LegacyCacheService:
    """Legacy compatibility cache service."""
    
    def __init__(self, config: InfrastructureConfig):
        self.config = config
    
    async def get(self, key: str):
        """Get cached value."""
        return None  # No caching in legacy compatibility mode
    
    async def set(self, key: str, value, ttl: Optional[int] = None):
        """Set cached value."""
        pass  # No caching in legacy compatibility mode
