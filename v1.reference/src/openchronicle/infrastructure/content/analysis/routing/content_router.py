"""
Content router component for making routing recommendations based on content analysis.

Date: August 4, 2025
Purpose: Provide routing recommendations including model parameters and configuration
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 1137-1193)
"""

from typing import Any

# Import logging utilities
from openchronicle.shared.logging_system import log_warning

from ..shared.interfaces import RoutingComponent


class ContentRouter(RoutingComponent):
    """Provide routing recommendations based on content analysis."""

    def __init__(self, model_manager):
        super().__init__(model_manager)

    def get_recommendation(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Get routing recommendation based on analysis."""
        return self.get_routing_recommendation(analysis)

    def route_request(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Route request and return comprehensive routing recommendations."""
        return self.get_routing_recommendation(analysis)

    async def process(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Process routing request and return routing configuration."""
        analysis = context.get("analysis", {})
        return self.route_request(analysis, context)

    def get_routing_recommendation(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """
        Recommend model routing based on content analysis.
        """
        content_flags = analysis.get("content_flags", [])
        token_priority = analysis.get("token_priority", "medium")

        # Get default adapter from model manager or fall back to mock
        default_adapter = "mock"  # Safe fallback
        if hasattr(self, "model_manager") and self.model_manager:
            try:
                # Try to get the configured default, or the first available adapter
                if hasattr(self.model_manager, "default_adapter") and self.model_manager.default_adapter:
                    default_adapter = self.model_manager.default_adapter
                elif hasattr(self.model_manager, "get_available_adapters"):
                    available = self.model_manager.get_available_adapters()
                    if available:
                        # Prefer non-mock adapters but use what's available
                        non_mock = [a for a in available if not a.startswith("mock")]
                        default_adapter = non_mock[0] if non_mock else available[0]
            except AttributeError as e:
                log_warning(f"Model manager configuration error: {e}, using mock fallback")
                default_adapter = "mock"
            except Exception as e:
                log_warning(f"Could not determine default adapter: {e}, using mock fallback")
                default_adapter = "mock"

        # Default routing
        recommendation = {
            "adapter": default_adapter,
            "max_tokens": 1024,
            "temperature": 0.7,
            "content_filter": False,
        }

        # Adjust based on content flags (list format)
        if (
            "nsfw" in content_flags
            or "explicit" in content_flags
            or "suggestive" in content_flags
            or "mature" in content_flags
            or "toxic_detected" in content_flags
        ):
            recommendation["content_filter"] = True

            # For sensitive content, prefer local models
            if hasattr(self, "model_manager") and self.model_manager:
                try:
                    available = self.model_manager.get_available_adapters()
                    local_adapters = [a for a in available if a in ["ollama", "mock"]]
                    if local_adapters:
                        recommendation["adapter"] = local_adapters[0]
                except AttributeError:
                    # Model manager doesn't have get_available_adapters method
                    pass
                except (KeyError, ValueError):
                    # Configuration or adapter data error
                    pass
                except Exception:
                    # Any other error in adapter selection
                    pass

        # Adjust token limits based on priority
        if token_priority == "high":
            recommendation["max_tokens"] = 2048
        elif token_priority == "low":
            recommendation["max_tokens"] = 512

        # Adjust temperature based on content type
        content_type = analysis.get("content_type", "action")
        if content_type == "dialogue":
            recommendation["temperature"] = 0.8  # More creative for dialogue
        elif content_type == "description":
            recommendation["temperature"] = 0.6  # More focused for descriptions

        return recommendation

    def get_model_parameters(self, content_type: str, content_flags: list[str]) -> dict[str, Any]:
        """Get recommended model parameters for content type and flags."""
        params = {
            "temperature": 0.7,
            "max_tokens": 1024,
            "top_p": 0.9,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
        }

        # Adjust based on content type
        if content_type == "creative":
            params["temperature"] = 0.9
            params["max_tokens"] = 1536
        elif content_type == "analysis":
            params["temperature"] = 0.3
            params["max_tokens"] = 2048
        elif content_type == "dialogue":
            params["temperature"] = 0.8
            params["presence_penalty"] = 0.1
        elif content_type == "description":
            params["temperature"] = 0.6
            params["max_tokens"] = 1024

        # Adjust based on content flags
        if "simple" in content_flags:
            params["max_tokens"] = 512
            params["temperature"] = 0.5
        elif "complex" in content_flags:
            params["max_tokens"] = 2048
            params["temperature"] = 0.7

        return params

    def get_safety_configuration(self, content_flags: list[str]) -> dict[str, Any]:
        """Get safety configuration based on content flags."""
        safety_config = {
            "content_filter": False,
            "toxicity_threshold": 0.7,
            "nsfw_detection": False,
            "output_filtering": False,
        }

        # Enable safety measures for sensitive content
        if any(flag in content_flags for flag in ["nsfw", "explicit", "suggestive", "mature", "toxic_detected"]):
            safety_config["content_filter"] = True
            safety_config["nsfw_detection"] = True
            safety_config["output_filtering"] = True

            if "explicit" in content_flags:
                safety_config["toxicity_threshold"] = 0.5

        return safety_config
