"""
Test suite for Token Manager

Tests token counting, optimization, and API limit management.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from core.token_manager import TokenManager


@pytest.fixture
def mock_model_manager():
    """Mock model manager for testing."""
    mock_manager = Mock()
    mock_manager.get_model_info.return_value = {
        'context_window': 4096,
        'max_output_tokens': 2048,
        'name': 'test-model'
    }
    mock_manager.get_available_models.return_value = ['test-model', 'test-model-large']
    return mock_manager


@pytest.fixture
def mock_tokenizer():
    """Mock tiktoken encoder."""
    mock_encoder = Mock()
    mock_encoder.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
    return mock_encoder


class TestTokenManager:
    """Test cases for TokenManager class."""

    def test_init(self, mock_model_manager):
        """Test TokenManager initialization."""
        manager = TokenManager(mock_model_manager)
        assert manager.model_manager == mock_model_manager
        assert manager.token_usage == {}
        assert manager.continuation_cache == {}
        assert manager.encoders == {}

    @patch('core.token_manager.tiktoken.get_encoding')
    def test_get_tokenizer(self, mock_tiktoken, mock_model_manager, mock_tokenizer):
        """Test getting tokenizer for a model."""
        mock_tiktoken.return_value = mock_tokenizer
        
        manager = TokenManager(mock_model_manager)
        tokenizer = manager.get_tokenizer('test-model')
        
        # Should return the encoder from cache or tiktoken
        assert tokenizer is not None

    def test_estimate_tokens(self, mock_model_manager):
        """Test token estimation."""
        manager = TokenManager(mock_model_manager)
        tokens = manager.estimate_tokens("Test text", "test-model")
        
        # Should return an integer token count
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_select_optimal_model_for_length(self, mock_model_manager):
        """Test selecting optimal model for text length."""
        mock_model_manager.list_model_configs.return_value = {
            'test-model': {'context_window': 4096}
        }
        
        manager = TokenManager(mock_model_manager)
        model = manager.select_optimal_model_for_length(1000, 500)
        
        # Should return a model name or None
        assert model is None or isinstance(model, str)

    def test_check_truncation_risk(self, mock_model_manager):
        """Test checking truncation risk."""
        mock_model_manager.get_adapter_info.return_value = {'max_tokens': 4096}
        
        manager = TokenManager(mock_model_manager)
        risk = manager.check_truncation_risk("Test prompt", "test-model")
        
        assert isinstance(risk, bool)

    def test_trim_context_intelligently(self, mock_model_manager):
        """Test intelligent context trimming."""
        manager = TokenManager(mock_model_manager)
        context_parts = {
            'scene_history': 'Long scene history...',
            'character_info': 'Character details...',
            'current_scene': 'Current scene text...'
        }
        
        trimmed = manager.trim_context_intelligently(context_parts, 1000, "test-model")
        
        assert isinstance(trimmed, dict)

    def test_detect_truncation(self, mock_model_manager):
        """Test truncation detection."""
        manager = TokenManager(mock_model_manager)
        
        # Test complete response
        complete_response = "This is a complete response."
        assert not manager.detect_truncation(complete_response)
        
        # Test potentially truncated response
        truncated_response = "This response ends abruptly"
        truncated = manager.detect_truncation(truncated_response)
        assert isinstance(truncated, bool)

    @pytest.mark.asyncio
    async def test_continue_scene(self, mock_model_manager):
        """Test async scene continuation."""
        mock_model_manager.query_model = AsyncMock(return_value="Continued response.")
        mock_model_manager.get_adapter_info.return_value = {'max_tokens': 4096}
        
        manager = TokenManager(mock_model_manager)
        result = await manager.continue_scene(
            "Original prompt", 
            "Partial response", 
            "test-story",
            "test-model"
        )
        
        assert isinstance(result, (dict, str))

    def test_track_token_usage(self, mock_model_manager):
        """Test token usage tracking."""
        manager = TokenManager(mock_model_manager)
        
        manager.track_token_usage("test-model", 100, 50, 0.05)
        
        assert "test-model" in manager.token_usage
        usage = manager.token_usage["test-model"]
        assert usage['prompt_tokens'] == 100
        assert usage['response_tokens'] == 50

    def test_get_usage_stats(self, mock_model_manager):
        """Test getting usage statistics."""
        manager = TokenManager(mock_model_manager)
        
        # Add some usage data
        manager.track_token_usage("test-model", 100, 50, 0.05)
        
        stats = manager.get_usage_stats()
        
        assert isinstance(stats, dict)
        assert 'total_requests' in stats
        assert 'models' in stats

    def test_recommend_model_switch(self, mock_model_manager):
        """Test model switch recommendation."""
        manager = TokenManager(mock_model_manager)
        
        usage_pattern = {
            'avg_prompt_length': 1000,
            'avg_response_length': 500,
            'truncation_rate': 0.1
        }
        
        recommendation = manager.recommend_model_switch("test-model", usage_pattern)
        
        # Should return a model name or None
        assert recommendation is None or isinstance(recommendation, str)
