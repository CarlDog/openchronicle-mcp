"""
Configuration management for OpenChronicle CLI.

Handles CLI-specific settings, user preferences, and integration
with the main OpenChronicle configuration system.
"""

import json
import os
from pathlib import Path
from typing import Any

import typer


class ConfigManager:
    """Manages CLI configuration and user preferences."""

    def __init__(self, config_dir: str | Path | None = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Optional custom config directory
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Use OpenChronicle's config directory by default
            self.config_dir = Path.cwd() / "config"

        self.cli_config_file = self.config_dir / "cli_config.json"
        self.user_preferences_file = self.config_dir / "user_preferences.json"

        # Default CLI configuration
        self.default_cli_config = {
            "output_format": "rich",
            "quiet_mode": False,
            "auto_confirm": False,
            "color_output": True,
            "max_table_rows": 50,
            "progress_bars": True,
            "editor": os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano"),
            "pager": os.environ.get("PAGER", "more" if os.name == "nt" else "less")
        }

        # Default user preferences
        self.default_user_preferences = {
            "default_story": None,
            "favorite_models": [],
            "recent_files": [],
            "workspace_paths": [],
            "aliases": {}
        }

        # Load existing configuration
        self._load_configurations()

    def _load_configurations(self):
        """Load CLI configuration and user preferences from files."""
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load CLI configuration
        if self.cli_config_file.exists():
            try:
                with open(self.cli_config_file, encoding='utf-8') as f:
                    self.cli_config = {**self.default_cli_config, **json.load(f)}
            except (OSError, json.JSONDecodeError):
                self.cli_config = self.default_cli_config.copy()
        else:
            self.cli_config = self.default_cli_config.copy()

        # Load user preferences
        if self.user_preferences_file.exists():
            try:
                with open(self.user_preferences_file, encoding='utf-8') as f:
                    self.user_preferences = {**self.default_user_preferences, **json.load(f)}
            except (OSError, json.JSONDecodeError):
                self.user_preferences = self.default_user_preferences.copy()
        else:
            self.user_preferences = self.default_user_preferences.copy()

    def save_configuration(self):
        """Save current configuration to files."""
        try:
            # Save CLI configuration
            with open(self.cli_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.cli_config, f, indent=2)

            # Save user preferences
            with open(self.user_preferences_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_preferences, f, indent=2)

        except OSError as e:
            typer.echo(f"Error saving configuration: {e}", err=True)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a CLI configuration setting.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        return self.cli_config.get(key, default)

    def set_setting(self, key: str, value: Any, save: bool = True):
        """
        Set a CLI configuration setting.
        
        Args:
            key: Setting key
            value: Setting value
            save: Whether to save to file immediately
        """
        self.cli_config[key] = value
        if save:
            self.save_configuration()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """
        Get a user preference.
        
        Args:
            key: Preference key
            default: Default value if key not found
            
        Returns:
            Preference value or default
        """
        return self.user_preferences.get(key, default)

    def set_preference(self, key: str, value: Any, save: bool = True):
        """
        Set a user preference.
        
        Args:
            key: Preference key
            value: Preference value
            save: Whether to save to file immediately
        """
        self.user_preferences[key] = value
        if save:
            self.save_configuration()

    def add_recent_file(self, file_path: str | Path, max_recent: int = 10):
        """
        Add a file to recent files list.
        
        Args:
            file_path: Path to file
            max_recent: Maximum number of recent files to keep
        """
        file_path = str(Path(file_path).absolute())
        recent_files = self.user_preferences.get("recent_files", [])

        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to beginning
        recent_files.insert(0, file_path)

        # Trim to max size
        recent_files = recent_files[:max_recent]

        self.set_preference("recent_files", recent_files)

    def add_favorite_model(self, model_name: str):
        """
        Add a model to favorites list.
        
        Args:
            model_name: Name of the model
        """
        favorites = self.user_preferences.get("favorite_models", [])
        if model_name not in favorites:
            favorites.append(model_name)
            self.set_preference("favorite_models", favorites)

    def remove_favorite_model(self, model_name: str):
        """
        Remove a model from favorites list.
        
        Args:
            model_name: Name of the model
        """
        favorites = self.user_preferences.get("favorite_models", [])
        if model_name in favorites:
            favorites.remove(model_name)
            self.set_preference("favorite_models", favorites)

    def get_openchronicle_config(self, config_file: str = "system_config.json") -> dict[str, Any]:
        """
        Load OpenChronicle system configuration.
        
        Args:
            config_file: Configuration file name
            
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid JSON
        """
        config_path = self.config_dir / config_file

        if not config_path.exists():
            raise FileNotFoundError(f"OpenChronicle config file not found: {config_path}")

        try:
            with open(config_path, encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {e}")

    def update_openchronicle_config(self, config_file: str, updates: dict[str, Any]):
        """
        Update OpenChronicle system configuration.
        
        Args:
            config_file: Configuration file name
            updates: Dictionary of updates to apply
        """
        config_path = self.config_dir / config_file

        # Load existing config
        if config_path.exists():
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = json.load(f)
            except (OSError, json.JSONDecodeError):
                config = {}
        else:
            config = {}

        # Apply updates
        config.update(updates)

        # Save updated config
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            typer.echo(f"Error updating config file {config_path}: {e}", err=True)
            raise

    def reset_cli_config(self):
        """Reset CLI configuration to defaults."""
        self.cli_config = self.default_cli_config.copy()
        self.save_configuration()

    def reset_user_preferences(self):
        """Reset user preferences to defaults."""
        self.user_preferences = self.default_user_preferences.copy()
        self.save_configuration()

    def export_settings(self, export_path: str | Path):
        """
        Export all settings to a file.
        
        Args:
            export_path: Path to export file
        """
        export_data = {
            "cli_config": self.cli_config,
            "user_preferences": self.user_preferences,
            "export_version": "1.0"
        }

        export_path = Path(export_path)
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

    def import_settings(self, import_path: str | Path, merge: bool = True):
        """
        Import settings from a file.
        
        Args:
            import_path: Path to import file
            merge: Whether to merge with existing settings or replace
        """
        import_path = Path(import_path)

        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")

        try:
            with open(import_path, encoding='utf-8') as f:
                import_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in import file: {e}")

        # Extract settings
        cli_config = import_data.get("cli_config", {})
        user_preferences = import_data.get("user_preferences", {})

        if merge:
            # Merge with existing settings
            self.cli_config.update(cli_config)
            self.user_preferences.update(user_preferences)
        else:
            # Replace existing settings
            self.cli_config = {**self.default_cli_config, **cli_config}
            self.user_preferences = {**self.default_user_preferences, **user_preferences}

        self.save_configuration()

    def get_all_settings(self) -> dict[str, Any]:
        """
        Get all CLI settings and preferences.
        
        Returns:
            Dictionary containing all settings
        """
        return {
            "cli_config": self.cli_config,
            "user_preferences": self.user_preferences,
            "config_files": {
                "cli_config_file": str(self.cli_config_file),
                "user_preferences_file": str(self.user_preferences_file),
                "config_dir": str(self.config_dir)
            }
        }
