"""
Base command infrastructure for OpenChronicle CLI.

Provides common functionality, error handling, and configuration management
for all CLI commands. Ensures consistent behavior across the application.
"""

import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Union

import typer
from rich.console import Console

from .output_manager import OutputManager
from .config_manager import ConfigManager


# Type variable for command return types
T = TypeVar('T')


class OpenChronicleCommand(ABC):
    """
    Abstract base class for all OpenChronicle CLI commands.
    
    Provides:
    - Consistent error handling
    - Configuration management
    - Output formatting
    - Common utilities
    """
    
    def __init__(
        self, 
        output_manager: Optional[OutputManager] = None,
        config_manager: Optional[ConfigManager] = None
    ):
        """
        Initialize the command with shared dependencies.
        
        Args:
            output_manager: Output formatting manager
            config_manager: Configuration management
        """
        self.output = output_manager or OutputManager()
        self.config = config_manager or ConfigManager()
        self.console = Console(stderr=True)
        
        # Validate OpenChronicle environment
        self._validate_environment()
        
    def _validate_environment(self):
        """Ensure we're running in a valid OpenChronicle environment."""
        # Check for core OpenChronicle files
        required_files = [
            "main.py",
            "core/__init__.py",
            "config/system_config.json"
        ]
        
        current_dir = Path.cwd()
        missing_files = []
        
        for file_path in required_files:
            if not (current_dir / file_path).exists():
                missing_files.append(file_path)
                
        if missing_files:
            self.output.error(
                f"OpenChronicle environment not detected. Missing files: {', '.join(missing_files)}\n"
                f"Please run this command from the OpenChronicle root directory.",
                exit_code=1
            )
            
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the command with the provided arguments.
        
        This method must be implemented by all command subclasses.
        
        Args:
            **kwargs: Command-specific arguments
            
        Returns:
            Command-specific return value
            
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Command subclasses must implement execute()")
        
    def safe_execute(self, **kwargs) -> Any:
        """
        Execute the command with comprehensive error handling.
        
        Args:
            **kwargs: Command-specific arguments
            
        Returns:
            Command result or None if error occurred
        """
        try:
            return self.execute(**kwargs)
        except KeyboardInterrupt:
            self.output.warning("Operation cancelled by user")
            return None
        except FileNotFoundError as e:
            self.output.error(f"File not found: {e}")
            return None
        except PermissionError as e:
            self.output.error(f"Permission denied: {e}")
            return None
        except ImportError as e:
            self.output.error(f"Missing dependency: {e}")
            return None
        except Exception as e:
            self.output.error(f"Unexpected error: {e}", error=e)
            return None
            
    def get_core_path(self, module_path: str = "") -> Path:
        """
        Get path to core OpenChronicle modules.
        
        Args:
            module_path: Optional subpath within core/
            
        Returns:
            Path to core module or subdirectory
        """
        base_path = Path.cwd() / "core"
        if module_path:
            return base_path / module_path
        return base_path
        
    def get_config_path(self, config_file: str = "") -> Path:
        """
        Get path to configuration files.
        
        Args:
            config_file: Optional specific config file
            
        Returns:
            Path to config directory or specific file
        """
        base_path = Path.cwd() / "config"
        if config_file:
            return base_path / config_file
        return base_path
        
    def import_core_module(self, module_name: str) -> Any:
        """
        Safely import a core OpenChronicle module.
        
        Args:
            module_name: Name of the module to import (e.g., "model_management")
            
        Returns:
            Imported module
            
        Raises:
            ImportError: If module cannot be imported
        """
        try:
            # Add current directory to path if not already present
            current_dir = str(Path.cwd())
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
                
            # Import the module
            module = __import__(f"core.{module_name}", fromlist=[module_name])
            return module
        except ImportError as e:
            self.output.error(f"Cannot import core module '{module_name}': {e}")
            raise
            
    def ensure_directory(self, path: Union[str, Path]) -> Path:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            path: Directory path to ensure
            
        Returns:
            Path object for the directory
        """
        path = Path(path)
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except PermissionError:
            self.output.error(f"Cannot create directory {path}: Permission denied")
            raise
        except OSError as e:
            self.output.error(f"Cannot create directory {path}: {e}")
            raise
            
    def read_json_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Safely read and parse a JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid
        """
        import json
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")
        except Exception as e:
            self.output.error(f"Error reading {path}: {e}")
            raise
            
    def write_json_file(self, file_path: Union[str, Path], data: Dict[str, Any], indent: int = 2):
        """
        Safely write data to a JSON file.
        
        Args:
            file_path: Path to write JSON file
            data: Data to write
            indent: JSON indentation level
        """
        import json
        
        path = Path(file_path)
        # Ensure parent directory exists
        self.ensure_directory(path.parent)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
        except Exception as e:
            self.output.error(f"Error writing JSON to {path}: {e}")
            raise
            
    def check_dependencies(self, required_modules: list) -> bool:
        """
        Check if required Python modules are available.
        
        Args:
            required_modules: List of module names to check
            
        Returns:
            True if all modules are available, False otherwise
        """
        import importlib
        
        missing_modules = []
        for module_name in required_modules:
            try:
                importlib.import_module(module_name)
            except ImportError:
                missing_modules.append(module_name)
                
        if missing_modules:
            self.output.error(
                f"Missing required dependencies: {', '.join(missing_modules)}\n"
                f"Please install them with: pip install {' '.join(missing_modules)}"
            )
            return False
            
        return True
        
    def format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
        
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get detailed information about a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        path = Path(file_path)
        if not path.exists():
            return {"exists": False}
            
        stat = path.stat()
        return {
            "exists": True,
            "path": str(path.absolute()),
            "size": stat.st_size,
            "size_formatted": self.format_file_size(stat.st_size),
            "modified": stat.st_mtime,
            "is_file": path.is_file(),
            "is_directory": path.is_dir(),
            "permissions": oct(stat.st_mode)[-3:]
        }


class ModelCommand(OpenChronicleCommand):
    """Base class for model-related commands."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model_manager = None
        
    @property
    def model_manager(self):
        """Lazy-load the model manager."""
        if self._model_manager is None:
            try:
                model_mgmt = self.import_core_module("model_management")
                self._model_manager = model_mgmt.ModelOrchestrator()
            except Exception as e:
                self.output.error(f"Cannot initialize model manager: {e}")
                raise
        return self._model_manager


class StoryCommand(OpenChronicleCommand):
    """Base class for story-related commands."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._story_manager = None
        
    @property
    def story_manager(self):
        """Lazy-load the story manager."""
        if self._story_manager is None:
            try:
                # Import relevant story management modules
                narrative = self.import_core_module("narrative_systems")
                # Initialize story manager components
                # This will be expanded based on actual story management architecture
                self._story_manager = {"narrative": narrative}
            except Exception as e:
                self.output.error(f"Cannot initialize story manager: {e}")
                raise
        return self._story_manager


class SystemCommand(OpenChronicleCommand):
    """Base class for system-related commands."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        status = {
            "environment": {
                "python_version": sys.version,
                "platform": sys.platform,
                "working_directory": str(Path.cwd())
            },
            "openchronicle": {
                "core_available": self.get_core_path().exists(),
                "config_available": self.get_config_path().exists(),
            }
        }
        
        # Check core modules
        core_modules = [
            "model_management", "narrative_systems", "character_management",
            "memory_management", "timeline_systems", "scene_systems"
        ]
        
        module_status = {}
        for module in core_modules:
            try:
                self.import_core_module(module)
                module_status[module] = "available"
            except ImportError:
                module_status[module] = "missing"
                
        status["core_modules"] = module_status
        return status
