"""
Test dynamic Ollama model discovery functionality.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime, UTC

# Add the parent directory to the path to import from core
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.model_adapter import ModelManager

class TestDynamicOllamaDiscovery:
    """Test dynamic Ollama model discovery functionality."""

    @pytest.fixture
    def mock_ollama_response(self):
        """Mock response from Ollama /api/tags endpoint."""
        return {
            "models": [
                {
                    "name": "llama3.2:latest",
                    "size": 4869077504,  # ~4.5GB
                    "modified_at": "2024-07-24T10:30:00Z"
                },
                {
                    "name": "gemma3:7b",
                    "size": 7123456789,  # ~6.6GB
                    "modified_at": "2024-07-23T15:45:00Z"
                },
                {
                    "name": "codellama:13b-instruct",
                    "size": 13958643712,  # ~13GB
                    "modified_at": "2024-07-22T09:15:00Z"
                },
                {
                    "name": "mistral:latest",
                    "size": 4109328384,  # ~3.8GB
                    "modified_at": "2024-07-21T14:20:00Z"
                }
            ]
        }

    @pytest.fixture
    def mock_registry(self):
        """Mock model registry."""
        return {
            "version": "1.0.0",
            "default_model": "ollama",
            "models": [
                {
                    "name": "ollama",
                    "type": "ollama",
                    "priority": 1,
                    "enabled": True,
                    "config": {
                        "base_url": "http://localhost:11434",
                        "model_name": "gemma3:latest"
                    }
                },
                {
                    "name": "mock",
                    "type": "mock",
                    "priority": 99,
                    "enabled": True
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_discover_ollama_models_success(self, mock_ollama_response):
        """Test successful Ollama model discovery."""
        manager = ModelManager()
        
        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_ollama_response
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await manager.discover_ollama_models()
        
        # Verify result structure
        assert "error" not in result
        assert result["total_models"] == 4
        assert "models" in result
        assert "timestamp" in result
        assert result["server_url"] == "http://localhost:11434"
        
        # Verify model parsing
        models = result["models"]
        
        # Test llama3.2 model
        assert "llama3.2:latest" in models
        llama_model = models["llama3.2:latest"]
        assert llama_model["base_name"] == "llama3.2"
        assert llama_model["family"] == "llama"
        assert llama_model["size_human"] == "4.5 GB"
        assert llama_model["capabilities"]["text_generation"] is True
        assert llama_model["capabilities"]["analysis"] is True
        
        # Test codellama model
        assert "codellama:13b-instruct" in models
        codellama_model = models["codellama:13b-instruct"]
        assert codellama_model["base_name"] == "codellama"
        assert codellama_model["family"] == "codellama"
        assert codellama_model["capabilities"]["code_generation"] is True
        assert codellama_model["capabilities"]["instruction_following"] is True

    @pytest.mark.asyncio
    async def test_discover_ollama_models_connection_error(self):
        """Test Ollama model discovery with connection error."""
        manager = ModelManager()
        
        # Mock connection error
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            result = await manager.discover_ollama_models()
        
        assert "error" in result
        assert "Connection refused" in result["error"]

    def test_guess_model_family(self):
        """Test model family guessing logic."""
        manager = ModelManager()
        
        assert manager._guess_model_family("llama3.2") == "llama"
        assert manager._guess_model_family("gemma-7b") == "gemma"
        assert manager._guess_model_family("mistral-instruct") == "mistral"
        assert manager._guess_model_family("codellama") == "codellama"
        assert manager._guess_model_family("phi-3-mini") == "phi"
        assert manager._guess_model_family("qwen2") == "qwen"
        assert manager._guess_model_family("random-model") == "unknown"

    def test_guess_model_capabilities(self):
        """Test model capabilities guessing logic."""
        manager = ModelManager()
        
        # Code model
        caps = manager._guess_model_capabilities("codellama-instruct")
        assert caps["code_generation"] is True
        assert caps["instruction_following"] is True
        assert caps["conversation"] is True
        
        # Chat model
        caps = manager._guess_model_capabilities("llama3-chat")
        assert caps["instruction_following"] is True
        assert caps["conversation"] is True
        assert caps["analysis"] is True
        
        # Large analysis model
        caps = manager._guess_model_capabilities("gemma-13b")
        assert caps["analysis"] is True
        
        # Basic model
        caps = manager._guess_model_capabilities("basic-model")
        assert caps["text_generation"] is True
        assert caps["code_generation"] is False

    @pytest.mark.asyncio
    async def test_add_discovered_ollama_models_simple(self):
        """Test the basic flow of adding discovered models (simplified test)."""
        manager = ModelManager()
        
        # Test with a non-existent registry file to test error handling
        with patch('os.path.exists', return_value=False):
            result = await manager.add_discovered_ollama_models()
        
        assert "errors" in result
        assert any("registry not found" in error.lower() for error in result["errors"])

    @pytest.mark.asyncio
    async def test_add_discovered_ollama_models_registry_not_found(self):
        """Test adding discovered models when registry doesn't exist."""
        manager = ModelManager()
        
        with patch('os.path.exists', return_value=False):
            result = await manager.add_discovered_ollama_models()
        
        assert "errors" in result
        assert any("registry not found" in error.lower() for error in result["errors"])

if __name__ == "__main__":
    # Run a simple test if executed directly
    import asyncio
    
    async def quick_test():
        manager = ModelManager()
        
        # Test model family guessing
        families = [
            ("llama3.2:latest", "llama"),
            ("gemma:7b", "gemma"),
            ("codellama:instruct", "codellama"),
            ("mistral-7b", "mistral"),
            ("unknown-model", "unknown")
        ]
        
        print("Testing model family detection:")
        for model_name, expected in families:
            actual = manager._guess_model_family(model_name)
            status = "✅" if actual == expected else "❌"
            print(f"  {status} {model_name} -> {actual} (expected: {expected})")
        
        # Test capability guessing
        print("\nTesting capability detection:")
        test_models = ["codellama:instruct", "llama3-chat", "basic-model"]
        for model_name in test_models:
            caps = manager._guess_model_capabilities(model_name)
            print(f"  {model_name}:")
            for cap, value in caps.items():
                if value:
                    print(f"    ✅ {cap}")
        
        print("\nDynamic Ollama discovery tests completed!")
    
    asyncio.run(quick_test())
