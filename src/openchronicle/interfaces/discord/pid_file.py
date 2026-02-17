"""PID file management for the Discord bot process."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PID_PATH = "data/discord_bot.pid"


class PidFile:
    """Write/read a PID file to prevent duplicate bot instances.

    Follows the same atomic-write pattern as ``SessionManager``:
    write to ``.tmp``, then ``os.replace()`` for crash safety.
    """

    def __init__(self, path: str = DEFAULT_PID_PATH) -> None:
        self._path = Path(path)

    def read_pid(self) -> int | None:
        """Return the PID stored on disk, or None if missing/corrupt."""
        try:
            text = self._path.read_text(encoding="utf-8").strip()
            return int(text)
        except (FileNotFoundError, ValueError):
            return None

    def is_alive(self) -> bool:
        """Check whether the recorded PID refers to a running process."""
        pid = self.read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except PermissionError:
            # Process exists but we can't signal it — still alive.
            return True
        except OSError:
            # ProcessLookupError (Unix) or generic OSError (Windows)
            # for a non-existent PID.
            return False
        return True

    def acquire(self) -> None:
        """Write the current process PID to disk (atomic)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(str(os.getpid()), encoding="utf-8")
        os.replace(str(tmp), str(self._path))

    def release(self) -> None:
        """Remove the PID file. Safe to call even if already gone."""
        self._path.unlink(missing_ok=True)
