"""
Storytelling-specific database migration utilities.

Handles data migration from JSON files to SQLite database for storytelling domain.
"""

import json
import os
import sqlite3
from typing import Any
from typing import Dict
from typing import List

from ..base import BaseMigrationManager
from ..base import ConnectionManager
from ..storytelling_operations import StorytellingDatabaseOperations as DatabaseOperations


class StorytellingMigrationManager(BaseMigrationManager):
    """Manages storytelling data migration from JSON to SQLite."""

    def __init__(self, connection_manager: ConnectionManager, operations: DatabaseOperations):
        super().__init__(connection_manager, operations)

    def migrate_data(self, entity_id: str, source_config: Dict[str, Any]) -> bool:
        """
        Migrate storytelling data from JSON files to database.

        Args:
            entity_id: Story ID for migration
            source_config: Configuration specifying source data paths
        """
        return self.migrate_from_json(entity_id)

    def get_migration_schema(self) -> List[str]:
        """Get storytelling-specific database schema creation statements."""
        return [
            """CREATE TABLE IF NOT EXISTS scenes (
                scene_id TEXT PRIMARY KEY,
                scene_number INTEGER,
                content TEXT,
                memory_state TEXT,
                characters_state TEXT,
                character_names TEXT,
                choices TEXT,
                scene_label TEXT,
                timestamp TEXT,
                story_id TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS characters (
                character_id TEXT PRIMARY KEY,
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

    def migrate_from_json(self, story_id: str) -> bool:
        """Migrate data from JSON files to database."""
        try:
            # Ensure database is initialized
            if not self.operations.init_database(story_id):
                return False

            # Get story directory paths
            story_dir = os.path.join("storage", "storypacks", story_id)

            if not os.path.exists(story_dir):
                print(f"Story directory not found: {story_dir}")
                return False

            success = True

            # Migrate scenes
            if not self._migrate_scenes(story_id, story_dir):
                success = False

            # Migrate characters
            if not self._migrate_characters(story_id, story_dir):
                success = False

            # Migrate memory
            if not self._migrate_memory(story_id, story_dir):
                success = False

            # Migrate bookmarks
            if not self._migrate_bookmarks(story_id, story_dir):
                success = False

        except (OSError, IOError, PermissionError) as e:
            # Handle file system errors during JSON migration
            print(f"File system error during JSON migration: {e}")
            return False
        except sqlite3.Error as e:
            # Handle database errors during migration operations
            print(f"Database error during JSON migration: {e}")
            return False
        except Exception as e:
            # Handle any other unexpected errors during migration
            print(f"Unexpected error during JSON migration: {e}")
            return False
        else:
            return success

    def cleanup_json_files(self, story_id: str) -> bool:
        """Clean up JSON files after successful migration."""
        try:
            story_dir = os.path.join("storage", "storypacks", story_id)

            if not os.path.exists(story_dir):
                return True  # Nothing to clean up

            # JSON files to clean up
            json_files = [
                "scenes.json",
                "characters.json",
                "memory.json",
                "bookmarks.json",
            ]

            for filename in json_files:
                filepath = os.path.join(story_dir, filename)
                if os.path.exists(filepath):
                    try:
                        # Create backup before deletion
                        backup_path = f"{filepath}.backup"
                        if not os.path.exists(backup_path):
                            os.rename(filepath, backup_path)
                        else:
                            os.remove(filepath)
                    except (OSError, IOError, PermissionError) as e:
                        # Handle file operation errors during cleanup
                        print(f"File system error cleaning up {filepath}: {e}")
                    except Exception as e:
                        print(f"Unexpected error cleaning up {filepath}: {e}")

        except (OSError, IOError, PermissionError) as e:
            # Handle file system errors during JSON cleanup operations
            print(f"File system error cleaning up JSON files: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error cleaning up JSON files: {e}")
            return False
        else:
            return True
            return False

    def _migrate_scenes(self, story_id: str, story_dir: str) -> bool:
        """Migrate scenes from JSON to database."""
        scenes_file = os.path.join(story_dir, "scenes.json")

        if not os.path.exists(scenes_file):
            return True  # No scenes to migrate

        try:
            with open(scenes_file, encoding="utf-8") as f:
                scenes_data = json.load(f)

            if not isinstance(scenes_data, list):
                print(f"Invalid scenes data format in {scenes_file}")
                return False

            with self.connection_manager.get_connection(story_id) as conn:
                cursor = conn.cursor()

                for scene in scenes_data:
                    if not isinstance(scene, dict):
                        continue

                    # Extract scene data
                    scene_id = scene.get("id", "")
                    title = scene.get("title", "")
                    content = scene.get("content", "")
                    characters = json.dumps(scene.get("characters", []))
                    timestamp = scene.get("timestamp", 0.0)
                    token_usage = scene.get("token_usage", 0)
                    mood = scene.get("mood", "")
                    scene_data = json.dumps(scene)

                    # Insert into database
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO scenes
                        (id, title, content, characters, timestamp, token_usage, mood, scene_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            scene_id,
                            title,
                            content,
                            characters,
                            timestamp,
                            token_usage,
                            mood,
                            scene_data,
                        ),
                    )

                    # Insert into FTS if available
                    try:
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO scenes_fts (id, title, content, characters)
                            VALUES (?, ?, ?, ?)
                        """,
                            (scene_id, title, content, characters),
                        )
                    except sqlite3.OperationalError:
                        # FTS table doesn't exist
                        pass

                conn.commit()
                return True

        except (OSError, IOError, PermissionError) as e:
            # Handle file system errors during scene migration
            print(f"File system error migrating scenes: {e}")
            return False
        except (json.JSONDecodeError, ValueError) as e:
            # Handle JSON parsing errors during scene migration
            print(f"JSON parsing error migrating scenes: {e}")
            return False
        except sqlite3.Error as e:
            # Handle database errors during scene migration
            print(f"Database error migrating scenes: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error migrating scenes: {e}")
            return False

    def _migrate_characters(self, story_id: str, story_dir: str) -> bool:
        """Migrate characters from JSON to database."""
        characters_file = os.path.join(story_dir, "characters.json")

        if not os.path.exists(characters_file):
            return True  # No characters to migrate

        try:
            with open(characters_file, encoding="utf-8") as f:
                characters_data = json.load(f)

            if not isinstance(characters_data, dict):
                print(f"Invalid characters data format in {characters_file}")
                return False

            with self.connection_manager.get_connection(story_id) as conn:
                cursor = conn.cursor()

                for char_id, char_data in characters_data.items():
                    if not isinstance(char_data, dict):
                        continue

                    # Extract character data
                    name = char_data.get("name", "")
                    description = char_data.get("description", "")
                    personality = char_data.get("personality", "")
                    relationships = json.dumps(char_data.get("relationships", {}))
                    character_data = json.dumps(char_data)
                    created_at = char_data.get("created_at", 0.0)
                    updated_at = char_data.get("updated_at", 0.0)

                    # Insert into database
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO characters
                        (id, name, description, personality, relationships, character_data, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            char_id,
                            name,
                            description,
                            personality,
                            relationships,
                            character_data,
                            created_at,
                            updated_at,
                        ),
                    )

                    # Insert into FTS if available
                    try:
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO characters_fts (id, name, description, personality)
                            VALUES (?, ?, ?, ?)
                        """,
                            (char_id, name, description, personality),
                        )
                    except sqlite3.OperationalError:
                        # FTS table doesn't exist
                        pass

                conn.commit()
                return True

        except (OSError, IOError, PermissionError) as e:
            # Handle file system errors during character migration
            print(f"File system error migrating characters: {e}")
            return False
        except (json.JSONDecodeError, ValueError) as e:
            # Handle JSON parsing errors during character migration
            print(f"JSON parsing error migrating characters: {e}")
            return False
        except sqlite3.Error as e:
            # Handle database errors during character migration
            print(f"Database error migrating characters: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error migrating characters: {e}")
            return False

    def _migrate_memory(self, story_id: str, story_dir: str) -> bool:
        """Migrate memory from JSON to database."""
        memory_file = os.path.join(story_dir, "memory.json")

        if not os.path.exists(memory_file):
            return True  # No memory to migrate

        try:
            with open(memory_file, encoding="utf-8") as f:
                memory_data = json.load(f)

            if not isinstance(memory_data, list):
                print(f"Invalid memory data format in {memory_file}")
                return False

            with self.connection_manager.get_connection(story_id) as conn:
                cursor = conn.cursor()

                for memory in memory_data:
                    if not isinstance(memory, dict):
                        continue

                    # Extract memory data
                    memory_id = memory.get("id", "")
                    memory_type = memory.get("type", "")
                    content = memory.get("content", "")
                    characters = json.dumps(memory.get("characters", []))
                    importance = memory.get("importance", 0.0)
                    timestamp = memory.get("timestamp", 0.0)
                    memory_data_json = json.dumps(memory)

                    # Insert into database
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO memory
                        (id, type, content, characters, importance, timestamp, memory_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            memory_id,
                            memory_type,
                            content,
                            characters,
                            importance,
                            timestamp,
                            memory_data_json,
                        ),
                    )

                    # Insert into FTS if available
                    try:
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO memory_fts (id, content, characters)
                            VALUES (?, ?, ?)
                        """,
                            (memory_id, content, characters),
                        )
                    except sqlite3.OperationalError:
                        # FTS table doesn't exist
                        pass

                conn.commit()
                return True

        except (OSError, IOError, PermissionError) as e:
            # Handle file system errors during memory migration
            print(f"File system error migrating memory: {e}")
            return False
        except (json.JSONDecodeError, ValueError) as e:
            # Handle JSON parsing errors during memory migration
            print(f"JSON parsing error migrating memory: {e}")
            return False
        except sqlite3.Error as e:
            # Handle database errors during memory migration
            print(f"Database error migrating memory: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error migrating memory: {e}")
            return False

    def _migrate_bookmarks(self, story_id: str, story_dir: str) -> bool:
        """Migrate bookmarks from JSON to database."""
        bookmarks_file = os.path.join(story_dir, "bookmarks.json")

        if not os.path.exists(bookmarks_file):
            return True  # No bookmarks to migrate

        try:
            with open(bookmarks_file, encoding="utf-8") as f:
                bookmarks_data = json.load(f)

            if not isinstance(bookmarks_data, list):
                print(f"Invalid bookmarks data format in {bookmarks_file}")
                return False

            with self.connection_manager.get_connection(story_id) as conn:
                cursor = conn.cursor()

                for bookmark in bookmarks_data:
                    if not isinstance(bookmark, dict):
                        continue

                    # Extract bookmark data
                    bookmark_id = bookmark.get("id", "")
                    scene_id = bookmark.get("scene_id", "")
                    title = bookmark.get("title", "")
                    description = bookmark.get("description", "")
                    tags = json.dumps(bookmark.get("tags", []))
                    created_at = bookmark.get("created_at", 0.0)
                    bookmark_data = json.dumps(bookmark)

                    # Insert into database
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO bookmarks
                        (id, scene_id, title, description, tags, created_at, bookmark_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            bookmark_id,
                            scene_id,
                            title,
                            description,
                            tags,
                            created_at,
                            bookmark_data,
                        ),
                    )

                conn.commit()
                return True

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error migrating bookmarks: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"JSON processing error migrating bookmarks: {e}")
            return False
        except (ValueError, TypeError) as e:
            print(f"Data validation error migrating bookmarks: {e}")
            return False
        except Exception as e:
            print(f"Error migrating bookmarks: {e}")
            return False
