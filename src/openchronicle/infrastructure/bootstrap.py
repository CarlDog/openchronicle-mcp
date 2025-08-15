from __future__ import annotations

from typing import Any

from openchronicle.shared.centralized_config import get_config
from openchronicle.plugins import load_plugin


def build_container() -> dict[str, Any]:
    """Minimal DI container placeholder for Phase 1.

    This function should construct and return the application's DI container.
    It's intentionally minimal to avoid behavior changes. In the current codebase,
    orchestration objects are typically assembled in interface layers; we expose
    a dict to align with the acceptance criteria's return convention.
    """
    # NOTE: Phase 1 keeps existing wiring elsewhere; return a minimal facade slot.
    return {}


def build_facade():
    cfg = get_config()
    container = build_container()
    plugin = load_plugin(getattr(cfg, "mode", "storytelling"))
    if plugin:
        try:
            plugin.register(container)  # Phase 1 is no-op; safe call
        except Exception as e:  # pragma: no cover - defensive
            # Don’t break startup; log and continue for Phase 1
            # Replace with proper logging call if available
            print(f"[warn] plugin register failed: {e}")
    return container["core_facade"] if "core_facade" in container else container.get("facade")
