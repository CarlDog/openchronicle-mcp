"""
Model adapter system for OpenChronicle.
Provides a unified interface for different LLM backends (OpenAI, Ollama, local models).
"""

import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_model_interaction, log_system_event, log_info, log_error

class ModelAdapter(ABC):
    """Abstract base class for model adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", "unknown")
        self.max_tokens = config.get("max_tokens", 2048)
        self.temperature = config.get("temperature", 0.7)
        self.initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the model adapter."""
        pass
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the model."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model."""
        pass
    
    def log_interaction(self, story_id: str, prompt: str, response: str, metadata: Dict[str, Any] = None):
        """Log the interaction for debugging/analysis."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "story_id": story_id,
            "model": self.model_name,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "metadata": metadata or {}
        }
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join("storage", story_id, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Log to file
        log_file = os.path.join(logs_dir, "model_interactions.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

class OpenAIAdapter(ModelAdapter):
    """OpenAI GPT adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("openai package required for OpenAI adapter")
        except Exception as e:
            log_error(f"Failed to initialize OpenAI adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a creative storytelling assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                stop=kwargs.get("stop_sequences", None)
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information."""
        return {
            "provider": "OpenAI",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class OllamaAdapter(ModelAdapter):
    """Ollama local model adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Ollama client."""
        try:
            import httpx
            self.client = httpx.AsyncClient(base_url=self.base_url)
            
            # Test connection
            response = await self.client.get("/api/tags")
            if response.status_code == 200:
                self.initialized = True
                log_info(f"Ollama adapter initialized successfully for {self.model_name}")
                return True
            else:
                log_error(f"Ollama connection failed: {response.status_code}")
                return False
        except ImportError:
            raise ImportError("httpx package required for Ollama adapter")
        except Exception as e:
            log_error(f"Failed to initialize Ollama adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Ollama."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens)
                }
            }
            
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Ollama model information."""
        return {
            "provider": "Ollama",
            "model_name": self.model_name,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class MockAdapter(ModelAdapter):
    """Mock adapter for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.responses = config.get("responses", [
            "This is a mock response.",
            "Another mock response for testing.",
            "A third mock response to cycle through."
        ])
        self.response_index = 0
    
    async def initialize(self) -> bool:
        """Initialize mock adapter."""
        self.initialized = True
        return True
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate mock response."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        # Check if this is an analysis prompt
        if "JSON format" in prompt and "content_type" in prompt:
            # Generate mock analysis JSON
            content_types = ["action", "dialogue", "description", "question", "command"]
            entities = {
                "characters": [],
                "locations": [],
                "items": [],
                "emotions": ["curious", "determined", "excited"]
            }
            
            # Extract some basic info from the prompt
            if "sword" in prompt.lower():
                entities["items"].append("sword")
            if "dragon" in prompt.lower():
                entities["characters"].append("dragon")
            if "castle" in prompt.lower():
                entities["locations"].append("castle")
            if "forest" in prompt.lower():
                entities["locations"].append("forest")
            
            # Determine content type
            if "?" in prompt:
                content_type = "question"
            elif "say" in prompt.lower() or "hello" in prompt.lower():
                content_type = "dialogue"
            elif "look" in prompt.lower() or "see" in prompt.lower():
                content_type = "description"
            else:
                content_type = "action"
            
            # Generate mock analysis
            analysis = {
                "content_type": content_type,
                "intent": "User wants to interact with the story",
                "entities": entities,
                "content_flags": {
                    "nsfw": False,
                    "violence": "battle" in prompt.lower() or "fight" in prompt.lower(),
                    "mature_themes": False,
                    "emotional_intensity": "medium"
                },
                "required_canon": [],
                "memory_triggers": [],
                "response_style": "narrative",
                "token_priority": "medium"
            }
            
            return json.dumps(analysis, indent=2)
        
        # Regular story response
        # Cycle through responses
        response = self.responses[self.response_index % len(self.responses)]
        self.response_index += 1
        
        # Add some variation based on prompt length
        if len(prompt) > 500:
            response += " [Extended response for longer prompt]"
        
        return response
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get mock model information."""
        return {
            "provider": "Mock",
            "model_name": self.model_name,
            "responses_count": len(self.responses),
            "current_index": self.response_index,
            "initialized": self.initialized
        }

class ModelManager:
    """Manages model adapters and provides unified access."""
    
    def __init__(self):
        self.adapters: Dict[str, ModelAdapter] = {}
        self.default_adapter = None
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load model configuration."""
        config_file = os.path.join("config", "models.json")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        # Default configuration
        return {
            "default_adapter": "mock",
            "adapters": {
                "openai": {
                    "type": "openai",
                    "model_name": "gpt-4o-mini",
                    "max_tokens": 2048,
                    "temperature": 0.7
                },
                "ollama": {
                    "type": "ollama",
                    "model_name": "llama3.2",
                    "base_url": "http://localhost:11434",
                    "max_tokens": 2048,
                    "temperature": 0.7
                },
                "mock": {
                    "type": "mock",
                    "model_name": "mock-model",
                    "responses": [
                        "The story continues with rich detail and engaging narrative.",
                        "Your character moves forward, discovering new possibilities.",
                        "The world around you shifts as the tale unfolds."
                    ]
                }
            }
        }
    
    def register_adapter(self, name: str, adapter: ModelAdapter):
        """Register a model adapter."""
        self.adapters[name] = adapter
    
    async def initialize_adapter(self, name: str) -> bool:
        """Initialize a specific adapter."""
        if name not in self.config["adapters"]:
            raise ValueError(f"Adapter '{name}' not found in configuration")
        
        adapter_config = self.config["adapters"][name]
        adapter_type = adapter_config["type"]
        
        if adapter_type == "openai":
            adapter = OpenAIAdapter(adapter_config)
        elif adapter_type == "ollama":
            adapter = OllamaAdapter(adapter_config)
        elif adapter_type == "mock":
            adapter = MockAdapter(adapter_config)
        elif adapter_type == "anthropic":
            adapter = AnthropicAdapter(adapter_config)
        elif adapter_type == "gemini":
            adapter = GeminiAdapter(adapter_config)
        elif adapter_type == "groq":
            adapter = GroqAdapter(adapter_config)
        elif adapter_type == "cohere":
            adapter = CohereAdapter(adapter_config)
        elif adapter_type == "mistral":
            adapter = MistralAdapter(adapter_config)
        elif adapter_type == "huggingface":
            adapter = HuggingFaceAdapter(adapter_config)
        elif adapter_type == "azure_openai":
            adapter = AzureOpenAIAdapter(adapter_config)
        elif adapter_type == "openai_image":
            adapter = OpenAIImageAdapter(adapter_config)
        elif adapter_type == "stability":
            adapter = StabilityAdapter(adapter_config)
        elif adapter_type == "replicate":
            adapter = ReplicateAdapter(adapter_config)
        elif adapter_type == "mock_image":
            adapter = MockImageAdapter(adapter_config)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        
        success = await adapter.initialize()
        if success:
            self.adapters[name] = adapter
            if self.default_adapter is None:
                self.default_adapter = name
        
        return success
    
    async def generate_response(self, prompt: str, adapter_name: str = None, story_id: str = None, **kwargs) -> str:
        """Generate response using specified or default adapter."""
        adapter_name = adapter_name or self.default_adapter
        
        if adapter_name not in self.adapters:
            # Try to initialize the adapter
            if not await self.initialize_adapter(adapter_name):
                raise RuntimeError(f"Failed to initialize adapter: {adapter_name}")
        
        adapter = self.adapters[adapter_name]
        response = await adapter.generate_response(prompt, **kwargs)
        
        # Log interaction if story_id provided
        if story_id:
            metadata = {"adapter": adapter_name, "kwargs": kwargs}
            adapter.log_interaction(story_id, prompt, response, metadata)
        
        return response
    
    def get_available_adapters(self) -> List[str]:
        """Get list of available adapters."""
        return list(self.config["adapters"].keys())
    
    def get_adapter_info(self, name: str) -> Dict[str, Any]:
        """Get information about a specific adapter."""
        if name in self.adapters:
            return self.adapters[name].get_model_info()
        elif name in self.config["adapters"]:
            config = self.config["adapters"][name]
            return {
                "provider": config["type"],
                "model_name": config.get("model_name", "unknown"),
                "initialized": False
            }
        else:
            raise ValueError(f"Adapter '{name}' not found")
    
    async def generate_image(self, prompt: str, adapter_name: str = None, **kwargs) -> str:
        """Generate image using specified or default image adapter."""
        # Use image_adapter from config if no adapter specified
        if adapter_name is None:
            adapter_name = self.config.get("image_adapter", "mock_image")
        
        if adapter_name not in self.adapters:
            # Try to initialize the adapter
            if not await self.initialize_adapter(adapter_name):
                raise RuntimeError(f"Failed to initialize image adapter: {adapter_name}")
        
        adapter = self.adapters[adapter_name]
        
        # Check if this is actually an image adapter
        if not hasattr(adapter, 'generate_image'):
            raise RuntimeError(f"Adapter '{adapter_name}' does not support image generation")
        
        return await adapter.generate_image(prompt, **kwargs)

    async def shutdown(self):
        """Shutdown all adapters."""
        for adapter in self.adapters.values():
            if hasattr(adapter, 'client') and adapter.client:
                if hasattr(adapter.client, 'aclose'):
                    await adapter.client.aclose()

# Global model manager instance
model_manager = ModelManager()

# ================================
# TEXT GENERATION ADAPTERS
# ================================

class AnthropicAdapter(ModelAdapter):
    """Anthropic Claude adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = config.get("base_url", "https://api.anthropic.com")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Anthropic client."""
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("anthropic package required for Anthropic adapter")
        except Exception as e:
            log_error(f"Failed to initialize Anthropic adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic Claude."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.messages.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Anthropic model information."""
        return {
            "provider": "Anthropic",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class GeminiAdapter(ModelAdapter):
    """Google Gemini adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Gemini client."""
        if not self.api_key:
            raise ValueError("Google API key required")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model_name)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("google-generativeai package required for Gemini adapter")
        except Exception as e:
            log_error(f"Failed to initialize Gemini adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Google Gemini."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.max_tokens),
                }
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Gemini model information."""
        return {
            "provider": "Google",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class GroqAdapter(ModelAdapter):
    """Groq fast inference adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("GROQ_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Groq client."""
        if not self.api_key:
            raise ValueError("Groq API key required")
        
        try:
            import groq
            self.client = groq.AsyncGroq(api_key=self.api_key)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("groq package required for Groq adapter")
        except Exception as e:
            log_error(f"Failed to initialize Groq adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Groq."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Groq model information."""
        return {
            "provider": "Groq",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class CohereAdapter(ModelAdapter):
    """Cohere Command adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("COHERE_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Cohere client."""
        if not self.api_key:
            raise ValueError("Cohere API key required")
        
        try:
            import cohere
            self.client = cohere.AsyncClient(api_key=self.api_key)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("cohere package required for Cohere adapter")
        except Exception as e:
            log_error(f"Failed to initialize Cohere adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Cohere."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.generate(
                model=self.model_name,
                prompt=prompt,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.generations[0].text
        except Exception as e:
            raise RuntimeError(f"Cohere API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Cohere model information."""
        return {
            "provider": "Cohere",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class MistralAdapter(ModelAdapter):
    """Mistral AI adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("MISTRAL_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Mistral client."""
        if not self.api_key:
            raise ValueError("Mistral API key required")
        
        try:
            from mistralai.async_client import MistralAsyncClient
            self.client = MistralAsyncClient(api_key=self.api_key)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("mistralai package required for Mistral adapter")
        except Exception as e:
            log_error(f"Failed to initialize Mistral adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Mistral."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            from mistralai.models.chat_completion import ChatMessage
            response = await self.client.chat(
                model=self.model_name,
                messages=[ChatMessage(role="user", content=prompt)],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Mistral API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Mistral model information."""
        return {
            "provider": "Mistral",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class HuggingFaceAdapter(ModelAdapter):
    """Hugging Face Inference API adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("HUGGINGFACE_API_KEY")
        self.base_url = config.get("base_url", "https://api-inference.huggingface.co/models/")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Hugging Face client."""
        if not self.api_key:
            raise ValueError("Hugging Face API key required")
        
        try:
            import httpx
            self.client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("httpx package required for Hugging Face adapter")
        except Exception as e:
            log_error(f"Failed to initialize Hugging Face adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Hugging Face."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.post(
                f"{self.base_url}{self.model_name}",
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": kwargs.get("max_tokens", self.max_tokens),
                        "temperature": kwargs.get("temperature", self.temperature)
                    }
                }
            )
            result = response.json()
            return result[0]["generated_text"]
        except Exception as e:
            raise RuntimeError(f"Hugging Face API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Hugging Face model information."""
        return {
            "provider": "Hugging Face",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class AzureOpenAIAdapter(ModelAdapter):
    """Azure OpenAI adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = config.get("azure_endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = config.get("api_version", "2024-02-01")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Azure OpenAI client."""
        if not self.api_key or not self.azure_endpoint:
            raise ValueError("Azure OpenAI API key and endpoint required")
        
        try:
            from openai import AsyncAzureOpenAI
            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.azure_endpoint,
                api_version=self.api_version
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("openai package required for Azure OpenAI adapter")
        except Exception as e:
            log_error(f"Failed to initialize Azure OpenAI adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Azure OpenAI."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Azure OpenAI API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Azure OpenAI model information."""
        return {
            "provider": "Azure OpenAI",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

# ================================
# IMAGE GENERATION ADAPTERS
# ================================

class ImageAdapter(ModelAdapter):
    """Abstract base class for image generation adapters."""
    
    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate an image from a text prompt. Returns base64 or URL."""
        pass
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Redirect to image generation for compatibility."""
        return await self.generate_image(prompt, **kwargs)

class OpenAIImageAdapter(ImageAdapter):
    """OpenAI DALL-E image adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.size = config.get("size", "1024x1024")
        self.quality = config.get("quality", "standard")
        self.style = config.get("style", "vivid")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("openai package required for OpenAI image adapter")
        except Exception as e:
            log_error(f"Failed to initialize OpenAI image adapter: {e}")
            return False
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using DALL-E."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.images.generate(
                model=self.model_name,
                prompt=prompt,
                size=kwargs.get("size", self.size),
                quality=kwargs.get("quality", self.quality),
                style=kwargs.get("style", self.style),
                n=1
            )
            return response.data[0].url
        except Exception as e:
            raise RuntimeError(f"OpenAI Image API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI image model information."""
        return {
            "provider": "OpenAI",
            "model_name": self.model_name,
            "size": self.size,
            "quality": self.quality,
            "style": self.style,
            "initialized": self.initialized
        }

class StabilityAdapter(ImageAdapter):
    """Stability AI Stable Diffusion adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("STABILITY_API_KEY")
        self.width = config.get("width", 1024)
        self.height = config.get("height", 1024)
        self.steps = config.get("steps", 30)
        self.cfg_scale = config.get("cfg_scale", 7)
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Stability client."""
        if not self.api_key:
            raise ValueError("Stability API key required")
        
        try:
            import httpx
            self.client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("httpx package required for Stability adapter")
        except Exception as e:
            log_error(f"Failed to initialize Stability adapter: {e}")
            return False
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using Stability AI."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.post(
                f"https://api.stability.ai/v1/generation/{self.model_name}/text-to-image",
                json={
                    "text_prompts": [{"text": prompt}],
                    "cfg_scale": kwargs.get("cfg_scale", self.cfg_scale),
                    "height": kwargs.get("height", self.height),
                    "width": kwargs.get("width", self.width),
                    "steps": kwargs.get("steps", self.steps),
                    "samples": 1
                }
            )
            result = response.json()
            return f"data:image/png;base64,{result['artifacts'][0]['base64']}"
        except Exception as e:
            raise RuntimeError(f"Stability API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Stability model information."""
        return {
            "provider": "Stability AI",
            "model_name": self.model_name,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "initialized": self.initialized
        }

class ReplicateAdapter(ImageAdapter):
    """Replicate API adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("REPLICATE_API_TOKEN")
        self.width = config.get("width", 1024)
        self.height = config.get("height", 1024)
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Replicate client."""
        if not self.api_key:
            raise ValueError("Replicate API token required")
        
        try:
            import replicate
            replicate.api_token = self.api_key
            self.client = replicate
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("replicate package required for Replicate adapter")
        except Exception as e:
            log_error(f"Failed to initialize Replicate adapter: {e}")
            return False
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using Replicate."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            output = self.client.run(
                self.model_name,
                input={
                    "prompt": prompt,
                    "width": kwargs.get("width", self.width),
                    "height": kwargs.get("height", self.height)
                }
            )
            return output[0] if isinstance(output, list) else output
        except Exception as e:
            raise RuntimeError(f"Replicate API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Replicate model information."""
        return {
            "provider": "Replicate",
            "model_name": self.model_name,
            "width": self.width,
            "height": self.height,
            "initialized": self.initialized
        }

class MockImageAdapter(ImageAdapter):
    """Mock image adapter for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.responses = config.get("responses", [
            "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzMzNzNkYyIvPgogIDx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zNWVtIj5Nb2NrIEltYWdlPC90ZXh0Pgo8L3N2Zz4K"
        ])
        self.response_index = 0
    
    async def initialize(self) -> bool:
        """Initialize mock image adapter."""
        self.initialized = True
        return True
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate mock image."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        # Cycle through responses
        response = self.responses[self.response_index % len(self.responses)]
        self.response_index += 1
        
        return response
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get mock image model information."""
        return {
            "provider": "Mock",
            "model_name": self.model_name,
            "responses_count": len(self.responses),
            "current_index": self.response_index,
            "initialized": self.initialized
        }
