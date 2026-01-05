"""
Bootstrap Module

Contains composition root and dependency injection configuration for OpenChronicle.
"""

from .composition_root import create_consistency_orchestrator
from .composition_root import create_memory_port_adapter


__all__ = ["create_consistency_orchestrator", "create_memory_port_adapter"]
