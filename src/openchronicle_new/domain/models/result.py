"""Generic result container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


@dataclass
class Result(Generic[T, E]):
    """Represents success or failure of an operation."""

    ok: bool
    value: Optional[T] = None
    error: Optional[E] = None
