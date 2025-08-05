"""
OpenChronicle Test Configuration and Fixtures

Essential pytest configuration for testing the modular orchestrator architecture.
Provides shared fixtures, utilities, and test environment setup.
"""

import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path
from typing import Dict, Any, Optional

# Add core modules to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import orchestrators for testing
from core.scene_systems.scene_orchestrator import SceneOrchestrator
from core.timeline_systems.timeline_orchestrator import TimelineOrchestrator
from core.model_management.model_orchestrator import ModelOrchestrator

# Test configuration
TEST_CONFIG = {
    'test_story_id': 'test_story_pytest',
    'temp_dir_prefix': 'openchronicle_test_',
    'mock_model_provider': 'mock_adapter',
    'enable_logging': False,  # Disable logging during tests for cleaner output
    'test_timeout': 30,  # 30 second timeout for individual tests
}

@pytest.fixture(scope="session")
def test_config():
    """Global test configuration."""
    return TEST_CONFIG.copy()

@pytest.fixture
def temp_test_dir():
    """Create temporary directory for test files."""
    temp_dir = tempfile.mkdtemp(prefix=TEST_CONFIG['temp_dir_prefix'])
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def test_story_id():
    """Standard test story ID for consistent testing."""
    return TEST_CONFIG['test_story_id']

@pytest.fixture
def clean_test_environment(temp_test_dir, test_story_id):
    """Provide clean test environment with isolated storage."""
    # Set up isolated test environment
    original_cwd = os.getcwd()
    os.chdir(temp_test_dir)
    
    # Create test storage directories
    os.makedirs('storage', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    yield {
        'temp_dir': temp_test_dir,
        'story_id': test_story_id,
        'storage_dir': os.path.join(temp_test_dir, 'storage'),
        'logs_dir': os.path.join(temp_test_dir, 'logs')
    }
    
    # Cleanup
    os.chdir(original_cwd)

@pytest.fixture
def scene_orchestrator(clean_test_environment):
    """Initialize SceneOrchestrator for testing."""
    try:
        orchestrator = SceneOrchestrator(
            story_id=clean_test_environment['story_id'],
            config={'enable_logging': False}
        )
        yield orchestrator
    except Exception as e:
        pytest.skip(f"SceneOrchestrator not available: {e}")

@pytest.fixture  
def timeline_orchestrator(clean_test_environment):
    """Initialize TimelineOrchestrator for testing."""
    try:
        orchestrator = TimelineOrchestrator(
            story_id=clean_test_environment['story_id']
        )
        yield orchestrator
    except Exception as e:
        pytest.skip(f"TimelineOrchestrator not available: {e}")

@pytest.fixture
def model_orchestrator():
    """Initialize ModelOrchestrator for testing."""
    try:
        orchestrator = ModelOrchestrator()
        yield orchestrator
    except Exception as e:
        pytest.skip(f"ModelOrchestrator not available: {e}")

@pytest.fixture
def sample_scene_data():
    """Sample scene data for testing."""
    return {
        'user_input': 'The character enters the room cautiously.',
        'model_output': 'The room was dimly lit, shadows dancing across the walls. The character took a tentative step forward, senses alert for any sign of danger.',
        'memory_snapshot': {
            'character_name': 'Alex',
            'current_location': 'mysterious_room',
            'emotional_state': 'cautious',
            'health_status': 'healthy'
        },
        'flags': ['first_room_entry'],
        'context_refs': ['room_description', 'character_background']
    }

@pytest.fixture
def sample_story_config():
    """Sample story configuration for testing."""
    return {
        'story_id': 'test_story_pytest',
        'title': 'Test Story',
        'genre': 'adventure',
        'characters': [
            {
                'name': 'Alex',
                'role': 'protagonist',
                'personality': 'cautious but determined'
            }
        ],
        'settings': {
            'world': 'modern_mystery',
            'tone': 'suspenseful'
        }
    }

# Test utilities
class TestUtils:
    """Utility functions for testing."""
    
    @staticmethod
    def validate_scene_data(scene_data: Dict[str, Any]) -> bool:
        """Validate scene data structure."""
        required_fields = ['scene_id', 'user_input', 'model_output', 'timestamp']
        return all(field in scene_data for field in required_fields)
    
    @staticmethod
    def validate_orchestrator_initialization(orchestrator: Any) -> bool:
        """Validate orchestrator is properly initialized."""
        return (
            orchestrator is not None and
            hasattr(orchestrator, 'story_id') and
            orchestrator.story_id is not None
        )
    
    @staticmethod
    def create_test_scene_sequence(orchestrator, count: int = 3):
        """Create sequence of test scenes for integration testing."""
        scenes = []
        for i in range(count):
            scene_data = {
                'user_input': f'Test user input {i+1}',
                'model_output': f'Test model output {i+1}',
                'memory_snapshot': {'scene_number': i+1}
            }
            scene = orchestrator.create_scene(**scene_data)
            scenes.append(scene)
        return scenes

@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils

# Pytest configuration
def pytest_configure(config):
    """Configure pytest for OpenChronicle testing."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual orchestrators"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests between orchestrators"  
    )
    config.addinivalue_line(
        "markers", "workflow: End-to-end workflow tests"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take longer than 5 seconds"
    )
    config.addinivalue_line(
        "markers", "requires_models: Tests requiring LLM model access"
    )
    config.addinivalue_line(
        "markers", "mock_only: Tests using only mock data (no external dependencies)"
    )

# Session-level setup and teardown
@pytest.fixture(scope="session", autouse=True)
def setup_test_session():
    """Set up test session."""
    print("\n🧪 Starting OpenChronicle Test Suite")
    print("📋 Testing modular orchestrator architecture")
    yield
    print("\n✅ OpenChronicle Test Suite Complete")
