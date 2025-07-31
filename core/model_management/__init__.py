"""
Model management package.

Provides orchestration and management functionality previously contained
in the monolithic ModelManager class. This modular approach separates
concerns for better maintainability and testability.
"""

# Import the main orchestrator as ModelManager for backward compatibility
from .orchestrator import ModelOrchestrator as ModelManager

__all__ = [
    'ModelManager',  # Main export for backward compatibility
]
