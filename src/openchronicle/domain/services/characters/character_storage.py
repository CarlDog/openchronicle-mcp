"""
Character Storage Manager

Provides unified character data persistence and management.
Handles loading, saving, and caching of character data across all components.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .character_base import CharacterEngineBase
from .character_base import CharacterEventHandler
from .character_data import CharacterData


logger = logging.getLogger(__name__)


class CharacterStorage(CharacterEngineBase, CharacterEventHandler):
    """
    Unified character data storage and management system.

    Provides centralized character data persistence, caching, and event-driven
    updates across all character management components.
    """

    def __init__(self, config: dict | None = None):
        """Initialize character storage manager."""
        # Store config first
        self.config = config or {}

        # Set storage configuration before calling parent init
        self.storage_path = self.config.get("storage_path", "storage/characters")
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.auto_save = self.config.get("auto_save", True)
        self.backup_enabled = self.config.get("backup_enabled", True)
        self.max_cache_size = self.config.get("max_cache_size", 1000)

        # Initialize base classes properly
        CharacterEngineBase.__init__(self, self.config)
        CharacterEventHandler.__init__(self)

        # Storage
        self.character_cache: dict[str, CharacterData] = {}
        self.pending_saves: set[str] = set()
        self.save_lock = threading.Lock()

        # Ensure storage directory exists
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Character storage initialized at {self.storage_path}")

    def _validate_config(self) -> None:
        """Validate storage configuration."""
        if not self.storage_path:
            raise ValueError("storage_path is required")

        # Validate storage path is writable
        try:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            test_file = Path(self.storage_path) / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise ValueError(f"Storage path not writable: {e}")

    def initialize_character(
        self, character_id: str, character_data: dict | None = None
    ) -> CharacterData:
        """Initialize or load character data."""
        # Check cache first
        if character_id in self.character_cache:
            self.logger.debug(f"Character {character_id} loaded from cache")
            return self.character_cache[character_id]

        # Try to load from storage
        loaded_character = self._load_character_from_storage(character_id)
        if loaded_character:
            self.character_cache[character_id] = loaded_character
            self.emit_event("character_loaded", {"character_id": character_id})
            return loaded_character

        # Create new character
        new_character = CharacterData(character_id=character_id)

        # Apply any provided initial data
        if character_data:
            self._apply_character_data(new_character, character_data)

        # Cache and optionally save
        self.character_cache[character_id] = new_character

        if self.auto_save:
            self.save_character(character_id)

        self.emit_event("character_created", {"character_id": character_id})
        return new_character

    def get_character_data(self, character_id: str) -> CharacterData | None:
        """Get character data by ID."""
        if character_id in self.character_cache:
            return self.character_cache[character_id]

        # Try to load from storage
        character = self._load_character_from_storage(character_id)
        if character:
            self.character_cache[character_id] = character
            return character

        return None

    def save_character(self, character_id: str, force: bool = False) -> bool:
        """Save character data to storage."""
        if character_id not in self.character_cache:
            self.logger.warning(f"Character {character_id} not found in cache")
            return False

        character = self.character_cache[character_id]

        with self.save_lock:
            try:
                # Create backup if enabled
                if self.backup_enabled:
                    self._create_backup(character_id)

                # Save to storage
                storage_file = Path(self.storage_path) / f"{character_id}.json"
                character_dict = character.to_dict()

                with storage_file.open("w", encoding="utf-8") as f:
                    json.dump(character_dict, f, indent=2, ensure_ascii=False)

                # Remove from pending saves
                self.pending_saves.discard(character_id)

                self.emit_event("character_saved", {"character_id": character_id})
                self.logger.debug(f"Character {character_id} saved to storage")
                return True

            except Exception as e:
                self.logger.error(f"Failed to save character {character_id}: {e}")
                return False

    def delete_character(self, character_id: str) -> bool:
        """Delete character data from storage and cache."""
        success = True

        # Remove from cache
        if character_id in self.character_cache:
            del self.character_cache[character_id]

        # Remove from storage
        storage_file = Path(self.storage_path) / f"{character_id}.json"
        if storage_file.exists():
            try:
                storage_file.unlink()
            except Exception as e:
                self.logger.error(
                    f"Failed to delete character file {character_id}: {e}"
                )
                success = False

        # Remove from pending saves
        self.pending_saves.discard(character_id)

        if success:
            self.emit_event("character_deleted", {"character_id": character_id})

        return success

    def list_characters(self) -> list[str]:
        """List all available character IDs."""
        character_ids = set()

        # Add cached characters
        character_ids.update(self.character_cache.keys())

        # Add storage characters
        storage_path = Path(self.storage_path)
        if storage_path.exists():
            for file_path in storage_path.glob("*.json"):
                if not file_path.stem.startswith("."):  # Skip hidden files
                    character_ids.add(file_path.stem)

        return sorted(list(character_ids))

    def update_character_component(
        self, character_id: str, component_name: str, component_data: Any
    ) -> bool:
        """Update a specific component of character data."""
        character = self.get_character_data(character_id)
        if not character:
            return False

        try:
            character.set_component_data(component_name, component_data)

            # Mark for save if auto-save enabled
            if self.auto_save:
                self.pending_saves.add(character_id)

            self.emit_event(
                "character_updated",
                {"character_id": character_id, "component": component_name},
            )

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to update character {character_id} component {component_name}: {e}"
            )
            return False

    def get_character_component(
        self, character_id: str, component_name: str
    ) -> Any | None:
        """Get specific component data for a character."""
        character = self.get_character_data(character_id)
        if not character:
            return None

        return character.get_component_data(component_name)

    def export_character_data(self, character_id: str) -> dict[str, Any]:
        """Export character data for external use."""
        character = self.get_character_data(character_id)
        if not character:
            return {}

        return character.to_dict()

    def import_character_data(self, character_data: dict[str, Any]) -> bool:
        """Import character data from external source."""
        try:
            character_id = character_data.get("character_id")
            if not character_id:
                raise ValueError("character_id is required")

            # Create or update character
            character = CharacterData.from_dict(character_data)
            self.character_cache[character_id] = character

            if self.auto_save:
                self.save_character(character_id)

            self.emit_event("character_imported", {"character_id": character_id})
            return True

        except Exception as e:
            self.logger.error(f"Failed to import character data: {e}")
            return False

    def save_all_pending(self) -> dict[str, bool]:
        """Save all characters with pending changes."""
        results = {}
        pending_copy = self.pending_saves.copy()

        for character_id in pending_copy:
            results[character_id] = self.save_character(character_id)

        return results

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "cached_characters": len(self.character_cache),
            "pending_saves": len(self.pending_saves),
            "cache_enabled": self.cache_enabled,
            "max_cache_size": self.max_cache_size,
        }

    def cleanup_cache(self, max_age_hours: int = 24) -> int:
        """Clean up old cached characters."""
        if not self.cache_enabled:
            return 0

        current_time = datetime.now()
        to_remove = []

        for character_id, character in self.character_cache.items():
            age_hours = (current_time - character.last_updated).total_seconds() / 3600
            if age_hours > max_age_hours and character_id not in self.pending_saves:
                to_remove.append(character_id)

        for character_id in to_remove:
            del self.character_cache[character_id]

        self.logger.info(f"Cleaned up {len(to_remove)} cached characters")
        return len(to_remove)

    # Private methods

    def _load_character_from_storage(
        self, character_id: str
    ) -> CharacterData | None:
        """Load character data from storage file."""
        storage_file = Path(self.storage_path) / f"{character_id}.json"

        if not storage_file.exists():
            return None

        try:
            with storage_file.open("r", encoding="utf-8") as f:
                character_dict = json.load(f)

            return CharacterData.from_dict(character_dict)

        except Exception as e:
            self.logger.error(f"Failed to load character {character_id}: {e}")
            return None

    def _apply_character_data(
        self, character: CharacterData, data: dict[str, Any]
    ) -> None:
        """Apply initial character data from dictionary."""
        for key, value in data.items():
            if hasattr(character, key):
                setattr(character, key, value)

    def _create_backup(self, character_id: str) -> bool:
        """Create backup of character data."""
        try:
            backup_dir = Path(self.storage_path) / "backups"
            backup_dir.mkdir(exist_ok=True)

            storage_file = Path(self.storage_path) / f"{character_id}.json"
            if storage_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"{character_id}_{timestamp}.json"

                import shutil

                shutil.copy2(storage_file, backup_file)

                return True

        except Exception as e:
            self.logger.error(f"Failed to create backup for {character_id}: {e}")

        return False
