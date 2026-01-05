"""Domain persistence exception taxonomy.

Introduces typed errors for repository operations to replace broad generic exceptions
and sentinel return values. Breaking change embraced per project philosophy.
"""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Base error for persistence layer operations."""


class SaveSceneError(PersistenceError):
    """Raised when a scene cannot be saved."""


class LoadSceneError(PersistenceError):
    """Raised when a scene cannot be loaded due to an unexpected error (not 'not found')."""


class ListScenesError(PersistenceError):
    """Raised when scenes cannot be listed."""


class CountScenesError(PersistenceError):
    """Raised when scenes cannot be counted."""


class DeleteSceneError(PersistenceError):
    """Raised when a scene cannot be deleted."""


class RollbackSceneError(PersistenceError):
    """Raised when a rollback operation fails."""
