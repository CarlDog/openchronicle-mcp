"""
Full-Text Search (FTS) management.

Handles FTS5 operations, index optimization, and search capabilities.
"""

import sqlite3
from typing import Optional, Dict, Any, List

from .connection import ConnectionManager
from .shared import FTSIndexInfo
from src.openchronicle.shared.security import SQLSecurityValidator, SecurityContext
from src.openchronicle.shared.logging_system import log_warning, log_error


class FTSManager:
    """Manages Full-Text Search operations and indexes."""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.sql_validator = SQLSecurityValidator()

    def has_fts5_support(self) -> bool:
        """Check if SQLite supports FTS5."""
        try:
            with sqlite3.connect(":memory:") as conn:
                context = SecurityContext(
                    operation="fts5_check", component="FTSManager"
                )
                query = "CREATE VIRTUAL TABLE test_fts USING fts5(content)"

                # Validate the query
                validation_result = self.sql_validator.validate_sql_query(
                    query, context
                )
                if not validation_result.is_valid:
                    log_warning(
                        f"FTS5 check query validation failed: {validation_result.error_message}"
                    )
                    return False

                cursor = conn.cursor()
                cursor.execute(query)
                cursor.execute("DROP TABLE test_fts")
                return True
        except sqlite3.OperationalError:
            return False

    def optimize_fts_index(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Optimize FTS indexes for better performance."""
        if not self.has_fts5_support():
            return False

        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                context = SecurityContext(
                    operation="optimize_fts", component="FTSManager", user_id=story_id
                )

                # Get list of FTS tables using secure query execution
                list_query = """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE '%_fts'
                """

                cursor = self.sql_validator.execute_safe_query(
                    conn, list_query, (), context
                )
                fts_tables = [row[0] for row in cursor.fetchall()]

                # Optimize each FTS table
                for table in fts_tables:
                    try:
                        # Validate table name to prevent injection
                        if not table.replace("_", "").replace("-", "").isalnum():
                            log_warning(f"Invalid FTS table name skipped: {table}")
                            continue

                        optimize_query = (
                            f"INSERT INTO {table}({table}) VALUES('optimize')"
                        )

                        # Validate and execute optimization query
                        validation_result = self.sql_validator.validate_sql_query(
                            optimize_query, context
                        )
                        if validation_result.is_valid:
                            self.sql_validator.execute_safe_query(
                                conn, optimize_query, (), context
                            )
                        else:
                            log_warning(
                                f"FTS optimization query validation failed for {table}: {validation_result.error_message}"
                            )
                    except sqlite3.OperationalError as e:
                        print(f"Warning: Could not optimize FTS table {table}: {e}")
                        continue

                conn.commit()
                return True

        except Exception as e:
            print(f"Error optimizing FTS indexes: {e}")
            return False

    def rebuild_fts_index(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Rebuild FTS indexes from scratch."""
        if not self.has_fts5_support():
            return False

        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Get list of FTS tables
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE '%_fts'
                """
                )
                fts_tables = [row[0] for row in cursor.fetchall()]

                # Rebuild each FTS table
                for table in fts_tables:
                    try:
                        cursor.execute(
                            f"INSERT INTO {table}({table}) VALUES('rebuild')"
                        )
                    except sqlite3.OperationalError as e:
                        print(f"Warning: Could not rebuild FTS table {table}: {e}")
                        continue

                conn.commit()
                return True

        except Exception as e:
            print(f"Error rebuilding FTS indexes: {e}")
            return False

    def get_fts_stats(
        self, story_id: str, is_test: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get FTS index statistics."""
        stats = {
            "fts_enabled": self.has_fts5_support(),
            "indexes": [],
            "total_docs": 0,
            "total_terms": 0,
        }

        if not stats["fts_enabled"]:
            return stats

        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Get list of FTS tables
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE '%_fts'
                """
                )
                fts_tables = [row[0] for row in cursor.fetchall()]

                for table in fts_tables:
                    try:
                        # Get document count
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        doc_count = cursor.fetchone()[0]

                        # Create index info
                        index_info = FTSIndexInfo(
                            table_name=table, index_name=table, total_docs=doc_count
                        )

                        stats["indexes"].append(index_info.to_dict())
                        stats["total_docs"] += doc_count

                    except sqlite3.OperationalError as e:
                        print(
                            f"Warning: Could not get stats for FTS table {table}: {e}"
                        )
                        continue

        except Exception as e:
            print(f"Error getting FTS stats: {e}")

        return stats

    def sync_fts_table(
        self,
        story_id: str,
        source_table: str,
        fts_table: str,
        columns: List[str],
        is_test: Optional[bool] = None,
    ) -> bool:
        """Synchronize FTS table with source table data."""
        if not self.has_fts5_support():
            return False

        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Clear existing FTS data
                cursor.execute(f"DELETE FROM {fts_table}")

                # Build column list for SELECT and INSERT
                column_list = ", ".join(columns)
                placeholders = ", ".join(["?" for _ in columns])

                # Copy data from source to FTS table
                cursor.execute(f"SELECT {column_list} FROM {source_table}")
                rows = cursor.fetchall()

                for row in rows:
                    cursor.execute(
                        f"INSERT INTO {fts_table}({column_list}) VALUES ({placeholders})",
                        row,
                    )

                conn.commit()
                return True

        except Exception as e:
            print(f"Error syncing FTS table {fts_table}: {e}")
            return False

    def search_fts(
        self,
        story_id: str,
        fts_table: str,
        query: str,
        limit: int = 50,
        is_test: Optional[bool] = None,
    ) -> List[sqlite3.Row]:
        """Perform FTS search on specified table."""
        if not self.has_fts5_support():
            return []

        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Escape FTS query
                escaped_query = self._escape_fts_query(query)

                # Execute FTS search
                cursor.execute(
                    f"SELECT * FROM {fts_table} WHERE {fts_table} MATCH ? ORDER BY rank LIMIT ?",
                    (escaped_query, limit),
                )

                return cursor.fetchall()

        except Exception as e:
            print(f"Error performing FTS search: {e}")
            return []

    def _escape_fts_query(self, query: str) -> str:
        """Escape special characters in FTS query."""
        # Basic FTS5 query escaping
        # Replace problematic characters that could break FTS syntax
        query = query.replace('"', '""')  # Escape quotes
        query = query.replace("'", "''")  # Escape single quotes

        # Remove other special FTS characters that could cause issues
        special_chars = ["(", ")", "*", "^", ":", "!"]
        for char in special_chars:
            query = query.replace(char, " ")

        # Clean up multiple spaces
        query = " ".join(query.split())

        return query
