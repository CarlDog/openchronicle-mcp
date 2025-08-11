"""
Enhanced OpenChronicle Configuration System

Upgrade of the existing centralized configuration to use Pydantic Settings
for improved validation, type safety, and environment variable support.
This replaces the dataclass-based approach with a more robust solution.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, field_validator, ConfigDict
    from pydantic_settings import BaseSettings
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Fallback to basic implementation if pydantic not available
    PYDANTIC_AVAILABLE = False
    from dataclasses import dataclass, field


class LogLevel(str, Enum):
    """Valid log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OutputFormat(str, Enum):
    """Valid CLI output formats."""
    RICH = "rich"
    JSON = "json"
    PLAIN = "plain"
    TABLE = "table"


class Environment(str, Enum):
    """Application environments."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


if PYDANTIC_AVAILABLE:
    # Enhanced Pydantic-based configuration classes
    
    class PerformanceSettings(BaseSettings):
        """Performance-related configuration with validation."""
        max_concurrent_requests: int = Field(15, ge=1, le=100, description="Maximum concurrent requests")
        request_timeout_seconds: int = Field(30, ge=5, le=300, description="Request timeout in seconds")
        memory_cache_size_mb: int = Field(1024, ge=100, le=8192, description="Memory cache size in MB")
        database_connection_pool_size: int = Field(10, ge=1, le=50, description="Database connection pool size")
        async_batch_size: int = Field(100, ge=10, le=1000, description="Async batch processing size")
        enable_request_caching: bool = Field(True, description="Enable request caching")
        cache_ttl_seconds: int = Field(3600, ge=60, le=86400, description="Cache TTL in seconds")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_PERF_",
            validate_assignment=True
        )

    class ModelSettings(BaseSettings):
        """Model-related configuration with validation."""
        default_text_model: str = Field("gpt-3.5-turbo", description="Default text generation model")
        default_image_model: str = Field("dall-e-3", description="Default image generation model")
        model_fallback_enabled: bool = Field(True, description="Enable model fallback")
        max_retries: int = Field(5, ge=1, le=10, description="Maximum retry attempts")
        retry_delay_seconds: float = Field(1.0, ge=0.1, le=10.0, description="Retry delay in seconds")
        context_window_buffer: int = Field(500, ge=100, le=2000, description="Context window buffer size")
        temperature: float = Field(0.9, ge=0.0, le=2.0, description="Model temperature")
        max_tokens: int = Field(4000, ge=100, le=32000, description="Maximum tokens per request")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_MODEL_",
            validate_assignment=True
        )

    class DatabaseSettings(BaseSettings):
        """Database configuration with validation."""
        database_path: str = Field("storage", description="Database storage path")
        backup_enabled: bool = Field(True, description="Enable automatic backups")
        backup_interval_hours: int = Field(24, ge=1, le=168, description="Backup interval in hours")
        auto_vacuum_enabled: bool = Field(True, description="Enable automatic database vacuum")
        checkpoint_interval_minutes: int = Field(60, ge=5, le=1440, description="Checkpoint interval in minutes")
        max_connections: int = Field(10, ge=1, le=100, description="Maximum database connections")
        query_timeout_seconds: int = Field(30, ge=5, le=300, description="Query timeout in seconds")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_DB_",
            validate_assignment=True
        )

    class SecuritySettings(BaseSettings):
        """Security configuration with validation."""
        enable_api_key_rotation: bool = Field(False, description="Enable API key rotation")
        max_request_rate_per_minute: int = Field(100, ge=10, le=1000, description="Maximum requests per minute")
        enable_input_sanitization: bool = Field(True, description="Enable input sanitization")
        log_sensitive_data: bool = Field(False, description="Log sensitive data (not recommended)")
        enable_audit_logging: bool = Field(True, description="Enable audit logging")
        session_timeout_minutes: int = Field(30, ge=5, le=480, description="Session timeout in minutes")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_SEC_",
            validate_assignment=True
        )

    class LoggingSettings(BaseSettings):
        """Logging configuration with validation."""
        log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")
        log_rotation_size_mb: int = Field(10, ge=1, le=100, description="Log rotation size in MB")
        log_backup_count: int = Field(10, ge=1, le=50, description="Number of log backups to keep")
        enable_contextual_logging: bool = Field(True, description="Enable contextual logging")
        enable_model_interaction_logging: bool = Field(True, description="Log model interactions")
        log_retention_days: int = Field(30, ge=1, le=365, description="Log retention period in days")
        enable_performance_logging: bool = Field(True, description="Enable performance logging")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_LOG_",
            validate_assignment=True
        )

    class StorageSettings(BaseSettings):
        """Storage configuration with validation."""
        base_storage_path: str = Field("storage", description="Base storage directory")
        scene_storage_path: str = Field("storage/scenes", description="Scene storage directory")
        character_storage_path: str = Field("storage/characters", description="Character storage directory")
        memory_storage_path: str = Field("storage/memory", description="Memory storage directory")
        backup_storage_path: str = Field("storage/backups", description="Backup storage directory")
        max_storage_size_gb: int = Field(10, ge=1, le=1000, description="Maximum storage size in GB")
        enable_compression: bool = Field(True, description="Enable storage compression")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_STORAGE_",
            validate_assignment=True
        )

        @field_validator('scene_storage_path', 'character_storage_path', 'memory_storage_path', 'backup_storage_path')
        @classmethod
        def validate_storage_paths(cls, v, info):
            """Ensure storage paths are relative to base path."""
            # Get base_path from the same instance
            if hasattr(info, 'data') and 'base_storage_path' in info.data:
                base_path = info.data['base_storage_path']
            else:
                base_path = 'storage'
            
            if not v.startswith(base_path):
                return f"{base_path}/{v.lstrip('/')}"
            return v

    class CLISettings(BaseSettings):
        """CLI-specific configuration with validation."""
        output_format: OutputFormat = Field(OutputFormat.RICH, description="CLI output format")
        quiet_mode: bool = Field(False, description="Enable quiet mode")
        auto_confirm: bool = Field(False, description="Auto-confirm prompts")
        color_output: bool = Field(True, description="Enable colored output")
        max_table_rows: int = Field(50, ge=10, le=1000, description="Maximum table rows to display")
        progress_bars: bool = Field(True, description="Show progress bars")
        editor: str = Field(
            default_factory=lambda: os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano"),
            description="Default text editor"
        )
        pager: str = Field(
            default_factory=lambda: os.environ.get("PAGER", "more" if os.name == "nt" else "less"),
            description="Default pager"
        )

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_CLI_",
            validate_assignment=True
        )

    class UserPreferences(BaseSettings):
        """User preferences with validation."""
        default_story: Optional[str] = Field(None, description="Default story to load")
        favorite_models: List[str] = Field(default_factory=list, description="List of favorite models")
        recent_files: List[str] = Field(default_factory=list, description="Recently accessed files")
        workspace_paths: List[str] = Field(default_factory=list, description="Workspace directory paths")
        aliases: Dict[str, str] = Field(default_factory=dict, description="Command aliases")

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_USER_",
            validate_assignment=True
        )

    class EnhancedOpenChronicleConfig(BaseSettings):
        """
        Enhanced OpenChronicle configuration with Pydantic validation.
        
        Provides:
        - Type validation and coercion
        - Environment variable support
        - Nested configuration sections
        - Validation rules
        - Documentation for all fields
        """
        
        # Core settings
        config_version: str = Field("3.0", description="Configuration version")
        environment: Environment = Field(Environment.DEVELOPMENT, description="Application environment")
        
        # Component configurations
        performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
        model: ModelSettings = Field(default_factory=ModelSettings)
        database: DatabaseSettings = Field(default_factory=DatabaseSettings)
        security: SecuritySettings = Field(default_factory=SecuritySettings)
        logging: LoggingSettings = Field(default_factory=LoggingSettings)
        storage: StorageSettings = Field(default_factory=StorageSettings)
        cli: CLISettings = Field(default_factory=CLISettings)
        user: UserPreferences = Field(default_factory=UserPreferences)

        model_config = ConfigDict(
            env_prefix="OPENCHRONICLE_",
            case_sensitive=False,
            validate_assignment=True,
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"  # Allow extra fields for backward compatibility
        )

        @field_validator('config_version')
        @classmethod
        def validate_config_version(cls, v):
            """Ensure config version is valid."""
            valid_versions = ["2.0", "3.0"]
            if v not in valid_versions:
                raise ValueError(f"Config version must be one of: {valid_versions}")
            return v

        def create_storage_directories(self) -> List[str]:
            """
            Create all configured storage directories.
            
            Returns:
                List of created directory paths
            """
            storage_paths = [
                self.storage.base_storage_path,
                self.storage.scene_storage_path,
                self.storage.character_storage_path,
                self.storage.memory_storage_path,
                self.storage.backup_storage_path,
            ]
            
            created_paths = []
            for path_str in storage_paths:
                path = Path(path_str)
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    created_paths.append(str(path))
            
            return created_paths

        def get_storage_path(self, storage_type: str) -> Path:
            """
            Get a fully resolved storage path.
            
            Args:
                storage_type: Type of storage (base, scene, character, memory, backup)
                
            Returns:
                Resolved Path object
            """
            storage_map = {
                "base": self.storage.base_storage_path,
                "scene": self.storage.scene_storage_path,
                "character": self.storage.character_storage_path,
                "memory": self.storage.memory_storage_path,
                "backup": self.storage.backup_storage_path,
            }
            
            if storage_type not in storage_map:
                raise ValueError(f"Unknown storage type: {storage_type}. Valid types: {list(storage_map.keys())}")
                
            return Path(storage_map[storage_type]).resolve()

        def to_legacy_dict(self) -> Dict[str, Any]:
            """Convert to legacy configuration format for backward compatibility."""
            return {
                "performance": self.performance.dict(),
                "model": self.model.dict(),
                "database": self.database.dict(),
                "security": self.security.dict(),
                "logging": self.logging.dict(),
                "storage": self.storage.dict(),
                "config_version": self.config_version,
                "last_updated": datetime.now().isoformat(),
                "environment": self.environment.value,
            }

        @classmethod
        def from_legacy_dict(cls, data: Dict[str, Any]) -> 'EnhancedOpenChronicleConfig':
            """Create configuration from legacy dictionary format."""
            # Convert enum strings to enum values
            if "environment" in data:
                data["environment"] = Environment(data["environment"])
            
            # Handle logging level conversion
            if "logging" in data and "log_level" in data["logging"]:
                data["logging"]["log_level"] = LogLevel(data["logging"]["log_level"])
            
            return cls(**data)

else:
    # Fallback dataclass-based configuration (if pydantic not available)
    from .centralized_config import (
        PerformanceConfig as PerformanceSettings,
        ModelConfig as ModelSettings,
        DatabaseConfig as DatabaseSettings,
        SecurityConfig as SecuritySettings,
        LoggingConfig as LoggingSettings,
        StorageConfig as StorageSettings,
        SystemConfig as EnhancedOpenChronicleConfig
    )
    
    # Create placeholder CLI and User settings
    @dataclass
    class CLISettings:
        output_format: str = "rich"
        quiet_mode: bool = False
        auto_confirm: bool = False
        color_output: bool = True
        max_table_rows: int = 50
        progress_bars: bool = True
        editor: str = field(default_factory=lambda: os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano"))
        pager: str = field(default_factory=lambda: os.environ.get("PAGER", "more" if os.name == "nt" else "less"))

    @dataclass 
    class UserPreferences:
        default_story: Optional[str] = None
        favorite_models: List[str] = field(default_factory=list)
        recent_files: List[str] = field(default_factory=list)
        workspace_paths: List[str] = field(default_factory=list)
        aliases: Dict[str, str] = field(default_factory=dict)


class ConfigurationManager:
    """
    Enhanced configuration manager that supports both Pydantic and fallback modes.
    
    Provides a unified interface for configuration management with:
    - Automatic migration from legacy formats
    - Environment variable support (when pydantic available)
    - Type validation and coercion
    - Backward compatibility
    """
    
    def __init__(self, config_dir: Path = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Configuration directory (defaults to ./config)
        """
        self.config_dir = config_dir or Path.cwd() / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.config = self._load_configuration()
        
        # Ensure storage directories exist
        if hasattr(self.config, 'create_storage_directories'):
            created_paths = self.config.create_storage_directories()
            if created_paths:
                print(f"✅ Created {len(created_paths)} missing storage directories")
        
    def _load_configuration(self) -> EnhancedOpenChronicleConfig:
        """Load configuration from files or environment variables."""
        if PYDANTIC_AVAILABLE:
            # Try to load from legacy files first
            legacy_data = self._load_legacy_files()
            if legacy_data:
                return EnhancedOpenChronicleConfig.from_legacy_dict(legacy_data)
            else:
                # Load from environment variables or defaults
                return EnhancedOpenChronicleConfig()
        else:
            # Fallback to existing centralized config
            from .centralized_config import CentralizedConfigManager
            legacy_manager = CentralizedConfigManager(str(self.config_dir / "system_config.json"))
            return legacy_manager.config
    
    def _load_legacy_files(self) -> Optional[Dict[str, Any]]:
        """Load configuration from legacy JSON files."""
        import json
        
        config_data = {}
        
        # Load system config
        system_path = self.config_dir / "system_config.json"
        if system_path.exists():
            try:
                with open(system_path) as f:
                    system_data = json.load(f)
                    config_data.update(system_data)
            except (json.JSONDecodeError, OSError):
                pass
        
        # Load CLI config
        cli_path = self.config_dir / "cli_config.json"
        if cli_path.exists():
            try:
                with open(cli_path) as f:
                    cli_data = json.load(f)
                    config_data["cli"] = cli_data
            except (json.JSONDecodeError, OSError):
                pass
        
        # Load user preferences
        user_path = self.config_dir / "user_preferences.json"
        if user_path.exists():
            try:
                with open(user_path) as f:
                    user_data = json.load(f)
                    config_data["user"] = user_data
            except (json.JSONDecodeError, OSError):
                pass
        
        return config_data if config_data else None
    
    def save_configuration(self) -> bool:
        """
        Save configuration to files.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if PYDANTIC_AVAILABLE and hasattr(self.config, 'to_legacy_dict'):
                # Save as legacy format for compatibility
                import json
                
                # System config
                system_data = self.config.to_legacy_dict()
                with open(self.config_dir / "system_config.json", "w") as f:
                    json.dump(system_data, f, indent=2)
                
                # CLI config
                cli_data = self.config.cli.dict()
                with open(self.config_dir / "cli_config.json", "w") as f:
                    json.dump(cli_data, f, indent=2)
                
                # User preferences
                user_data = self.config.user.dict()
                with open(self.config_dir / "user_preferences.json", "w") as f:
                    json.dump(user_data, f, indent=2)
                
            else:
                # Use legacy save method
                from .centralized_config import CentralizedConfigManager
                legacy_manager = CentralizedConfigManager(str(self.config_dir / "system_config.json"))
                legacy_manager.config = self.config
                return legacy_manager.save_config()
            
            print("✅ Configuration saved successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")
            return False
    
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration value.
        
        Args:
            section: Configuration section name
            key: Setting key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        try:
            config_section = getattr(self.config, section)
            return getattr(config_section, key, default)
        except AttributeError:
            return default
    
    def set_setting(self, section: str, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a specific configuration value.
        
        Args:
            section: Configuration section name
            key: Setting key
            value: New value
            save: Whether to save to file immediately
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_section = getattr(self.config, section)
            setattr(config_section, key, value)
            
            if save:
                return self.save_configuration()
            return True
            
        except (AttributeError, ValueError) as e:
            print(f"❌ Failed to set {section}.{key} = {value}: {e}")
            return False
    
    def validate_configuration(self) -> List[str]:
        """
        Validate current configuration.
        
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        if PYDANTIC_AVAILABLE:
            # Pydantic handles validation automatically
            try:
                # Try to reconstruct config to trigger validation
                if hasattr(self.config, 'dict'):
                    EnhancedOpenChronicleConfig(**self.config.dict())
            except Exception as e:
                issues.append(f"Configuration validation failed: {e}")
        else:
            # Manual validation for fallback mode
            from .centralized_config import CentralizedConfigManager
            legacy_manager = CentralizedConfigManager()
            legacy_manager.config = self.config
            issues = legacy_manager.validate_config()
        
        return issues
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """Get information about the current configuration."""
        info = {
            "pydantic_available": PYDANTIC_AVAILABLE,
            "config_version": getattr(self.config, 'config_version', 'unknown'),
            "environment": getattr(self.config, 'environment', 'unknown'),
            "config_dir": str(self.config_dir),
        }
        
        if PYDANTIC_AVAILABLE and hasattr(self.config, 'dict'):
            info["validation_enabled"] = True
            info["environment_variables_supported"] = True
        else:
            info["validation_enabled"] = False
            info["environment_variables_supported"] = False
            
        return info


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def get_config() -> EnhancedOpenChronicleConfig:
    """Get the current configuration."""
    return get_config_manager().config


def reset_config() -> None:
    """Reset the global configuration manager."""
    global _config_manager
    _config_manager = None


if __name__ == "__main__":
    # Test the enhanced configuration system
    print("🧪 Testing Enhanced Configuration System")
    
    config_manager = get_config_manager()
    config_info = config_manager.get_configuration_info()
    
    print(f"✅ Configuration loaded: {config_info}")
    print(f"📊 Pydantic available: {config_info['pydantic_available']}")
    print(f"🔧 Validation enabled: {config_info['validation_enabled']}")
    print(f"🌍 Environment variables supported: {config_info['environment_variables_supported']}")
    
    # Test configuration access
    config = get_config()
    print(f"📝 Default text model: {config.model.default_text_model}")
    print(f"🎨 CLI output format: {config.cli.output_format}")
    
    # Test validation
    issues = config_manager.validate_configuration()
    if issues:
        print(f"⚠️ Configuration issues: {issues}")
    else:
        print("✅ Configuration is valid")
    
    print("🎉 Enhanced configuration system test completed!")
