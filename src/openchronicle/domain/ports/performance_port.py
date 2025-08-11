"""
Performance Port - Interface for performance monitoring operations

Defines the contract for all performance monitoring operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IPerformancePort(ABC):
    """Interface for performance monitoring operations."""

    @abstractmethod
    def start_monitoring(self, model_name: str, operation: str) -> str:
        """
        Start monitoring a model operation.
        
        Args:
            model_name: Name of the model
            operation: Type of operation being monitored
            
        Returns:
            Monitoring session ID
        """
        pass

    @abstractmethod
    def end_monitoring(self, session_id: str, success: bool = True, error: Optional[str] = None) -> Dict[str, Any]:
        """
        End monitoring session and get metrics.
        
        Args:
            session_id: Monitoring session ID
            success: Whether operation was successful
            error: Error message if failed
            
        Returns:
            Performance metrics
        """
        pass

    @abstractmethod
    def get_model_metrics(self, model_name: str) -> Dict[str, Any]:
        """
        Get performance metrics for a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Performance metrics
        """
        pass

    @abstractmethod
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get overall system performance metrics.
        
        Returns:
            System performance metrics
        """
        pass

    @abstractmethod
    def record_usage(self, model_name: str, tokens_used: int, cost: float = 0.0) -> bool:
        """
        Record model usage statistics.
        
        Args:
            model_name: Name of the model
            tokens_used: Number of tokens used
            cost: Cost of the operation
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_usage_stats(self, model_name: str, timeframe: str = "day") -> Dict[str, Any]:
        """
        Get usage statistics for a model.
        
        Args:
            model_name: Name of the model
            timeframe: Timeframe for statistics ("hour", "day", "week", "month")
            
        Returns:
            Usage statistics
        """
        pass
