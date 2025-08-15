from typing import Dict, Any


def metadata() -> dict:
    return {"name": "storytelling", "version": "0.1.0"}


def register(container: Dict[str, Any]) -> None:
    # Phase 1: no-op registration; wiring will come in Phase 4.
    # Keep this function so bootstrap can call it safely.
    pass
