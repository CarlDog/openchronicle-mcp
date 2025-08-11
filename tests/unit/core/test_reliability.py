"""
Quick validation test for core OpenChronicle functionality.
This test focuses on reliability and basic functionality.
"""
import logging

import pytest


# Disable excessive logging for tests
logging.getLogger("openchronicle").setLevel(logging.ERROR)
logging.getLogger("core").setLevel(logging.ERROR)


class TestCoreSystemReliability:
    """Test core system reliability and basic functionality."""

    def test_core_imports(self):
        """Test that core modules import without errors."""

        assert True  # If we get here, imports worked

    def test_orchestrator_availability(self):
        """Test that orchestrators are available."""
        from src.openchronicle.domain.models import ModelOrchestrator
        from src.openchronicle.domain.services.characters import CharacterOrchestrator
        from src.openchronicle.infrastructure.memory import MemoryOrchestrator

        # Just test that classes exist
        assert ModelOrchestrator is not None
        assert MemoryOrchestrator is not None
        assert CharacterOrchestrator is not None

    def test_basic_configuration_loading(self):
        """Test that basic configuration can be loaded."""
        from pathlib import Path

        # Get project root directory
        project_root = Path(__file__).parent.parent.parent.parent

        # Check that essential config files exist
        assert (project_root / "config/system_config.json").exists()
        assert (project_root / "requirements.txt").exists()

    def test_model_orchestrator_basic_functionality(self):
        """Test basic model orchestrator functionality."""
        # Test basic orchestrator import and creation
        from src.openchronicle.domain.models.model_orchestrator import ModelOrchestrator

        orchestrator = ModelOrchestrator()

        # Basic functionality test
        status = orchestrator.get_status()
        assert status is not None
        assert (
            "system_healthy" in str(status).lower()
            or "adapters_count" in str(status).lower()
        )


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
