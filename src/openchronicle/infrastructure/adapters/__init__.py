"""
Infrastructure layer LLM adapters for OpenChronicle.

This module provides concrete implementations for interacting with various
Large Language Model providers. These adapters implement the ModelManager
interface defined in the application layer.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import json
import logging

from ...domain import NarrativeContext, ModelResponse
from ...application.orchestrators import ModelManager


@dataclass
class ModelConfig:
    """Configuration for a model adapter."""
    name: str
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_id: str = ""
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30
    rate_limit: int = 60  # requests per minute
    fallback_models: List[str] = None
    
    def __post_init__(self):
        if self.fallback_models is None:
            self.fallback_models = []


class BaseModelAdapter(ABC):
    """Base class for all model adapters."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self._request_times = []  # For rate limiting
    
    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text using the model."""
        pass
    
    async def _check_rate_limit(self):
        """Check if we're within rate limits."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        if len(self._request_times) >= self.config.rate_limit:
            sleep_time = 60 - (now - self._request_times[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self._request_times.append(now)
    
    def _format_context_for_model(self, context: NarrativeContext) -> str:
        """Format narrative context into a prompt for the model."""
        prompt_parts = []
        
        # Story context
        prompt_parts.append(f"Story ID: {context.story_id}")
        
        # Memory state summary
        if context.memory_state:
            if context.memory_state.character_memories:
                prompt_parts.append("Characters present:")
                for char_id, memory in context.memory_state.character_memories.items():
                    if char_id in context.participant_ids:
                        character = context.characters.get(char_id)
                        if character:
                            prompt_parts.append(f"- {character.name}: {character.description}")
        
        # Scene context
        if context.scene_type:
            prompt_parts.append(f"Scene type: {context.scene_type}")
        
        if context.location:
            prompt_parts.append(f"Location: {context.location}")
        
        # User input
        prompt_parts.append(f"User input: {context.user_input}")
        
        # Additional context
        if context.additional_context:
            prompt_parts.append("Additional context:")
            for key, value in context.additional_context.items():
                prompt_parts.append(f"- {key}: {value}")
        
        return "\n".join(prompt_parts)


class MockModelAdapter(BaseModelAdapter):
    """Mock model adapter for testing and development."""
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate mock response."""
        await self._check_rate_limit()
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        # Generate a mock response based on prompt content
        if "character" in prompt.lower():
            return "The character responds thoughtfully, considering their motivations and the current situation."
        elif "action" in prompt.lower():
            return "A dramatic action unfolds, changing the course of the narrative."
        elif "dialogue" in prompt.lower():
            return '"This is an interesting development," the character remarks with intrigue.'
        else:
            return "The story continues to unfold in unexpected ways, revealing new depths to the narrative."


class OpenAIAdapter(BaseModelAdapter):
    """OpenAI API adapter."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._client = None
    
    async def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
        return self._client
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text using OpenAI API."""
        await self._check_rate_limit()
        
        client = await self._get_client()
        
        try:
            response = await client.chat.completions.create(
                model=self.config.model_id or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
                timeout=self.config.timeout
            )
            
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicAdapter(BaseModelAdapter):
    """Anthropic Claude API adapter."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._client = None
    
    async def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(
                    api_key=self.config.api_key
                )
            except ImportError:
                raise ImportError("Anthropic package not installed. Run: pip install anthropic")
        return self._client
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text using Anthropic API."""
        await self._check_rate_limit()
        
        client = await self._get_client()
        
        try:
            response = await client.messages.create(
                model=self.config.model_id or "claude-3-haiku-20240307",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise


class OllamaAdapter(BaseModelAdapter):
    """Ollama local model adapter."""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text using Ollama API."""
        await self._check_rate_limit()
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.config.model_id or "llama2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens or self.config.max_tokens,
                        "temperature": temperature or self.config.temperature
                    }
                }
                
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("response", "")
                    else:
                        raise Exception(f"Ollama API error: {response.status}")
        except ImportError:
            raise ImportError("aiohttp package not installed. Run: pip install aiohttp")
        except Exception as e:
            self.logger.error(f"Ollama API error: {e}")
            raise


class ModelManagerImpl(ModelManager):
    """Implementation of the ModelManager interface."""
    
    def __init__(self):
        self.adapters: Dict[str, BaseModelAdapter] = {}
        self.fallback_chains: Dict[str, List[str]] = {}
        self.logger = logging.getLogger("ModelManager")
    
    def register_adapter(self, name: str, adapter: BaseModelAdapter):
        """Register a model adapter."""
        self.adapters[name] = adapter
        self.logger.info(f"Registered model adapter: {name}")
    
    def set_fallback_chain(self, primary: str, fallbacks: List[str]):
        """Set fallback chain for a model."""
        self.fallback_chains[primary] = fallbacks
    
    async def generate_response(
        self, 
        context: NarrativeContext, 
        model_preference: Optional[str] = None
    ) -> ModelResponse:
        """Generate AI response using preferred model with fallbacks."""
        start_time = time.time()
        
        # Determine models to try
        models_to_try = []
        if model_preference and model_preference in self.adapters:
            models_to_try.append(model_preference)
            models_to_try.extend(self.fallback_chains.get(model_preference, []))
        else:
            # Use first available model
            models_to_try = list(self.adapters.keys())
        
        if not models_to_try:
            return ModelResponse(
                success=False,
                content="",
                model_name="none",
                tokens_used=0,
                generation_time=0.0,
                error="No models available"
            )
        
        # Format the context into a prompt
        prompt = self._format_narrative_prompt(context)
        
        # Try models in order
        last_error = None
        for model_name in models_to_try:
            if model_name not in self.adapters:
                continue
            
            try:
                adapter = self.adapters[model_name]
                content = await adapter.generate_text(prompt)
                
                generation_time = time.time() - start_time
                
                return ModelResponse(
                    content=content,
                    model_name=model_name,
                    provider=adapter.config.provider,
                    timestamp=datetime.now(),
                    tokens_used=self._estimate_tokens(prompt + content),
                    generation_time=generation_time,
                    finish_reason="completed"
                )
            
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Model {model_name} failed: {e}")
                continue
        
        # All models failed
        generation_time = time.time() - start_time
        return ModelResponse(
            content="",
            model_name="failed",
            provider="none",
            timestamp=datetime.now(),
            tokens_used=0,
            generation_time=generation_time,
            finish_reason=f"error: {last_error}"
        )
    
    def _format_narrative_prompt(self, context: NarrativeContext) -> str:
        """Format narrative context into a comprehensive prompt."""
        prompt_parts = [
            "You are a creative narrative AI assistant helping to generate an interactive story.",
            "",
            "Context:"
        ]
        
        # Add character information
        if context.characters and context.participant_ids:
            prompt_parts.append("Characters involved:")
            for char_id in context.participant_ids:
                character = context.characters.get(char_id)
                if character:
                    prompt_parts.extend([
                        f"- {character.name}: {character.description}",
                        f"  Personality: {character.personality_traits}",
                        f"  Current emotional state: {character.emotional_state}"
                    ])
        
        # Add memory context
        if context.memory_state and context.memory_state.recent_events:
            prompt_parts.append("\nRecent story events:")
            for event in context.memory_state.recent_events[-3:]:  # Last 3 events
                prompt_parts.append(f"- {event}")
        
        # Add scene details
        if context.scene_type:
            prompt_parts.append(f"\nScene type: {context.scene_type}")
        
        if context.location:
            prompt_parts.append(f"Location: {context.location}")
        
        # Add user input
        prompt_parts.extend([
            "",
            "User input:",
            context.user_input,
            "",
            "Please generate a creative, engaging response that:"
        ])
        
        # Add guidelines
        guidelines = [
            "- Maintains character consistency and personality",
            "- Advances the narrative meaningfully",
            "- Responds appropriately to the user's input",
            "- Creates engaging dialogue and descriptions",
            "- Keeps the story immersive and entertaining"
        ]
        
        if context.scene_type == "dialogue":
            guidelines.append("- Focuses on character dialogue and interaction")
        elif context.scene_type == "action":
            guidelines.append("- Emphasizes action and dynamic scenes")
        
        prompt_parts.extend(guidelines)
        prompt_parts.append("\nResponse:")
        
        return "\n".join(prompt_parts)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (actual tokenization varies by model)."""
        # Rough approximation: 1 token ≈ 4 characters for English text
        return len(text) // 4


# Factory function for creating adapters
def create_adapter(provider: str, config: ModelConfig) -> BaseModelAdapter:
    """Factory function to create model adapters."""
    adapters = {
        "mock": MockModelAdapter,
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter
    }
    
    adapter_class = adapters.get(provider.lower())
    if not adapter_class:
        raise ValueError(f"Unknown provider: {provider}")
    
    return adapter_class(config)


# Export all adapter components
__all__ = [
    "ModelConfig",
    "BaseModelAdapter",
    "MockModelAdapter",
    "OpenAIAdapter", 
    "AnthropicAdapter",
    "OllamaAdapter",
    "ModelManagerImpl",
    "create_adapter"
]
