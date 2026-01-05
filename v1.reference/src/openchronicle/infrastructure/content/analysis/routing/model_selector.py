"""
Model selection component for choosing the best model for content generation.

Date: August 4, 2025
Purpose: Intelligent model selection based on content analysis and routing rules
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 812-880)
"""

from typing import Any

from openchronicle.shared.logging_system import log_system_event

# Import logging utilities
from openchronicle.shared.logging_system import log_warning

from ..shared.interfaces import RoutingComponent


class ModelSelector(RoutingComponent):
    """Select the best model for content generation based on analysis."""

    def __init__(self, model_manager):
        super().__init__(model_manager)

    def get_recommendation(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Get routing recommendation based on analysis."""
        recommended_model = self.recommend_generation_model(analysis)
        return {
            "recommended_model": recommended_model,
            "routing_metadata": self._get_routing_metadata(analysis, recommended_model),
            "routing_confidence": analysis.get("confidence", 0.5),
        }

    def route_request(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Route content generation request to the best model."""
        recommended_model = self.recommend_generation_model(analysis)

        return {
            "selected_model": recommended_model,
            "routing_metadata": self._get_routing_metadata(analysis, recommended_model),
        }

    async def process(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Process routing request and return model selection."""
        analysis = context.get("analysis", {})
        return self.route_request(analysis, context)

    def recommend_generation_model(self, analysis: dict[str, Any]) -> str:
        """Recommend the best model for content generation based on analysis."""
        content_type = analysis.get("content_type", "general")
        content_flags = analysis.get("content_flags", [])
        confidence = analysis.get("confidence", 0.0)

        config = self.model_manager.config
        content_routing = config.get("content_routing", {})

        # Priority-based routing with confidence thresholds
        candidates = []
        routing_reason = ""

        # High-confidence NSFW content
        if ("explicit" in content_flags) and confidence > 0.7:
            candidates = content_routing.get("nsfw_models", [])
            routing_reason = f"Explicit content detected with {confidence:.2f} confidence"

        # Suggestive or mature content with sufficient confidence
        elif ("suggestive" in content_flags or "mature" in content_flags) and confidence > 0.5:
            candidates = content_routing.get("nsfw_models", [])
            routing_reason = f"Mature content detected with {confidence:.2f} confidence"

        # NSFW content type but low confidence - route to safe models
        elif content_type == "nsfw" and confidence <= 0.5:
            candidates = content_routing.get("safe_models", [])
            routing_reason = f"Low-confidence NSFW content ({confidence:.2f}) routed to safe models"

        # Creative content
        elif content_type == "creative" or "creative" in content_flags:
            candidates = content_routing.get("creative_models", [])
            routing_reason = "Creative content detected"

        # Simple/quick responses
        elif "simple" in content_flags or analysis.get("word_count", 0) < 5:
            candidates = content_routing.get("fast_models", [])
            routing_reason = "Simple/quick response needed"

        # Analysis requests
        elif content_type == "analysis" or "analysis" in content_flags:
            candidates = content_routing.get("analysis_models", [])
            routing_reason = "Analysis content detected"

        # Default to safe models
        else:
            candidates = content_routing.get("safe_models", [])
            routing_reason = "Default safe routing"

        # Filter for enabled models
        enabled_models = [
            name for name in candidates if self.model_manager.list_model_configs().get(name, {}).get("enabled", True)
        ]

        if not enabled_models:
            log_warning(f"No enabled models for routing decision: {routing_reason}")
            # Fallback to any enabled model
            all_models = self.model_manager.list_model_configs()
            enabled_models = [name for name, config in all_models.items() if config.get("enabled", True)]

            if enabled_models:
                recommended = enabled_models[0]
                routing_reason = f"Fallback to {recommended} (no suitable models enabled)"
            else:
                recommended = "mock"
                routing_reason = "Emergency fallback to mock model"
                log_warning(
                    "WARNING: Using mock adapter for AI processing - this is for testing only and "
                    "will not provide real AI functionality!"
                )
                log_warning("Please configure a real AI model (Ollama, OpenAI, Anthropic, etc.) for production use.")
        else:
            recommended = enabled_models[0]  # First in priority order

        # Log routing decision
        log_system_event(
            "model_routing",
            f"Recommended {recommended} for generation. Reason: {routing_reason}",
        )

        return recommended

    def _get_routing_metadata(self, analysis: dict[str, Any], selected_model: str) -> dict[str, Any]:
        """Get metadata about the routing decision."""
        return {
            "content_type": analysis.get("content_type", "general"),
            "content_flags": analysis.get("content_flags", []),
            "confidence": analysis.get("confidence", 0.0),
            "selected_model": selected_model,
            "routing_timestamp": analysis.get("timestamp"),
            "word_count": analysis.get("word_count", 0),
        }
