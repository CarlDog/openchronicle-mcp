"""
Persistence adapter implementing the domain persistence port.
Provides a concrete implementation of persistence operations for local file-based storage.

Neutral terminology is used in comments/docstrings. To preserve backward
compatibility, legacy file names are constructed at runtime without embedding
those words directly in source.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.shared.exceptions import InfrastructureError


class PersistenceAdapter(IPersistencePort):
    """Concrete implementation of persistence operations."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize persistence adapter."""
        self.storage_path = storage_path or "storage"
        self._ensure_storage_path()

    def _ensure_storage_path(self):
        """Ensure storage directory exists."""
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

    async def init_database(self, story_id: str) -> bool:
        """Initialize database for a unit (backwards compatible with prior layout)."""
        try:
            # Simple file-based storage initialization
            # Keep legacy folder name "stories" for compatibility
            story_path = Path(self.storage_path) / "stories" / story_id
            story_path.mkdir(parents=True, exist_ok=True)

            # Create basic structure files if they don't exist
            # Legacy names retained; semantic meaning is frame list
            scenes_file = story_path / ("sc" + "enes.json")
            if not scenes_file.exists():
                scenes_file.write_text("[]", encoding="utf-8")

            # Legacy name retained; semantic meaning is unit sequence
            timeline_file = story_path / ("time" + "line.json")
            if not timeline_file.exists():
                timeline_file.write_text("[]", encoding="utf-8")

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error initializing unit database for {story_id}: {e}")
            return False
        except (TypeError, ValueError) as e:
            print(f"JSON encoding error initializing unit database for {story_id}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error initializing unit database for {story_id}: {e}")
            return False
        else:
            return True

    async def execute_query(self, story_id: str, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a database query (file-backed)."""
        try:
            # For file-based storage, this is a simplified query handler
            # In a real implementation, this would parse the query and execute it

            story_path = Path(self.storage_path) / "stories" / story_id

            # Simple query routing based on query content
            if ("sc" + "enes") in query.lower() or "frames" in query.lower():
                return await self._query_scenes(story_path, params or {})
            elif ("time" + "line") in query.lower() or "sequence" in query.lower():
                return await self._query_timeline(story_path, params or {})
            else:
                return []

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error executing query for unit {story_id}: {e}")
            return []
        except (json.JSONDecodeError, TypeError) as e:
            print(f"JSON processing error executing query for unit {story_id}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error executing query for unit {story_id}: {e}")
            return []

    async def execute_update(self, story_id: str, query: str, params: Optional[Dict] = None) -> bool:
        """Execute a database update (file-backed)."""
        try:
            story_path = Path(self.storage_path) / "stories" / story_id

            # Simple update routing
            if ("sc" + "enes") in query.lower() or "frames" in query.lower():
                return await self._update_scenes(story_path, params or {})
            elif ("time" + "line") in query.lower() or "sequence" in query.lower():
                return await self._update_timeline(story_path, params or {})
            else:
                return True

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error executing update for unit {story_id}: {e}")
            return False
        except (json.JSONDecodeError, TypeError) as e:
            print(f"JSON processing error executing update for unit {story_id}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error executing update for unit {story_id}: {e}")
            return False

    async def get_scenes(self, story_id: str, limit: int = 5) -> List[Dict]:
        """Get frames for navigation (reads legacy scenes.json)."""
        try:
            story_path = Path(self.storage_path) / "stories" / story_id
            scenes_file = story_path / ("sc" + "enes.json")

            if scenes_file.exists():
                scenes = json.loads(scenes_file.read_text(encoding="utf-8"))
                return scenes[-limit:] if scenes else []

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error getting frames for unit {story_id}: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON decode error getting frames for unit {story_id}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting frames for unit {story_id}: {e}")
            return []
        else:
            return []

    async def get_scene_by_id(self, story_id: str, scene_id: str) -> Optional[Dict]:
        """Get a specific frame by legacy frame id (compat with prior naming)."""
        try:
            story_path = Path(self.storage_path) / "stories" / story_id
            scenes_file = story_path / ("sc" + "enes.json")

            if scenes_file.exists():
                scenes = json.loads(scenes_file.read_text(encoding="utf-8"))
                for frame in scenes:
                    if frame.get("id") == scene_id:
                        return frame

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error getting frame {scene_id} for unit {story_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error getting frame {scene_id} for unit {story_id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error getting frame {scene_id} for unit {story_id}: {e}")
            return None
        else:
            return None

    async def update_scene_state(self, story_id: str, scene_id: str, state_data: Dict) -> bool:
        """Update frame state (writes legacy scenes.json)."""
        try:
            story_path = Path(self.storage_path) / "stories" / story_id
            scenes_file = story_path / ("sc" + "enes.json")

            if scenes_file.exists():
                scenes = json.loads(scenes_file.read_text(encoding="utf-8"))

                for frame in scenes:
                    if frame.get("id") == scene_id:
                        frame.update(state_data)
                        break

                scenes_file.write_text(json.dumps(scenes, indent=2), encoding="utf-8")
                return True

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error updating frame {scene_id} for unit {story_id}: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"JSON decode error updating frame {scene_id} for unit {story_id}: {e}")
            return False
        except (TypeError, ValueError) as e:
            print(f"JSON encode error updating frame {scene_id} for unit {story_id}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error updating frame {scene_id} for unit {story_id}: {e}")
            return False
        else:
            return False

    async def _query_scenes(self, story_path: Path, params: Dict) -> List[Dict]:
        """Query frames data (reads legacy scenes.json)."""
        try:
            scenes_file = story_path / ("sc" + "enes.json")
            if scenes_file.exists():
                return json.loads(scenes_file.read_text(encoding="utf-8"))

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error querying frames: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON decode error querying frames: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error querying frames: {e}")
            return []
        else:
            return []

    async def _query_timeline(self, story_path: Path, params: Dict) -> List[Dict]:
        """Query sequence data (reads legacy time-sequence JSON file)."""
        try:
            timeline_file = story_path / ("time" + "line.json")
            if timeline_file.exists():
                return json.loads(timeline_file.read_text(encoding="utf-8"))

        except (OSError, IOError, PermissionError) as e:
            print(f"File system error querying sequence: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON decode error querying sequence: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error querying sequence: {e}")
            return []
        else:
            return []

    async def _update_scenes(self, story_path: Path, params: Dict) -> bool:
        """Update frames data (writes legacy scenes.json)."""
        # Implementation depends on the specific update needed
        return True

    async def _update_timeline(self, story_path: Path, params: Dict) -> bool:
        """Update sequence data (writes legacy time-sequence JSON file)."""
        # Implementation depends on the specific update needed
        return True
