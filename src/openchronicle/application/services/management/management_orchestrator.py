"""
Management Systems Orchestrator

Unified management system that integrates token and bookmark management.
Provides a single entry point for all management operations.
"""

from datetime import datetime
from typing import Any

from openchronicle.shared.logging_system import log_error, log_info, log_system_event

from .bookmark import BookmarkManager
from .shared import ConfigValidator
from .shared import ManagementConfig
from .token import TokenManager


class ManagementOrchestrator:
    """
    Unified management orchestrator for OpenChronicle Core.

    Integrates token management and bookmark management into a single API.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the management orchestrator."""
        try:
            # Validate and set configuration
            validated_config = ConfigValidator.validate_management_config(config or {})
            self.config = ManagementConfig.from_dict(validated_config)

            # Initialize token management
            self.token_manager = TokenManager(self.config.token_config)

            # Initialize bookmark managers (per story)
            self.bookmark_managers: dict[str, BookmarkManager] = {}

            log_system_event(
                "management_orchestrator", "Management orchestrator initialized"
            )

        except Exception as e:
            log_error(f"Failed to initialize ManagementOrchestrator: {e}")
            raise Exception(f"Management orchestrator initialization failed: {e}")

    # =====================================================================
    # TOKEN MANAGEMENT INTERFACE
    # =====================================================================

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens in text for specified model."""
        return self.token_manager.count_tokens(text, model)

    def estimate_tokens(self, text: str, model: str | None = None) -> int:
        """Estimate tokens with padding factor."""
        return self.token_manager.estimate_tokens(text, model)

    def select_optimal_model(
        self, text: str, requirements: dict[str, Any] | None = None
    ) -> str:
        """Select the optimal model for given text and requirements."""
        return self.token_manager.select_optimal_model(text, requirements)

    def trim_context(
        self,
        text: str,
        max_tokens: int,
        model: str | None = None,
        strategy: str = "truncate_middle",
    ) -> str:
        """Trim context to fit within token limit."""
        return self.token_manager.trim_context(text, max_tokens, model, strategy)

    def track_token_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        response_tokens: int,
        usage_type=None,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Track token usage for analytics."""
        return self.token_manager.track_token_usage(
            model_name, prompt_tokens, response_tokens, usage_type, cost, metadata
        )

    def get_token_usage_stats(self) -> dict[str, Any]:
        """Get comprehensive token usage statistics."""
        return self.token_manager.get_usage_stats()

    def get_token_cost_analysis(self) -> dict[str, Any]:
        """Get detailed token cost analysis."""
        return self.token_manager.get_cost_analysis()

    def recommend_model_switch(
        self, current_model: str, usage_pattern: dict[str, Any] | None = None
    ) -> str | None:
        """Get model switch recommendations."""
        return self.token_manager.recommend_model_switch(current_model, usage_pattern)

    def optimize_token_usage(
        self, text: str, model: str | None = None
    ) -> dict[str, Any]:
        """Optimize token usage for given text."""
        if model is None:
            model = self.select_optimal_model(text)

        original_tokens = self.estimate_tokens(text, model)

        # Try to optimize by trimming if text is very long
        max_tokens = 4096  # Default reasonable limit
        if original_tokens > max_tokens:
            optimized_text = self.trim_context(text, max_tokens, model)
            optimized_tokens = self.estimate_tokens(optimized_text, model)

            return {
                "optimized_text": optimized_text,
                "original_tokens": original_tokens,
                "optimized_tokens": optimized_tokens,
                "tokens_saved": original_tokens - optimized_tokens,
                "model_used": model,
                "optimization_applied": True,
            }

        return {
            "optimized_text": text,
            "original_tokens": original_tokens,
            "optimized_tokens": original_tokens,
            "tokens_saved": 0,
            "model_used": model,
            "optimization_applied": False,
        }

    # =====================================================================
    # BOOKMARK MANAGEMENT INTERFACE
    # =====================================================================

    def get_bookmark_manager(self, story_id: str) -> BookmarkManager:
        """Get or create bookmark manager for a story."""
        if story_id not in self.bookmark_managers:
            self.bookmark_managers[story_id] = BookmarkManager(
                story_id, self.config.bookmark_config
            )
        return self.bookmark_managers[story_id]

    def create_bookmark(
        self,
        story_id: str,
        scene_id: str,
        label: str,
        description: str | None = None,
        bookmark_type: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Create a new bookmark."""
        manager = self.get_bookmark_manager(story_id)
        return manager.create_bookmark(
            scene_id, label, description, bookmark_type, metadata
        )

    def organize_bookmarks_by_category(
        self, story_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Organize bookmarks by category for better management."""
        manager = self.get_bookmark_manager(story_id)
        all_bookmarks = manager.list_bookmarks(
            limit=1000
        )  # Get all bookmarks with large limit

        # Organize by bookmark type (category)
        organized = {}
        for bookmark in all_bookmarks:
            bookmark_type = bookmark.get("type", "user")
            if bookmark_type not in organized:
                organized[bookmark_type] = []
            organized[bookmark_type].append(bookmark)

        # Sort each category by creation date (newest first)
        for category in organized:
            organized[category].sort(
                key=lambda x: x.get("created_at", ""), reverse=True
            )

        log_info(
            f"Organized {len(all_bookmarks)} bookmarks into {len(organized)} categories for story {story_id}"
        )
        return organized

    def get_bookmark(self, story_id: str, bookmark_id: int) -> dict[str, Any] | None:
        """Get a bookmark by ID."""
        manager = self.get_bookmark_manager(story_id)
        return manager.get_bookmark(bookmark_id)

    def list_bookmarks(
        self,
        story_id: str,
        bookmark_type: str | None = None,
        scene_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List bookmarks with optional filtering."""
        manager = self.get_bookmark_manager(story_id)
        return manager.list_bookmarks(bookmark_type, scene_id, limit)

    def search_bookmarks(
        self,
        story_id: str,
        query: str,
        bookmark_type: str | None = None,
        search_fields: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search bookmarks by label or description."""
        manager = self.get_bookmark_manager(story_id)
        return manager.search_bookmarks(query, bookmark_type, search_fields, limit)

    def get_chapter_structure(self, story_id: str) -> dict[int, list[dict[str, Any]]]:
        """Get chapter structure from bookmarks organized by levels."""
        manager = self.get_bookmark_manager(story_id)
        return manager.get_chapter_structure()

    def auto_create_chapter_bookmark(
        self, story_id: str, scene_id: str, chapter_title: str, chapter_level: int = 1
    ) -> int:
        """Automatically create a chapter bookmark."""
        manager = self.get_bookmark_manager(story_id)
        return manager.auto_create_chapter_bookmark(
            scene_id, chapter_title, chapter_level
        )


    # =====================================================================
    # UNIFIED OPERATIONS
    # =====================================================================

    def analyze_story_content(
        self, story_id: str, content: str, model: str | None = None
    ) -> dict[str, Any]:
        """Analyze story content using both token and bookmark insights."""
        try:
            # Token analysis
            token_count = self.count_tokens(content, model)
            optimal_model = self.select_optimal_model(content)

            # Bookmark analysis
            manager = self.get_bookmark_manager(story_id)
            bookmarks = manager.list_bookmarks(limit=100)
            chapter_structure = manager.get_chapter_structure()

            analysis = {
                "content_analysis": {
                    "token_count": token_count,
                    "optimal_model": optimal_model,
                    "estimated_cost": self.token_manager.cost_calculator.estimate_cost(
                        optimal_model, token_count
                    ),
                    "content_length": len(content),
                    "complexity_score": self._calculate_complexity_score(
                        content, token_count
                    ),
                },
                "bookmark_analysis": {
                    "total_bookmarks": len(bookmarks),
                    "chapter_count": sum(
                        len(chapters) for chapters in chapter_structure.values()
                    ),
                    "chapter_levels": len(chapter_structure),
                    "recent_bookmarks": bookmarks[:5] if bookmarks else [],
                },
                "recommendations": self._generate_content_recommendations(
                    content, token_count, bookmarks
                ),
            }

            return analysis

        except Exception as e:
            log_error(f"Story content analysis failed: {e}")
            return {"error": str(e)}

    def optimize_story_navigation(self, story_id: str) -> dict[str, Any]:
        """Optimize story navigation structure."""
        try:
            manager = self.get_bookmark_manager(story_id)

            # Get current structure
            timeline = manager.get_timeline_bookmarks()
            chapters = manager.get_chapter_structure()

            # Analyze gaps and opportunities
            optimization = {
                "current_structure": {
                    "timeline_length": len(timeline),
                    "chapter_count": sum(
                        len(level_chapters) for level_chapters in chapters.values()
                    ),
                    "chapter_levels": len(chapters),
                },
                "recommendations": [],
                "auto_improvements": [],
            }

            # Check for missing chapter markers
            if len(timeline) > 20 and len(chapters.get(1, [])) < 3:
                optimization["recommendations"].append(
                    "Consider adding more chapter bookmarks for better navigation"
                )

            # Check for uneven chapter distribution
            if timeline:
                scenes_per_chapter = len(timeline) / max(len(chapters.get(1, [])), 1)
                if scenes_per_chapter > 15:
                    optimization["recommendations"].append(
                        "Chapters may be too long - consider subdividing"
                    )

            return optimization

        except Exception as e:
            log_error(f"Story navigation optimization failed: {e}")
            return {"error": str(e)}

    def get_management_stats(self) -> dict[str, Any]:
        """Get comprehensive management system statistics."""
        try:
            # Token stats
            token_stats = self.get_token_usage_stats()

            # Bookmark stats for all managed stories
            bookmark_stats = {}
            total_bookmarks = 0

            for story_id, manager in self.bookmark_managers.items():
                stats = manager.get_stats()
                bookmark_stats[story_id] = stats
                total_bookmarks += stats.get("total_bookmarks", 0)

            return {
                "token_management": {
                    "total_requests": token_stats.get("total_requests", 0),
                    "total_tokens": token_stats.get("total_tokens", 0),
                    "total_cost": token_stats.get("total_cost", 0),
                    "active_models": len(token_stats.get("models", {})),
                },
                "bookmark_management": {
                    "managed_stories": len(self.bookmark_managers),
                    "total_bookmarks": total_bookmarks,
                    "story_stats": bookmark_stats,
                },
                "system_health": {
                    "token_cache_size": len(self.token_manager.tokenizer.cache.cache),
                    "bookmark_managers_active": len(self.bookmark_managers),
                },
            }

        except Exception as e:
            log_error(f"Management stats collection failed: {e}")
            return {"error": str(e)}

    def _calculate_complexity_score(self, content: str, token_count: int) -> float:
        """Calculate content complexity score."""
        # Simple complexity based on token density and structure
        words = len(content.split())
        if words == 0:
            return 0.0

        token_per_word = token_count / words
        sentence_count = content.count(".") + content.count("!") + content.count("?")
        avg_sentence_length = words / max(sentence_count, 1)

        # Normalize to 0-1 scale
        complexity = min(1.0, (token_per_word * 0.5) + (avg_sentence_length / 50))
        return complexity

    def _generate_content_recommendations(
        self, content: str, token_count: int, bookmarks: list[dict[str, Any]]
    ) -> list[str]:
        """Generate recommendations based on content and bookmark analysis."""
        recommendations = []

        # Token-based recommendations
        if token_count > 4000:
            recommendations.append(
                "Consider splitting content into smaller sections for better processing"
            )

        if token_count < 100:
            recommendations.append(
                "Content may be too brief for comprehensive analysis"
            )

        # Bookmark-based recommendations
        if len(bookmarks) == 0:
            recommendations.append("Consider adding bookmarks to improve navigation")

        chapter_bookmarks = [
            b for b in bookmarks if b.get("bookmark_type") == "chapter"
        ]
        if len(bookmarks) > 10 and len(chapter_bookmarks) == 0:
            recommendations.append(
                "Add chapter bookmarks to organize your story structure"
            )

        return recommendations

    # =====================================================================
    # SYSTEM MANAGEMENT
    # =====================================================================

    def clear_all_caches(self):
        """Clear all system caches."""
        self.token_manager.clear_caches()
        log_system_event("management_orchestrator", "All caches cleared")

    def export_all_data(self) -> dict[str, Any]:
        """Export all management data."""
        try:
            # Export token data
            token_data = self.token_manager.export_stats()

            # Export bookmark data for all stories
            bookmark_data = {}
            for story_id, manager in self.bookmark_managers.items():
                bookmark_data[story_id] = manager.export_bookmarks()

            return {
                "export_type": "management_orchestrator",
                "token_management": token_data,
                "bookmark_management": bookmark_data,
                "system_config": self.config.to_dict(),
            }

        except Exception as e:
            log_error(f"Data export failed: {e}")
            raise Exception(f"Export failed: {e}")

    def update_config(self, new_config: dict[str, Any]):
        """Update system configuration."""
        try:
            validated_config = ConfigValidator.validate_management_config(new_config)
            self.config = ManagementConfig.from_dict(
                {**self.config.to_dict(), **validated_config}
            )

            # Update token manager config if provided
            if "token_config" in new_config:
                self.token_manager.update_config(new_config["token_config"])

            log_system_event("management_orchestrator", "Configuration updated")

        except Exception as e:
            log_error(f"Config update failed: {e}")
            raise Exception(f"Config update failed: {e}")

    def get_management_performance_metrics(self) -> dict[str, Any]:
        """Get comprehensive performance metrics for management systems."""
        try:
            # Token management metrics
            token_stats = self.get_token_usage_stats()
            token_cost = self.get_token_cost_analysis()

            # Bookmark management metrics
            bookmark_metrics = {}
            for story_id, manager in self.bookmark_managers.items():
                try:
                    stats = manager.get_stats()
                    bookmark_metrics[story_id] = {
                        "total_bookmarks": stats.get("total_bookmarks", 0),
                        "bookmark_types": stats.get("bookmark_types", {}),
                        "recent_activity": stats.get("recent_activity", 0),
                    }
                except Exception as e:
                    log_error(f"Failed to get bookmark stats for {story_id}: {e}")
                    bookmark_metrics[story_id] = {"error": str(e)}

            # System performance
            performance_metrics = {
                "token_management": {
                    "total_tokens_processed": token_stats.get("total_tokens", 0),
                    "total_cost": token_cost.get("total_cost", 0.0),
                    "models_used": len(token_stats.get("model_usage", {})),
                    "average_tokens_per_request": token_stats.get(
                        "average_tokens_per_request", 0
                    ),
                },
                "bookmark_management": {
                    "active_stories": len(self.bookmark_managers),
                    "story_metrics": bookmark_metrics,
                    "total_bookmarks_across_stories": sum(
                        metrics.get("total_bookmarks", 0)
                        for metrics in bookmark_metrics.values()
                        if isinstance(metrics, dict) and "total_bookmarks" in metrics
                    ),
                },
                "system_health": {
                    "uptime_status": "operational",
                    "last_updated": str(datetime.now()),
                    "memory_usage": "normal",  # Could be enhanced with actual memory monitoring
                },
            }

            log_info("Generated management performance metrics")
            return performance_metrics

        except Exception as e:
            log_error(f"Failed to generate performance metrics: {e}")
            return {
                "error": str(e),
                "status": "failed",
                "timestamp": str(datetime.now()),
            }
