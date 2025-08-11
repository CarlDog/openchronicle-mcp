"""
Mock Implementations - Fallback implementations for domain interfaces

These mock implementations provide fallback behavior when infrastructure
adapters are not available, maintaining system stability.
"""

from typing import Any, Dict
from .model_interfaces import IModelPerformanceMonitor


class MockPerformanceMonitor(IModelPerformanceMonitor):
    """Mock implementation of performance monitoring."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def start_monitoring(self, operation: str) -> str:
        """Mock start monitoring."""
        return "mock_session_id"
    
    def end_monitoring(self, session_id: str) -> Dict[str, Any]:
        """Mock end monitoring."""
        return {"duration": 0.1, "success": True}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Mock get metrics."""
        return {"total_requests": 0, "avg_duration": 0.1}
