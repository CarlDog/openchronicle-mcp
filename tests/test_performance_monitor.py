#!/usr/bin/env python3
"""
Test suite for Phase 3.0 Day 3: PerformanceMonitor Component

Tests extracted performance monitoring functionality with comprehensive coverage
of tracking, reporting, and analytics capabilities.

File: tests/test_performance_monitor.py
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Mock utilities before importing component
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock performance monitoring utilities
mock_performance_monitor = Mock()
mock_performance_monitor.start_monitoring = Mock()
mock_performance_monitor.generate_performance_report = Mock()
mock_performance_monitor.save_report_to_file = Mock()
mock_performance_monitor.get_system_health_summary = Mock()
mock_performance_monitor.get_model_analytics = Mock()
mock_performance_monitor.track_operation = Mock()

# Setup module mocking
sys.modules['utilities.performance_monitor'] = Mock()
sys.modules['utilities.performance_monitor'].PerformanceMonitor = Mock(return_value=mock_performance_monitor)

# Mock logging system
mock_log_info = Mock()
mock_log_error = Mock()  
mock_log_warning = Mock()
mock_log_system_event = Mock()

sys.modules['utilities.logging_system'] = Mock()
sys.modules['utilities.logging_system'].log_info = mock_log_info
sys.modules['utilities.logging_system'].log_error = mock_log_error
sys.modules['utilities.logging_system'].log_warning = mock_log_warning
sys.modules['utilities.logging_system'].log_system_event = mock_log_system_event

# Now import the component
from core.model_management.performance_monitor import PerformanceMonitor


class TestPerformanceMonitor:
    """Test suite for PerformanceMonitor component."""
    
    @pytest.fixture
    def mock_adapters(self):
        """Create mock adapters dictionary."""
        return {
            "gpt4": Mock(provider_name="openai", model_name="gpt-4", initialized=True),
            "claude": Mock(provider_name="anthropic", model_name="claude-3", initialized=True),
            "ollama": Mock(provider_name="ollama", model_name="llama3", initialized=False)
        }
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {
            "performance_monitoring": {
                "enabled": True,
                "track_system_metrics": True,
                "save_reports": True
            }
        }
    
    @pytest.fixture
    def performance_monitor(self, mock_adapters, mock_config):
        """Create PerformanceMonitor instance."""
        return PerformanceMonitor(mock_adapters, mock_config)
    
    def test_initialization(self, performance_monitor):
        """Test PerformanceMonitor initialization."""
        assert performance_monitor is not None
        assert performance_monitor.adapters is not None
        assert performance_monitor.config is not None
        assert performance_monitor.monitoring_enabled is True
        
        # Verify initialization logging
        mock_log_system_event.assert_called()
        calls = [call.args for call in mock_log_system_event.call_args_list]
        assert any("performance_monitor_initialized" in call for call in calls)
    
    def test_initialization_without_utilities(self, mock_adapters, mock_config):
        """Test initialization when utilities not available."""
        with patch('core.model_management.performance_monitor.PERFORMANCE_MONITOR_AVAILABLE', False):
            monitor = PerformanceMonitor(mock_adapters, mock_config)
            assert monitor.monitoring_enabled is False
            assert monitor.performance_monitor is None
    
    def test_performance_monitoring_initialization(self, performance_monitor):
        """Test performance monitoring system initialization."""
        # Verify performance monitor setup
        assert performance_monitor.performance_monitor is not None
        assert performance_monitor.monitoring_enabled is True
        
        # Verify start_monitoring was called
        mock_performance_monitor.start_monitoring.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_performance_report_success(self, performance_monitor):
        """Test successful performance report generation."""
        # Setup mock report
        mock_report = Mock()
        mock_report.total_operations = 100
        mock_report.successful_operations = 95
        mock_report.avg_duration = 1.5
        mock_report.avg_efficiency_score = 0.85
        mock_report.bottlenecks = []
        mock_report.optimization_recommendations = []
        mock_report.time_period = "24 hours"
        mock_report.performance_trend = "stable"
        mock_report.trend_confidence = 0.9
        mock_report.fastest_models = [("gpt4", 0.9), ("claude", 0.8)]
        mock_report.most_efficient_models = [("gpt4", 0.9), ("claude", 0.8)]
        mock_report.most_reliable_models = [("gpt4", 0.95), ("claude", 0.92)]
        mock_report.model_rankings = {"gpt4": 0.92, "claude": 0.88}
        
        mock_performance_monitor.generate_performance_report.return_value = mock_report
        mock_performance_monitor.save_report_to_file.return_value = "/path/to/report.json"
        mock_performance_monitor.get_system_health_summary.return_value = {"cpu": 50, "memory": 60}
        
        # Generate report
        result = await performance_monitor.generate_performance_report(24)
        
        # Verify success
        assert result["success"] is True
        assert result["report"] == mock_report
        assert result["report_file"] == "/path/to/report.json"
        assert "summary" in result
        assert result["summary"]["total_operations"] == 100
        assert result["summary"]["success_rate"] == 0.95
        
        # Verify method calls
        mock_performance_monitor.generate_performance_report.assert_called_once_with(24)
        mock_performance_monitor.save_report_to_file.assert_called_once()
        mock_performance_monitor.get_system_health_summary.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_performance_report_monitoring_disabled(self, mock_adapters, mock_config):
        """Test performance report generation when monitoring is disabled."""
        with patch('core.model_management.performance_monitor.PERFORMANCE_MONITOR_AVAILABLE', False):
            monitor = PerformanceMonitor(mock_adapters, mock_config)
            result = await monitor.generate_performance_report(24)
            
            assert result["success"] is False
            assert "Performance monitoring not available" in result["error"]
            assert "recommendations" in result
    
    @pytest.mark.asyncio
    async def test_get_model_performance_analytics_success(self, performance_monitor):
        """Test successful model performance analytics retrieval."""
        # Setup mock analytics
        mock_analytics = {
            "gpt4": {"avg_response_time": 1.2, "success_rate": 0.98},
            "claude": {"avg_response_time": 1.5, "success_rate": 0.95}
        }
        
        mock_performance_monitor.get_model_analytics.return_value = mock_analytics
        
        # Get analytics for all adapters
        result = await performance_monitor.get_model_performance_analytics()
        
        # Verify success
        assert result["success"] is True
        assert result["analytics"] == mock_analytics
        assert "adapter_status" in result
        assert "gpt4" in result["adapter_status"]
        assert result["adapter_status"]["gpt4"]["available"] is True
        assert result["adapter_status"]["gpt4"]["type"] == "openai"
        
        # Verify method call
        mock_performance_monitor.get_model_analytics.assert_called_once_with(None)
    
    @pytest.mark.asyncio
    async def test_get_model_performance_analytics_specific_adapter(self, performance_monitor):
        """Test analytics retrieval for specific adapter."""
        mock_analytics = {"gpt4": {"avg_response_time": 1.2}}
        mock_performance_monitor.get_model_analytics.return_value = mock_analytics
        
        result = await performance_monitor.get_model_performance_analytics("gpt4")
        
        assert result["success"] is True
        assert "gpt4" in result["adapter_status"]
        mock_performance_monitor.get_model_analytics.assert_called_once_with("gpt4")
    
    @pytest.mark.asyncio
    async def test_get_model_performance_analytics_monitoring_disabled(self, mock_adapters, mock_config):
        """Test analytics retrieval when monitoring is disabled."""
        with patch('core.model_management.performance_monitor.PERFORMANCE_MONITOR_AVAILABLE', False):
            monitor = PerformanceMonitor(mock_adapters, mock_config)
            result = await monitor.get_model_performance_analytics()
            
            assert result["success"] is False
            assert "Performance monitoring not available" in result["error"]
    
    def test_track_model_operation_enabled(self, performance_monitor):
        """Test model operation tracking when monitoring is enabled."""
        mock_context_manager = Mock()
        mock_performance_monitor.track_operation.return_value = mock_context_manager
        
        result = performance_monitor.track_model_operation("gpt4", "generate", prompt_length=100)
        
        assert result == mock_context_manager
        mock_performance_monitor.track_operation.assert_called_once_with("gpt4", "generate", prompt_length=100)
    
    def test_track_model_operation_disabled(self, mock_adapters, mock_config):
        """Test model operation tracking when monitoring is disabled."""
        with patch('core.model_management.performance_monitor.PERFORMANCE_MONITOR_AVAILABLE', False):
            monitor = PerformanceMonitor(mock_adapters, mock_config)
            result = monitor.track_model_operation("gpt4", "generate")
            
            # Should return a context manager (dummy implementation)
            assert result is not None
    
    def test_get_performance_config_success(self, performance_monitor):
        """Test performance configuration retrieval."""
        mock_registry = {
            "performance_tuning": {
                "max_concurrent_requests": 5,
                "timeout_seconds": 30
            }
        }
        
        with patch("builtins.open", create=True) as mock_open:
            with patch("os.path.exists", return_value=True):
                with patch("json.load", return_value=mock_registry):
                    config = performance_monitor.get_performance_config()
                    
                    assert config == mock_registry["performance_tuning"]
    
    def test_get_performance_config_file_not_found(self, performance_monitor):
        """Test performance configuration when file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            config = performance_monitor.get_performance_config()
            assert config == {}
    
    def test_is_monitoring_enabled(self, performance_monitor):
        """Test monitoring status check."""
        assert performance_monitor.is_monitoring_enabled() is True
        
        # Test disabled state
        performance_monitor.monitoring_enabled = False
        assert performance_monitor.is_monitoring_enabled() is False
    
    def test_get_system_health_summary_success(self, performance_monitor):
        """Test system health summary retrieval."""
        mock_health = {"cpu": 45, "memory": 70, "disk": 80}
        mock_performance_monitor.get_system_health_summary.return_value = mock_health
        
        result = performance_monitor.get_system_health_summary()
        
        assert result == mock_health
        mock_performance_monitor.get_system_health_summary.assert_called_once()
    
    def test_get_system_health_summary_monitoring_disabled(self, mock_adapters, mock_config):
        """Test system health summary when monitoring is disabled."""
        with patch('core.model_management.performance_monitor.PERFORMANCE_MONITOR_AVAILABLE', False):
            monitor = PerformanceMonitor(mock_adapters, mock_config)
            result = monitor.get_system_health_summary()
            
            assert result["available"] is False
            assert "Performance monitoring not available" in result["reason"]
    
    @pytest.mark.asyncio
    async def test_optimize_model_performance_success(self, performance_monitor):
        """Test model performance optimization."""
        # Setup mock report with recommendations
        mock_report = Mock()
        mock_report.optimization_recommendations = [
            Mock(adapter_name="gpt4", risk_level="low", auto_apply=True, id="opt1", type="cache"),
            Mock(adapter_name="claude", risk_level="medium", auto_apply=False, id="opt2", type="batch")
        ]
        
        mock_performance_monitor.generate_performance_report.return_value = mock_report
        mock_performance_monitor.save_report_to_file.return_value = "/path/to/report.json"
        mock_performance_monitor.get_system_health_summary.return_value = {"cpu": 50}
        
        # Mock generate_performance_report method
        async def mock_generate_report(hours):
            return {
                "success": True,
                "report": mock_report,
                "report_file": "/path/to/report.json"
            }
        
        with patch.object(performance_monitor, 'generate_performance_report', side_effect=mock_generate_report):
            result = await performance_monitor.optimize_model_performance()
            
            assert result["success"] is True
            assert "optimizations_applied" in result
            assert result["total_optimizations"] >= 0
    
    @pytest.mark.asyncio
    async def test_optimize_model_performance_monitoring_disabled(self, mock_adapters, mock_config):
        """Test optimization when monitoring is disabled."""
        with patch('core.model_management.performance_monitor.PERFORMANCE_MONITOR_AVAILABLE', False):
            monitor = PerformanceMonitor(mock_adapters, mock_config)
            result = await monitor.optimize_model_performance()
            
            assert result["success"] is False
            assert "Performance monitoring not available" in result["error"]
    
    def test_generate_registry_performance_updates(self, performance_monitor):
        """Test registry performance updates generation."""
        # Setup mock report
        mock_report = Mock()
        mock_report.model_rankings = {"gpt4": 0.92, "claude": 0.88}
        mock_report.total_operations = 150
        mock_report.fastest_models = [("gpt4", 0.95), ("claude", 0.85)]
        mock_report.most_efficient_models = [("gpt4", 0.90), ("claude", 0.80)]
        mock_report.most_reliable_models = [("gpt4", 0.98), ("claude", 0.92)]
        
        result = performance_monitor._generate_registry_performance_updates(mock_report)
        
        assert result["success"] is True
        assert "updates" in result
        assert "gpt4" in result["updates"]
        assert result["updates"]["gpt4"]["performance_rating"] == 0.92
        assert result["updates"]["gpt4"]["speed_rank"] == 1
        assert result["updates"]["gpt4"]["efficiency_rank"] == 1
    
    @pytest.mark.asyncio
    async def test_apply_automatic_optimizations(self, performance_monitor):
        """Test automatic optimizations application."""
        # Setup mock recommendations
        mock_recommendations = [
            Mock(risk_level="low", auto_apply=True, id="opt1", adapter_name="gpt4", type="cache"),
            Mock(risk_level="high", auto_apply=False, id="opt2", adapter_name="claude", type="memory"),
            Mock(risk_level="low", auto_apply=True, id="opt3", adapter_name="gpt4", type="batch")
        ]
        
        mock_report = Mock()
        mock_report.optimization_recommendations = mock_recommendations
        
        result = await performance_monitor._apply_automatic_optimizations(mock_report)
        
        # Should apply 2 low-risk auto-apply optimizations
        assert len(result) == 2
        assert all(opt["applied"] is False for opt in result)  # Mock implementation doesn't apply
    
    @pytest.mark.asyncio
    async def test_apply_optimization(self, performance_monitor):
        """Test individual optimization application."""
        mock_recommendation = Mock()
        mock_recommendation.id = "test_opt"
        mock_recommendation.adapter_name = "gpt4"
        mock_recommendation.type = "cache"
        
        result = await performance_monitor._apply_optimization(mock_recommendation)
        
        assert "recommendation_id" in result
        assert result["recommendation_id"] == "test_opt"
        assert result["adapter_name"] == "gpt4"
        assert result["optimization_type"] == "cache"
        assert result["applied"] is False  # Mock implementation


class TestPerformanceMonitorIntegration:
    """Integration tests for PerformanceMonitor component."""
    
    @pytest.fixture
    def integration_adapters(self):
        """Create realistic adapter mocks for integration testing."""
        return {
            "gpt4": Mock(
                provider_name="openai",
                model_name="gpt-4",
                initialized=True,
                generate_response=AsyncMock(return_value="Generated response")
            ),
            "claude": Mock(
                provider_name="anthropic",
                model_name="claude-3",
                initialized=True,
                generate_response=AsyncMock(return_value="Claude response")
            )
        }
    
    @pytest.fixture
    def integration_monitor(self, integration_adapters, mock_config):
        """Create PerformanceMonitor for integration testing."""
        return PerformanceMonitor(integration_adapters, mock_config)
    
    @pytest.mark.asyncio
    async def test_full_performance_workflow(self, integration_monitor):
        """Test complete performance monitoring workflow."""
        # Setup mock report for workflow
        mock_report = Mock()
        mock_report.total_operations = 50
        mock_report.successful_operations = 48
        mock_report.avg_duration = 1.2
        mock_report.avg_efficiency_score = 0.88
        mock_report.bottlenecks = []
        mock_report.optimization_recommendations = []
        mock_report.time_period = "24 hours"
        mock_report.performance_trend = "improving"
        mock_report.trend_confidence = 0.85
        mock_report.fastest_models = [("gpt4", 0.92)]
        mock_report.most_efficient_models = [("gpt4", 0.90)]
        mock_report.most_reliable_models = [("gpt4", 0.96)]
        mock_report.model_rankings = {"gpt4": 0.92}
        
        mock_performance_monitor.generate_performance_report.return_value = mock_report
        mock_performance_monitor.save_report_to_file.return_value = "/tmp/test_report.json"
        mock_performance_monitor.get_system_health_summary.return_value = {"status": "healthy"}
        
        # 1. Generate performance report
        report_result = await integration_monitor.generate_performance_report(24)
        assert report_result["success"] is True
        
        # 2. Get analytics for specific adapter
        mock_performance_monitor.get_model_analytics.return_value = {"gpt4": {"response_time": 1.1}}
        analytics_result = await integration_monitor.get_model_performance_analytics("gpt4")
        assert analytics_result["success"] is True
        
        # 3. Check monitoring status
        assert integration_monitor.is_monitoring_enabled() is True
        
        # 4. Get system health
        health = integration_monitor.get_system_health_summary()
        assert "status" in health or "available" in health
        
        # Verify all components worked together
        assert report_result["summary"]["total_operations"] == 50
        assert analytics_result["adapter_status"]["gpt4"]["available"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
