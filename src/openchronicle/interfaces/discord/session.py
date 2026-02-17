"""Discord user → OC conversation session mapping.

JSON-file-backed dict mapping Discord user IDs (str) to OC conversation IDs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class SessionManager:
    """Manages Discord user ID → OC conversation ID mapping.

    Thread-safe for single-process use (discord.py is single-threaded async).
    File is read/written atomically on each operation to survive restarts.
    """

    def __init__(self, path: str = "data/discord_sessions.json") -> None:
        self._path = Path(path)

    def get_conversation_id(self, discord_user_id: str) -> str | None:
        """Get the conversation ID for a Discord user, or None if not mapped."""
        sessions = self._load()
        return sessions.get(discord_user_id)

    def set_conversation_id(self, discord_user_id: str, conversation_id: str) -> None:
        """Map a Discord user to a conversation ID."""
        sessions = self._load()
        sessions[discord_user_id] = conversation_id
        self._save(sessions)

    def clear(self, discord_user_id: str) -> None:
        """Remove the session mapping for a Discord user."""
        sessions = self._load()
        sessions.pop(discord_user_id, None)
        self._save(sessions)

    def _load(self) -> dict[str, str]:
        """Load sessions from disk. Returns empty dict if file doesn't exist."""
        if not self._path.exists():
            return {}
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                return {}
            return data
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, sessions: dict[str, str]) -> None:
        """Write sessions atomically to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(self._path))
