"""
Example Adapter Implementation - Demonstrates the Model Management Framework

This example shows how easy it is to create a new adapter using the Template Method pattern.
With the new framework, implementing an adapter requires minimal code and automatically
gets retry logic, metrics tracking, error handling, and more.

Comparison:
- Old approach: ~500+ lines of boilerplate per adapter
- New approach: ~50-100 lines focused on provider-specific logic
"""

import asyncio
import sys
import os
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.model_management.base_adapter import BaseAPIAdapter
from core.model_management.adapter_interfaces import AdapterConfig

class ExampleOpenAIAdapter(BaseAPIAdapter):
    """
    Example OpenAI adapter implementation using the new framework
    
    This shows how simple it is to implement a new adapter with:
    - Automatic API key handling
    - Built-in retry logic and error handling  
    - Automatic metrics tracking
    - Configuration validation
    - Health checks and connection management
    """
    
    def get_provider_name(self) -> str:
        return "example_openai"
    
    def get_supported_models(self) -> List[str]:
        return [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o"
        ]
    
    def get_api_key_env_var(self) -> str:
        return "OPENAI_API_KEY"
    
    async def _create_client(self) -> Any:
        """Create OpenAI client - this would import openai in real implementation"""
        # In real implementation:
        # import openai
        # return openai.AsyncOpenAI(api_key=self.api_key, base_url=self.config.base_url)
        
        # For example, return mock client
        from unittest.mock import Mock
        mock_client = Mock()
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        return mock_client
    
    async def _generate_response_impl(self, prompt: str, params: Dict[str, Any]) -> Any:
        """Generate response using OpenAI API - simplified for example"""
        # In real implementation:
        # response = await self.client.chat.completions.create(
        #     model=self.model_name,
        #     messages=[{"role": "user", "content": prompt}],
        #     max_tokens=params.get('max_tokens', self.config.max_tokens),
        #     temperature=params.get('temperature', self.config.temperature),
        #     top_p=params.get('top_p', self.config.top_p)
        # )
        # return response
        
        # For example, return mock response
        from unittest.mock import Mock
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = f"Example response to: {prompt[:50]}..."
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 150
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        return mock_response
    
    def _extract_content(self, raw_response: Any) -> str:
        """Extract content from OpenAI response"""
        return raw_response.choices[0].message.content


class ExampleOllamaAdapter(BaseAPIAdapter):
    """
    Example Ollama adapter - shows local model support
    
    This demonstrates how the same framework works for both 
    cloud APIs and local model servers.
    """
    
    def get_provider_name(self) -> str:
        return "example_ollama"
    
    def get_supported_models(self) -> List[str]:
        return [
            "llama2",
            "llama2:13b",
            "codellama",
            "mistral",
            "neural-chat"
        ]
    
    def get_api_key_env_var(self) -> str:
        # Ollama doesn't need API key
        return None
    
    def _get_api_key(self) -> str:
        """Override to skip API key requirement for Ollama"""
        return None  # Ollama doesn't need API key
        
    def _validate_api_key(self) -> None:
        # Override to skip API key validation for Ollama
        pass
    
    async def _create_client(self) -> Any:
        """Create Ollama client"""
        # In real implementation:
        # import aiohttp
        # return aiohttp.ClientSession()
        
        from unittest.mock import Mock
        return Mock()
    
    async def _generate_response_impl(self, prompt: str, params: Dict[str, Any]) -> Any:
        """Generate response using Ollama API"""
        # In real implementation:
        # async with self.client.post(
        #     f"{self.config.base_url or 'http://localhost:11434'}/api/generate",
        #     json={
        #         "model": self.model_name,
        #         "prompt": prompt,
        #         "options": {
        #             "temperature": params.get('temperature', self.config.temperature),
        #             "top_p": params.get('top_p', self.config.top_p),
        #             "num_predict": params.get('max_tokens', self.config.max_tokens)
        #         }
        #     }
        # ) as response:
        #     data = await response.json()
        #     return data
        
        from unittest.mock import Mock
        mock_response = Mock()
        mock_response.response = f"Ollama example response to: {prompt[:50]}..."
        mock_response.done = True
        return mock_response
    
    def _extract_content(self, raw_response: Any) -> str:
        """Extract content from Ollama response"""
        return raw_response.response


async def demonstrate_framework():
    """
    Demonstration of how easy it is to use the new framework
    """
    from core.model_management.adapter_registry import AdapterRegistry, AdapterFactory
    from core.model_management.adapter_config import ConfigManager
    
    print("🚀 Model Management Framework Demonstration\n")
    
    # 1. Set up registry and factory
    registry = AdapterRegistry()
    factory = AdapterFactory(registry)
    config_manager = ConfigManager()
    
    # 2. Register our example adapters
    registry.register_adapter(ExampleOpenAIAdapter, name="example_openai")
    registry.register_adapter(ExampleOllamaAdapter, name="example_ollama")
    
    print(f"📋 Registered adapters: {registry.list_adapters()}")
    
    # 3. Create and use OpenAI adapter
    print("\n🔧 Creating OpenAI adapter...")
    openai_adapter = factory.create_adapter(
        "example_openai", 
        "gpt-3.5-turbo",
        api_key="example_key_123"
    )
    
    await openai_adapter.initialize()
    print(f"✅ OpenAI adapter initialized: {openai_adapter}")
    
    # Generate response
    response = await openai_adapter.generate_response("Hello, how are you?")
    print(f"💬 OpenAI Response: {response.content}")
    print(f"📊 Tokens used: {response.tokens_used}, Time: {response.response_time:.3f}s")
    
    # 4. Create and use Ollama adapter
    print("\n🔧 Creating Ollama adapter...")
    ollama_adapter = factory.create_adapter(
        "example_ollama", 
        "llama2",
        base_url="http://localhost:11434"
    )
    
    await ollama_adapter.initialize()
    print(f"✅ Ollama adapter initialized: {ollama_adapter}")
    
    # Generate response
    response = await ollama_adapter.generate_response("Explain quantum computing")
    print(f"💬 Ollama Response: {response.content}")
    print(f"📊 Tokens used: {response.tokens_used}, Time: {response.response_time:.3f}s")
    
    # 5. Show usage statistics
    print("\n📈 Usage Statistics:")
    openai_stats = openai_adapter.get_usage_stats()
    ollama_stats = ollama_adapter.get_usage_stats()
    
    print(f"OpenAI requests: {openai_stats.get('requests_made', 0)}")
    print(f"Ollama requests: {ollama_stats.get('requests_made', 0)}")
    
    # 6. Show adapter capabilities
    print("\n🎯 Adapter Capabilities:")
    for adapter_name in registry.list_adapters():
        info = registry.get_adapter_info(adapter_name)
        print(f"{adapter_name}: {info.capabilities}")
    
    # 7. Cleanup
    await openai_adapter.cleanup()
    await ollama_adapter.cleanup()
    print("\n🧹 Cleanup completed")


if __name__ == "__main__":
    print("Model Management Framework - Example Implementation")
    print("=" * 60)
    print("This demonstrates the power and simplicity of the new framework.")
    print("Each adapter requires minimal code while getting full functionality.")
    print("=" * 60)
    
    asyncio.run(demonstrate_framework())
