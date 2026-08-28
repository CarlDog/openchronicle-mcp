"""Return recent OpenChronicle working context to a Codex compact resume."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

PROJECT_ID = "fe2ef898-0152-40a4-af97-ed97cc86ca45"


def _load_context() -> str:
    executable = shutil.which("oc")
    if executable is None:
        return (
            "OpenChronicle context reload was unavailable because the `oc` CLI "
            "is not on PATH. Search OpenChronicle manually before continuing."
        )

    command = [
        executable,
        "memory",
        "search",
        "context scope milestone",
        "--project-id",
        PROJECT_ID,
        "--tags",
        "context",
        "--top-k",
        "3",
        "--full",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (
            f"OpenChronicle context reload failed ({type(exc).__name__}). "
            "Search OpenChronicle manually before continuing."
        )

    if completed.returncode != 0:
        return (
            "OpenChronicle context reload did not complete successfully. "
            "Search OpenChronicle manually before continuing."
        )

    context = completed.stdout.strip()
    if not context:
        return "No recent OpenChronicle working-state memories were returned."
    return (
        "OpenChronicle working-state memories reloaded after compaction:\n\n"
        f"{context}\n\n"
        "Search OpenChronicle for task-specific decisions before continuing."
    )


def main() -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _load_context(),
        }
    }
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
