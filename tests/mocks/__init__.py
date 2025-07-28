"""
Mock adapters and testing utilities for OpenChronicle.

This package contains all mock AI adapters and testing utilities.
Mock functionality is completely isolated from production code.

Usage:
    from tests.mocks import MockAdapter, MockImageAdapter, create_mock_adapter
    
    # Create a mock adapter for testing
    config = {"model_name": "test-model", "responses": ["Test response"]}
    mock_adapter = create_mock_adapter("mock", config)
"""

from .mock_adapters import (
    MockAdapter,
    MockImageAdapter,
    create_mock_adapter,
    get_mock_registry_entries,
    get_mock_fallback_chains
)

__all__ = [
    "MockAdapter",
    "MockImageAdapter", 
    "create_mock_adapter",
    "get_mock_registry_entries",
    "get_mock_fallback_chains"
]
