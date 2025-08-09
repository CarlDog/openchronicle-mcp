#!/usr/bin/env python3
"""
Week 2 Task 2: Centralized Configuration System
Creates a unified configuration management system with typed classes for better maintainability.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import json
import os
import sys
from datetime import datetime

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .logging_system import log_info, log_error, log_warning, log_system_event


@dataclass
class PerformanceConfig:
    """Performance-related configuration settings."""
    max_concurrent_requests: int = 5
    request_timeout_seconds: int = 30
    memory_cache_size_mb: int = 512
    database_connection_pool_size: int = 10
    async_batch_size: int = 100
    enable_request_caching: bool = True
    cache_ttl_seconds: int = 3600


@dataclass
class ModelConfig:
    """Model-related configuration settings."""
    default_text_model: str = "gpt-3.5-turbo"
    default_image_model: str = "dall-e-3"
    model_fallback_enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    context_window_buffer: int = 500
    temperature: float = 0.7
    max_tokens: int = 4000


@dataclass
class DatabaseConfig:
    """Database-related configuration settings."""
    database_path: str = "storage"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    auto_vacuum_enabled: bool = True
    checkpoint_interval_minutes: int = 60
    max_connections: int = 10
    query_timeout_seconds: int = 30


@dataclass
class SecurityConfig:
    """Security-related configuration settings."""
    enable_api_key_rotation: bool = False
    max_request_rate_per_minute: int = 100
    enable_input_sanitization: bool = True
    log_sensitive_data: bool = False
    enable_audit_logging: bool = True
    session_timeout_minutes: int = 30


@dataclass
class LoggingConfig:
    """Logging-related configuration settings."""
    log_level: str = "INFO"
    log_rotation_size_mb: int = 10
    log_backup_count: int = 10
    enable_contextual_logging: bool = True
    enable_model_interaction_logging: bool = True
    log_retention_days: int = 30
    enable_performance_logging: bool = True


@dataclass
class StorageConfig:
    """Storage-related configuration settings."""
    base_storage_path: str = "storage"
    scene_storage_path: str = "storage/scenes"
    character_storage_path: str = "storage/characters"
    memory_storage_path: str = "storage/memory"
    backup_storage_path: str = "storage/backups"
    max_storage_size_gb: int = 10
    enable_compression: bool = True


@dataclass
class SystemConfig:
    """Centralized system configuration."""
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    
    # Metadata
    config_version: str = "2.0"
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    environment: str = "development"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """Create SystemConfig from dictionary."""
        return cls(
            performance=PerformanceConfig(**data.get('performance', {})),
            model=ModelConfig(**data.get('model', {})),
            database=DatabaseConfig(**data.get('database', {})),
            security=SecurityConfig(**data.get('security', {})),
            logging=LoggingConfig(**data.get('logging', {})),
            storage=StorageConfig(**data.get('storage', {})),
            config_version=data.get('config_version', '2.0'),
            last_updated=data.get('last_updated', datetime.now().isoformat()),
            environment=data.get('environment', 'development')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SystemConfig to dictionary."""
        return {
            'performance': self.performance.__dict__,
            'model': self.model.__dict__,
            'database': self.database.__dict__,
            'security': self.security.__dict__,
            'logging': self.logging.__dict__,
            'storage': self.storage.__dict__,
            'config_version': self.config_version,
            'last_updated': self.last_updated,
            'environment': self.environment
        }


class CentralizedConfigManager:
    """Centralized configuration management system."""
    
    def __init__(self, config_path: str = "config/system_config.json"):
        """Initialize the configuration manager."""
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(exist_ok=True)
        
        # Load or create default configuration
        self.config = self._load_or_create_config()
        
        # Auto-create storage directories on startup
        self._ensure_storage_directories()
        
        log_system_event("config_manager_initialized", 
                        "Centralized configuration manager initialized",
                        {"config_path": str(self.config_path)})
    
    def _ensure_storage_directories(self):
        """Ensure all storage directories exist, creating them if necessary."""
        storage_paths = [
            self.config.storage.base_storage_path,
            self.config.storage.scene_storage_path,
            self.config.storage.character_storage_path,
            self.config.storage.memory_storage_path,
            self.config.storage.backup_storage_path
        ]
        
        created_paths = []
        for path_str in storage_paths:
            path = Path(path_str)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    created_paths.append(str(path))
                except Exception as e:
                    log_error(f"Failed to create storage directory {path}: {e}",
                             context_tags=["config", "directory", "error"])
        
        if created_paths:
            log_info(f"Auto-created {len(created_paths)} missing storage directories",
                    context_tags=["config", "auto_create", "startup"])
            for path in created_paths:
                log_info(f"Created directory: {path}",
                        context_tags=["config", "directory"])
        else:
            log_info("All storage directories already exist",
                    context_tags=["config", "validation"])
    
    def _load_or_create_config(self) -> SystemConfig:
        """Load configuration from file or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                config = SystemConfig.from_dict(data)
                log_info("Configuration loaded successfully", 
                        context_tags=["config", "load"])
                return config
                
            except Exception as e:
                log_error(f"Failed to load configuration: {e}", 
                         context_tags=["config", "error"])
                log_warning("Creating default configuration")
                return self._create_default_config()
        else:
            log_info("Creating new configuration file")
            return self._create_default_config()
    
    def _create_default_config(self) -> SystemConfig:
        """Create default configuration."""
        config = SystemConfig()
        self.save_config(config)
        return config
    
    def save_config(self, config: Optional[SystemConfig] = None) -> bool:
        """Save configuration to file."""
        if config is None:
            config = self.config
        
        try:
            # Update last_updated timestamp
            config.last_updated = datetime.now().isoformat()
            
            # Create backup before saving
            self._create_backup()
            
            # Save configuration
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            log_info("Configuration saved successfully", 
                    context_tags=["config", "save"])
            log_system_event("config_saved", 
                           "System configuration saved",
                           {"path": str(self.config_path)})
            return True
            
        except Exception as e:
            log_error(f"Failed to save configuration: {e}", 
                     context_tags=["config", "error"])
            return False
    
    def _create_backup(self) -> bool:
        """Create backup of current configuration."""
        if not self.config_path.exists():
            return True
        
        try:
            backup_dir = self.config_path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"system_config_{timestamp}.json"
            
            # Copy current config to backup
            import shutil
            shutil.copy2(self.config_path, backup_path)
            
            log_info(f"Configuration backup created: {backup_path.name}", 
                    context_tags=["config", "backup"])
            return True
            
        except Exception as e:
            log_warning(f"Failed to create config backup: {e}", 
                       context_tags=["config", "backup", "error"])
            return False
    
    def update_config(self, section: str, **kwargs) -> bool:
        """Update specific configuration section."""
        try:
            config_section = getattr(self.config, section)
            
            for key, value in kwargs.items():
                if hasattr(config_section, key):
                    setattr(config_section, key, value)
                    log_info(f"Updated {section}.{key} = {value}", 
                            context_tags=["config", "update"])
                else:
                    log_warning(f"Unknown config key: {section}.{key}", 
                               context_tags=["config", "warning"])
            
            return self.save_config()
            
        except Exception as e:
            log_error(f"Failed to update config section {section}: {e}", 
                     context_tags=["config", "error"])
            return False
    
    def get_config_value(self, section: str, key: str) -> Any:
        """Get specific configuration value."""
        try:
            config_section = getattr(self.config, section)
            return getattr(config_section, key)
        except AttributeError:
            log_warning(f"Unknown config path: {section}.{key}", 
                       context_tags=["config", "warning"])
            return None
    
    def validate_config(self) -> List[str]:
        """Validate configuration and auto-create missing directories."""
        issues = []
        
        # Auto-create and validate storage paths
        storage_paths = [
            self.config.storage.base_storage_path,
            self.config.storage.scene_storage_path,
            self.config.storage.character_storage_path,
            self.config.storage.memory_storage_path,
            self.config.storage.backup_storage_path
        ]
        
        for path_str in storage_paths:
            path = Path(path_str)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    log_info(f"Auto-created missing storage directory: {path}",
                            context_tags=["config", "auto_create", "directory"])
                except Exception as e:
                    issues.append(f"Failed to create storage path: {path} - {e}")
            
            # Verify path is accessible after creation
            if not path.exists():
                issues.append(f"Storage path still does not exist after creation attempt: {path}")
            elif not os.access(path, os.W_OK):
                issues.append(f"Storage path is not writable: {path}")
        
        # Validate performance settings
        if self.config.performance.max_concurrent_requests < 1:
            issues.append("max_concurrent_requests must be at least 1")
        
        if self.config.performance.request_timeout_seconds < 1:
            issues.append("request_timeout_seconds must be at least 1")
        
        # Validate model settings
        if self.config.model.max_retries < 0:
            issues.append("max_retries cannot be negative")
        
        if not 0.0 <= self.config.model.temperature <= 2.0:
            issues.append("temperature must be between 0.0 and 2.0")
        
        # Log validation completion
        if not issues:
            log_info("Configuration validation passed - all directories exist and are writable",
                    context_tags=["config", "validation", "success"])
        else:
            log_warning(f"Configuration validation found {len(issues)} issues",
                       context_tags=["config", "validation", "issues"])
        
        return issues
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for logging/debugging."""
        return {
            "config_version": self.config.config_version,
            "last_updated": self.config.last_updated,
            "environment": self.config.environment,
            "sections": {
                "performance": list(self.config.performance.__dict__.keys()),
                "model": list(self.config.model.__dict__.keys()),
                "database": list(self.config.database.__dict__.keys()),
                "security": list(self.config.security.__dict__.keys()),
                "logging": list(self.config.logging.__dict__.keys()),
                "storage": list(self.config.storage.__dict__.keys())
            }
        }


# Global configuration manager instance
_config_manager = None

def get_config_manager() -> CentralizedConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = CentralizedConfigManager()
    return _config_manager

def get_config() -> SystemConfig:
    """Get the current system configuration."""
    return get_config_manager().config

# Convenience functions for common config access
def get_performance_config() -> PerformanceConfig:
    """Get performance configuration."""
    return get_config().performance

def get_model_config() -> ModelConfig:
    """Get model configuration."""
    return get_config().model

def get_database_config() -> DatabaseConfig:
    """Get database configuration."""
    return get_config().database

def get_security_config() -> SecurityConfig:
    """Get security configuration."""
    return get_config().security

def get_logging_config() -> LoggingConfig:
    """Get logging configuration."""
    return get_config().logging

def get_storage_config() -> StorageConfig:
    """Get storage configuration."""
    return get_config().storage


if __name__ == "__main__":
    # Test the centralized configuration system
    print("🧪 Testing Centralized Configuration System")
    
    config_manager = get_config_manager()
    
    # Show current configuration
    print("📋 Current Configuration Summary:")
    summary = config_manager.get_config_summary()
    print(json.dumps(summary, indent=2))
    
    # Test configuration updates
    print("\n🔧 Testing Configuration Updates:")
    config_manager.update_config("performance", max_concurrent_requests=10)
    config_manager.update_config("model", temperature=0.8)
    
    # Validate configuration
    print("\n✅ Validating Configuration:")
    issues = config_manager.validate_config()
    if issues:
        print("⚠️ Configuration Issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ Configuration is valid")
    
    # Test convenience functions
    print("\n📖 Testing Convenience Functions:")
    perf_config = get_performance_config()
    print(f"Max concurrent requests: {perf_config.max_concurrent_requests}")
    
    model_config = get_model_config()
    print(f"Default model: {model_config.default_text_model}")
    print(f"Temperature: {model_config.temperature}")
    
    print("\n✅ Centralized configuration system test completed!")
