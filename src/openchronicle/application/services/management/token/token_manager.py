"""
Token Management System - Main Orchestrator

Modernized token management system that integrates all token components.
Provides unified API for tokenization, optimization, and usage tracking.
"""

from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event


from ..shared import ConfigValidator
from ..shared import TokenManagerConfig
from ..shared import TokenManagerException
from ..shared import TokenUsageType
from .token_optimizer import ContextTrimmer
from .token_optimizer import ModelSelector
from .token_optimizer import TruncationDetector
from .tokenizer_manager import TokenEstimator
from .tokenizer_manager import TokenizerManager
from .usage_tracker import CostCalculator
from .usage_tracker import UsageRecommender
from .usage_tracker import UsageTracker


class TokenManager:
    """
    Unified token management system.

    Integrates tokenization, optimization, and usage tracking into a single API.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the token management system."""
        try:
            # Validate and set configuration
            validated_config = ConfigValidator.validate_token_config(config or {})
            self.config = TokenManagerConfig.from_dict(validated_config)

            # Initialize components
            self.tokenizer = TokenizerManager(
                default_model=self.config.default_model,
                cache_size=self.config.cache_size,
            )

            self.estimator = TokenEstimator(tokenizer_manager=self.tokenizer)

            self.optimizer = ModelSelector(
                model_manager=None,  # Will need to be provided later
                tokenizer_manager=self.tokenizer,
            )

            self.trimmer = ContextTrimmer(tokenizer_manager=self.tokenizer)

            self.truncation_detector = TruncationDetector()

            self.usage_tracker = UsageTracker(cache_size=self.config.cache_size)

            self.cost_calculator = CostCalculator()
            self.recommender = UsageRecommender(
                self.usage_tracker, self.cost_calculator
            )

            # Initialize model registry
            self.model_configs = self.config.model_configs

            log_system_event("token_system", "Token management system initialized")

        except Exception as e:
            log_error(f"Failed to initialize TokenManager: {e}")
            raise TokenManagerException(f"Initialization failed: {e}")

    # =====================================================================
    # TOKENIZATION INTERFACE
    # =====================================================================

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens in text for specified model."""
        model = model or self.config.default_model
        return self.tokenizer.estimate_tokens(text, model)

    def estimate_tokens(self, text: str, model: str | None = None) -> int:
        """Estimate tokens with padding factor."""
        model = model or self.config.default_model
        return self.tokenizer.estimate_tokens(text, model)

    def tokenize_text(self, text: str, model: str | None = None) -> list[int]:
        """Tokenize text into token IDs."""
        model = model or self.config.default_model
        return self.tokenizer.tokenize(text, model)

    def detokenize_text(self, tokens: list[int], model: str | None = None) -> str:
        """Convert token IDs back to text."""
        model = model or self.config.default_model
        return self.tokenizer.detokenize(tokens, model)

    # =====================================================================
    # OPTIMIZATION INTERFACE
    # =====================================================================

    def select_optimal_model(
        self, text: str, requirements: dict[str, Any] | None = None
    ) -> str:
        """Select the optimal model for given text and requirements."""
        token_count = self.count_tokens(text)
        return self.optimizer.select_optimal_model(token_count, requirements or {})

    def trim_context(
        self,
        text: str,
        max_tokens: int,
        model: str | None = None,
        strategy: str = "truncate_middle",
    ) -> str:
        """Trim context to fit within token limit."""
        model = model or self.config.default_model
        return self.trimmer.trim_context(text, max_tokens, model, strategy)

    def check_truncation_risk(
        self, text: str, model: str | None = None
    ) -> dict[str, Any]:
        """Check if text might be truncated by model."""
        model = model or self.config.default_model
        return self.truncation_detector.check_truncation_risk(text, model)

    def split_text_for_model(
        self, text: str, model: str | None = None, chunk_size: int | None = None
    ) -> list[str]:
        """Split text into chunks that fit model limits."""
        model = model or self.config.default_model
        if chunk_size is None:
            model_config = self.model_configs.get(model, {})
            chunk_size = (
                model_config.get("max_tokens", 4096) - self.config.safety_margin
            )

        return self.trimmer.split_text(text, chunk_size, model)

    # =====================================================================
    # USAGE TRACKING INTERFACE
    # =====================================================================

    def track_token_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        response_tokens: int,
        usage_type: TokenUsageType = TokenUsageType.PROMPT,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Track token usage for analytics."""
        # Calculate cost if not provided
        if cost is None:
            cost = self.cost_calculator.calculate_cost(
                model_name, prompt_tokens, response_tokens
            )

        self.usage_tracker.track_token_usage(
            model_name, prompt_tokens, response_tokens, usage_type, cost, metadata
        )

    def get_usage_stats(self) -> dict[str, Any]:
        """Get comprehensive usage statistics."""
        return self.usage_tracker.get_usage_stats()

    def get_model_usage(self, model_name: str) -> dict[str, Any]:
        """Get usage statistics for a specific model."""
        return self.usage_tracker.get_model_usage(model_name)

    def get_cost_analysis(self) -> dict[str, Any]:
        """Get detailed cost analysis."""
        return self.usage_tracker.get_cost_analysis()

    def recommend_model_switch(
        self, current_model: str, usage_pattern: dict[str, Any] | None = None
    ) -> str | None:
        """Get model switch recommendations."""
        pattern = usage_pattern or self._analyze_usage_pattern(current_model)
        return self.recommender.recommend_model_switch(
            current_model, pattern, self.config.available_models
        )

    # =====================================================================
    # UTILITY METHODS
    # =====================================================================

    def validate_model_choice(self, model: str, text: str) -> dict[str, Any]:
        """Validate if model choice is appropriate for given text."""
        token_count = self.count_tokens(text, model)
        model_config = self.model_configs.get(model, {})
        max_tokens = model_config.get("max_tokens", 4096)

        validation = {
            "is_valid": token_count <= max_tokens,
            "token_count": token_count,
            "max_tokens": max_tokens,
            "utilization": token_count / max_tokens if max_tokens > 0 else 0,
            "recommended_action": "none",
        }

        if not validation["is_valid"]:
            validation["recommended_action"] = "trim_or_split"
        elif validation["utilization"] > 0.9:
            validation["recommended_action"] = "consider_splitting"

        return validation

    def get_model_capabilities(self, model: str) -> dict[str, Any]:
        """Get capabilities and limits for a specific model."""
        return self.model_configs.get(
            model,
            {
                "max_tokens": 4096,
                "cost_per_1k": 0.01,
                "supports_function_calling": False,
                "context_length": 4096,
            },
        )

    def optimize_for_cost(self, text: str, max_cost: float) -> dict[str, Any]:
        """Find the most cost-effective model for given text."""
        token_count = self.estimate_tokens(text)

        # Check costs for all available models
        costs = self.cost_calculator.get_cost_comparison(
            self.config.available_models, token_count
        )

        # Filter models under budget
        affordable_models = [model for model, cost in costs.items() if cost <= max_cost]

        if not affordable_models:
            return {
                "success": False,
                "message": f"No models available under ${max_cost:.4f} budget",
                "cheapest_option": min(costs.items(), key=lambda x: x[1]),
            }

        # Select the best affordable model (cheapest that can handle the text)
        best_model = min(affordable_models, key=lambda m: costs[m])

        return {
            "success": True,
            "recommended_model": best_model,
            "estimated_cost": costs[best_model],
            "token_count": token_count,
            "alternatives": [
                (m, costs[m]) for m in affordable_models if m != best_model
            ],
        }

    def _analyze_usage_pattern(self, model: str) -> dict[str, Any]:
        """Analyze usage patterns for a model."""
        model_stats = self.usage_tracker.get_model_usage(model)

        if not model_stats:
            return {"low_usage": True}

        # Analyze patterns
        total_cost = model_stats.get("total_cost", 0)
        avg_tokens = model_stats.get("average_tokens", 0)

        pattern = {
            "high_cost": total_cost > 5.0,  # More than $5
            "low_usage": model_stats.get("requests", 0) < 10,
            "frequent_truncation": False,  # Would need truncation tracking
            "high_token_usage": avg_tokens > 2000,
        }

        return pattern

    # Convenience alias methods (no legacy guarantee)
    def get_token_count(self, text: str, model: str = None) -> int:
        return self.count_tokens(text, model)

    def get_optimal_model(self, text: str) -> str:
        return self.select_optimal_model(text)

    def trim_to_limit(self, text: str, limit: int, model: str = None) -> str:
        return self.trim_context(text, limit, model)

    # =====================================================================
    # SYSTEM MANAGEMENT
    # =====================================================================

    def clear_caches(self):
        """Clear all internal caches."""
        self.tokenizer.clear_cache()
        self.usage_tracker.clear_usage_data()
        log_system_event("token_system", "Caches cleared")

    def export_stats(self) -> dict[str, Any]:
        """Export all statistics and usage data."""
        return {
            "usage_data": self.usage_tracker.export_usage_data(),
            "model_configs": self.model_configs,
            "system_config": self.config.to_dict(),
            "cache_stats": {
                "tokenizer_cache_size": len(self.tokenizer.cache.cache),
                "usage_cache_size": len(self.usage_tracker.cache.cache),
            },
        }

    def update_config(self, new_config: dict[str, Any]):
        """Update system configuration."""
        try:
            validated_config = ConfigValidator.validate_token_config(new_config)
            self.config = TokenManagerConfig.from_dict(
                {**self.config.to_dict(), **validated_config}
            )
            log_system_event("token_system", "Configuration updated")
        except Exception as e:
            log_error(f"Failed to update config: {e}")
            raise TokenManagerException(f"Config update failed: {e}")
