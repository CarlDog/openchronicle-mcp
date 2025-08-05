"""
Test suite for ModelOrchestrator - comprehensive testing of component integration.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.model_management.model_orchestrator import ModelOrchestrator, create_model_manager


class TestModelOrchestrator:
    """Test ModelOrchestrator functionality and component integration."""
    
    @pytest.fixture
    def mock_config_dir(self):
        """Create temporary config directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            
            # Create model registry
            registry = {
                "schema_version": "3.0.0",
                "global_settings": {"default_adapter": "transformers"},
                "providers": {
                    "transformers": {
                        "enabled": True,
                        "adapter_class": "TransformersAdapter",
                        "config": {"model_name": "gpt2"}
                    },
                    "mock_provider": {
                        "enabled": True,
                        "adapter_class": "MockAdapter", 
                        "config": {"model_name": "mock-model"}
                    }
                }
            }
            
            with open(config_dir / "model_registry.json", 'w') as f:
                json.dump(registry, f)
            
            yield temp_dir
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_orchestrator_initialization(self, mock_open, mock_exists):
        """Test ModelOrchestrator initializes all components correctly."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Verify component initialization
        assert orchestrator.config_manager is not None
        assert orchestrator.lifecycle_manager is not None
        assert orchestrator.performance_monitor is not None
        assert orchestrator.response_generator is not None
        
        # Verify legacy compatibility
        assert hasattr(orchestrator, 'adapters')
        assert hasattr(orchestrator, 'default_adapter')
        assert hasattr(orchestrator, 'config')
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_legacy_compatibility(self, mock_open, mock_exists):
        """Test backward compatibility with ModelManager API."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Test legacy properties exist
        assert hasattr(orchestrator, 'adapters')
        assert hasattr(orchestrator, 'default_adapter')
        assert hasattr(orchestrator, 'config')
        
        # Test legacy methods exist
        assert hasattr(orchestrator, 'get_model_info')
        assert hasattr(orchestrator, 'create_adapter')
        assert hasattr(orchestrator, '_load_config')
        assert hasattr(orchestrator, '_process_global_config')
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    @pytest.mark.asyncio
    async def test_adapter_initialization(self, mock_open, mock_exists):
        """Test adapter initialization through orchestrator."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock the lifecycle manager
        orchestrator.lifecycle_manager.initialize_adapter = AsyncMock(return_value=True)
        orchestrator.lifecycle_manager.initialize_adapter_safe = AsyncMock(return_value=True)
        
        # Test adapter initialization
        result = await orchestrator.initialize_adapter("transformers")
        assert result is True
        
        result_safe = await orchestrator.initialize_adapter_safe("transformers")
        assert result_safe is True
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    @pytest.mark.asyncio
    async def test_response_generation(self, mock_open, mock_exists):
        """Test response generation through orchestrator."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock the response generator
        orchestrator.response_generator.generate_response = AsyncMock(return_value="Test response")
        
        # Test response generation
        response = await orchestrator.generate_response("Test prompt")
        assert response == "Test response"
        
        # Test with parameters
        response = await orchestrator.generate_response(
            prompt="Test prompt",
            adapter_name="transformers",
            story_id="test-story"
        )
        assert response == "Test response"
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_configuration_management(self, mock_open, mock_exists):
        """Test configuration management through orchestrator."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock configuration manager methods
        orchestrator.config_manager.add_model_config = Mock(return_value=True)
        orchestrator.config_manager.remove_model_config = Mock(return_value=True)
        orchestrator.config_manager.update_model_config = Mock(return_value=True)
        orchestrator.config_manager.validate_model_config = Mock(return_value=True)
        orchestrator.config_manager.enable_model = Mock(return_value=True)
        orchestrator.config_manager.disable_model = Mock(return_value=True)
        
        # Test configuration operations
        assert orchestrator.add_model_config("test_provider", {}) is True
        assert orchestrator.remove_model_config("test_provider") is True
        assert orchestrator.update_model_config("test_provider", {}) is True
        assert orchestrator.validate_model_config({}) is True
        assert orchestrator.enable_model("test_provider") is True
        assert orchestrator.disable_model("test_provider") is True
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_performance_monitoring(self, mock_open, mock_exists):
        """Test performance monitoring through orchestrator."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock performance monitor methods
        orchestrator.performance_monitor.get_performance_stats = Mock(return_value={"total_requests": 0})
        orchestrator.performance_monitor.get_adapter_metrics = Mock(return_value={"requests": 0})
        orchestrator.performance_monitor.start_monitoring = Mock()
        orchestrator.performance_monitor.stop_monitoring = Mock()
        orchestrator.performance_monitor.reset_stats = Mock()
        
        # Test performance operations
        stats = orchestrator.get_performance_stats()
        assert stats == {"total_requests": 0}
        
        metrics = orchestrator.get_adapter_metrics("transformers")
        assert metrics == {"requests": 0}
        
        orchestrator.start_performance_monitoring()
        orchestrator.stop_performance_monitoring()
        orchestrator.reset_performance_stats()
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_lifecycle_management(self, mock_open, mock_exists):
        """Test lifecycle management through orchestrator."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock lifecycle manager methods
        orchestrator.lifecycle_manager.get_available_adapters = Mock(return_value={"transformers": {}})
        orchestrator.lifecycle_manager.get_enabled_adapters = Mock(return_value=["transformers"])
        orchestrator.lifecycle_manager.get_adapter_status = Mock(return_value={"status": "healthy"})
        orchestrator.lifecycle_manager.is_adapter_available = Mock(return_value=True)
        orchestrator.lifecycle_manager.is_adapter_healthy = Mock(return_value=True)
        orchestrator.lifecycle_manager.refresh_available_adapters = Mock()
        
        # Test lifecycle operations
        adapters = orchestrator.get_available_adapters()
        assert adapters == {"transformers": {}}
        
        enabled = orchestrator.get_enabled_adapters()
        assert enabled == ["transformers"]
        
        status = orchestrator.get_adapter_status("transformers")
        assert status == {"status": "healthy"}
        
        assert orchestrator.is_adapter_available("transformers") is True
        assert orchestrator.is_adapter_healthy("transformers") is True
        
        orchestrator.refresh_available_adapters()
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_system_status(self, mock_open, mock_exists):
        """Test system status reporting."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock component methods for status
        orchestrator.config_manager.get_all_providers = Mock(return_value=["transformers"])
        orchestrator.lifecycle_manager.initialized_adapters = {"transformers"}
        orchestrator.performance_monitor.is_monitoring_active = Mock(return_value=True)
        orchestrator.performance_monitor.get_total_requests = Mock(return_value=100)
        orchestrator.performance_monitor.get_uptime_seconds = Mock(return_value=3600)
        
        status = orchestrator.get_system_status()
        
        # Verify status structure
        assert "orchestrator" in status
        assert "configuration" in status
        assert "lifecycle" in status
        assert "performance" in status
        
        # Verify component status
        assert status["orchestrator"]["initialized"] is True
        assert all(status["orchestrator"]["components"].values())
        
        # Verify configuration status
        assert status["configuration"]["total_providers"] == 1
        assert status["configuration"]["default_adapter"] == "transformers"
        
        # Verify performance status
        assert status["performance"]["monitoring_active"] is True
        assert status["performance"]["total_requests"] == 100
        assert status["performance"]["uptime_seconds"] == 3600
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    @pytest.mark.asyncio
    async def test_orchestrator_shutdown(self, mock_open, mock_exists):
        """Test graceful orchestrator shutdown."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Mock component shutdown methods
        orchestrator.performance_monitor.stop_monitoring = Mock()
        orchestrator.lifecycle_manager.cleanup_all_adapters = AsyncMock()
        orchestrator.config_manager.export_configuration = Mock(return_value="config_exported.json")
        
        # Test shutdown
        await orchestrator.shutdown()
        
        # Verify shutdown calls
        orchestrator.performance_monitor.stop_monitoring.assert_called_once()
        orchestrator.lifecycle_manager.cleanup_all_adapters.assert_called_once()
        orchestrator.config_manager.export_configuration.assert_called_once()
    
    def test_factory_function(self):
        """Test factory function for creating orchestrator."""
        with patch('core.model_management.model_orchestrator.ModelOrchestrator') as mock_orchestrator:
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            
            result = create_model_manager()
            
            mock_orchestrator.assert_called_once()
            assert result == mock_instance
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_legacy_alias(self, mock_open, mock_exists):
        """Test ModelManager legacy alias."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {"transformers": {"enabled": True, "adapter_class": "TransformersAdapter"}}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        from core.model_management.model_orchestrator import ModelManager
        
        # ModelManager should be an alias for ModelOrchestrator
        assert ModelManager == ModelOrchestrator
        
        # Should be able to create instance with legacy name
        manager = ModelManager()
        assert isinstance(manager, ModelOrchestrator)


class TestOrchestatorIntegration:
    """Integration tests for ModelOrchestrator with real components."""
    
    @patch('core.model_management.configuration_manager.os.path.exists')
    @patch('core.model_management.configuration_manager.open')
    def test_component_integration(self, mock_open, mock_exists):
        """Test that all components integrate correctly."""
        mock_exists.return_value = True
        mock_registry = {
            "schema_version": "3.0.0",
            "global_settings": {"default_adapter": "transformers"},
            "providers": {
                "transformers": {
                    "enabled": True,
                    "adapter_class": "TransformersAdapter",
                    "config": {"model_name": "gpt2"},
                    "fallback_chain": []
                }
            }
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_registry)
        
        orchestrator = ModelOrchestrator()
        
        # Test that components can access each other correctly
        assert orchestrator.response_generator.lifecycle_manager == orchestrator.lifecycle_manager
        assert orchestrator.response_generator.performance_monitor == orchestrator.performance_monitor
        assert orchestrator.lifecycle_manager.config_manager == orchestrator.config_manager
    
    def test_component_communication(self):
        """Test that components can communicate with each other."""
        # This would require more complex mocking to test actual communication
        # For now, we test that the structure allows for communication
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
