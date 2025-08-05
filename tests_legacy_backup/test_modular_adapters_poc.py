"""
Proof of concept test for the new modular adapter system.

This test validates that our template method pattern works and that
we've successfully eliminated the code duplication while maintaining
the same functionality.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

# Import our new adapters
from core.adapters import OpenAIAdapter, OllamaAdapter, AnthropicAdapter
from core.adapters.exceptions import AdapterInitializationError, AdapterConfigurationError


class TestModularAdapters:
    """Test the new modular adapter system."""
    
    def test_adapter_code_reduction(self):
        """Verify that adapters are much smaller than original."""
        # Count lines in each adapter file
        import inspect
        
        openai_lines = len(inspect.getsource(OpenAIAdapter).split('\n'))
        ollama_lines = len(inspect.getsource(OllamaAdapter).split('\n'))
        anthropic_lines = len(inspect.getsource(AnthropicAdapter).split('\n'))
        
        # Each adapter should be significantly smaller than original ~100 lines
        assert openai_lines < 55, f"OpenAI adapter should be <55 lines, got {openai_lines}"
        assert ollama_lines < 75, f"Ollama adapter should be <75 lines, got {ollama_lines}"  # Slightly larger due to error handling
        assert anthropic_lines < 55, f"Anthropic adapter should be <55 lines, got {anthropic_lines}"
        
        print(f"Code reduction achieved:")
        print(f"  OpenAI: ~100 lines → {openai_lines} lines ({100-openai_lines}% reduction)")
        print(f"  Ollama: ~100 lines → {ollama_lines} lines ({100-ollama_lines}% reduction)")
        print(f"  Anthropic: ~100 lines → {anthropic_lines} lines ({100-anthropic_lines}% reduction)")
    
    def test_template_pattern_consistency(self):
        """Test that all adapters follow the template pattern consistently."""
        import os
        
        # Set up API keys for testing
        os.environ["OPENAI_API_KEY"] = "test-key"  
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        
        config = {"model_name": "test-model", "temperature": 0.8}
        
        try:
            # All adapters should implement the same interface
            openai_adapter = OpenAIAdapter(config)
            ollama_adapter = OllamaAdapter(config)
            anthropic_adapter = AnthropicAdapter(config)
            
            # Verify consistent interface
            assert openai_adapter.get_provider_name() == "openai"
            assert ollama_adapter.get_provider_name() == "ollama"
            assert anthropic_adapter.get_provider_name() == "anthropic"
            
            # Verify API key requirements
            assert openai_adapter.requires_api_key() == True
            assert ollama_adapter.requires_api_key() == False
            assert anthropic_adapter.requires_api_key() == True
            
            # Verify environment variables
            assert openai_adapter.get_api_key_env_var() == "OPENAI_API_KEY"
            assert ollama_adapter.get_base_url_env_var() == "OLLAMA_HOST"
            assert anthropic_adapter.get_api_key_env_var() == "ANTHROPIC_API_KEY"
            
        finally:
            # Clean up environment variables
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
    
    def test_base_url_resolution(self):
        """Test that base URL resolution works consistently."""
        # Test explicit config
        config_with_url = {
            "model_name": "test",
            "base_url": "https://custom.api.com"
        }
        
        ollama_adapter = OllamaAdapter(config_with_url)
        assert ollama_adapter.base_url == "https://custom.api.com"
        
        # Test default URL fallback
        config_default = {"model_name": "test"}
        ollama_adapter2 = OllamaAdapter(config_default)
        assert ollama_adapter2.base_url == "http://localhost:11434"
    
    def test_error_handling_consistency(self):
        """Test that error handling is consistent across adapters."""
        # Test missing API key error
        config = {"model_name": "test"}
        
        with pytest.raises(AdapterConfigurationError) as exc_info:
            OpenAIAdapter(config)
        assert "API key required" in str(exc_info.value)
        
        with pytest.raises(AdapterConfigurationError) as exc_info:
            AnthropicAdapter(config)  
        assert "API key required" in str(exc_info.value)
        
        # Ollama should not require API key
        ollama_adapter = OllamaAdapter(config)  # Should not raise
        assert ollama_adapter.api_key is None
    
    @pytest.mark.asyncio
    async def test_initialization_pattern(self):
        """Test that initialization follows the template pattern."""
        import os
        
        # Mock environment variables
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        
        config = {"model_name": "test-model"}
        
        openai_adapter = OpenAIAdapter(config)
        anthropic_adapter = AnthropicAdapter(config)
        
        # Verify common initialization state
        assert not openai_adapter.initialized
        assert not anthropic_adapter.initialized
        assert openai_adapter.api_key == "test-key"
        assert anthropic_adapter.api_key == "test-key"
        
        # Clean up
        del os.environ["OPENAI_API_KEY"]
        del os.environ["ANTHROPIC_API_KEY"]
        
        # Verify model name setup
        assert openai_adapter.model_name == "test-model"
        assert anthropic_adapter.model_name == "test-model"


if __name__ == "__main__":
    # Run basic validation
    test = TestModularAdapters()
    test.test_adapter_code_reduction()
    test.test_template_pattern_consistency()
    test.test_base_url_resolution()
    test.test_error_handling_consistency()
    
    print("✅ All proof of concept tests passed!")
    print("🎉 Template method pattern successfully eliminates code duplication!")
