"""
Token Management - Usage Tracking Component

Extracted from token_manager.py
Handles token usage tracking, statistics, and cost monitoring.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import os
import sys
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
from src.openchronicle.shared.logging_system import (
    log_system_event,
    log_info,
    log_warning,
)

from ..shared import (
    TokenUsageRecord,
    TokenUsageType,
    StatisticsCalculator,
    TokenManagerException,
    CacheManager,
)


class UsageTracker:
    """Tracks token usage across models and sessions."""

    def __init__(self, cache_size: int = 1000):
        self.usage_records: List[TokenUsageRecord] = []
        self.session_stats = {}
        self.model_stats = {}
        self.cache = CacheManager(cache_size)

    def track_token_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        response_tokens: int,
        usage_type: TokenUsageType = TokenUsageType.PROMPT,
        cost: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Track token usage for a specific operation."""
        # Create usage record
        record = TokenUsageRecord(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            usage_type=usage_type,
            metadata=metadata or {},
        )

        # Add cost information
        if cost > 0:
            record.metadata["cost"] = cost

        self.usage_records.append(record)

        # Update model stats
        if model_name not in self.model_stats:
            self.model_stats[model_name] = {
                "prompt_tokens": 0,
                "response_tokens": 0,
                "total_cost": 0.0,
                "requests": 0,
                "first_used": record.timestamp,
                "last_used": record.timestamp,
            }

        stats = self.model_stats[model_name]
        stats["prompt_tokens"] += prompt_tokens
        stats["response_tokens"] += response_tokens
        stats["total_cost"] += cost
        stats["requests"] += 1
        stats["last_used"] = record.timestamp

        # Log usage event
        log_system_event(
            "token_usage",
            f"{model_name}: {prompt_tokens}+{response_tokens} tokens, ${cost:.4f}",
        )

        # Cache recent usage for quick access
        cache_key = f"recent_{model_name}"
        recent_usage = self.cache.get(cache_key) or []
        recent_usage.append(record.to_dict())

        # Keep only last 10 records per model
        if len(recent_usage) > 10:
            recent_usage = recent_usage[-10:]

        self.cache.set(cache_key, recent_usage)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive token usage statistics."""
        if not self.usage_records:
            return {
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_response_tokens": 0,
                "total_cost": 0.0,
                "total_requests": 0,
                "models": {},
                "usage_by_type": {},
                "session_summary": {},
            }

        # Use StatisticsCalculator for detailed stats
        detailed_stats = StatisticsCalculator.calculate_token_stats(self.usage_records)

        # Add model-specific stats
        detailed_stats["models"] = self.model_stats.copy()

        # Add session summary
        detailed_stats["session_summary"] = {
            "start_time": min(
                record.timestamp for record in self.usage_records
            ).isoformat(),
            "end_time": max(
                record.timestamp for record in self.usage_records
            ).isoformat(),
            "duration_minutes": self._calculate_session_duration(),
            "unique_models": len(
                set(record.model_name for record in self.usage_records)
            ),
        }

        return detailed_stats

    def get_model_usage(self, model_name: str) -> Dict[str, Any]:
        """Get usage statistics for a specific model."""
        if model_name not in self.model_stats:
            return {}

        model_records = [r for r in self.usage_records if r.model_name == model_name]
        return StatisticsCalculator.calculate_token_stats(model_records)

    def get_recent_usage(
        self, model_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent usage records for a model."""
        cache_key = f"recent_{model_name}"
        recent = self.cache.get(cache_key) or []
        return recent[-limit:] if len(recent) > limit else recent

    def get_cost_analysis(self) -> Dict[str, Any]:
        """Get detailed cost analysis."""
        total_cost = sum(
            self.model_stats[model]["total_cost"] for model in self.model_stats
        )

        if total_cost == 0:
            return {"total_cost": 0, "cost_by_model": {}, "recommendations": []}

        cost_by_model = {
            model: stats["total_cost"] for model, stats in self.model_stats.items()
        }

        # Sort by cost (highest first)
        sorted_costs = sorted(cost_by_model.items(), key=lambda x: x[1], reverse=True)

        recommendations = []
        if len(sorted_costs) > 1:
            highest_cost_model, highest_cost = sorted_costs[0]
            if highest_cost > total_cost * 0.5:  # If one model is >50% of costs
                recommendations.append(
                    f"Consider reducing usage of {highest_cost_model} (${highest_cost:.4f})"
                )

        return {
            "total_cost": total_cost,
            "cost_by_model": cost_by_model,
            "cost_distribution": [
                (model, cost / total_cost) for model, cost in sorted_costs
            ],
            "recommendations": recommendations,
        }

    def _calculate_session_duration(self) -> float:
        """Calculate session duration in minutes."""
        if len(self.usage_records) < 2:
            return 0.0

        start_time = min(record.timestamp for record in self.usage_records)
        end_time = max(record.timestamp for record in self.usage_records)
        duration = end_time - start_time
        return duration.total_seconds() / 60

    def clear_usage_data(self):
        """Clear all usage data."""
        self.usage_records.clear()
        self.model_stats.clear()
        self.session_stats.clear()
        self.cache.clear()

    def export_usage_data(self) -> Dict[str, Any]:
        """Export all usage data for external analysis."""
        return {
            "usage_records": [record.to_dict() for record in self.usage_records],
            "model_stats": self.model_stats,
            "session_stats": self.session_stats,
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
        }


class CostCalculator:
    """Calculates costs for token usage."""

    def __init__(self):
        # Default cost per 1K tokens (can be overridden with actual pricing)
        self.default_costs = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude": 0.008,
            "claude-instant": 0.0015,
            "groq": 0.0001,
            "ollama": 0.0,  # Local models are free
            "default": 0.01,
        }

    def calculate_cost(
        self,
        model_name: str,
        prompt_tokens: int,
        response_tokens: int,
        custom_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calculate cost for token usage."""
        total_tokens = prompt_tokens + response_tokens

        # Use custom rates if provided, otherwise use defaults
        rates = custom_rates or self.default_costs

        # Get rate for model (fallback to default)
        rate_per_1k = rates.get(model_name.lower(), rates.get("default", 0.01))

        return (total_tokens / 1000) * rate_per_1k

    def estimate_cost(
        self,
        model_name: str,
        estimated_tokens: int,
        custom_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """Estimate cost for estimated token usage."""
        return self.calculate_cost(
            model_name, estimated_tokens // 2, estimated_tokens // 2, custom_rates
        )

    def get_cost_comparison(
        self,
        models: List[str],
        token_count: int,
        custom_rates: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compare costs across multiple models for the same token count."""
        return {
            model: self.estimate_cost(model, token_count, custom_rates)
            for model in models
        }


class UsageRecommender:
    """Provides recommendations based on usage patterns."""

    def __init__(self, usage_tracker: UsageTracker, cost_calculator: CostCalculator):
        self.usage_tracker = usage_tracker
        self.cost_calculator = cost_calculator

    def recommend_model_switch(
        self,
        current_model: str,
        usage_pattern: Dict[str, Any],
        available_models: List[str],
    ) -> Optional[str]:
        """Recommend model switching based on usage patterns."""
        recommendations = []

        if usage_pattern.get("high_cost", False):
            # Recommend cheaper models
            costs = self.cost_calculator.get_cost_comparison(available_models, 1000)
            current_cost = costs.get(current_model, float("inf"))

            cheaper_models = [
                model
                for model, cost in costs.items()
                if cost < current_cost * 0.5 and model != current_model
            ]

            if cheaper_models:
                # Return the cheapest alternative
                cheapest = min(cheaper_models, key=lambda m: costs[m])
                return cheapest

        if usage_pattern.get("frequent_truncation", False):
            # Recommend models with higher token limits (would need model capability data)
            log_warning(
                "Frequent truncation detected - consider upgrading to higher-capacity model"
            )

        if usage_pattern.get("low_usage", False):
            # Recommend cheaper models for light usage
            costs = self.cost_calculator.get_cost_comparison(available_models, 1000)
            cheapest_model = min(costs.items(), key=lambda x: x[1])
            if cheapest_model[0] != current_model:
                return cheapest_model[0]

        return None

    def get_optimization_suggestions(self) -> List[str]:
        """Get general optimization suggestions based on usage history."""
        stats = self.usage_tracker.get_usage_stats()
        suggestions = []

        if stats["total_cost"] > 10.0:  # If spending more than $10
            suggestions.append("Consider optimizing prompt length to reduce costs")

        if len(stats["models"]) > 3:  # Using many different models
            suggestions.append("Consider standardizing on fewer models for consistency")

        # Check for inefficient patterns
        cost_analysis = self.usage_tracker.get_cost_analysis()
        if cost_analysis["recommendations"]:
            suggestions.extend(cost_analysis["recommendations"])

        return suggestions
