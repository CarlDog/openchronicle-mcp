"""
OpenChronicle Core - Character Validation Engine

Handles character validation, consistency checks, and action validation.
Extracted from character_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

import logging
from datetime import datetime
from typing import Any
from typing import Tuple

from ..core.character_base import CharacterValidationProvider
from ..core.character_data import CharacterData


logger = logging.getLogger(__name__)


class CharacterValidationEngine:
    """Handles character validation and consistency checking."""

    def __init__(self, config: dict | None = None):
        """Initialize character validation engine."""
        self.config = config or {}
        self.validation_providers: list[CharacterValidationProvider] = []

        # Configuration
        self.strict_validation = self.config.get("strict_validation", False)
        self.consistency_checks_enabled = self.config.get("consistency_checks_enabled", True)
        self.action_validation_enabled = self.config.get("action_validation_enabled", True)

        logger.info("Character validation engine initialized")

    def register_validation_provider(self, provider: CharacterValidationProvider) -> None:
        """Register a validation provider."""
        if provider not in self.validation_providers:
            self.validation_providers.append(provider)
            logger.info(f"Registered validation provider: {provider.__class__.__name__}")

    def unregister_validation_provider(self, provider: CharacterValidationProvider) -> None:
        """Unregister a validation provider."""
        if provider in self.validation_providers:
            self.validation_providers.remove(provider)
            logger.info(f"Unregistered validation provider: {provider.__class__.__name__}")

    def validate_character_consistency(
        self, character: CharacterData, context: dict[str, Any] = None
    ) -> dict[str, Any]:
        """
        Validate character consistency across all aspects.

        Args:
            character: Character to validate
            context: Optional validation context

        Returns:
            Dictionary containing validation results
        """
        try:
            if not character:
                return {
                    "valid": False,
                    "error": "No character provided for validation",
                    "timestamp": datetime.now().isoformat(),
                }

            context = context or {}
            validation_result = {
                "character_id": character.character_id,
                "valid": True,
                "issues": [],
                "warnings": [],
                "context": context,
                "timestamp": datetime.now().isoformat(),
            }

            # Basic character data validation
            basic_issues = self._validate_basic_character_data(character)
            validation_result["issues"].extend(basic_issues)

            # Personality consistency validation
            if self.consistency_checks_enabled:
                personality_issues = self._validate_personality_consistency(character)
                validation_result["issues"].extend(personality_issues)

            # Stats validation
            stats_issues = self._validate_character_stats(character)
            validation_result["issues"].extend(stats_issues)

            # Relationship validation
            relationship_issues = self._validate_relationships(character)
            validation_result["issues"].extend(relationship_issues)

            # Use external validation providers
            for provider in self.validation_providers:
                try:
                    provider_valid, provider_error = provider.validate_character_consistency(
                        character.character_id, context
                    )
                    if not provider_valid:
                        validation_result["issues"].append(f"{provider.__class__.__name__}: {provider_error}")
                except (AttributeError, KeyError) as e:
                    logger.exception(f"Validation provider data structure error in {provider.__class__.__name__}")
                    if self.strict_validation:
                        validation_result["issues"].append(f"Validation provider data error: {e}")
                except (ValueError, TypeError) as e:
                    logger.exception(f"Validation provider parameter error in {provider.__class__.__name__}")
                    if self.strict_validation:
                        validation_result["issues"].append(f"Validation provider parameter error: {e}")
                except Exception as e:
                    logger.exception(f"Error in validation provider {provider.__class__.__name__}")
                    if self.strict_validation:
                        validation_result["issues"].append(f"Validation provider error: {e}")

            # Determine overall validity
            validation_result["valid"] = len(validation_result["issues"]) == 0

            if validation_result["valid"]:
                logger.info(f"Character {character.character_id} passed consistency validation")
            else:
                logger.warning(
                    f"Character {character.character_id} failed consistency validation: "
                    f"{len(validation_result['issues'])} issues found"
                )

        except Exception as e:
            logger.exception("Error validating character consistency")
            return {
                "character_id": getattr(character, "character_id", "unknown"),
                "valid": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return validation_result

    def validate_character_action(self, character: CharacterData, action_data: dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a proposed character action.

        Args:
            character: Character performing the action
            action_data: Action details

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if not self.action_validation_enabled:
                return True, ""

            if not character:
                return False, "No character provided for action validation"

            action_type = action_data.get("type", "unknown")

            # Basic action validation
            if action_type == "stat_update":
                return self._validate_stat_update_action(character, action_data)
            elif action_type == "relationship_management":
                return self._validate_relationship_action(character, action_data)
            elif action_type == "personality_change":
                return self._validate_personality_change_action(character, action_data)
            elif action_type == "dialogue":
                return self._validate_dialogue_action(character, action_data)
            else:
                # Use external validation providers for unknown actions
                for provider in self.validation_providers:
                    try:
                        valid, error = provider.validate_character_action(character.character_id, action_data)
                        if not valid:
                            return False, error
                    except (AttributeError, KeyError) as e:
                        logger.exception("Action validation provider data structure error")
                        if self.strict_validation:
                            return False, f"Validation provider data error: {e}"
                    except (ValueError, TypeError) as e:
                        logger.exception("Action validation provider parameter error")
                        if self.strict_validation:
                            return False, f"Validation provider parameter error: {e}"
                    except Exception as e:
                        logger.exception("Error in action validation provider")
                        if self.strict_validation:
                            return False, f"Validation provider error: {e}"

        except (AttributeError, KeyError) as e:
            logger.exception("Character action data structure error")
            return False, f"Action validation data error: {e}"
        except (ValueError, TypeError) as e:
            logger.exception("Character action parameter error")
            return False, f"Action validation parameter error: {e}"
        except Exception as e:
            logger.exception("Error validating character action")
            return False, f"Action validation error: {e}"
        else:
            return True, ""

    def _validate_basic_character_data(self, character: CharacterData) -> list[str]:
        """Validate basic character data integrity."""
        issues = []

        if not character.character_id:
            issues.append("Missing character ID")

        if not character.name or len(character.name.strip()) == 0:
            issues.append("Missing or empty character name")

        if not character.description or len(character.description.strip()) < 10:
            issues.append("Character description too short or missing")

        if not character.traits or len(character.traits) == 0:
            issues.append("No character traits defined")

        return issues

    def _validate_personality_consistency(self, character: CharacterData) -> list[str]:
        """Validate personality consistency."""
        issues = []

        if not character.personality:
            issues.append("No personality data defined")
            return issues

        # Check for conflicting personality traits
        if "aggressive" in character.traits and "peaceful" in character.traits:
            issues.append("Conflicting personality traits: aggressive and peaceful")

        if "extroverted" in character.traits and "introverted" in character.traits:
            issues.append("Conflicting personality traits: extroverted and introverted")

        # Validate personality scores if present
        for trait, value in character.personality.items():
            if isinstance(value, (int, float)):
                if value < 0 or value > 1:
                    issues.append(f"Personality trait '{trait}' value {value} outside valid range [0,1]")

        return issues

    def _validate_character_stats(self, character: CharacterData) -> list[str]:
        """Validate character statistics."""
        issues = []

        if not character.stats:
            issues.append("No character stats defined")
            return issues

        # Basic stat validation
        from ..core.character_data import CharacterStatType

        for stat_type in CharacterStatType:
            stat_value = getattr(character.stats, stat_type.value, None)
            if stat_value is None:
                issues.append(f"Missing stat: {stat_type.value}")
            elif stat_value < 1 or stat_value > 20:
                issues.append(f"Stat {stat_type.value} value {stat_value} outside valid range [1,20]")

        return issues

    def _validate_relationships(self, character: CharacterData) -> list[str]:
        """Validate character relationships."""
        issues = []

        if not isinstance(character.relationships, dict):
            issues.append("Relationships must be a dictionary")
            return issues

        for character_id, relationship_data in character.relationships.items():
            if not isinstance(relationship_data, dict):
                issues.append(f"Relationship with {character_id} must be a dictionary")
                continue

            relationship_type = relationship_data.get("type")
            if not relationship_type:
                issues.append(f"Missing relationship type for {character_id}")

            relationship_strength = relationship_data.get("strength")
            if isinstance(relationship_strength, (int, float)):
                if relationship_strength < -1 or relationship_strength > 1:
                    issues.append(f"Relationship strength with {character_id} outside valid range [-1,1]")

        return issues

    def _validate_stat_update_action(self, character: CharacterData, action_data: dict[str, Any]) -> Tuple[bool, str]:
        """Validate stat update action."""
        stat_type = action_data.get("stat_type")
        new_value = action_data.get("new_value")
        reason = action_data.get("reason")

        if not stat_type:
            return False, "Missing stat_type in action data"

        if new_value is None:
            return False, "Missing new_value in action data"

        if not isinstance(new_value, int):
            return False, "new_value must be an integer"

        if new_value < 1 or new_value > 20:
            return False, f"Stat value {new_value} outside valid range [1,20]"

        if not reason:
            return False, "Missing reason for stat update"

        return True, ""

    def _validate_relationship_action(self, character: CharacterData, action_data: dict[str, Any]) -> Tuple[bool, str]:
        """Validate relationship management action."""
        relationship_data = action_data.get("data", {})

        if not isinstance(relationship_data, dict):
            return False, "Relationship data must be a dictionary"

        target_character = relationship_data.get("target_character")
        if not target_character:
            return False, "Missing target_character in relationship data"

        return True, ""

    def _validate_personality_change_action(
        self, character: CharacterData, action_data: dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate personality change action."""
        changes = action_data.get("changes", {})

        if not isinstance(changes, dict):
            return False, "Personality changes must be a dictionary"

        for trait, value in changes.items():
            if isinstance(value, (int, float)):
                if value < 0 or value > 1:
                    return False, f"Personality trait '{trait}' value {value} outside valid range [0,1]"

        return True, ""

    def _validate_dialogue_action(self, character: CharacterData, action_data: dict[str, Any]) -> Tuple[bool, str]:
        """Validate dialogue action."""
        content = action_data.get("content", "")

        if not content or len(content.strip()) == 0:
            return False, "Dialogue content cannot be empty"

        if len(content) > 10000:  # Arbitrary max length
            return False, "Dialogue content too long"

        return True, ""

    def get_validation_status(self) -> dict[str, Any]:
        """Get validation engine status."""
        return {
            "engine_status": "active",
            "validation_providers_count": len(self.validation_providers),
            "strict_validation": self.strict_validation,
            "consistency_checks_enabled": self.consistency_checks_enabled,
            "action_validation_enabled": self.action_validation_enabled,
            "provider_types": [provider.__class__.__name__ for provider in self.validation_providers],
        }
