"""
OpenAI adapter implementation.

This adapter demonstrates the massive code reduction achieved through the BaseAPIAdapter
template pattern. The original OpenAI adapter was ~100 lines of mostly duplicated code.
This implementation is only ~30 lines of provider-specific logic.

Following OpenChronicle naming convention: openai_adapter.py
"""

from typing import Any

from ..adapter_exceptions import AdapterResponseError
from ..api_adapter_base import BaseAPIAdapter


class OpenAIAdapter(BaseAPIAdapter):
    """OpenAI GPT adapter using template method pattern."""

    def get_provider_name(self) -> str:
        return "openai"

    def get_api_key_env_var(self) -> str:
        return "OPENAI_API_KEY"

    def get_default_base_url(self) -> str:
        return "https://api.openai.com/v1"

    async def _create_client(self) -> Any:
        """Create OpenAI client - only provider-specific logic needed."""
        import openai

        return openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI API."""
        client = await self.get_client()

        try:
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a creative storytelling assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                timeout=kwargs.get("timeout", self.timeout),
            )

            content = response.choices[0].message.content
            if not content:
                raise AdapterResponseError(
                    self.get_provider_name(), "Empty response received"
                )

            return content.strip()

        except Exception as e:
            if "rate limit" in str(e).lower():
                from ..adapter_exceptions import AdapterRateLimitError

                raise AdapterRateLimitError(self.get_provider_name())
            if "timeout" in str(e).lower():
                from ..adapter_exceptions import AdapterTimeoutError

                raise AdapterTimeoutError(self.get_provider_name(), self.timeout)
            raise AdapterResponseError(
                self.get_provider_name(), f"API request failed: {e}"
            )
