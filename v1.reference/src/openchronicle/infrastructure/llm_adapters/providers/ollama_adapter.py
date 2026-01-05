"""
Ollama adapter implementation.

Demonstrates the template pattern working for local API providers.
Original Ollama adapter was ~100 lines, now reduced to ~40 lines.

Following OpenChronicle naming convention: ollama_adapter.py
"""

import asyncio
from typing import Any

from ..adapter_exceptions import AdapterConnectionError
from ..adapter_exceptions import AdapterResponseError
from ..api_adapter_base import LocalModelAdapter


class OllamaAdapter(LocalModelAdapter):
    """Ollama local model adapter using template method pattern."""

    def get_provider_name(self) -> str:
        return "ollama"

    def get_default_base_url(self) -> str:
        return "http://localhost:11434"

    async def _create_client(self) -> Any:
        """Create HTTP client for Ollama API."""
        import httpx

        timeout = self.config.get("timeout", self.timeout)
        client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

        # Test connection during client creation
        try:
            response = await client.get("/api/tags")
            if response.status_code != 200:
                raise AdapterConnectionError(
                    self.get_provider_name(),
                    f"Ollama connection failed: HTTP {response.status_code}",
                )
        except httpx.RequestError as e:
            await client.aclose()
            raise AdapterConnectionError(self.get_provider_name(), f"Failed to connect to Ollama: {e}") from e
        else:
            return client

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Ollama API."""
        client = await self.get_client()

        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens),
                },
            }

            response = await client.post("/api/generate", json=payload)

            if response.status_code != 200:
                raise AdapterResponseError(
                    self.get_provider_name(),
                    f"Ollama API error: HTTP {response.status_code}",
                )

            result = response.json()
            content = result.get("response", "").strip()

            if not content:
                raise AdapterResponseError(self.get_provider_name(), "Empty response received from Ollama")

        except asyncio.TimeoutError:
            from ..adapter_exceptions import AdapterTimeoutError

            raise AdapterTimeoutError(self.get_provider_name(), self.timeout) from None
        except ValueError as e:
            # JSON parsing error
            raise AdapterResponseError(self.get_provider_name(), f"Malformed response: {e}") from e
        except Exception as e:
            # Check for network/connection errors in exception message
            msg = str(e).lower()
            if any(term in msg for term in ["connection", "network", "timeout", "unreachable"]):
                raise AdapterConnectionError(self.get_provider_name(), f"Network error: {e}") from e
            raise AdapterResponseError(self.get_provider_name(), f"Ollama request failed: {e}") from e
        else:
            return content
