"""
Storytelling Persistence Base (plugin-local)

Provides minimal, domain-agnostic primitives used by the storytelling plugin
to avoid importing core infrastructure directly.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


@dataclass
class DatabaseConfig:
    """Configuration for database operations (plugin-local)."""

    production_base_path: str = "storage/storypacks"
    test_base_path: str = "storage/temp/test_data"
    db_filename: str = "openchronicle.db"
    timeout: float = 30.0
    check_same_thread: bool = False

    def get_base_path(self, is_test: bool | None = None) -> str:
        if is_test is None:
            is_test = "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING") == "1"
        return self.test_base_path if is_test else self.production_base_path


class ConnectionManager:
    """Manages SQLite connections for storytelling (plugin-local)."""

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self.config = config or DatabaseConfig()

    def get_db_path(self, entity_id: str, is_test: bool | None = None) -> str:
        base_path = self.config.get_base_path(is_test)
        return os.path.join(base_path, entity_id, self.config.db_filename)

    def ensure_db_dir(self, entity_id: str, is_test: bool | None = None) -> None:
        db_path = self.get_db_path(entity_id, is_test)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def get_connection(self, entity_id: str, is_test: bool | None = None) -> sqlite3.Connection:
        self.ensure_db_dir(entity_id, is_test)
        db_path = self.get_db_path(entity_id, is_test)
        conn = sqlite3.connect(
            db_path,
            timeout=self.config.timeout,
            check_same_thread=self.config.check_same_thread,
        )
        conn.row_factory = sqlite3.Row
        return conn


class BaseDatabaseOperations:
    """Abstract base for database operations (plugin-local)."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self.connection_manager = connection_manager

    def init_database(self, entity_id: str, is_test: Optional[bool] = None) -> bool:
        raise NotImplementedError

    def get_schema_statements(self) -> List[str]:
        raise NotImplementedError

    def execute_query(
        self,
        entity_id: str,
        query: str,
        params: Optional[tuple] = None,
        is_test: Optional[bool] = None,
    ) -> List[tuple]:
        try:
            with self.connection_manager.get_connection(entity_id, is_test) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except Exception as e:
            print(f"Query execution failed: {e}")
            return []

    def execute_update(
        self,
        entity_id: str,
        query: str,
        params: Optional[tuple] = None,
        is_test: Optional[bool] = None,
    ) -> bool:
        try:
            with self.connection_manager.get_connection(entity_id, is_test) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()
                return True
        except Exception as e:
            print(f"Update execution failed: {e}")
            return False


class MigrationRegistry:
    """Plugin-local registry for migration managers."""

    def __init__(self) -> None:
        self._managers: Dict[str, BaseMigrationManager] = {}

    def register(self, domain: str, manager: BaseMigrationManager) -> None:
        self._managers[domain] = manager

    def get(self, domain: str) -> Optional[BaseMigrationManager]:
        return self._managers.get(domain)


class BaseMigrationManager:
    """Abstract base migration manager (plugin-local)."""

    def __init__(self, connection_manager: ConnectionManager, operations: BaseDatabaseOperations) -> None:
        self.connection_manager = connection_manager
        self.operations = operations

    def migrate_data(self, entity_id: str, source_config: Dict[str, Any]) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def get_migration_schema(self) -> List[str]:  # pragma: no cover - interface
        raise NotImplementedError
