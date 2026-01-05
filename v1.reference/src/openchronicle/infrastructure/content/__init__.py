"""
Unified Content Management System

A comprehensive system combining content analysis and context building.

Components:
- Analysis: Detection, extraction, routing components
- Context: Context-building helpers (no orchestrator)

Usage:
    This package now exposes modular content components only.
    Orchestrators have moved behind plugin/domain ports.
"""

# Export submodules (components only)
from . import analysis
from . import context


__version__ = "5.0.0"
__all__ = [
    # Submodules
    "analysis",
    "context",
]
