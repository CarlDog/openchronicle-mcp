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
        import core.model_management
        import core.memory_management
        import core.character_management
        assert True  # If we get here, imports worked
    
    def test_orchestrator_availability(self):
        """Test that orchestrators are available."""
        from core.model_management import ModelOrchestrator
        from core.memory_management import MemoryOrchestrator
        from core.character_management import CharacterOrchestrator
        
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
    
    @pytest.mark.skipif(True, reason="Integration test - run separately")
    def test_model_orchestrator_basic_functionality(self):
        """Test basic model orchestrator functionality."""
        # This would test actual functionality when ready
        pass


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
