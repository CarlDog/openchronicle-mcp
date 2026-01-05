"""
OpenChronicle Core - Character Management Engine

Handles character lifecycle, storage operations, and basic ma        try:
            character = self.storage.get_character(character_id)
            if character:
                logger.debug(f"Retrieved character {character_id}")
            else:
                logger.debug(f"Character {character_id} not found")
        except (KeyError, AttributeError) as e:
            logger.exception("Character data structure error retrieving")
            return None
        except (ValueError, TypeError) as e:
            logger.exception("Character data validation error retrieving")
            return None
        except Exception as e:
            logger.exception("Error retrieving character")
            return None
        else:
            return characterted from character_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

import logging
from typing import Any

from ..core.character_base import CharacterEventHandler
from ..core.character_data import CharacterData
from ..core.character_storage import CharacterStorage


logger = logging.getLogger(__name__)


class CharacterManagementEngine(CharacterEventHandler):
    """Handles character creation, storage, and basic lifecycle management."""

    def __init__(self, config: dict | None = None):
        """Initialize character management engine."""
        super().__init__()
        self.config = config or {}

        # Initialize storage
        storage_config = self.config.get("storage", {})
        self.storage = CharacterStorage(storage_config)

        # Configuration
        self.auto_save = self.config.get("auto_save", True)
        self.event_logging_enabled = self.config.get("event_logging_enabled", True)

        # Subscribe to storage events
        self.storage.subscribe_to_event("character_updated", self._on_character_updated)
        self.storage.subscribe_to_event("character_created", self._on_character_created)

        logger.info("Character management engine initialized")

    def _create_character_sync(
        self,
        character_data: dict[str, Any],
        validate: bool = True,
    ) -> CharacterData | None:
        """
        Create a new character synchronously.

        Args:
            character_data: Character creation data
            validate: Whether to validate character data

        Returns:
            Created CharacterData or None if creation failed
        """
        try:
            character_id = character_data.get("character_id")
            if not character_id:
                logger.error("No character_id provided in character data")
                return None

            # Check if character already exists
            if self.storage.get_character(character_id):
                logger.warning(f"Character {character_id} already exists")
                return None

            # Create character data object
            character = CharacterData(
                character_id=character_id,
                name=character_data.get("name", character_id),
                description=character_data.get("description", ""),
                traits=character_data.get("traits", []),
                personality=character_data.get("personality", {}),
                background=character_data.get("background", {}),
                relationships=character_data.get("relationships", {}),
                metadata=character_data.get("metadata", {}),
            )

            # Initialize stats if provided
            if "stats" in character_data:
                from ..core.character_data import CharacterStats

                character.stats = CharacterStats.from_dict(character_data["stats"])

            # Store character
            if self.storage.create_character(character):
                self.emit_event(
                    "character_created",
                    {
                        "character_id": character_id,
                        "character_data": character_data,
                        "timestamp": character.metadata.get("created_at"),
                    },
                )
                logger.info(f"Character {character_id} created successfully")
                return character
            else:
                logger.error(f"Failed to store character {character_id}")
                return None

        except (ValueError, TypeError, KeyError) as e:
            logger.exception("Invalid character data during creation")
            return None
        except Exception as e:
            logger.exception("Unexpected error creating character")
            return None

    def get_character(self, character_id: str) -> CharacterData | None:
        """
        Retrieve a character by ID.

        Args:
            character_id: Unique character identifier

        Returns:
            CharacterData or None if not found
        """
        try:
            character = self.storage.get_character(character_id)
            if character:
                logger.debug(f"Retrieved character {character_id}")
            else:
                logger.debug(f"Character {character_id} not found")
        except (KeyError, AttributeError) as e:
            logger.exception("Character data structure error retrieving")
            return None
        except (ValueError, TypeError) as e:
            logger.exception("Character parameter error retrieving")
            return None
        except Exception as e:
            logger.exception("Error retrieving character")
            return None
        else:
            return character

    def delete_character(self, character_id: str) -> bool:
        """
        Delete a character.

        Args:
            character_id: Unique character identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if not self.storage.get_character(character_id):
                logger.warning(f"Character {character_id} not found for deletion")
                success = False
            else:
                success = self.storage.delete_character(character_id)
                if success:
                    self.emit_event(
                        "character_deleted",
                        {"character_id": character_id},
                    )
                    logger.info(f"Character {character_id} deleted successfully")
                else:
                    logger.error(f"Failed to delete character {character_id}")

        except (KeyError, AttributeError) as e:
            logger.exception("Character data structure error deleting")
            return False
        except (OSError, IOError) as e:
            logger.exception("Storage error deleting character")
            return False
        except Exception as e:
            logger.exception("Error deleting character")
            return False
        else:
            return success

    def list_characters(self) -> list[str]:
        """Get list of all character IDs."""
        try:
            return self.storage.list_characters()
        except (OSError, IOError) as e:
            logger.exception("Storage error listing characters")
            return []
        except (AttributeError, KeyError) as e:
            logger.exception("Character data structure error listing characters")
            return []
        except Exception as e:
            logger.exception("Error listing characters")
            return []

    def get_character_state(self, character_id: str) -> dict[str, Any]:
        """
        Get comprehensive character state.

        Args:
            character_id: Unique character identifier

        Returns:
            Dictionary containing character state
        """
        try:
            character = self.get_character(character_id)
            if not character:
                state = {}
            else:
                state = {
                    "character_id": character_id,
                    "exists": True,
                    "name": character.name,
                    "description": character.description,
                    "traits": character.traits,
                    "personality": character.personality,
                    "background": character.background,
                    "relationships": character.relationships,
                    "metadata": character.metadata,
                }

                # Include stats if available
                if character.stats:
                    state["stats"] = {
                        "strength": character.stats.strength,
                        "dexterity": character.stats.dexterity,
                        "intelligence": character.stats.intelligence,
                        "wisdom": character.stats.wisdom,
                        "charisma": character.stats.charisma,
                        "constitution": character.stats.constitution,
                    }

                logger.debug(f"Retrieved state for character {character_id}")

        except Exception as e:
            logger.exception("Error getting character state for")
            return {"character_id": character_id, "exists": False, "error": str(e)}
        else:
            return state

    def _update_character_state_sync(self, character_id: str, state_updates: dict[str, Any]) -> bool:
        """
        Update character state synchronously.

        Args:
            character_id: Unique character identifier
            state_updates: Dictionary of state updates

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            character = self.get_character(character_id)
            if not character:
                logger.error(f"Character {character_id} not found for state update")
                success = False
            else:
                # Update character attributes
                for key, value in state_updates.items():
                    if hasattr(character, key):
                        setattr(character, key, value)
                        logger.debug(f"Updated {key} for character {character_id}")

                # Save updated character
                success = self.storage.update_character(character)
                if success:
                    self.emit_event(
                        "character_state_updated",
                        {
                            "character_id": character_id,
                            "updates": state_updates,
                        },
                    )
                    logger.info(f"Character {character_id} state updated successfully")
                else:
                    logger.error(f"Failed to save character {character_id} state updates")

        except (KeyError, AttributeError) as e:
            logger.exception(f"Character data structure error updating {character_id} state")
            return False
        except (ValueError, TypeError) as e:
            logger.exception("Character state validation error for")
            return False
        except Exception as e:
            logger.exception(f"Error updating character {character_id} state")
            return False
        else:
            return success

    def _on_character_updated(self, event_data: dict[str, Any]) -> None:
        """Handle character updated event."""
        if self.event_logging_enabled:
            character_id = event_data.get("character_id", "unknown")
            logger.info(f"Character {character_id} updated: {event_data}")

    def _on_character_created(self, event_data: dict[str, Any]) -> None:
        """Handle character created event."""
        if self.event_logging_enabled:
            character_id = event_data.get("character_id", "unknown")
            logger.info(f"Character {character_id} created: {event_data}")

    def get_management_status(self) -> dict[str, Any]:
        """Get character management engine status."""
        try:
            character_count = len(self.list_characters())
            return {
                "engine_status": "active",
                "character_count": character_count,
                "auto_save_enabled": self.auto_save,
                "event_logging_enabled": self.event_logging_enabled,
                "storage_type": type(self.storage).__name__,
            }
        except Exception as e:
            logger.exception("Error getting management status")
            return {"engine_status": "error", "error": str(e)}
