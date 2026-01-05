"""
Core Database Operations - Domain-agnostic database operations.

Provides base database operation interfaces and neutral database utilities
that can be extended by domain-specific plugins.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


class BaseDatabaseOperations(ABC):
    """
    Abstract base database operations for domain-agnostic database management.

    Domain-specific plugins should inherit from this class and implement
    their own database operations while following the same interface patterns.
    """

    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    @abstractmethod
    def init_database(self, entity_id: str, is_test: Optional[bool] = None) -> bool:
        """
        Initialize domain-specific database tables.

        Args:
            entity_id: Unique identifier for the database context
            is_test: Whether this is for test purposes

        Returns:
            bool: True if initialization succeeded
        """
        pass

    @abstractmethod
    def get_schema_statements(self) -> List[str]:
        """
        Get domain-specific database schema creation statements.

        Returns:
            List[str]: SQL CREATE TABLE statements for domain
        """
        pass

    def execute_query(
        self, entity_id: str, query: str, params: Optional[tuple] = None, is_test: Optional[bool] = None
    ) -> List[tuple]:
        """
        Execute a SELECT query and return results.

        Args:
            entity_id: Unique identifier for database context
            query: SQL SELECT query
            params: Query parameters
            is_test: Whether this is for test purposes

        Returns:
            List[tuple]: Query results
        """
        try:
            with self.connection_manager.get_connection(entity_id, is_test) as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Query execution failed: {e}")
            return []

    def execute_update(
        self, entity_id: str, query: str, params: Optional[tuple] = None, is_test: Optional[bool] = None
    ) -> bool:
        """
        Execute an UPDATE/INSERT/DELETE query.

        Args:
            entity_id: Unique identifier for database context
            query: SQL modification query
            params: Query parameters
            is_test: Whether this is for test purposes

        Returns:
            bool: True if update succeeded
        """
        try:
            with self.connection_manager.get_connection(entity_id, is_test) as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                return True
        except Exception as e:
            print(f"Update execution failed: {e}")
            return False


class DatabaseOperationsRegistry:
    """
    Registry for domain-specific database operations.

    Allows plugins to register their operations managers and provides
    a unified interface for database operations across domains.
    """

    def __init__(self):
        self._operations: Dict[str, BaseDatabaseOperations] = {}

    def register_operations(self, domain: str, operations: BaseDatabaseOperations) -> None:
        """Register domain-specific database operations."""
        self._operations[domain] = operations

    def get_operations(self, domain: str) -> Optional[BaseDatabaseOperations]:
        """Get database operations for a specific domain."""
        return self._operations.get(domain)

    def get_available_domains(self) -> List[str]:
        """Get list of domains with registered operations."""
        return list(self._operations.keys())


# Global operations registry instance
_operations_registry = DatabaseOperationsRegistry()


def get_operations_registry() -> DatabaseOperationsRegistry:
    """Get the global database operations registry instance."""
    return _operations_registry


# Backward compatibility class - DEPRECATED
# This exists for compatibility and should be replaced with domain-specific operations


class DatabaseOperations:
    """DEPRECATED and removed from core.

    Use domain-specific operations provided by plugins.
    """

    def __init__(self, connection_manager):  # pragma: no cover - maintained for import compatibility
        raise ImportError("DatabaseOperations is no longer available in core. Use plugin-provided operations via DI.")
