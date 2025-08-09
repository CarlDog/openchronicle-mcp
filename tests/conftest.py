"""
Pytest configuration and fixtures for OpenChronicle tests.

Provides common test setup, mock objects, and utility functions
for both unit and integration tests, with support for the four-tier
testing strategy (production-real, production-mock, smoke, stress).
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import Mock, MagicMock, AsyncMock

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestConfigurationManager:
    """Manages test configurations for different testing tiers."""
    
    def __init__(self):
        self.current_tier = self._detect_current_tier()
        self.mock_adapters_enabled = self._should_use_mock_adapters()
    
    def _detect_current_tier(self) -> str:
        """Detect which test tier is currently running."""
        # Check environment variables first
        tier = os.environ.get('OPENCHRONICLE_TEST_TIER', 'standard')
        if tier != 'standard':
            return tier
            
        # Check for pytest markers in sys.argv
        import sys
        argv_str = ' '.join(sys.argv)
        if 'production_real' in argv_str:
            return 'production_real'
        elif 'production_mock' in argv_str or 'mock_only' in argv_str:
            return 'production_mock'
        elif 'smoke' in argv_str or 'core' in argv_str:
            return 'smoke'
        elif 'stress' in argv_str or 'chaos' in argv_str:
            return 'stress'
        
        return 'standard'
    
    def _should_use_mock_adapters(self) -> bool:
        """Determine if mock adapters should be used."""
        return self.current_tier in ['production_mock', 'smoke', 'stress', 'standard']
    
    def get_model_adapter_config(self) -> Dict[str, Any]:
        """Get model adapter configuration for current test tier."""
        if self.mock_adapters_enabled:
            return {
                'adapter_type': 'mock',
                'mock_responses': True,
                'enable_real_api_calls': False,
                'timeout': 5.0
            }
        else:
            return {
                'adapter_type': 'real',
                'mock_responses': False,
                'enable_real_api_calls': True,
                'timeout': 30.0,
                'retry_attempts': 3
            }
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration for current test tier."""
        base_config = {
            'use_memory_db': True,
            'enable_foreign_keys': True,
            'auto_vacuum': True
        }
        
        if self.current_tier == 'stress':
            stress_config = {
                'connection_pool_size': 10,
                'max_connections': 50,
                'timeout': 60.0
            }
            base_config.update(stress_config)
        
        return base_config


# Global configuration instance
test_config = TestConfigurationManager()


def pytest_configure(config):
    """Pytest hook to setup test configuration."""
    # Set environment variables based on markers
    markexpr = getattr(config.option, 'markexpr', '')
    if markexpr:
        if 'production_real' in markexpr:
            os.environ['OPENCHRONICLE_TEST_TIER'] = 'production_real'
        elif 'production_mock' in markexpr:
            os.environ['OPENCHRONICLE_TEST_TIER'] = 'production_mock'
        elif 'smoke' in markexpr:
            os.environ['OPENCHRONICLE_TEST_TIER'] = 'smoke'
        elif 'stress' in markexpr:
            os.environ['OPENCHRONICLE_TEST_TIER'] = 'stress'


def get_mock_model_adapter():
    """Create a mock model adapter for testing."""
    mock_adapter = AsyncMock()
    mock_adapter.generate_response.return_value = {
        'content': 'Mock response content',
        'metadata': {'model': 'mock-model', 'tokens': 50}
    }
    mock_adapter.is_available.return_value = True
    mock_adapter.get_model_info.return_value = {
        'name': 'mock-model',
        'provider': 'mock',
        'capabilities': ['text_generation']
    }
    return mock_adapter


def get_mock_image_adapter():
    """Create a mock image adapter for testing."""
    mock_adapter = AsyncMock()
    mock_adapter.generate_image.return_value = {
        'image_data': b'mock_image_data',
        'metadata': {'format': 'png', 'size': '512x512'}
    }
    mock_adapter.is_available.return_value = True
    return mock_adapter

# Import core modules
from core.scene_systems.scene_orchestrator import SceneOrchestrator
from core.timeline_systems.timeline_orchestrator import TimelineOrchestrator
from core.model_management.model_orchestrator import ModelOrchestrator
from core.memory_management.memory_orchestrator import MemoryOrchestrator
from core.context_systems.context_orchestrator import ContextOrchestrator

# Import enhanced mock adapters for isolated testing
from tests.mocks.mock_adapters import MockModelOrchestrator, MockDatabaseManager


# ===== TIER-BASED FIXTURES =====

@pytest.fixture
def tier_config():
    """Provide test tier configuration."""
    return test_config


@pytest.fixture
def model_adapter(tier_config):
    """Provide model adapter based on test tier."""
    if tier_config.mock_adapters_enabled:
        return get_mock_model_adapter()
    else:
        # Return real adapter (would need actual implementation)
        pytest.skip("Real model adapter not configured for testing")


@pytest.fixture
def image_adapter(tier_config):
    """Provide image adapter based on test tier."""
    if tier_config.mock_adapters_enabled:
        return get_mock_image_adapter()
    else:
        # Return real adapter (would need actual implementation)
        pytest.skip("Real image adapter not configured for testing")


# ===== FIXTURES =====

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp(prefix="opencronicle_test_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def test_story_id():
    """Generate a unique story ID for testing."""
    return f"test_story_{pytest.importorskip('uuid').uuid4().hex[:8]}"


@pytest.fixture
def clean_test_environment(temp_test_dir, test_story_id):
    """Create a clean test environment with temporary storage."""
    # Create test directories
    test_storage = Path(temp_test_dir) / "storage"
    test_storage.mkdir(exist_ok=True)
    
    # Create subdirectories
    (test_storage / "characters").mkdir(exist_ok=True)
    (test_storage / "scenes").mkdir(exist_ok=True)
    (test_storage / "memory").mkdir(exist_ok=True)
    (test_storage / "timeline").mkdir(exist_ok=True)
    
    # Set environment variables for test configuration
    os.environ['OPENCHRONICLE_STORAGE_PATH'] = str(test_storage)
    os.environ['OPENCHRONICLE_TEST_MODE'] = 'true'
    
    yield {
        'story_id': test_story_id,
        'storage_path': str(test_storage),
        'temp_dir': temp_test_dir
    }
    
    # Cleanup environment variables
    os.environ.pop('OPENCHRONICLE_STORAGE_PATH', None)
    os.environ.pop('OPENCHRONICLE_TEST_MODE', None)


@pytest.fixture
def mock_model_orchestrator():
    """Create a mock model orchestrator for testing."""
    orchestrator = MockModelOrchestrator(
        simulate_failures=False,
        enable_fallback=True,
        max_retries=3
    )
    return orchestrator


@pytest.fixture
def mock_database_manager():
    """Create a mock database manager for testing."""
    db_manager = MockDatabaseManager(
        simulate_delay=0.01,
        simulate_failures=False,
        failure_rate=0.05
    )
    return db_manager


@pytest.fixture
def scene_orchestrator(clean_test_environment):
    """Create a scene orchestrator for testing."""
    story_id = clean_test_environment['story_id']
    orchestrator = SceneOrchestrator(
        story_id=story_id,
        config={'enable_logging': False}
    )
    return orchestrator


@pytest.fixture  
def timeline_orchestrator(clean_test_environment):
    """Create a timeline orchestrator for testing."""
    story_id = clean_test_environment['story_id']
    orchestrator = TimelineOrchestrator(story_id=story_id)
    return orchestrator


@pytest.fixture
def memory_orchestrator():
    """Create a memory orchestrator for testing."""
    return MemoryOrchestrator()


@pytest.fixture
def context_orchestrator():
    """Create a context orchestrator for testing."""
    return ContextOrchestrator()


@pytest.fixture
def model_orchestrator():
    """Create a model orchestrator for testing."""
    return ModelOrchestrator()


@pytest.fixture
def sample_scene_data():
    """Create sample scene data for testing."""
    return {
        'story_id': 'test_story_123',
        'scene_content': 'The hero enters the dark forest, sensing danger lurking in the shadows.',
        'character_ids': ['char_001', 'char_002'],
        'location': 'Dark Forest',
        'mood': 'tense',
        'chapter': 3,
        'scene_number': 7,
        'timestamp': '2024-01-15T14:30:00Z',
        'tags': ['adventure', 'danger', 'forest'],
        'context_data': {
            'weather': 'misty',
            'time_of_day': 'afternoon',
            'season': 'autumn'
        }
    }


# ===== UTILITY FUNCTIONS =====

def create_test_scene_data(scene_id: str = None, **kwargs) -> Dict[str, Any]:
    """Create test scene data with default values."""
    if scene_id is None:
        scene_id = f"test_scene_{pytest.importorskip('uuid').uuid4().hex[:8]}"
    
    default_data = {
        'scene_id': scene_id,
        'user_input': kwargs.get('user_input', 'Test user input'),
        'model_output': kwargs.get('model_output', 'Test model output'),
        'memory_snapshot': kwargs.get('memory_snapshot', {'characters': {}, 'location': 'test'}),
        'flags': kwargs.get('flags', ['test']),
        'context_refs': kwargs.get('context_refs', []),
        'analysis_data': kwargs.get('analysis_data', {'mood': 'neutral', 'tokens': 50}),
        'scene_label': kwargs.get('scene_label', 'test_scene'),
        'model_name': kwargs.get('model_name', 'test_model'),
        'timestamp': kwargs.get('timestamp', 1234567890)
    }
    
    # Override with any provided kwargs
    default_data.update(kwargs)
    return default_data


def create_test_character_data(character_name: str = None, **kwargs) -> Dict[str, Any]:
    """Create test character data with default values."""
    if character_name is None:
        character_name = f"test_character_{pytest.importorskip('uuid').uuid4().hex[:8]}"
    
    default_data = {
        'name': character_name,
        'personality': kwargs.get('personality', 'Test personality'),
        'background': kwargs.get('background', 'Test background'),
        'current_state': kwargs.get('current_state', {
            'emotional_state': 'neutral',
            'physical_state': 'healthy',
            'location': 'test_location'
        }),
        'relationships': kwargs.get('relationships', {}),
        'goals': kwargs.get('goals', ['test_goal'])
    }
    
    # Override with any provided kwargs
    default_data.update(kwargs)
    return default_data


def create_test_memory_snapshot(**kwargs) -> Dict[str, Any]:
    """Create test memory snapshot with default values."""
    default_data = {
        'characters': kwargs.get('characters', {}),
        'world_state': kwargs.get('world_state', {'location': 'test_location'}),
        'recent_events': kwargs.get('recent_events', []),
        'flags': kwargs.get('flags', []),
        'timestamp': kwargs.get('timestamp', 1234567890)
    }
    
    # Override with any provided kwargs
    default_data.update(kwargs)
    return default_data


# ===== TEST UTILITIES =====

class TestUtils:
    """Utility functions for testing."""
    
    def __init__(self):
        import random
        self.random = random
    
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
    
    def generate_test_scene(self) -> Dict[str, Any]:
        """Generate test scene data for scene orchestrator testing."""
        return {
            "scene_id": f"test_scene_{self.random.randint(1000, 9999)}",
            "user_input": f"Test user input {self.random.randint(1, 100)}",
            "model_output": f"Test model response {self.random.randint(1, 100)}",
            "structured_tags": ["test", "scene", "generated"],
            "timestamp": "2025-01-01T12:00:00Z",
            "story_id": "test_story",
            "scene_metadata": {
                "mood": "test",
                "characters": ["test_character"],
                "location": "test_location"
            }
        }
    
    def generate_test_timeline(self) -> Dict[str, Any]:
        """Generate test timeline data for timeline orchestrator testing."""
        return {
            "timeline_id": f"test_timeline_{self.random.randint(1000, 9999)}",
            "story_id": "test_story",
            "entries": [
                {
                    "entry_id": f"entry_{i}",
                    "scene_id": f"scene_{i}",
                    "timestamp": f"2025-01-01T12:{i:02d}:00Z",
                    "sequence": i
                }
                for i in range(1, 4)
            ],
            "metadata": {
                "created": "2025-01-01T12:00:00Z",
                "last_updated": "2025-01-01T12:00:00Z",
                "total_entries": 3
            }
        }
    

# ===== MOCK DATA GENERATORS =====

class MockDataGenerator:
    """Generate realistic mock data for testing."""
    
    @staticmethod
    def generate_scene_sequence(count: int = 5) -> List[Dict[str, Any]]:
        """Generate a sequence of related scenes."""
        scenes = []
        for i in range(count):
            scenes.append(create_test_scene_data(
                scene_id=f"scene_{i+1:03d}",
                user_input=f"Scene {i+1} user input",
                model_output=f"Scene {i+1} generated content with narrative elements.",
                memory_snapshot={
                    'scene_number': i+1,
                    'character_state': 'active',
                    'location': f'location_{i+1}'
                },
                flags=[f'flag_{i+1}'],
                context_refs=[f'context_{i+1}'],
                scene_label=f'scene_{i+1}'
            ))
        return scenes
    
    @staticmethod
    def generate_character_sequence(count: int = 3) -> List[Dict[str, Any]]:
        """Generate a sequence of related characters."""
        characters = []
        for i in range(count):
            characters.append(create_test_character_data(
                character_name=f"character_{i+1}",
                personality=f"Personality {i+1}",
                background=f"Background {i+1}",
                current_state={
                    'emotional_state': ['happy', 'sad', 'angry'][i % 3],
                    'physical_state': 'healthy',
                    'location': f'location_{i+1}'
                }
            ))
        return characters
    
    @staticmethod
    def generate_memory_sequence(count: int = 3) -> List[Dict[str, Any]]:
        """Generate a sequence of memory snapshots."""
        memories = []
        for i in range(count):
            memories.append(create_test_memory_snapshot(
                characters={
                    f"character_{j+1}": create_test_character_data(f"character_{j+1}")
                    for j in range(i+1)
                },
                world_state={
                    'location': f'location_{i+1}',
                    'time_of_day': ['morning', 'afternoon', 'evening'][i % 3]
                },
                recent_events=[f"Event {j+1}" for j in range(i+1)],
                flags=[f"flag_{j+1}" for j in range(i+1)]
            ))
        return memories


# ===== CONFIGURATION =====

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "mock_only: mark test as using only mock data"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add default markers."""
    for item in items:
        # Add default markers based on test location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add slow marker for tests that might take time
        if any(keyword in item.name.lower() for keyword in ['performance', 'stress', 'load']):
            item.add_marker(pytest.mark.slow)
