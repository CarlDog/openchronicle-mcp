"""JSON configuration file loading.

Loads ``${OC_CONFIG_DIR}/core.json``. Missing file is silently treated
as an empty dict (backward compatible). Invalid JSON raises
``ConfigLoadError`` with the file path. v2's per-plugin config files
(``<plugins_dir>/<plugin>/config.json``) are gone with the plugin
system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# The single core config file that the system recognizes.
CORE_CONFIG_NAME = "core.json"


class ConfigLoadError(Exception):
    """Raised when a JSON config file exists but contains invalid JSON."""

    def __init__(self, path: str | Path, cause: Exception) -> None:
        self.path = str(path)
        self.cause = cause
        super().__init__(f"Invalid JSON in config file {self.path}: {cause}")


def load_json_config(path: str | Path) -> dict:
    """Load a single JSON config file.

    Returns an empty dict if the file does not exist.
    Raises ``ConfigLoadError`` if the file exists but is not valid JSON.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        text = p.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(p, exc) from exc
    if not isinstance(data, dict):
        raise ConfigLoadError(p, ValueError(f"Expected JSON object, got {type(data).__name__}"))
    return data


def load_config_files(config_dir: str | Path) -> dict[str, Any]:
    """Load ``core.json`` from the given directory.

    Returns the parsed dict (e.g.
    ``{"embedding": {...}, "api": {...}, "maintenance": {...}}``) or
    an empty dict if the file is missing.
    """
    config_path = Path(config_dir)
    return load_json_config(config_path / CORE_CONFIG_NAME)
