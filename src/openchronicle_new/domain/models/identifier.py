"""Basic identifier model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Identifier:
    """Simple string identifier."""

    value: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value
