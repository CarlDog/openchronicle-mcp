"""
Performance interface port for domain layer operations.
Abstract interfaces for performance operations without dependency violations.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


class IPerformanceInterfacePort(ABC):
    """Port for performance interface operations."""

    @abstractmethod
    async def collect_metrics(self, metric_type: str, data: Dict) -> bool:
        """Collect performance metrics."""
        pass

    @abstractmethod
    async def store_metrics(self, metrics: Dict) -> bool:
        """Store performance metrics."""
        pass

    @abstractmethod
    async def analyze_bottlenecks(self, data: Dict) -> Dict[str, Any]:
        """Analyze performance bottlenecks."""
        pass

    @abstractmethod
    async def get_performance_report(self, criteria: Dict) -> Dict[str, Any]:
        """Generate performance report."""
        pass

    @abstractmethod
    async def track_resource_usage(self, resource_type: str) -> Dict[str, Any]:
        """Track resource usage."""
        pass

    @abstractmethod
    async def optimize_performance(self, optimization_type: str) -> bool:
        """Apply performance optimizations."""
        pass
