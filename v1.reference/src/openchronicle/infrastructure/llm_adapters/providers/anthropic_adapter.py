"""
Anthropic Claude adapter implementation.

Another example of the template pattern reducing adapter code from ~100 to ~30 lines.
Shows consistency across different API providers.

Following OpenChronicle naming convention: anthropic_adapter.py
"""

import asyncio
from typing import Any

from ..adapter_exceptions import AdapterResponseError
from ..api_adapter_base import BaseAPIAdapter


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
                raise AdapterResponseError(self.get_provider_name(), "Empty response received from Anthropic")

            return content.strip()

        except (asyncio.TimeoutError, TimeoutError):
            from ..adapter_exceptions import AdapterTimeoutError

            raise AdapterTimeoutError(self.get_provider_name(), self.timeout) from None
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            raise AdapterResponseError(self.get_provider_name(), f"Malformed response: {e}") from e
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg:
                from ..adapter_exceptions import AdapterRateLimitError

                raise AdapterRateLimitError(self.get_provider_name()) from e
            raise AdapterResponseError(self.get_provider_name(), f"Anthropic API request failed: {e}") from e
