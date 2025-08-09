"""
Quick validation test for core OpenChronicle functionality.
This test focuses on reliability and basic functionality.
"""
import pytest
import logging

# Disable excessive logging for tests
logging.getLogger('openchronicle').setLevel(logging.ERROR)
logging.getLogger('core').setLevel(logging.ERROR)


class TestCoreSystemReliability:
    """Test core system reliability and basic functionality."""
    
    def test_core_imports(self):
        """Test that core modules import without errors."""
        import core.models
        import core.memory
        import core.characters
        assert True  # If we get here, imports worked
    
    def test_orchestrator_availability(self):
        """Test that orchestrators are available."""
        from core.models import ModelOrchestrator
        from core.memory import MemoryOrchestrator
        from core.characters import CharacterOrchestrator
        
        # Just test that classes exist
        assert ModelOrchestrator is not None
        assert MemoryOrchestrator is not None
        assert CharacterOrchestrator is not None
    
    def test_basic_configuration_loading(self):
        """Test that basic configuration can be loaded."""
        from pathlib import Path
        
        # Check that essential config files exist
        assert Path("config/system_config.json").exists()
        assert Path("requirements.txt").exists()
    
    def test_model_orchestrator_basic_functionality(self):
        """Test basic model orchestrator functionality.""" 
        # Test basic orchestrator import and creation
        from core.models.model_orchestrator import ModelOrchestrator
        orchestrator = ModelOrchestrator()
        
        # Basic functionality test
        status = orchestrator.get_status()
        assert status is not None
        assert 'system_healthy' in str(status).lower() or 'adapters_count' in str(status).lower()


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
