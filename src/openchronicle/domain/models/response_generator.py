"""
Response Generator for OpenChronicle Model Management.

This module extracts the core response generation logic from the monolithic
ModelManager class as part of Phase 3.0 system decomposition.

Key Features:
- Clean response generation interface
- Fallback chain support
- Performance tracking integration
- Error handling and logging
- Adapter selection and routing
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from src.openchronicle.shared.logging_system import log_error
from src.openchronicle.shared.logging_system import log_info
from src.openchronicle.shared.logging_system import log_system_event
from src.openchronicle.shared.logging_system import log_warning


logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Handles core response generation logic with fallback support.

    This class is extracted from ModelManager to provide focused,
    testable response generation functionality.
    """

    def __init__(
        self,
        adapter_registry: dict[str, Any],
        config: dict[str, Any],
        performance_monitor=None,
    ):
        """
        Initialize the response generator.

        Args:
            adapter_registry: Dictionary of available adapters
            config: System configuration
            performance_monitor: Optional performance monitoring instance
        """
        self.adapters = adapter_registry
        self.config = config
        self.performance_monitor = performance_monitor
        self.default_adapter = config.get("default_adapter")

        log_info("ResponseGenerator initialized")

    async def generate_response(
        self,
        prompt: str,
        adapter_name: str | None = None,
        story_id: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate response using specified or default adapter with fallback support.

        Args:
            prompt: The prompt to generate a response for
            adapter_name: Optional specific adapter to use
            story_id: Optional story ID for interaction logging
            **kwargs: Additional parameters for generation

        Returns:
            Generated response text

        Raises:
            RuntimeError: When no adapters are available
        """
        adapter_name = adapter_name or self.default_adapter

        # Enhanced fallback logic for when no adapter is specified
        if not adapter_name:
            adapter_name = await self._get_emergency_fallback_adapter()

        # Start performance tracking if available
        tracker_context = self._get_performance_tracker(
            adapter_name, "generate", len(prompt)
        )

        async with tracker_context as tracker:
            # Use fallback chain if configured
            if self._has_fallback_chain(adapter_name):
                return await self._generate_with_fallback_chain(
                    adapter_name, prompt, story_id, tracker, **kwargs
                )

            # Single adapter logic
            return await self._generate_with_single_adapter(
                adapter_name, prompt, story_id, tracker, **kwargs
            )

    async def _get_emergency_fallback_adapter(self) -> str:
        """
        Find an emergency fallback adapter when none is specified.

        Returns:
            Name of available adapter

        Raises:
            RuntimeError: When no adapters are available
        """
        # First priority: Try transformers if available
        if "transformers" in self.adapters:
            log_warning("No default adapter specified, using transformers as fallback")
            return "transformers"

        # Second priority: Try to find any available adapter (excluding mock adapters)
        available_adapters = [
            name for name in self.adapters.keys() if not name.startswith("mock")
        ]

        if available_adapters:
            adapter_name = available_adapters[0]
            log_warning(
                f"No default adapter specified, using emergency fallback: {adapter_name}"
            )
            return adapter_name

        raise RuntimeError(
            "No adapter specified and no production adapters available. "
            "Please configure AI services (OpenAI, Anthropic, etc.) or ensure transformers is properly installed."
        )

    def _has_fallback_chain(self, adapter_name: str) -> bool:
        """Check if adapter has a configured fallback chain."""
        return (
            "fallback_chains" in self.config
            and adapter_name in self.config["fallback_chains"]
        )

    async def _generate_with_fallback_chain(
        self,
        adapter_name: str,
        prompt: str,
        story_id: str | None,
        tracker: Any,
        **kwargs,
    ) -> str:
        """
        Generate response using fallback chain logic.

        Args:
            adapter_name: Primary adapter name
            prompt: The prompt to generate response for
            story_id: Optional story ID for logging
            tracker: Performance tracker instance
            **kwargs: Additional generation parameters

        Returns:
            Generated response text

        Raises:
            RuntimeError: When all adapters in chain fail
        """
        chain = self.config["fallback_chains"][adapter_name]
        log_info(f"Using fallback chain for {adapter_name}: {chain}")
        log_system_event(
            "fallback_chain_usage", f"Using fallback chain for {adapter_name}: {chain}"
        )

        for attempt_adapter in chain:
            try:
                # Skip unavailable adapters
                if not self._is_adapter_available(attempt_adapter):
                    log_info(
                        f"Skipping adapter '{attempt_adapter}' in fallback chain - not available"
                    )
                    continue

                # Generate response with this adapter
                adapter = self.adapters[attempt_adapter]
                response = await adapter.generate_response(prompt, **kwargs)

                # Update performance tracking
                self._update_tracker_metrics(tracker, response)

                # Log interaction if story_id provided
                if story_id:
                    self._log_interaction(
                        adapter,
                        attempt_adapter,
                        prompt,
                        response,
                        story_id,
                        chain,
                        **kwargs,
                    )

                log_info(f"Successfully generated response using {attempt_adapter}")
                log_system_event(
                    "fallback_chain_success",
                    f"Successfully generated response using {attempt_adapter} "
                    f"(fallback position {chain.index(attempt_adapter)})",
                )
                return response

            except Exception as e:
                log_error(f"Adapter {attempt_adapter} failed: {e}")
                log_system_event(
                    "fallback_chain_failure", f"Adapter {attempt_adapter} failed: {e}"
                )
                continue

        # All adapters in chain failed
        log_system_event(
            "fallback_chain_exhausted",
            f"All adapters in fallback chain failed for {adapter_name}",
        )
        raise RuntimeError(f"All adapters in fallback chain failed for {adapter_name}")

    async def _generate_with_single_adapter(
        self,
        adapter_name: str,
        prompt: str,
        story_id: str | None,
        tracker: Any,
        **kwargs,
    ) -> str:
        """
        Generate response using a single adapter.

        Args:
            adapter_name: Name of adapter to use
            prompt: The prompt to generate response for
            story_id: Optional story ID for logging
            tracker: Performance tracker instance
            **kwargs: Additional generation parameters

        Returns:
            Generated response text

        Raises:
            KeyError: When adapter is not available
        """
        if adapter_name not in self.adapters:
            raise KeyError(
                f"Adapter '{adapter_name}' not available. "
                f"Available adapters: {list(self.adapters.keys())}"
            )

        adapter = self.adapters[adapter_name]
        response = await adapter.generate_response(prompt, **kwargs)

        # Update performance tracking
        self._update_tracker_metrics(tracker, response)

        # Log interaction if story_id provided
        if story_id:
            metadata = {"adapter": adapter_name, "kwargs": kwargs}
            adapter.log_interaction(story_id, prompt, response, metadata)

        log_info(f"Successfully generated response using {adapter_name}")
        return response

    def _is_adapter_available(self, adapter_name: str) -> bool:
        """Check if adapter is available in both registry and configuration."""
        return adapter_name in self.adapters and adapter_name in self.config.get(
            "adapters", {}
        )

    def _update_tracker_metrics(self, tracker: Any, response: str):
        """Update performance tracker with response metrics."""
        if tracker and response:
            tracker.set_tokens_processed(len(response.split()))
            tracker.set_response_size(len(response.encode("utf-8")))

    def _log_interaction(
        self,
        adapter: Any,
        adapter_name: str,
        prompt: str,
        response: str,
        story_id: str,
        chain: list[str],
        **kwargs,
    ):
        """Log the interaction with metadata."""
        metadata = {
            "adapter": adapter_name,
            "kwargs": kwargs,
            "fallback_position": chain.index(adapter_name),
        }
        adapter.log_interaction(story_id, prompt, response, metadata)

    @asynccontextmanager
    async def _get_performance_tracker(
        self, adapter_name: str, operation: str, prompt_length: int
    ):
        """Get performance tracker context manager."""
        if self.performance_monitor:
            async with self.performance_monitor.track_model_operation(
                adapter_name, operation, prompt_length=prompt_length
            ) as tracker:
                yield tracker
        else:
            # Dummy tracker when no performance monitor available
            class DummyTracker:
                def set_tokens_processed(self, count):
                    pass

                def set_response_size(self, size):
                    pass

            yield DummyTracker()

    def get_available_adapters(self) -> list[str]:
        """Get list of available adapter names."""
        return list(self.adapters.keys())

    def get_default_adapter(self) -> str | None:
        """Get the default adapter name."""
        return self.default_adapter

    def set_default_adapter(self, adapter_name: str):
        """Set the default adapter."""
        if adapter_name in self.adapters:
            self.default_adapter = adapter_name
            log_info(f"Default adapter set to: {adapter_name}")
        else:
            raise ValueError(f"Adapter '{adapter_name}' not available")
