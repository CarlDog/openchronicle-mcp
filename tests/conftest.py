"""
Pytest configuration and fixtures for OpenChronicle tests.
Sets up test logging and common test utilities.
"""

import os
import sys
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utilities.logging_system import setup_logging, get_logger


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Automatically set up logging for all tests using tests/logs directory."""
    test_logs_dir = Path(__file__).parent / "logs"
    test_logs_dir.mkdir(exist_ok=True)
    
    # Set up the logger to use tests/logs
    logger = setup_logging(log_dir=test_logs_dir)
    logger.log_system_event("test_session", "Test session started", {
        "test_logs_dir": str(test_logs_dir)
    })
    
    yield logger
    
    # Log session end
    logger.log_system_event("test_session", "Test session completed")


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_test_database():
    """Mock database operations to use test paths."""
    with patch('core.database._is_test_context', return_value=True):
        yield


@pytest.fixture
def clean_test_data():
    """Clean up test data before and after tests."""
    test_data_dir = project_root / "storage" / "temp" / "test_data"
    
    # Clean before test
    if test_data_dir.exists():
        for item in test_data_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    
    yield
    
    # Clean after test (optional - comment out if you want to inspect test data)
    # if test_data_dir.exists():
    #     for item in test_data_dir.iterdir():
    #         if item.is_dir():
    #             shutil.rmtree(item)
    #         else:
    #             item.unlink()


@pytest.fixture
def test_registry_path():
    """Provide path to test-only registry with mock adapters."""
    return Path(__file__).parent / "mocks" / "test_registry.json"


@pytest.fixture
def mock_model_manager(test_registry_path):
    """Create ModelManager instance using test registry."""
    from core.model_adapter import ModelManager
    with patch.object(ModelManager, '_load_registry') as mock_load:
        with open(test_registry_path, 'r') as f:
            test_config = json.load(f)
        mock_load.return_value = test_config
        
        manager = ModelManager()
        return manager


def pytest_runtest_setup(item):
    """Setup for each test - log test start."""
    logger = get_logger()
    logger.log_system_event("test_start", f"Starting test: {item.name}", {
        "test_file": str(item.fspath),
        "test_function": item.name
    })


def pytest_runtest_teardown(item, nextitem):
    """Teardown for each test - log test completion."""
    logger = get_logger()
    logger.log_system_event("test_end", f"Completed test: {item.name}", {
        "test_file": str(item.fspath),
        "test_function": item.name
    })


def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    logger = get_logger()
    logger.log_system_event("pytest_session", "Pytest session starting", {
        "total_items": len(session.items) if hasattr(session, 'items') else 0
    })


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    logger = get_logger()
    logger.log_system_event("pytest_session", "Pytest session finished", {
        "exit_status": exitstatus,
        "test_results": "success" if exitstatus == 0 else "failure"
    })
