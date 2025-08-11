"""
Infrastructure layer repositories for OpenChronicle.

This module provides concrete implementations of the repository interfaces
defined in the application layer. These repositories handle data persistence
and retrieval from various storage systems.
"""

import json
import sqlite3
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
from pathlib import Path
import aiofiles
import asyncio
from contextlib import asynccontextmanager

from ...domain import Story, Character, Scene, StoryStatus
from ...application.orchestrators import (
    StoryRepository,
    CharacterRepository,
    SceneRepository,
)


class FileSystemStoryRepository:
    """File-based repository for Story entities."""

    def __init__(self, storage_path: str = "storage/stories"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def save(self, story: Story) -> bool:
        """Save a story to the file system."""
        try:
            story_file = self.storage_path / f"{story.id}.json"
            story_data = {
                "id": story.id,
                "title": story.title,
                "description": story.description,
                "status": story.status.value if story.status else "active",
                "world_state": story.world_state,
                "created_at": (
                    story.created_at.isoformat() if story.created_at else None
                ),
                "updated_at": (
                    story.updated_at.isoformat() if story.updated_at else None
                ),
            }

            async with aiofiles.open(story_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(story_data, indent=2, ensure_ascii=False))

            return True
        except Exception as e:
            print(f"Error saving story {story.id}: {e}")
            return False

    async def get_by_id(self, story_id: str) -> Optional[Story]:
        """Get a story by ID."""
        try:
            story_file = self.storage_path / f"{story_id}.json"
            if not story_file.exists():
                return None

            async with aiofiles.open(story_file, "r", encoding="utf-8") as f:
                content = await f.read()
                story_data = json.loads(content)

            return Story(
                id=story_data["id"],
                title=story_data["title"],
                description=story_data.get("description", ""),
                status=StoryStatus(story_data.get("status", "active")),
                world_state=story_data.get("world_state", {}),
                created_at=(
                    datetime.fromisoformat(story_data["created_at"])
                    if story_data.get("created_at")
                    else None
                ),
                updated_at=(
                    datetime.fromisoformat(story_data["updated_at"])
                    if story_data.get("updated_at")
                    else None
                ),
            )
        except Exception as e:
            print(f"Error loading story {story_id}: {e}")
            return None

    async def delete(self, story_id: str) -> bool:
        """Delete a story."""
        try:
            story_file = self.storage_path / f"{story_id}.json"
            if story_file.exists():
                story_file.unlink()
            return True
        except Exception as e:
            print(f"Error deleting story {story_id}: {e}")
            return False

    async def list_all(self, limit: int = 50, offset: int = 0) -> List[Story]:
        """List all stories with pagination."""
        stories = []
        try:
            story_files = list(self.storage_path.glob("*.json"))
            story_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            for story_file in story_files[offset : offset + limit]:
                story_id = story_file.stem
                story = await self.get_by_id(story_id)
                if story:
                    stories.append(story)

            return stories
        except Exception as e:
            print(f"Error listing stories: {e}")
            return []


class FileSystemCharacterRepository:
    """File-based repository for Character entities."""

    def __init__(self, storage_path: str = "storage/characters"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def save(self, character: Character) -> bool:
        """Save a character to the file system."""
        try:
            char_file = self.storage_path / f"{character.id}.json"
            char_data = {
                "id": character.id,
                "story_id": character.story_id,
                "name": character.name,
                "description": character.description,
                "personality_traits": character.personality_traits,
                "background": character.background,
                "goals": character.goals,
                "emotional_state": character.emotional_state,
                "relationships": character.relationships,
                "memory_profile": character.memory_profile,
                "is_active": character.is_active,
                "created_at": (
                    character.created_at.isoformat() if character.created_at else None
                ),
                "updated_at": (
                    character.updated_at.isoformat() if character.updated_at else None
                ),
            }

            async with aiofiles.open(char_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(char_data, indent=2, ensure_ascii=False))

            return True
        except Exception as e:
            print(f"Error saving character {character.id}: {e}")
            return False

    async def get_by_id(self, character_id: str) -> Optional[Character]:
        """Get a character by ID."""
        try:
            char_file = self.storage_path / f"{character_id}.json"
            if not char_file.exists():
                return None

            async with aiofiles.open(char_file, "r", encoding="utf-8") as f:
                content = await f.read()
                char_data = json.loads(content)

            return Character(
                id=char_data["id"],
                story_id=char_data["story_id"],
                name=char_data["name"],
                description=char_data.get("description", ""),
                personality_traits=char_data.get("personality_traits", {}),
                background=char_data.get("background", ""),
                goals=char_data.get("goals", []),
                emotional_state=char_data.get("emotional_state", {}),
                relationships=char_data.get("relationships", {}),
                memory_profile=char_data.get("memory_profile", {}),
                is_active=char_data.get("is_active", True),
                created_at=(
                    datetime.fromisoformat(char_data["created_at"])
                    if char_data.get("created_at")
                    else None
                ),
                updated_at=(
                    datetime.fromisoformat(char_data["updated_at"])
                    if char_data.get("updated_at")
                    else None
                ),
            )
        except Exception as e:
            print(f"Error loading character {character_id}: {e}")
            return None

    async def get_by_story(self, story_id: str) -> List[Character]:
        """Get all characters in a story."""
        characters = []
        try:
            for char_file in self.storage_path.glob("*.json"):
                character = await self.get_by_id(char_file.stem)
                if character and character.story_id == story_id:
                    characters.append(character)

            return sorted(characters, key=lambda c: c.created_at or datetime.min)
        except Exception as e:
            print(f"Error getting characters for story {story_id}: {e}")
            return []


class FileSystemSceneRepository:
    """File-based repository for Scene entities."""

    def __init__(self, storage_path: str = "storage/scenes"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def save(self, scene: Scene) -> bool:
        """Save a scene to the file system."""
        try:
            scene_file = self.storage_path / f"{scene.id}.json"
            scene_data = {
                "id": scene.id,
                "story_id": scene.story_id,
                "user_input": scene.user_input,
                "ai_response": scene.ai_response,
                "model_used": scene.model_used,
                "tokens_used": scene.tokens_used,
                "generation_time": scene.generation_time,
                "scene_type": scene.scene_type,
                "participant_ids": scene.participant_ids,
                "location": scene.location,
                "metadata": scene.metadata,
                "created_at": (
                    scene.created_at.isoformat() if scene.created_at else None
                ),
            }

            async with aiofiles.open(scene_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(scene_data, indent=2, ensure_ascii=False))

            return True
        except Exception as e:
            print(f"Error saving scene {scene.id}: {e}")
            return False

    async def get_by_id(self, scene_id: str) -> Optional[Scene]:
        """Get a scene by ID."""
        try:
            scene_file = self.storage_path / f"{scene_id}.json"
            if not scene_file.exists():
                return None

            async with aiofiles.open(scene_file, "r", encoding="utf-8") as f:
                content = await f.read()
                scene_data = json.loads(content)

            return Scene(
                id=scene_data["id"],
                story_id=scene_data["story_id"],
                user_input=scene_data["user_input"],
                ai_response=scene_data["ai_response"],
                model_used=scene_data["model_used"],
                tokens_used=scene_data.get("tokens_used", 0),
                generation_time=scene_data.get("generation_time", 0.0),
                scene_type=scene_data.get("scene_type", "narrative"),
                participant_ids=scene_data.get("participant_ids", []),
                location=scene_data.get("location", ""),
                metadata=scene_data.get("metadata", {}),
                created_at=(
                    datetime.fromisoformat(scene_data["created_at"])
                    if scene_data.get("created_at")
                    else None
                ),
            )
        except Exception as e:
            print(f"Error loading scene {scene_id}: {e}")
            return None

    async def get_by_story(
        self, story_id: str, limit: int = 50, offset: int = 0
    ) -> List[Scene]:
        """Get scenes for a story with pagination."""
        scenes = []
        try:
            story_scenes = []
            for scene_file in self.storage_path.glob("*.json"):
                scene = await self.get_by_id(scene_file.stem)
                if scene and scene.story_id == story_id:
                    story_scenes.append(scene)

            # Sort by creation time
            story_scenes.sort(key=lambda s: s.created_at or datetime.min)

            return story_scenes[offset : offset + limit]
        except Exception as e:
            print(f"Error getting scenes for story {story_id}: {e}")
            return []


# SQLite-based repositories for better performance and querying
class SQLiteStoryRepository:
    """SQLite-based repository for Story entities."""

    def __init__(self, db_path: str = "storage/openchronicle.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        asyncio.create_task(self._initialize_db())

    async def _initialize_db(self):
        """Initialize the database schema."""
        async with aiofiles.open("temp_init.sql", "w") as f:
            await f.write(
                """
                CREATE TABLE IF NOT EXISTS stories (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'active',
                    world_state TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
                CREATE INDEX IF NOT EXISTS idx_stories_updated ON stories(updated_at);
            """
            )

        # Execute in sync context for initialization
        conn = sqlite3.connect(self.db_path)
        try:
            with open("temp_init.sql", "r") as f:
                conn.executescript(f.read())
            conn.commit()
        finally:
            conn.close()
            Path("temp_init.sql").unlink(missing_ok=True)


# Export all repository implementations
__all__ = [
    "FileSystemStoryRepository",
    "FileSystemCharacterRepository",
    "FileSystemSceneRepository",
    "SQLiteStoryRepository",
]
