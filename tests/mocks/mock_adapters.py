"""
Mock adapters for testing OpenChronicle.

This module contains all mock AI adapters used for testing purposes.
Mock adapters should NEVER be used in production - they provide simulated
responses only and are designed for development, testing, and demonstrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC
import random

# Import the base adapter from production code
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from core.model_adapter import ModelAdapter
from utilities.logging_system import log_system_event, log_info, log_error


class MockAdapter(ModelAdapter):
    """Mock text adapter for testing and development."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.responses = config.get("responses", [
            "The story continues with rich detail and engaging narrative.",
            "Your character moves forward, discovering new possibilities.", 
            "The world around you shifts as the tale unfolds.",
            "An unexpected development changes everything.",
            "The path ahead becomes clearer as you proceed."
        ])
        self.current_index = 0
        
    async def initialize(self) -> bool:
        """Initialize mock adapter."""
        self.initialized = True
        log_system_event("mock_adapter_init", "Mock text adapter initialized for testing")
        return True
        
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a mock response."""
        # ALWAYS warn when mock adapter is used for generation
        log_system_event("mock_adapter_usage", 
                        "WARNING: Mock adapter generating simulated response - NOT real AI!")
        
        # Cycle through predefined responses
        response = self.responses[self.current_index % len(self.responses)]
        self.current_index += 1
        
        # Add some variability to make responses feel less static
        if random.random() < 0.3:  # 30% chance of variation
            variations = [
                f"[Mock Response] {response}",
                f"{response} (This is a simulated response for testing)",
                f"🤖 Mock AI: {response}"
            ]
            response = random.choice(variations)
        
        log_info(f"Mock adapter generated response: {response[:50]}...")
        return response
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get mock model information."""
        return {
            "provider": "Mock",
            "model_name": self.model_name,
            "responses_count": len(self.responses),
            "current_index": self.current_index,
            "initialized": self.initialized,
            "warning": "This is a MOCK adapter - provides simulated responses only!"
        }


class MockImageAdapter(ModelAdapter):
    """Mock image adapter for testing and development."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.responses = config.get("responses", [
            "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzMzNzNkYyIvPgogIDx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zNWVtIj5Nb2NrIEltYWdlPC90ZXh0Pgo8L3N2Zz4K"
        ])
        self.current_index = 0
        
    async def initialize(self) -> bool:
        """Initialize mock image adapter."""
        self.initialized = True
        log_system_event("mock_image_adapter_init", "Mock image adapter initialized for testing")
        return True
        
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a mock image response."""
        log_system_event("mock_image_adapter_usage", 
                        "WARNING: Mock image adapter generating simulated image - NOT real AI!")
        
        # Cycle through predefined image responses
        response = self.responses[self.current_index % len(self.responses)]
        self.current_index += 1
        
        log_info(f"Mock image adapter generated mock image for prompt: {prompt[:30]}...")
        return response
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get mock image model information."""
        return {
            "provider": "MockImage", 
            "model_name": self.model_name,
            "responses_count": len(self.responses),
            "current_index": self.current_index,
            "initialized": self.initialized,
            "warning": "This is a MOCK image adapter - provides simulated images only!"
        }


def create_mock_adapter(adapter_type: str, config: Dict[str, Any]) -> Optional[ModelAdapter]:
    """
    Factory function to create mock adapters.
    
    Args:
        adapter_type: Type of mock adapter ("mock" or "mock_image")
        config: Adapter configuration
        
    Returns:
        Mock adapter instance or None if unknown type
    """
    if adapter_type == "mock":
        return MockAdapter(config)
    elif adapter_type == "mock_image":
        return MockImageAdapter(config)
    else:
        log_error(f"Unknown mock adapter type: {adapter_type}")
        return None


def get_mock_registry_entries() -> Dict[str, Any]:
    """
    Get mock adapter entries for the model registry.
    
    Returns:
        Dict with mock adapter configurations for testing
    """
    return {
        "text_models": {
            "testing": [
                {
                    "name": "mock",
                    "provider": "mock",
                    "enabled": True,
                    "priority": 99,
                    "model_name": "mock-model",
                    "supports_nsfw": True,
                    "content_types": [
                        "general",
                        "fantasy", 
                        "sci-fi",
                        "mystery",
                        "creative",
                        "mature",
                        "testing"
                    ],
                    "description": "Mock model for testing and development - NOT FOR PRODUCTION USE",
                    "fallbacks": [],
                    "config": {
                        "responses": [
                            "The story continues with rich detail and engaging narrative.",
                            "Your character moves forward, discovering new possibilities.",
                            "The world around you shifts as the tale unfolds.",
                            "An unexpected development changes everything.",
                            "The path ahead becomes clearer as you proceed."
                        ]
                    }
                },
                {
                    "name": "test-sync",
                    "enabled": True,
                    "type": "mock",
                    "model_name": "test-sync",
                    "description": "Synchronous test adapter for unit testing"
                }
            ]
        },
        "image_models": {
            "testing": [
                {
                    "name": "mock_image",
                    "provider": "mock",
                    "enabled": True,
                    "priority": 99,
                    "model_name": "mock-image-model",
                    "supports_nsfw": True,
                    "content_types": [
                        "character_portraits",
                        "scene_images", 
                        "general_images",
                        "testing"
                    ],
                    "description": "Mock image generator for testing and development - NOT FOR PRODUCTION USE",
                    "fallbacks": [],
                    "config": {
                        "size": "1024x1024",
                        "responses": [
                            "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzMzNzNkYyIvPgogIDx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zNWVtIj5Nb2NrIEltYWdlPC90ZXh0Pgo8L3N2Zz4K"
                        ]
                    }
                }
            ]
        }
    }


def get_mock_fallback_chains() -> Dict[str, List[str]]:
    """
    Get fallback chains that include mock adapters (for testing only).
    
    Returns:
        Dict with fallback chains including mock adapters
    """
    return {
        "testing_text": [
            "mock"
        ],
        "testing_image": [
            "mock_image"
        ],
        "development_fallback": [
            "mock"
        ]
    }


# Export the main classes and functions
__all__ = [
    "MockAdapter",
    "MockImageAdapter", 
    "create_mock_adapter",
    "get_mock_registry_entries",
    "get_mock_fallback_chains"
]
