import os
import json

STORYPACKS_DIR = os.path.join(os.getcwd(), "storage", "storypacks")


def list_storypacks():
    """List all valid storypacks with meta.json (preferred) or meta.yaml (legacy)."""
    storypacks = []
    for name in os.listdir(STORYPACKS_DIR):
        path = os.path.join(STORYPACKS_DIR, name)
        if os.path.isdir(path):
            # Check for meta.json first, then meta.yaml for backward compatibility
            if (os.path.exists(os.path.join(path, "meta.json")) or 
                os.path.exists(os.path.join(path, "meta.yaml"))):
                storypacks.append(name)
    return storypacks


def load_meta(path):
    """Load meta.json or meta.yaml contents."""
    if path.endswith('.json'):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:  # yaml
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def load_storypack(name):
    """Load a storypack by folder name."""
    path = os.path.join(STORYPACKS_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Storypack '{name}' not found in {STORYPACKS_DIR}")

    # Check for meta.json first, then meta.yaml for backward compatibility
    meta_json_path = os.path.join(path, "meta.json")
    meta_yaml_path = os.path.join(path, "meta.yaml")
    
    if os.path.exists(meta_json_path):
        meta_path = meta_json_path
    elif os.path.exists(meta_yaml_path):
        meta_path = meta_yaml_path
    else:
        raise FileNotFoundError(f"meta.json or meta.yaml missing in storypack '{name}'")

    meta = load_meta(meta_path)

    return {
        "id": name,
        "path": path,
        "meta": meta,
        "canon_dir": os.path.join(path, "canon"),
        "characters_dir": os.path.join(path, "characters"),
        "memory_dir": os.path.join(path, "memory"),
        "style_guide": os.path.join(path, "style_guide.json") if os.path.exists(os.path.join(path, "style_guide.json")) else os.path.join(path, "style_guide.md"),
    }
