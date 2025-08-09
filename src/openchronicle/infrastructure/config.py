"""
Infrastructure Configuration

Configuration settings for the infrastructure layer.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class InfrastructureConfig:
    """Configuration for infrastructure layer."""
    
    # Database settings
    database_path: str = "storage/openchronicle.db"
    enable_database_health_checks: bool = True
    
    # Cache settings
    cache_type: str = "memory"  # memory, redis, file
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    
    # Memory management
    memory_persistence_path: str = "storage/memory"
    memory_auto_cleanup: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file_path: Optional[str] = "logs/openchronicle.log"
    
    # Model configuration
    default_model_adapter: str = "openai"
    model_config_path: str = "config/model_registry.json"
    
    # File storage
    stories_path: str = "import"
    scenes_path: str = "demo_storage/scenes"
    characters_path: str = "demo_storage/characters"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "database_path": self.database_path,
            "enable_database_health_checks": self.enable_database_health_checks,
            "cache_type": self.cache_type,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "cache_max_size": self.cache_max_size,
            "memory_persistence_path": self.memory_persistence_path,
            "memory_auto_cleanup": self.memory_auto_cleanup,
            "log_level": self.log_level,
            "log_file_path": self.log_file_path,
            "default_model_adapter": self.default_model_adapter,
            "model_config_path": self.model_config_path,
            "stories_path": self.stories_path,
            "scenes_path": self.scenes_path,
            "characters_path": self.characters_path
        }
