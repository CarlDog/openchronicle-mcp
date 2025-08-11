"""
Memory Management System Package
==============================

This package provides a comprehensive memory management system for OpenChronicle,
organized into specialized components for different aspects of memory handling.

Package Structure:
- persistence/: Data storage and retrieval components
- character/: Character-specific memory management
- context/: Context generation and world state management
- shared/: Common models and utilities
- memory_orchestrator.py: Main coordination interface

Created as part of Phase 5B Memory Management Enhancement
"""

# Main orchestrator (primary interface)
from .memory_orchestrator import MemoryOrchestrator


__all__ = ["MemoryOrchestrator"]
