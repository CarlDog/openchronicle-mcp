"""Environment-based configuration adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ConfigEnv:
    """Minimal environment configuration reader."""

    def get(self, key: str, default: str | None = None) -> str | None:
        return os.getenv(key, default)
