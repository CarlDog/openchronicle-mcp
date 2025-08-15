import json
import os
from typing import Any


STORYPACKS_DIR = os.path.join(os.getcwd(), "storage", "storypacks")


def list_storypacks() -> list[str]:
    """List all valid storypacks with meta.json."""
    storypacks: list[str] = []
    for name in os.listdir(STORYPACKS_DIR):
        path = os.path.join(STORYPACKS_DIR, name)
        if os.path.isdir(path):
            # Check for meta.json only
            if os.path.exists(os.path.join(path, "meta.json")):
                storypacks.append(name)
    return storypacks


def load_meta(path: str) -> dict[str, Any]:
    """Load meta.json contents."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
        # Ensure we return the expected type
        return data if isinstance(data, dict) else {}


def load_storypack(name: str) -> dict[str, Any]:
    """Load a storypack by folder name."""
    path = os.path.join(STORYPACKS_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Storypack '{name}' not found in {STORYPACKS_DIR}")

    # Check for meta.json only
    meta_json_path = os.path.join(path, "meta.json")

    if os.path.exists(meta_json_path):
        meta_path = meta_json_path
    else:
        raise FileNotFoundError(f"meta.json missing in storypack '{name}'")

    meta = load_meta(meta_path)

    return {
        "id": name,
        "path": path,
        "meta": meta,
        "canon_dir": os.path.join(path, "canon"),
        "characters_dir": os.path.join(path, "characters"),
        "memory_dir": os.path.join(path, "memory"),
        "style_guide": (
            os.path.join(path, "style_guide.json")
            if os.path.exists(os.path.join(path, "style_guide.json"))
            else os.path.join(path, "style_guide.md")
        ),
    }
