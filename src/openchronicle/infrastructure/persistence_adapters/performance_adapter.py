"""
Performance Adapter - Implementation of IPerformancePort

This adapter wraps the existing infrastructure performance functions
to implement the domain interface, maintaining the dependency inversion principle.
"""

import time
from typing import Any, Dict, List, Optional
import uuid

from src.openchronicle.domain.ports.performance_port import IPerformancePort


class PerformanceAdapter(IPerformancePort):
    """Concrete implementation of performance monitoring operations using existing infrastructure."""

    def __init__(self):
        """Initialize performance adapter."""
        self.active_sessions = {}
        
        # Import here to avoid circular dependencies
        try:
            from src.openchronicle.infrastructure.performance.model_monitor import PerformanceMonitor
            self.monitor = PerformanceMonitor({})
        except ImportError as e:
            print(f"Performance infrastructure not available: {e}")
            self.monitor = None

    def start_monitoring(self, model_name: str, operation: str) -> str:
        """
        Start monitoring a model operation.
        
        Args:
            model_name: Name of the model
            operation: Type of operation being monitored
            
        Returns:
            Monitoring session ID
        """
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "model_name": model_name,
            "operation": operation,
            "start_time": time.time(),
            "status": "active"
        }
        
        if self.monitor:
            try:
                self.monitor.start_monitoring(model_name, operation, session_id)
            except Exception as e:
                print(f"Error starting monitoring: {e}")
                
        return session_id

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
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
            
        session = self.active_sessions[session_id]
        end_time = time.time()
        duration = end_time - session["start_time"]
        
        metrics = {
            "session_id": session_id,
            "model_name": session["model_name"],
            "operation": session["operation"],
            "duration": duration,
            "success": success,
            "error": error
        }
        
        if self.monitor:
            try:
                metrics.update(self.monitor.end_monitoring(session_id, success, error))
            except Exception as e:
                print(f"Error ending monitoring: {e}")
                
        # Clean up session
        del self.active_sessions[session_id]
        
        return metrics

    def get_model_metrics(self, model_name: str) -> Dict[str, Any]:
        """
        Get performance metrics for a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Performance metrics
        """
        if self.monitor:
            try:
                return self.monitor.get_model_metrics(model_name)
            except Exception as e:
                print(f"Error getting model metrics: {e}")
                
        return {"model_name": model_name, "metrics": "unavailable"}

    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get overall system performance metrics.
        
        Returns:
            System performance metrics
        """
        if self.monitor:
            try:
                return self.monitor.get_system_metrics()
            except Exception as e:
                print(f"Error getting system metrics: {e}")
                
        return {"system_metrics": "unavailable"}

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
        if self.monitor:
            try:
                return self.monitor.record_usage(model_name, tokens_used, cost)
            except Exception as e:
                print(f"Error recording usage: {e}")
                return False
                
        return True  # Assume success if monitoring not available

    def get_usage_stats(self, model_name: str, timeframe: str = "day") -> Dict[str, Any]:
        """
        Get usage statistics for a model.
        
        Args:
            model_name: Name of the model
            timeframe: Timeframe for statistics ("hour", "day", "week", "month")
            
        Returns:
            Usage statistics
        """
        if self.monitor:
            try:
                return self.monitor.get_usage_stats(model_name, timeframe)
            except Exception as e:
                print(f"Error getting usage stats: {e}")
                
        return {"model_name": model_name, "timeframe": timeframe, "stats": "unavailable"}
