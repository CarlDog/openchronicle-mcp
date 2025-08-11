"""
Anthropic Claude adapter implementation.

Another example of the template pattern reducing adapter code from ~100 to ~30 lines.
Shows consistency across different API providers.

Following OpenChronicle naming convention: anthropic_adapter.py
"""

from typing import Any
from ..api_adapter_base import BaseAPIAdapter
from ..adapter_exceptions import AdapterResponseError


class AnthropicAdapter(BaseAPIAdapter):
    """Anthropic Claude adapter using template method pattern."""

    def get_provider_name(self) -> str:
        return "anthropic"

    def get_api_key_env_var(self) -> str:
        return "ANTHROPIC_API_KEY"

    def get_default_base_url(self) -> str:
        return "https://api.anthropic.com"

    async def _create_client(self) -> Any:
        """Create Anthropic client."""
        import anthropic

        return anthropic.AsyncAnthropic(api_key=self.api_key, base_url=self.base_url)

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic Claude API."""
        client = await self.get_client()

        try:
            response = await client.messages.create(
                model=self.model_name,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text if response.content else ""
            if not content:
                raise AdapterResponseError(
                    self.get_provider_name(), "Empty response received from Anthropic"
                )

            return content.strip()

        except Exception as e:
            if "rate limit" in str(e).lower():
                from ..adapter_exceptions import AdapterRateLimitError

                raise AdapterRateLimitError(self.get_provider_name())
            elif "timeout" in str(e).lower():
                from ..adapter_exceptions import AdapterTimeoutError

                raise AdapterTimeoutError(self.get_provider_name(), self.timeout)
            else:
                raise AdapterResponseError(
                    self.get_provider_name(), f"Anthropic API request failed: {e}"
                )
