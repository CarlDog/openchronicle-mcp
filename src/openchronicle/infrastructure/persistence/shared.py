"""
Shared database models and configurations.

Provides common data structures and configuration classes used across
all database components.
"""

import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class DatabaseConfig:
    """Configuration for database operations."""

    # Path configuration
    production_base_path: str = "storage/storypacks"
    test_base_path: str = "storage/temp/test_data"
    db_filename: str = "openchronicle.db"

    # Connection settings
    timeout: float = 30.0
    check_same_thread: bool = False

    # FTS settings
    enable_fts: bool = True
    fts_version: str = "fts5"

    def get_base_path(self, is_test: bool | None = None) -> str:
        """Get appropriate base path based on test context."""
        if is_test is None:
            is_test = self._is_test_context()
        return self.test_base_path if is_test else self.production_base_path

    @staticmethod
    def _is_test_context() -> bool:
        """Detect if we're running in a test context."""
        return "pytest" in sys.modules or "unittest" in sys.modules


@dataclass
class DatabaseStats:
    """Database statistics and metrics."""

    # Basic table statistics
    scenes_count: int = 0
    characters_count: int = 0
    memory_entries_count: int = 0
    bookmarks_count: int = 0

    # Size information
    total_size_bytes: int = 0
    total_size_mb: float = 0.0

    # FTS statistics
    fts_enabled: bool = False
    fts_indexes_count: int = 0
    fts_total_docs: int = 0

    # Performance metrics
    total_tables: int = 0
    index_count: int = 0

    # Database file info
    database_path: str = ""
    last_modified: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for backward compatibility."""
        return {
            "scenes_count": self.scenes_count,
            "characters_count": self.characters_count,
            "memory_entries_count": self.memory_entries_count,
            "bookmarks_count": self.bookmarks_count,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": self.total_size_mb,
            "fts_enabled": self.fts_enabled,
            "fts_indexes_count": self.fts_indexes_count,
            "fts_total_docs": self.fts_total_docs,
            "total_tables": self.total_tables,
            "index_count": self.index_count,
            "database_path": self.database_path,
            "last_modified": self.last_modified,
        }


@dataclass
class FTSIndexInfo:
    """Information about an FTS index."""

    table_name: str
    index_name: str
    total_docs: int = 0
    total_terms: int = 0
    size_bytes: int = 0
    last_optimized: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "table_name": self.table_name,
            "index_name": self.index_name,
            "total_docs": self.total_docs,
            "total_terms": self.total_terms,
            "size_bytes": self.size_bytes,
            "last_optimized": self.last_optimized,
        }
