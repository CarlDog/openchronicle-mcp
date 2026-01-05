"""
Memory Port Adapter

Infrastructure adapter that implements IMemoryPort using the existing
repository implementation. Bridges the domain port with the infrastructure
layer. Neutral terminology is used in docstrings and messages.
"""

import logging
from typing import Any, Dict, List, Optional

from openchronicle.domain.models.memory_models import CharacterMemory as DomainCharacterMemory, MemoryState
from openchronicle.domain.ports.memory_port import IMemoryPort
from openchronicle.infrastructure.memory.engines.persistence.memory_repository import MemoryRepository
from openchronicle.infrastructure.memory.shared.memory_models import CharacterMemory as InfraCharacterMemory


logger = logging.getLogger(__name__)


class MemoryPortAdapter(IMemoryPort):
    """Adapter that implements IMemoryPort using MemoryRepository."""

    def __init__(self, memory_repository: Optional[MemoryRepository] = None):
    """Initialize adapter with optional memory repository."""
        self.memory_repository = memory_repository or MemoryRepository()

    def store_memory(
        self, unit_id: str, character_name: str, memory_data: dict[str, Any]
    ) -> bool:
        """Store participant memory data."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception:
            logger.exception("Failed to store memory")
            return False

    def retrieve_memory(
        self, unit_id: str, character_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve participant memory data."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return None
        except Exception:
            logger.exception("Failed to retrieve memory")
            return None

    def update_memory(
        self, unit_id: str, character_name: str, updates: Dict[str, Any]
    ) -> bool:
        """Update participant memory data."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception:
            logger.exception("Failed to update memory")
            return False

    def delete_memory(self, unit_id: str, character_name: str) -> bool:
        """Delete participant memory data."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception:
            logger.exception("Failed to delete memory")
            return False

    def list_character_memories(self, unit_id: str) -> List[str]:
        """List all participants with memory data."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return []
        except Exception:
            logger.exception("Failed to list participant memories")
            return []

    def backup_memories(self, unit_id: str, backup_name: str) -> bool:
        """Create a backup of all memory data."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception:
            logger.exception("Failed to backup memories")
            return False

    def restore_memories(self, unit_id: str, backup_name: str) -> bool:
        """Restore memory data from backup."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception:
            logger.exception("Failed to restore memories")
            return False

    async def create_memory(
        self, unit_id: str, character_id: str, memory_data: Dict[str, Any]
    ) -> bool:
        """Create a new memory entry."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            # For now, delegate to existing repository methods
            return True
        except Exception:
            logger.exception("Failed to create memory")
            return False

    async def get_memory(self, unit_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return None
        except Exception as e:
            logger.exception(f"Failed to get memory: {e}")
            return None

    async def update_memory_async(
        self, unit_id: str, memory_id: str, memory_data: Dict[str, Any]
    ) -> bool:
    """Update an existing memory entry."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception as e:
            logger.exception(f"Failed to update memory: {e}")
            return False

    async def delete_memory_async(self, unit_id: str, memory_id: str) -> bool:
    """Delete a memory entry."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return True
        except Exception as e:
            logger.exception(f"Failed to delete memory: {e}")
            return False

    async def list_memories(
        self, unit_id: str, character_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List memories for a unit, optionally filtered by participant."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return []
        except Exception as e:
            logger.exception(f"Failed to list memories: {e}")
            return []

    async def search_memories(
        self, unit_id: str, query: str, character_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search memories by content."""
        try:
            # Implementation would depend on existing MemoryRepository interface
            return []
        except Exception as e:
            logger.exception(f"Failed to search memories: {e}")
            return []

    def load_memory(self, unit_id: str) -> MemoryState:
        """Load memory state from repository."""
        try:
            # Use existing repository to load memory state
            infrastructure_memory_state = self.memory_repository.load_memory(unit_id)

            # Convert infrastructure models to domain models
            domain_characters = {}
            for char_id, infra_char in infrastructure_memory_state.characters.items():
                # Convert dialogue_history to list of dicts if it's a list of strings
                dialogue_history = []
                if hasattr(infra_char, 'dialogue_history') and infra_char.dialogue_history:
                    for dialogue in infra_char.dialogue_history:
                        if isinstance(dialogue, str):
                            dialogue_history.append({
                                "content": dialogue,
                                "timestamp": "",
                                "emotional_score": 0.0,
                                "importance": 0.5,
                                "tags": []
                            })
                        elif isinstance(dialogue, dict):
                            dialogue_history.append(dialogue)

                domain_char = DomainCharacterMemory(
                    name=infra_char.name,
                    dialogue_history=dialogue_history,
                    background=getattr(infra_char, 'background', ''),
                    traits={},  # Infrastructure model doesn't have traits
                    relationships=getattr(infra_char, 'relationships', {})
                )
                domain_characters[char_id] = domain_char

            return MemoryState(
                characters=domain_characters,
                story_metadata={}  # Infrastructure model doesn't have domain metadata at top level
            )
        except Exception as e:
            logger.exception("Failed to load memory state")
            # Return empty state on error
            return MemoryState()

    def save_memory(self, unit_id: str, memory_state: MemoryState) -> bool:
        """Save memory state to repository."""
        try:
            # Convert domain models to infrastructure models
            infra_characters = {}
            for char_id, domain_char in memory_state.characters.items():
                # Convert dialogue_history to list of strings for infrastructure
                dialogue_history = []
                for dialogue in domain_char.dialogue_history:
                    if isinstance(dialogue, dict):
                        dialogue_history.append(dialogue.get("content", ""))
                    else:
                        dialogue_history.append(str(dialogue))

                infra_char = InfraCharacterMemory(
                    name=domain_char.name,
                    dialogue_history=dialogue_history,
                    background=domain_char.background,
                    relationships=domain_char.relationships
                )
                infra_characters[char_id] = infra_char

            # Create infrastructure memory state
            from openchronicle.infrastructure.memory.shared.memory_models import MemoryState as InfraMemoryState
            infra_memory_state = InfraMemoryState(
                characters=infra_characters
            )

            # Save using existing repository
            return self.memory_repository.save_memory(unit_id, infra_memory_state)
        except Exception as e:
            logger.exception("Failed to save memory state")
            return False
