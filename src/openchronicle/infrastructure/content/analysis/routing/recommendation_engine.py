"""
Recommendation engine for suggesting model management actions and improvements.

Date: August 4, 2025
Purpose: Analyze system state and recommend model management improvements
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 1753-1875)
"""

from typing import Dict, List, Any, Optional

from ..shared.interfaces import RoutingComponent

# Import logging utilities
from src.openchronicle.shared.logging_system import log_error


class RecommendationEngine(RoutingComponent):
    """Analyze system state and recommend model management improvements."""

    def __init__(self, model_manager):
        super().__init__(model_manager)

    def route_request(
        self, analysis: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route recommendation request based on content type and system state."""
        content_type = analysis.get("content_type", "general")
        system_resources = context.get("system_resources")

        # This would be async in the original, but we'll make it sync for consistency
        recommendations = self._suggest_model_management_actions_sync(
            content_type, system_resources
        )

        return {
            "recommendations": recommendations,
            "content_type": content_type,
            "system_state": self._get_system_state(),
        }

    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process recommendation request and return suggestions."""
        analysis = context.get("analysis", {})
        return self.route_request(analysis, context)

    async def suggest_model_management_actions(
        self, content_type: str, system_resources: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Suggest model management actions based on system state and requirements.

        Args:
            content_type: The type of content being analyzed
            system_resources: Optional system resource information

        Returns:
            Dictionary with suggested actions
        """
        return self._suggest_model_management_actions_sync(
            content_type, system_resources
        )

    def _suggest_model_management_actions_sync(
        self, content_type: str, system_resources: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Synchronous version of suggest_model_management_actions."""
        try:
            suggestions = {
                "actions": [],
                "priority": "medium",
                "resource_impact": "low",
                "estimated_improvement": "medium",
            }

            # Check current model availability (simplified for modular version)
            all_models = self.model_manager.list_model_configs()
            working_models = self._get_working_models(content_type)

            # Analyze system state and generate suggestions
            working_analysis_models = [
                m for m in working_models if m not in ["mock", "mock_image"]
            ]

            if len(working_models) == 0:
                suggestions["priority"] = "high"
                suggestions["actions"].append(
                    {
                        "type": "install_model",
                        "description": f"No working models found - install suitable model for {content_type} content",
                        "commands": self._get_install_commands(content_type),
                    }
                )

            elif len(working_analysis_models) == 0:
                # Only mock models available
                suggestions["priority"] = "high"
                suggestions["actions"].append(
                    {
                        "type": "replace_mock",
                        "description": "Only mock/test models available - install actual AI model",
                        "commands": self._get_install_commands(content_type),
                    }
                )

            elif len(working_analysis_models) < 2:
                # Very limited options - suggest more models
                suggestions["priority"] = "medium"
                suggestions["actions"].append(
                    {
                        "type": "expand_options",
                        "description": f"Limited model options for {content_type} - install additional models for redundancy",
                        "commands": self._get_install_commands(content_type),
                    }
                )

            # Check quality of available models
            if working_analysis_models:
                # For modular version, assume basic quality scoring
                best_score = 0.7  # Placeholder
                if best_score < 0.7:
                    suggestions["actions"].append(
                        {
                            "type": "improve_quality",
                            "description": f"Available models have low suitability scores (best: {best_score:.2f}) - consider better alternatives",
                            "commands": self._get_install_commands(content_type),
                            "current_best_score": best_score,
                        }
                    )

            # Check for API key opportunities
            api_models = ["openai", "anthropic", "groq", "gemini"]
            missing_api_models = [
                name
                for name in api_models
                if name in all_models and len(working_analysis_models) < 3
            ]
            if missing_api_models and len(working_analysis_models) < 3:
                suggestions["actions"].append(
                    {
                        "type": "enable_api_models",
                        "description": "Enable cloud API models for better performance and reliability",
                        "models": missing_api_models,
                        "commands": [
                            f"Add API key for {model}"
                            for model in missing_api_models[:2]
                        ],
                    }
                )

            # Check for resource optimization opportunities
            if system_resources:
                memory_usage = system_resources.get("memory_percent", 0)
                if memory_usage > 80:
                    suggestions["actions"].append(
                        {
                            "type": "optimize_resources",
                            "description": "System memory usage high - consider model optimization",
                            "commands": [
                                "Consider smaller model variants",
                                "Enable model offloading",
                            ],
                        }
                    )

            # Check for unsuitable models that could be disabled
            unsuitable_models = self._get_unsuitable_models(content_type)
            if unsuitable_models:
                suggestions["actions"].append(
                    {
                        "type": "disable_unsuitable",
                        "description": f"Disable code-focused models for {content_type} tasks",
                        "models": unsuitable_models,
                    }
                )

            return suggestions

        except Exception as e:
            log_error(f"Error generating model management suggestions: {e}")
            return {"actions": [], "priority": "low", "error": str(e)}

    def _get_working_models(self, content_type: str) -> List[str]:
        """Get list of working models for content type."""
        # Simplified version - in full implementation would test model connectivity
        all_models = self.model_manager.list_model_configs()
        return [
            name for name, config in all_models.items() if config.get("enabled", True)
        ]

    def _get_install_commands(self, content_type: str) -> List[str]:
        """Get installation commands for content type."""
        commands = []

        if content_type == "analysis":
            commands.extend(
                ["ollama pull llama3.1:8b-instruct", "ollama pull llama3.2:3b-instruct"]
            )
        elif content_type == "creative":
            commands.extend(["ollama pull llama3.1:8b", "ollama pull mixtral:8x7b"])
        else:
            commands.extend(["ollama pull llama3.2:3b", "ollama pull qwen2:7b"])

        return commands

    def _get_unsuitable_models(self, content_type: str) -> List[str]:
        """Get list of models unsuitable for content type."""
        # Simplified version - would check model characteristics in full implementation
        code_focused_models = ["codellama", "deepseek-coder", "code-llama"]
        all_models = self.model_manager.list_model_configs()

        return [name for name in code_focused_models if name in all_models]

    def _get_system_state(self) -> Dict[str, Any]:
        """Get current system state summary."""
        all_models = self.model_manager.list_model_configs()
        enabled_models = [
            name for name, config in all_models.items() if config.get("enabled", True)
        ]

        return {
            "total_models": len(all_models),
            "enabled_models": len(enabled_models),
            "available_adapters": getattr(
                self.model_manager, "get_available_adapters", lambda: []
            )(),
            "default_adapter": getattr(self.model_manager, "default_adapter", "mock"),
        }
