"""PID file management for the Discord bot process."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PID_PATH = "data/discord_bot.pid"


def _process_exists(pid: int) -> bool:
    """Check whether a process with ``pid`` is currently running.

    POSIX: ``os.kill(pid, 0)`` is a no-op signal that just probes existence
    (PermissionError implies the process exists but we lack signalling
    rights; ProcessLookupError/OSError implies it doesn't).

    Windows: ``os.kill(pid, 0)`` is **not** a probe — per Python docs, it
    maps to ``TerminateProcess`` with exit code 0, which would actually
    kill the process if it exists. Use ``OpenProcess`` via ctypes with
    ``PROCESS_QUERY_LIMITED_INFORMATION`` (a side-effect-free handle) to
    probe existence safely. Returning the handle null means the process
    is gone; otherwise it exists.
    """
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False

    try:
        os.kill(pid, 0)
    except PermissionError:
        # Process exists but we can't signal it — still alive.
        return True
    except OSError:
        # ProcessLookupError on Unix for a non-existent PID.
        return False
    return True


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
        """Check whether the recorded PID refers to a running process.

        Safe on Windows: uses OpenProcess instead of os.kill(pid, 0), which
        on Windows would actually terminate the target process rather than
        probing it.
        """
        pid = self.read_pid()
        if pid is None:
            return False
        return _process_exists(pid)

    def acquire(self) -> None:
        """Write the current process PID to disk (atomic)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(str(os.getpid()), encoding="utf-8")
        os.replace(str(tmp), str(self._path))

    def release(self) -> None:
        """Remove the PID file. Safe to call even if already gone."""
        self._path.unlink(missing_ok=True)
