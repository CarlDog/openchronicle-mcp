"""Envelope model for passing data with identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .identifier import Identifier

T = TypeVar("T")


@dataclass
class Envelope(Generic[T]):
    """Data envelope carrying an identifier and payload."""

    identifier: Identifier
    payload: T
