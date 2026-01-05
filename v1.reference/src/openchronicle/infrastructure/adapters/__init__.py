"""
Infrastructure layer LLM adapters for OpenChronicle.

This module provides concrete implementations for interacting with various
Large Language Model providers. These adapters implement the model management
port interface defined in the domain layer.
"""

import asyncio
import logging
import time
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime

from openchronicle.domain import ModelResponse
from openchronicle.domain import NarrativeContext
from openchronicle.domain.ports.model_management_port import IModelManagementPort
from openchronicle.shared.exceptions import InfrastructureError
from openchronicle.shared.exceptions import ModelError
from openchronicle.shared.exceptions import ModelResponseError


@dataclass
class ModelConfig:
    """Configuration for a model adapter."""

    name: str
    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model_id: str = ""
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30
    rate_limit: int = 60  # requests per minute
    fallback_models: list[str] | None = None

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
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> str:
        """Generate text using the model."""

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
        """Format runtime context into a prompt for the model."""
        prompt_parts = []
        # Context identifier
        prompt_parts.append(f"Context ID: {context.story_id}")

        # Memory state summary
        if context.memory_state:
            if context.memory_state.character_memories:
                prompt_parts.append("Participants present:")
                for char_id, _memory in context.memory_state.character_memories.items():
                    if char_id in context.participant_ids:
                        participant = context.characters.get(char_id)
                        if participant:
                            prompt_parts.append(f"- {participant.name}: {participant.description}")

        # Context type
        if context.scene_type:
            prompt_parts.append(f"Context type: {context.scene_type}")

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
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> str:
        """Generate mock response."""
        await self._check_rate_limit()

        # Simulate processing time
        await asyncio.sleep(0.1)

        # Generate a mock response based on prompt content
        lower = prompt.lower()
        if "entity" in lower:
            return "The entity responds thoughtfully, considering relevant factors and the current state."
        if "action" in lower:
            return "A significant change unfolds, affecting subsequent steps."
        if "dialogue" in lower:
            return '"This is an interesting development," the agent remarks with intrigue.'
        return "The process continues with additional detail, revealing useful context."


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

                self._client = openai.AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
            except ImportError as e:
                raise ImportError("OpenAI package not installed. Run: pip install openai") from e
        return self._client

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
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
                timeout=self.config.timeout,
            )
        except ImportError as e:
            self.logger.exception("OpenAI package not available")
            raise ModelError(f"OpenAI client not available: {e}") from e
        except (ConnectionError, TimeoutError) as e:
            self.logger.exception("OpenAI connection error")
            raise ModelError(f"OpenAI connection failed: {e}") from e
        except Exception as e:
            self.logger.exception("OpenAI API error")
            raise ModelError(f"OpenAI API failed: {e}") from e
        else:
            content = response.choices[0].message.content  # type: ignore[attr-defined]
            return content or ""


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

                self._client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
            except ImportError as e:
                raise ImportError("Anthropic package not installed. Run: pip install anthropic") from e
        return self._client

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> str:
        """Generate text using Anthropic API."""
        await self._check_rate_limit()

        client = await self._get_client()

        try:
            response = await client.messages.create(
                model=self.config.model_id or "claude-3-haiku-20240307",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature,
            )
        except ImportError as e:
            self.logger.exception("Anthropic package not available")
            raise ModelError(f"Anthropic client not available: {e}") from e
        except (ConnectionError, TimeoutError) as e:
            self.logger.exception("Anthropic connection error")
            raise ModelError(f"Anthropic connection failed: {e}") from e
        except Exception as e:
            self.logger.exception("Anthropic API error")
            raise ModelError(f"Anthropic API failed: {e}") from e
        else:
            # Safely extract text from response content blocks
            text_out = ""
            try:
                for block in getattr(response, "content", []) or []:
                    t = getattr(block, "text", None)
                    if isinstance(t, str):
                        text_out += t
            except Exception:
                pass
            return text_out or ""


class OllamaAdapter(BaseModelAdapter):
    """Ollama local model adapter."""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> str:
        """Generate text using Ollama API."""

        def _raise_ollama_api_error(status):
            raise ModelResponseError(f"Ollama API error: {status}")

        await self._check_rate_limit()

        try:
            import aiohttp  # type: ignore

            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.config.model_id or "llama2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens or self.config.max_tokens,
                        "temperature": temperature or self.config.temperature,
                    },
                }

                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("response", "")
                    _raise_ollama_api_error(response.status)
        except ImportError as e:
            self.logger.exception("aiohttp package not available")
            raise InfrastructureError("aiohttp package not installed. Run: pip install aiohttp") from e
        except (ConnectionError, TimeoutError) as e:
            self.logger.exception("Ollama connection error")
            raise ModelError(f"Ollama connection failed: {e}") from e
        except Exception as e:
            self.logger.exception("Ollama API error")
            raise ModelError(f"Ollama API failed: {e}") from e

        # Fallback return to satisfy all code paths
        return ""


class ModelManagementAdapter(IModelManagementPort):
    """Implementation of the model management port interface."""

    def __init__(self):
        self.adapters: dict[str, BaseModelAdapter] = {}
        self.fallback_chains: dict[str, list[str]] = {}
        self.logger = logging.getLogger("ModelManagementAdapter")

    def register_adapter(self, name: str, adapter: BaseModelAdapter):
        """Register a model adapter."""
        self.adapters[name] = adapter
        self.logger.info(f"Registered model adapter: {name}")

    def set_fallback_chain(self, primary: str, fallbacks: list[str]):
        """Set fallback chain for a model."""
        self.fallback_chains[primary] = fallbacks

    async def generate_response(self, context: NarrativeContext, model_preference: str | None = None) -> ModelResponse:
        """Generate AI response using preferred model with fallbacks."""
        start_time = time.time()

        # Determine models to try
        models_to_try: list[str] = []
        if model_preference and model_preference in self.adapters:
            models_to_try.append(model_preference)
            models_to_try.extend(self.fallback_chains.get(model_preference, []))
        else:
            # Use first available model(s)
            models_to_try = list(self.adapters.keys())

        if not models_to_try:
            generation_time = time.time() - start_time
            return ModelResponse(
                content="",
                model_name="none",
                provider="none",
                timestamp=datetime.now(),
                tokens_used=0,
                generation_time=generation_time,
                finish_reason="error: no models available",
            )

        # Format the context into a prompt
        prompt = self._format_runtime_prompt(context)

        # Try models in order
        last_error: str | None = None
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
                    finish_reason="completed",
                )

            except ModelError as e:
                # Domain-level errors; try next model
                last_error = str(e)
                self.logger.warning(f"Model {model_name} failed with domain error: {e}")
                continue
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
            finish_reason=f"error: {last_error}",
        )

    def _format_runtime_prompt(self, context: NarrativeContext) -> str:
        """Format runtime context into a comprehensive prompt."""
        prompt_parts = [
            "You are a helpful AI assistant supporting an interactive experience.",
            "",
            "Context:",
        ]

        # Add participant information
        if context.characters and context.participant_ids:
            prompt_parts.append("Participants involved:")
            for char_id in context.participant_ids:
                participant = context.characters.get(char_id)
                if participant:
                    prompt_parts.extend(
                        [
                            f"- {participant.name}: {participant.description}",
                            f"  Personality: {participant.personality_traits}",
                            f"  Current emotional state: {participant.emotional_state}",
                        ]
                    )

        # Add recent context
        if context.memory_state and context.memory_state.recent_events:
            prompt_parts.append("\nRecent events:")
            for event in context.memory_state.recent_events[-3:]:  # Last 3 events
                prompt_parts.append(f"- {event}")

        # Add step details
        if context.scene_type:
            prompt_parts.append(f"\nStep type: {context.scene_type}")

        if context.location:
            prompt_parts.append(f"Location: {context.location}")

        # Add user input
        prompt_parts.extend(
            [
                "",
                "User input:",
                context.user_input,
                "",
                "Please generate a helpful, engaging response that:",
            ]
        )

        # Add guidelines
        guidelines = [
            "- Maintains participant consistency",
            "- Progresses the interaction meaningfully",
            "- Responds appropriately to the user's input",
            "- Creates engaging conversation and descriptions",
            "- Keeps the experience immersive and coherent",
        ]

        if context.scene_type == "dialog":
            guidelines.append("- Focuses on participant conversation and interaction")
        elif context.scene_type == "action":
            guidelines.append("- Emphasizes action and dynamic steps")

        prompt_parts.extend(guidelines)
        prompt_parts.append("\nResponse:")

        return "\n".join(prompt_parts)

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (actual tokenization varies by model)."""
        # Rough approximation: 1 token ≈ 4 chars for English text
        return len(text) // 4


# Factory function for creating adapters
def create_adapter(provider: str, config: ModelConfig) -> BaseModelAdapter:
    """Factory function to create model adapters."""
    adapters = {
        "mock": MockModelAdapter,
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
    }

    adapter_class = adapters.get(provider.lower())
    if not adapter_class:
        raise ValueError(f"Unknown provider: {provider}")

    return adapter_class(config)


# Export all adapter components
__all__ = [
    "AnthropicAdapter",
    "BaseModelAdapter",
    "MockModelAdapter",
    "ModelConfig",
    "ModelManagementAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "create_adapter",
]
