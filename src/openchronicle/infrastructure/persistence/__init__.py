# Database Systems Module
"""
Modular database management system for OpenChronicle.

This module provides organized database operations through:
- DatabaseOrchestrator: Main coordinator for all database operations
- Connection management with automatic test context detection
- FTS5 operations with fallback support
- Migration utilities for data transitions
- Statistics and optimization tools
"""

from .database_orchestrator import DatabaseOrchestrator
from .database_orchestrator import database_orchestrator


__all__ = [
    "DatabaseOrchestrator",
    "database_orchestrator",
]
