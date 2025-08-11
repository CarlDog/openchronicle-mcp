"""
Pytest configuration and fixtures for OpenChronicle tests.

Provides common test setup, mock objects, and utility functions
for both unit and integration tests, with support for the four-tier
testing strategy (production-real, production-mock, smoke, stress).
"""

import asyncio
import os
import shutil
import sys
import tempfile
import uuid
from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest


# -----------------------------------------------------------------------------
# PYTHONPATH SETUP
# -----------------------------------------------------------------------------
# Add the project root to the Python path (prefer editable install in CI)
project_root = Path(__file__).resolve().parent.parent
src_dir = project_root / "src"
# Ensure src/ is on path for direct test execution without editable install
for p in (project_root, src_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# -----------------------------------------------------------------------------
# TEST CONFIG MANAGER
# -----------------------------------------------------------------------------
class TestConfigurationManager:
    """Manages test configurations for different testing tiers."""

    def __init__(self) -> None:
        self.current_tier = self._detect_current_tier()
        self.mock_adapters_enabled = self._should_use_mock_adapters()

    def _detect_current_tier(self) -> str:
        """Detect which test tier is currently running."""
        tier = os.environ.get("OPENCHRONICLE_TEST_TIER", "standard")
        if tier != "standard":
            return tier

        argv_str = " ".join(sys.argv)
        if "production_real" in argv_str:
            return "production_real"
        if "production_mock" in argv_str or "mock_only" in argv_str:
            return "production_mock"
        if "smoke" in argv_str or "core" in argv_str:
            return "smoke"
        if "stress" in argv_str or "chaos" in argv_str:
            return "stress"
        return "standard"

    def _should_use_mock_adapters(self) -> bool:
        """Determine if mock adapters should be used."""
        return self.current_tier in ["production_mock", "smoke", "stress", "standard"]

    def get_model_adapter_config(self) -> dict[str, Any]:
        """Get model adapter configuration for current test tier."""
        if self.mock_adapters_enabled:
            return {
                "adapter_type": "mock",
                "mock_responses": True,
                "enable_real_api_calls": False,
                "timeout": 5.0,
            }
        return {
            "adapter_type": "real",
            "mock_responses": False,
            "enable_real_api_calls": True,
            "timeout": 30.0,
            "retry_attempts": 3,
        }

    def get_database_config(self) -> dict[str, Any]:
        """Get database configuration for current test tier."""
        base_config: dict[str, Any] = {
            "use_memory_db": True,
            "enable_foreign_keys": True,
            "auto_vacuum": True,
        }
        if self.current_tier == "stress":
            base_config.update(
                {"connection_pool_size": 10, "max_connections": 50, "timeout": 60.0}
            )
        return base_config


# Global configuration instance
test_config = TestConfigurationManager()


# -----------------------------------------------------------------------------
# PYTEST OPTIONS / MARKERS
# -----------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("openchronicle")
    group.addoption(
        "--keep-artifacts",
        action="store_true",
        default=False,
        help="Do not delete test artifacts at the end of the session.",
    )
    group.addoption(
        "--artifact-root",
        action="store",
        default=None,
        help="Override artifact root directory for test outputs.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers and test tier env."""
    # Markers
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "mock_only: mark test as using only mock data")

    # Set tier env from -m expression when provided
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "production_real" in markexpr:
        os.environ["OPENCHRONICLE_TEST_TIER"] = "production_real"
    elif "production_mock" in markexpr:
        os.environ["OPENCHRONICLE_TEST_TIER"] = "production_mock"
    elif "smoke" in markexpr:
        os.environ["OPENCHRONICLE_TEST_TIER"] = "smoke"
    elif "stress" in markexpr:
        os.environ["OPENCHRONICLE_TEST_TIER"] = "stress"


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Modify test collection to add default markers based on file path / name."""
    for item in items:
        p = str(item.fspath)
        if "integration" in p:
            item.add_marker(pytest.mark.integration)
        elif "unit" in p:
            item.add_marker(pytest.mark.unit)

        if any(k in item.name.lower() for k in ["performance", "stress", "load"]):
            item.add_marker(pytest.mark.slow)


# -----------------------------------------------------------------------------
# ARTIFACT MANAGEMENT
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def artifact_root(pytestconfig: pytest.Config) -> Path:
    """
    One sandbox for all test artifacts. Everything that writes to disk should
    land somewhere under here so we can clean it safely at session end.
    """
    override: str | None = pytestconfig.getoption("--artifact-root")
    if override:
        root = Path(override).expanduser().resolve()
    else:
        root = (
            Path(tempfile.gettempdir()) / f"openchronicle_tests_{uuid.uuid4().hex[:8]}"
        )
    root.mkdir(parents=True, exist_ok=True)
    os.environ["OPENCHRONICLE_ARTIFACT_ROOT"] = str(root)
    return root


@pytest.fixture(autouse=True, scope="session")
def _cwd_into_artifact_root(artifact_root: Path) -> Iterator[None]:
    """
    Autouse: run the entire session from inside artifact_root so any unguarded
    writes (logs, tmp files) end up in a safe place we can delete.
    """
    prev = Path.cwd()
    os.chdir(artifact_root)
    try:
        yield
    finally:
        os.chdir(prev)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Final cleanup of the artifact root unless user asked to keep it."""
    keep = session.config.getoption("--keep-artifacts")
    root_env = os.environ.get("OPENCHRONICLE_ARTIFACT_ROOT", "")
    root = Path(root_env) if root_env else None
    if keep or not root or not root.exists():
        print(f"[CLEANUP] Skipping artifact deletion: keep={keep}, root={root}")
        return
    try:
        shutil.rmtree(root, ignore_errors=True)
        print(f"[CLEANUP] Removed test artifact root: {root}")
    except Exception as e:
        print(f"[CLEANUP ERROR] Failed to remove {root}: {e}")


@pytest.fixture
def temp_test_dir(artifact_root: Path) -> Iterator[str]:
    """Per-test temporary directory under artifact_root (auto-cleaned)."""
    d = artifact_root / f"case_{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    try:
        yield str(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# -----------------------------------------------------------------------------
# EVENT LOOP (if not using pytest-asyncio's auto policy)
# -----------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


# -----------------------------------------------------------------------------
# MOCK ADAPTERS
# -----------------------------------------------------------------------------
def get_mock_model_adapter():
    """Create a mock model adapter for testing."""
    mock_adapter = AsyncMock()
    mock_adapter.generate_response.return_value = {
        "content": "Mock response content",
        "metadata": {"model": "mock-model", "tokens": 50},
    }
    mock_adapter.is_available.return_value = True
    mock_adapter.get_model_info.return_value = {
        "name": "mock-model",
        "provider": "mock",
        "capabilities": ["text_generation"],
    }
    return mock_adapter


def get_mock_image_adapter():
    """Create a mock image adapter for testing."""
    mock_adapter = AsyncMock()
    mock_adapter.generate_image.return_value = {
        "image_data": b"mock_image_data",
        "metadata": {"format": "png", "size": "512x512"},
    }
    mock_adapter.is_available.return_value = True
    return mock_adapter


# Enhanced mock adapters (imported normally)
from tests.fixtures.mock_adapters import MockDatabaseManager  # noqa: E402
from tests.fixtures.mock_adapters import MockModelOrchestrator  # noqa: E402


# -----------------------------------------------------------------------------
# TIER-BASED FIXTURES
# -----------------------------------------------------------------------------
@pytest.fixture
def tier_config():
    """Provide test tier configuration."""
    return test_config


@pytest.fixture
def model_adapter(tier_config):
    """Provide model adapter based on test tier."""
    if tier_config.mock_adapters_enabled:
        return get_mock_model_adapter()
    pytest.skip("Real model adapter not configured for testing")


@pytest.fixture
def image_adapter(tier_config):
    """Provide image adapter based on test tier."""
    if tier_config.mock_adapters_enabled:
        return get_mock_image_adapter()
    pytest.skip("Real image adapter not configured for testing")


# -----------------------------------------------------------------------------
# ORCHESTRATOR FIXTURES (lazy imports to avoid import-time side effects)
# -----------------------------------------------------------------------------
@pytest.fixture
def scene_orchestrator(clean_test_environment):
    """Create a scene orchestrator for testing."""
    from openchronicle.domain.services.scenes.scene_orchestrator import (
        SceneOrchestrator,
    )

    story_id = clean_test_environment["story_id"]
    return SceneOrchestrator(story_id=story_id, config={"enable_logging": False})


@pytest.fixture
def timeline_orchestrator(clean_test_environment):
    """Create a timeline orchestrator for testing."""
    from openchronicle.domain.services.timeline.timeline_orchestrator import (
        TimelineOrchestrator,
    )

    story_id = clean_test_environment["story_id"]
    return TimelineOrchestrator(story_id=story_id)


@pytest.fixture
def memory_orchestrator():
    """Create a memory orchestrator for testing."""
    from openchronicle.infrastructure.memory.memory_orchestrator import (
        MemoryOrchestrator,
    )

    return MemoryOrchestrator()


@pytest.fixture
def context_orchestrator():
    """Create a context orchestrator for testing."""
    from openchronicle.infrastructure.content.context.orchestrator import (
        ContextOrchestrator,
    )

    return ContextOrchestrator()


@pytest.fixture
def model_orchestrator():
    """Create a model orchestrator for testing."""
    from openchronicle.domain.models.model_orchestrator import ModelOrchestrator

    return ModelOrchestrator()


# -----------------------------------------------------------------------------
# BASIC DATA / ENV FIXTURES
# -----------------------------------------------------------------------------
@pytest.fixture
def test_story_id() -> str:
    """Generate a unique story ID for testing."""
    return f"test_story_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def clean_test_environment(
    temp_test_dir: str, test_story_id: str
) -> Iterator[dict[str, Any]]:
    """Create a clean test environment with temporary storage."""
    test_storage = Path(temp_test_dir) / "storage"
    (test_storage / "characters").mkdir(parents=True, exist_ok=True)
    (test_storage / "scenes").mkdir(parents=True, exist_ok=True)
    (test_storage / "memory").mkdir(parents=True, exist_ok=True)
    (test_storage / "timeline").mkdir(parents=True, exist_ok=True)

    os.environ["OPENCHRONICLE_STORAGE_PATH"] = str(test_storage)
    os.environ["OPENCHRONICLE_TEST_MODE"] = "true"

    try:
        yield {
            "story_id": test_story_id,
            "storage_path": str(test_storage),
            "temp_dir": temp_test_dir,
        }
    finally:
        os.environ.pop("OPENCHRONICLE_STORAGE_PATH", None)
        os.environ.pop("OPENCHRONICLE_TEST_MODE", None)


# -----------------------------------------------------------------------------
# TEST UTILITIES / MOCK DATA
# -----------------------------------------------------------------------------
def create_test_scene_data(scene_id: str | None = None, **kwargs) -> dict[str, Any]:
    """Create test scene data with default values."""
    if scene_id is None:
        scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
    data: dict[str, Any] = {
        "scene_id": scene_id,
        "user_input": kwargs.get("user_input", "Test user input"),
        "model_output": kwargs.get("model_output", "Test model output"),
        "memory_snapshot": kwargs.get(
            "memory_snapshot", {"characters": {}, "location": "test"}
        ),
        "flags": kwargs.get("flags", ["test"]),
        "context_refs": kwargs.get("context_refs", []),
        "analysis_data": kwargs.get("analysis_data", {"mood": "neutral", "tokens": 50}),
        "scene_label": kwargs.get("scene_label", "test_scene"),
        "model_name": kwargs.get("model_name", "test_model"),
        "timestamp": kwargs.get("timestamp", 1234567890),
    }
    data.update(kwargs)
    return data


def create_test_character_data(
    character_name: str | None = None, **kwargs
) -> dict[str, Any]:
    """Create test character data with default values."""
    if character_name is None:
        character_name = f"test_character_{uuid.uuid4().hex[:8]}"
    data: dict[str, Any] = {
        "name": character_name,
        "personality": kwargs.get("personality", "Test personality"),
        "background": kwargs.get("background", "Test background"),
        "current_state": kwargs.get(
            "current_state",
            {
                "emotional_state": "neutral",
                "physical_state": "healthy",
                "location": "test_location",
            },
        ),
        "relationships": kwargs.get("relationships", {}),
        "goals": kwargs.get("goals", ["test_goal"]),
    }
    data.update(kwargs)
    return data


def create_test_memory_snapshot(**kwargs) -> dict[str, Any]:
    """Create test memory snapshot with default values."""
    data: dict[str, Any] = {
        "characters": kwargs.get("characters", {}),
        "world_state": kwargs.get("world_state", {"location": "test_location"}),
        "recent_events": kwargs.get("recent_events", []),
        "flags": kwargs.get("flags", []),
        "timestamp": kwargs.get("timestamp", 1234567890),
    }
    data.update(kwargs)
    return data


@pytest.fixture
def sample_scene_data() -> dict[str, Any]:
    """Basic scene data payload for scene orchestrator tests."""
    return {
        "scene_content": "Test scene content",
        "location": "test_location",
        "tags": ["test"],
        "scene_number": 1,
    }


class TestUtils:
    """Utility functions for testing."""

    @staticmethod
    def validate_scene_data(scene_data: dict[str, Any]) -> bool:
        required = ["scene_id", "user_input", "model_output"]
        return all(k in scene_data for k in required)

    @staticmethod
    def validate_orchestrator_initialization(orchestrator: Any) -> bool:
        return bool(getattr(orchestrator, "story_id", None))

    @staticmethod
    def create_test_scene_sequence(orchestrator, count: int = 3):
        scenes = []
        for i in range(count):
            scene_data = {
                "user_input": f"Test user input {i+1}",
                "model_output": f"Test model output {i+1}",
                "memory_snapshot": {"scene_number": i + 1},
            }
            scene = orchestrator.create_scene(**scene_data)
            scenes.append(scene)
        return scenes

    @staticmethod
    def generate_test_scene() -> dict[str, Any]:
        r = uuid.uuid4().hex[:6]
        return {
            "scene_id": f"test_scene_{r}",
            "user_input": f"Test user input {r}",
            "model_output": f"Test model response {r}",
            "structured_tags": ["test", "scene", "generated"],
            "timestamp": "2025-01-01T12:00:00Z",
            "story_id": "test_story",
            "scene_metadata": {
                "mood": "test",
                "characters": ["test_character"],
                "location": "test_location",
            },
        }

    @staticmethod
    def generate_test_timeline() -> dict[str, Any]:
        return {
            "timeline_id": f"test_timeline_{uuid.uuid4().hex[:6]}",
            "story_id": "test_story",
            "entries": [
                {
                    "entry_id": f"entry_{i}",
                    "scene_id": f"scene_{i}",
                    "timestamp": f"2025-01-01T12:{i:02d}:00Z",
                    "sequence": i,
                }
                for i in range(1, 4)
            ],
            "metadata": {
                "created": "2025-01-01T12:00:00Z",
                "last_updated": "2025-01-01T12:00:00Z",
                "total_entries": 3,
            },
        }


# -----------------------------------------------------------------------------
# MOCK ORCHESTRATOR FIXTURES — Option A defaults + factories for special cases
# -----------------------------------------------------------------------------
@pytest.fixture
def mock_model_orchestrator():
    """Simple default mock; no dynamic knobs (Pylance-friendly)."""
    return MockModelOrchestrator()


@pytest.fixture
def mock_database_manager():
    """Simple default mock; no dynamic knobs (Pylance-friendly)."""
    return MockDatabaseManager()


@pytest.fixture
def make_mock_model_orchestrator() -> Callable[..., Any]:
    """
    Factory for rare tests that need custom behavior:
        m = make_mock_model_orchestrator(simulate_failures=True, max_retries=2)
    Only sets attributes that actually exist on the mock.
    """

    def _make(**opts: Any) -> Any:
        m = MockModelOrchestrator()
        for k, v in opts.items():
            if hasattr(m, k):
                setattr(m, k, v)
        return m

    return _make


@pytest.fixture
def make_mock_database_manager() -> Callable[..., Any]:
    """
    Factory for rare tests that need custom DB behavior:
        db = make_mock_database_manager(simulate_delay=0.05, failure_rate=0.1)
    Only sets attributes that actually exist on the mock.
    """

    def _make(**opts: Any) -> Any:
        db = MockDatabaseManager()
        for k, v in opts.items():
            if hasattr(db, k):
                setattr(db, k, v)
        return db

    return _make
