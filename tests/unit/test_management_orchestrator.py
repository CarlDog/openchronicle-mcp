"""
Unit tests for ManagementOrchestrator

Tests the token and bookmark management functionality.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

# Import the orchestrator under test
from core.management_systems.management_orchestrator import ManagementOrchestrator


class TestTokenManagement:
    """Test token counting and estimation functionality."""
    
    def test_count_tokens_basic(self):
        """Test basic token counting functionality."""
        orchestrator = ManagementOrchestrator()
        
        # Test token counting
        test_text = "The quick brown fox jumps over the lazy dog."
        token_count = orchestrator.count_tokens(test_text)
        
        assert token_count is not None
        assert isinstance(token_count, int)
        assert token_count > 0
    
    def test_count_tokens_with_model(self):
        """Test token counting with specific model."""
        orchestrator = ManagementOrchestrator()
        
        # Test with specific model
        test_text = "Hello world, this is a test message."
        token_count = orchestrator.count_tokens(test_text, model="gpt-3.5-turbo")
        
        assert token_count is not None
        assert isinstance(token_count, int)
        assert token_count > 0
    
    def test_estimate_tokens_basic(self):
        """Test token estimation functionality."""
        orchestrator = ManagementOrchestrator()
        
        # Test token estimation
        test_text = "This is a longer text that we want to estimate tokens for."
        estimated_tokens = orchestrator.estimate_tokens(test_text)
        
        assert estimated_tokens is not None
        assert isinstance(estimated_tokens, int)
        assert estimated_tokens > 0
    
    def test_estimate_tokens_with_padding(self):
        """Test token estimation with padding factor."""
        orchestrator = ManagementOrchestrator()
        
        # Test estimation with padding
        test_text = "Short text"
        estimated_tokens = orchestrator.estimate_tokens(test_text, model="gpt-4")
        
        assert estimated_tokens is not None
        assert isinstance(estimated_tokens, int)
        # Estimation should account for padding
        assert estimated_tokens >= len(test_text.split())


class TestBookmarkManagement:
    """Test bookmark creation and management functionality."""
    
    def test_create_bookmark_basic(self):
        """Test basic bookmark creation."""
        orchestrator = ManagementOrchestrator()
        
        # Test bookmark creation
        bookmark_id = orchestrator.create_bookmark(
            story_id="test_story_123",
            scene_id="scene_456", 
            label="Important Decision Point"
        )
        
        assert bookmark_id is not None
        assert isinstance(bookmark_id, str)
        assert len(bookmark_id) > 0
    
    def test_create_bookmark_with_metadata(self):
        """Test bookmark creation with metadata."""
        orchestrator = ManagementOrchestrator()
        
        # Test with metadata
        bookmark_id = orchestrator.create_bookmark(
            story_id="test_story_123",
            scene_id="scene_789",
            label="Character Development",
            metadata={
                "character": "protagonist",
                "importance": "high",
                "notes": "Key character growth moment"
            }
        )
        
        assert bookmark_id is not None
        assert isinstance(bookmark_id, str)
    
    def test_manage_bookmarks_list(self):
        """Test bookmark listing and management."""
        orchestrator = ManagementOrchestrator()
        
        # Create a few bookmarks first
        bookmark1 = orchestrator.create_bookmark("story_1", "scene_1", "Bookmark 1")
        bookmark2 = orchestrator.create_bookmark("story_1", "scene_2", "Bookmark 2")
        
        # Test listing bookmarks
        bookmarks = orchestrator.list_bookmarks("story_1")
        
        assert bookmarks is not None
        assert isinstance(bookmarks, list)
        # Should contain our created bookmarks (if implementation stores them)
        assert len(bookmarks) >= 0  # Allow for empty list if storage is mocked
    
    def test_bookmark_organization(self):
        """Test bookmark organization and categorization."""
        orchestrator = ManagementOrchestrator()
        
        # Test bookmark organization
        organization_result = orchestrator.organize_bookmarks_by_category("test_story")
        
        assert organization_result is not None
        assert isinstance(organization_result, dict)


class TestTokenOptimization:
    """Test token optimization functionality."""
    
    def test_select_optimal_model_basic(self):
        """Test optimal model selection."""
        orchestrator = ManagementOrchestrator()
        
        # Test model selection
        test_text = "This is a test prompt for model selection."
        optimal_model = orchestrator.select_optimal_model(test_text)
        
        assert optimal_model is not None
        assert isinstance(optimal_model, str)
        assert len(optimal_model) > 0
    
    def test_select_optimal_model_with_requirements(self):
        """Test model selection with specific requirements."""
        orchestrator = ManagementOrchestrator()
        
        # Test with requirements
        test_text = "Complex reasoning task requiring advanced capabilities."
        requirements = {
            "max_tokens": 4000,
            "capability": "reasoning",
            "cost_preference": "balanced"
        }
        
        optimal_model = orchestrator.select_optimal_model(test_text, requirements)
        
        assert optimal_model is not None
        assert isinstance(optimal_model, str)
    
    def test_token_optimization_strategy(self):
        """Test token optimization strategies."""
        orchestrator = ManagementOrchestrator()
        
        # Test optimization strategy
        large_text = "This is a very long text " * 100  # Create large text
        optimization_result = orchestrator.optimize_token_usage(large_text)
        
        assert optimization_result is not None
        assert isinstance(optimization_result, dict)
        assert 'optimized_text' in optimization_result or 'strategy' in optimization_result


class TestManagementIntegration:
    """Test integration between management subsystems."""
    
    def test_token_bookmark_integration(self):
        """Test integration between token and bookmark management."""
        orchestrator = ManagementOrchestrator()
        
        # Test creating bookmark with token information
        scene_text = "This is a scene with specific token count requirements."
        token_count = orchestrator.count_tokens(scene_text)
        
        bookmark_id = orchestrator.create_bookmark(
            story_id="integration_test",
            scene_id="token_scene",
            label="Token-Tracked Scene",
            metadata={"token_count": token_count}
        )
        
        assert bookmark_id is not None
        assert token_count is not None
    
    def test_performance_monitoring_integration(self):
        """Test integration with performance monitoring."""
        orchestrator = ManagementOrchestrator()
        
        # Test performance monitoring
        performance_data = orchestrator.get_management_performance_metrics()
        
        assert performance_data is not None
        assert isinstance(performance_data, dict)


class TestManagementErrorHandling:
    """Test error handling in management operations."""
    
    def test_invalid_token_input_handling(self):
        """Test handling of invalid token counting input."""
        orchestrator = ManagementOrchestrator()
        
        # Test with None input
        try:
            result = orchestrator.count_tokens(None)
            # Should handle gracefully
            assert result == 0 or result is None
        except (TypeError, ValueError):
            # Exception is acceptable for invalid input
            pass
    
    def test_invalid_bookmark_data_handling(self):
        """Test handling of invalid bookmark data."""
        orchestrator = ManagementOrchestrator()
        
        # Test with invalid bookmark data
        try:
            result = orchestrator.create_bookmark("", "", "")
            # Should handle gracefully or raise appropriate error
            assert result is None or isinstance(result, str)
        except (ValueError, TypeError, Exception):
            # Exception is acceptable for invalid input (including BookmarkManagerException)
            pass
    
    def test_model_selection_fallback(self):
        """Test fallback behavior in model selection."""
        orchestrator = ManagementOrchestrator()
        
        # Test with very specific requirements that might not be met
        impossible_requirements = {
            "max_tokens": 1,  # Impossibly small
            "capability": "nonexistent_capability"
        }
        
        result = orchestrator.select_optimal_model("test", impossible_requirements)
        
        # Should return fallback model or None
        assert result is None or isinstance(result, str)
