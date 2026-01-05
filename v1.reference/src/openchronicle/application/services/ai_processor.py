"""
AI Processor Service - Core AI Processing for OpenChronicle

This service handles AI-related processing workflows:
- Model response generation with routing
- Content analysis and classification
- AI-powered content enhancement
- Model adapter orchestration

Follows hexagonal architecture principles with dependency injection.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from openchronicle.shared.exceptions import ApplicationError
from openchronicle.shared.exceptions import ModelError
from openchronicle.shared.retry_policy import RetryPolicy


if TYPE_CHECKING:
    from openchronicle.domain.ports.content_analysis_port import IContentAnalysisPort
    from openchronicle.domain.ports.model_management_port import IModelManagementPort


@dataclass
class AIProcessingConfig:
    """Configuration for AI processing workflows."""

    default_max_tokens: int = 1024
    default_temperature: float = 0.7
    enable_content_analysis: bool = True
    enable_retry_policy: bool = True
    max_retry_attempts: int = 3
    retry_base_delay: float = 0.4


class AIProcessor:
    """
    Core AI processing service that orchestrates AI-powered operations
    across the OpenChronicle system.

    Uses dependency injection to access model management and content analysis
    capabilities while remaining decoupled from infrastructure implementations.
    """

    def __init__(
        self,
        config: AIProcessingConfig | None = None,
        model_management_port: "IModelManagementPort | None" = None,
        content_analysis_port: "IContentAnalysisPort | None" = None,
    ):
        self.config = config or AIProcessingConfig()
        self.model_management_port = model_management_port
        self.content_analysis_port = content_analysis_port

        # Set up retry policy if enabled
        if self.config.enable_retry_policy:
            self.retry_policy = RetryPolicy(
                max_attempts=self.config.max_retry_attempts,
                base_delay=self.config.retry_base_delay,
                retry_exceptions=(Exception,),  # TODO: narrow to specific exceptions
            )
        else:
            self.retry_policy = None

    async def generate_response(
        self,
        prompt: str,
        story_id: str | None = None,
        adapter_name: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Generate AI response using the configured model management port.

        Args:
            prompt: The input prompt for AI generation
            story_id: Optional story context identifier
            adapter_name: Optional specific adapter to use
            max_tokens: Optional token limit override
            temperature: Optional temperature override

        Returns:
            Generated AI response text
        """
        # Use config defaults if not specified
        tokens = max_tokens or self.config.default_max_tokens
        temp = temperature or self.config.default_temperature

        if self.model_management_port is not None:
            # Use injected port
            async def _attempt():
                return await self.model_management_port.generate_response(
                    prompt=prompt,
                    story_id=story_id,
                    adapter_name=adapter_name,
                    max_tokens=tokens,
                    temperature=temp,
                )

            if self.retry_policy:
                return await self.retry_policy.run(_attempt)
            else:
                return await _attempt()
        else:
            # Fallback for backward compatibility
            from openchronicle.domain.ports.model_management_port import IModelManagementPort

            class MockModelManagementPort(IModelManagementPort):
                async def generate_response(
                    self,
                    prompt: str,
                    story_id: str | None = None,
                    adapter_name: str | None = None,
                    max_tokens: int | None = None,
                    temperature: float | None = None,
                ) -> str:
                    return f"[Mock AI Response for prompt: {prompt[:50]}...]"

                async def get_available_adapters(self) -> list[str]:
                    return ["mock_adapter"]

                async def validate_adapter(self, adapter_name: str) -> bool:
                    return adapter_name == "mock_adapter"

            mock_port = MockModelManagementPort()
            return await mock_port.generate_response(
                prompt=prompt,
                story_id=story_id,
                adapter_name=adapter_name,
                max_tokens=tokens,
                temperature=temp,
            )

    async def analyze_content(
        self,
        content: str,
        analysis_type: str = "sentiment",
    ) -> dict[str, Any]:
        """
        Analyze content using AI-powered analysis capabilities.

        Args:
            content: The content to analyze
            analysis_type: Type of analysis ("sentiment", "themes", "classification")

        Returns:
            Analysis results dictionary
        """
        if not self.config.enable_content_analysis:
            return {"analysis_disabled": True}

        if self.content_analysis_port is not None:
            # Use injected port
            if analysis_type == "sentiment":
                return await self.content_analysis_port.analyze_content_sentiment(content)
            elif analysis_type == "themes":
                themes = await self.content_analysis_port.detect_content_themes(content)
                return {"themes": themes}
            else:
                # Generic analysis
                return {
                    "sentiment": await self.content_analysis_port.analyze_content_sentiment(content),
                    "themes": await self.content_analysis_port.detect_content_themes(content),
                }
        else:
            # Fallback for backward compatibility
            from openchronicle.domain.ports.content_analysis_port import IContentAnalysisPort

            class MockContentAnalysisPort(IContentAnalysisPort):
                async def generate_content_flags(self, analysis: dict[str, Any], content: str) -> list[dict[str, Any]]:
                    return [{"name": "mock_flag", "value": "test", "type": "content"}]

                async def analyze_content_sentiment(self, content: str) -> dict[str, Any]:
                    return {"sentiment": "neutral", "confidence": 0.5, "mock": True}

                async def detect_content_themes(self, content: str) -> list[str]:
                    return ["general", "mock"]

            mock_port = MockContentAnalysisPort()

            if analysis_type == "sentiment":
                return await mock_port.analyze_content_sentiment(content)
            elif analysis_type == "themes":
                themes = await mock_port.detect_content_themes(content)
                return {"themes": themes}
            else:
                return {
                    "sentiment": await mock_port.analyze_content_sentiment(content),
                    "themes": await mock_port.detect_content_themes(content),
                }

    async def generate_content_flags(
        self,
        content: str,
        analysis_data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate content flags for the given content.

        Args:
            content: Content to analyze for flags
            analysis_data: Optional pre-computed analysis data

        Returns:
            List of content flags
        """
        if not self.config.enable_content_analysis:
            return []

        # Use existing analysis or compute new one
        if analysis_data is None:
            analysis_data = await self.analyze_content(content)

        if self.content_analysis_port is not None:
            return await self.content_analysis_port.generate_content_flags(analysis_data, content)
        else:
            # Fallback
            return [
                {
                    "name": "processed_content",
                    "value": "ai_processed",
                    "type": "system",
                    "confidence": 1.0,
                }
            ]

    async def enhance_content(
        self,
        content: str,
        enhancement_type: str = "improve",
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Use AI to enhance or improve content.

        Args:
            content: Content to enhance
            enhancement_type: Type of enhancement ("improve", "expand", "summarize")
            context: Optional context for enhancement

        Returns:
            Enhanced content
        """
        # Build enhancement prompt based on type
        if enhancement_type == "improve":
            prompt = f"Improve the following content while maintaining its core message:\n\n{content}"
        elif enhancement_type == "expand":
            prompt = f"Expand on the following content with more detail:\n\n{content}"
        elif enhancement_type == "summarize":
            prompt = f"Summarize the following content concisely:\n\n{content}"
        else:
            prompt = f"Process the following content ({enhancement_type}):\n\n{content}"

        # Add context if provided
        if context:
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            prompt = f"Context:\n{context_str}\n\n{prompt}"

        # Generate enhanced content
        return await self.generate_response(
            prompt=prompt,
            max_tokens=self.config.default_max_tokens,
            temperature=self.config.default_temperature,
        )

    async def get_processing_capabilities(self) -> dict[str, Any]:
        """
        Get information about available AI processing capabilities.

        Returns:
            Dictionary describing available capabilities
        """
        capabilities = {
            "response_generation": True,
            "content_analysis": self.config.enable_content_analysis,
            "content_enhancement": True,
            "retry_policy": self.config.enable_retry_policy,
        }

        if self.model_management_port is not None:
            try:
                adapters = await self.model_management_port.get_available_adapters()
                capabilities["available_adapters"] = adapters
            except (ModelError, ApplicationError) as e:
                capabilities["available_adapters"] = ["service_error"]
            except (AttributeError, KeyError) as e:
                # Data structure error
                capabilities["available_adapters"] = ["data_error"]
            except Exception as e:
                capabilities["available_adapters"] = ["unknown_error"]
        else:
            capabilities["available_adapters"] = ["mock_adapter"]

        return capabilities


class AIProcessorFactory:
    """Factory for creating AI processor with dependencies."""

    @staticmethod
    def create(
        config: AIProcessingConfig | None = None,
        model_management_port: "IModelManagementPort | None" = None,
        content_analysis_port: "IContentAnalysisPort | None" = None,
    ) -> AIProcessor:
        """Create an AI processor with all dependencies."""
        if config is None:
            config = AIProcessingConfig()

        return AIProcessor(
            config=config,
            model_management_port=model_management_port,
            content_analysis_port=content_analysis_port,
        )

    @staticmethod
    def create_with_defaults() -> AIProcessor:
        """Create an AI processor with default configuration and mock ports."""
        return AIProcessorFactory.create()


# Convenience method for backward compatibility
def create_ai_processor_with_defaults() -> AIProcessor:
    """Create an AI processor with default configuration."""
    return AIProcessorFactory.create_with_defaults()
