"""
Core Migration Framework - Domain-agnostic database migration utilities.

Provides base migration interfaces and neutral migration infrastructure
that can be extended by domain-specific plugins.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


class BaseMigrationManager(ABC):
    """
    Abstract base migration manager for domain-agnostic migrations.

    Domain-specific plugins should inherit from this class and implement
    their own migration logic while following the same interface patterns.
    """

    def __init__(self, connection_manager, operations):
        self.connection_manager = connection_manager
        self.operations = operations

    @abstractmethod
    def migrate_data(self, entity_id: str, source_config: Dict[str, Any]) -> bool:
        """
        Abstract method for domain-specific data migration.

        Args:
            entity_id: Unique identifier for the migration target
            source_config: Configuration for source data location/format

        Returns:
            bool: True if migration succeeded, False otherwise
        """
        pass

    @abstractmethod
    def get_migration_schema(self) -> List[str]:
        """
        Get the database schema creation statements for this domain.

        Returns:
            List[str]: SQL statements to create domain-specific tables
        """
        pass

    def validate_migration_environment(self) -> bool:
        """
        Validate that the environment is ready for migration.

        Returns:
            bool: True if environment is valid for migration
        """
        try:
            # Basic validation that can be overridden by plugins
            return self.connection_manager is not None and self.operations is not None
        except Exception:
            return False


class MigrationRegistry:
    """
    Registry for domain-specific migration managers.

    Allows plugins to register their migration managers and provides
    a unified interface for running migrations across domains.
    """

    def __init__(self):
        self._managers: Dict[str, BaseMigrationManager] = {}

    def register_migration_manager(self, domain: str, manager: BaseMigrationManager) -> None:
        """Register a domain-specific migration manager."""
        self._managers[domain] = manager

    def get_migration_manager(self, domain: str) -> Optional[BaseMigrationManager]:
        """Get migration manager for a specific domain."""
        return self._managers.get(domain)

    def get_available_domains(self) -> List[str]:
        """Get list of domains with registered migration managers."""
        return list(self._managers.keys())

    def run_migration(self, domain: str, entity_id: str, source_config: Dict[str, Any]) -> bool:
        """
        Run migration for a specific domain.

        Args:
            domain: Domain name (e.g., 'storytelling', 'analytics')
            entity_id: Unique identifier for migration target
            source_config: Configuration for source data

        Returns:
            bool: True if migration succeeded
        """
        manager = self.get_migration_manager(domain)
        if not manager:
            raise ValueError(f"No migration manager registered for domain: {domain}")

        return manager.migrate_data(entity_id, source_config)


# Global migration registry instance
_migration_registry = MigrationRegistry()


def get_migration_registry() -> MigrationRegistry:
    """Get the global migration registry instance."""
    return _migration_registry


# Backward compatibility functions - DEPRECATED
# These exist for compatibility and should be replaced with domain-specific migrations


def migrate_from_json(story_id: str) -> bool:
    """DEPRECATED and removed from core.

    Migrations are provided by domain-specific plugins. Invoke the plugin's
    migration manager directly via its API or DI container.
    """
    raise ImportError(
        "migrate_from_json is no longer available in core. Use the storytelling plugin's migration manager."
    )
