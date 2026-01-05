"""
Storytelling-specific database operations.

Extends core database operations with storytelling domain logic.
"""

from typing import List
from typing import Optional

from .base import BaseDatabaseOperations


class StorytellingDatabaseOperations(BaseDatabaseOperations):
    """Handles storytelling-specific database operations."""

    def get_schema_statements(self) -> List[str]:
        """Get storytelling-specific database schema creation statements."""
        return [
            """CREATE TABLE IF NOT EXISTS scenes (
                scene_id TEXT PRIMARY KEY,
                timestamp TEXT,
                input TEXT,
                output TEXT,
                memory_snapshot TEXT,
                flags TEXT,
                canon_refs TEXT,
                analysis TEXT,
                scene_label TEXT,
                structured_tags TEXT,
                story_id TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS characters (
                character_id TEXT,
                character_name TEXT,
                appearance TEXT,
                personality TEXT,
                character_data TEXT,
                last_modified TEXT,
                is_active INTEGER DEFAULT 1,
                memory_state TEXT,
                interaction_count INTEGER DEFAULT 0,
                story_id TEXT,
                PRIMARY KEY (character_id, story_id)
            )""",
            """CREATE TABLE IF NOT EXISTS stories (
                story_id TEXT PRIMARY KEY,
                story_name TEXT,
                description TEXT,
                genre TEXT,
                created_date TEXT,
                last_modified TEXT,
                scene_count INTEGER DEFAULT 0,
                character_count INTEGER DEFAULT 0,
                metadata TEXT
            )""",
        ]

    def init_database(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Initialize the storytelling database with required tables."""
        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Execute all schema statements
                for schema_statement in self.get_schema_statements():
                    cursor.execute(schema_statement)

                conn.commit()
                return True
        except Exception as e:
            print(f"Database initialization failed: {e}")
            return False
