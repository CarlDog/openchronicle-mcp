"""Scene analysis package init (import-safe).

- Avoid any runtime imports that could execute class bodies.
- Provide TYPE_CHECKING-only hints for tooling.
- No legacy aliases; use `scene_statistics.SceneStatistics` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Hints only; do not import at runtime
    try:
        from .scene_statistics import SceneStatistics  # noqa: F401
    except ImportError:  # pragma: no cover - defensive for tooling only
        SceneStatistics = None  # type: ignore
    except Exception:  # pragma: no cover - unexpected import error
        SceneStatistics = None  # type: ignore
    # No other runtime imports.

__all__: list[str] = []
