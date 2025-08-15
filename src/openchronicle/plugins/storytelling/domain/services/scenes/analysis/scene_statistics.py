"""
Scene Statistics - Scene statistics and analytics

Provides comprehensive statistics and analytics for scenes:
- Token usage analysis
- Scene length statistics
- Performance metrics
- Content analysis
"""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Optional

from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.shared.logging_system import log_error_with_context


class SceneStatistics:
    """Handles scene statistics and analytics."""

    def __init__(self, story_id: str, persistence_port: Optional[IPersistencePort] = None):
        """Initialize statistics for a specific story.

        Args:
            story_id: Story identifier
        """
        self.story_id = story_id
        self.persistence = persistence_port

    def get_scenes_with_long_turns(self) -> list[dict[str, Any]]:
        """Return scenes with unusually long user inputs or model outputs."""
        try:
            if not self.persistence:
                return []
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_id, timestamp, input, output, scene_label, structured_tags,
                       LENGTH(input) as input_length,
                       LENGTH(output) as output_length
                FROM scenes
                WHERE LENGTH(input) > 2000 OR LENGTH(output) > 2000
                ORDER BY timestamp DESC
            """,
            )

            results: list[dict[str, Any]] = []
            for row in rows:
                scene_data: dict[str, Any] = {
                    "scene_id": row["scene_id"],
                    "timestamp": row["timestamp"],
                    "scene_label": row.get("scene_label"),
                    "input_length": row["input_length"],
                    "output_length": row["output_length"],
                    "total_length": row["input_length"] + row["output_length"],
                    "input_preview": (
                        row["input"][:200] + "..." if len(row["input"]) > 200 else row["input"]
                    ),
                    "output_preview": (
                        row["output"][:200] + "..." if len(row["output"]) > 200 else row["output"]
                    ),
                }

                if row.get("structured_tags"):
                    try:
                        tags = json.loads(row["structured_tags"])
                        scene_data["tokens_used"] = tags.get("tokens_used", 0)
                        scene_data["model_used"] = tags.get("model_used", "unknown")
                    except (json.JSONDecodeError, TypeError):
                        pass

                results.append(scene_data)

        except Exception as e:  # noqa: BLE001 - broad for telemetry safety at boundary
            log_error_with_context(e, {"operation": "get_scenes_with_long_turns", "story_id": self.story_id})
            return []
        else:
            return results

    def get_token_usage_stats(self) -> dict[str, Any]:
        """Return comprehensive token usage statistics."""
        try:
            if not self.persistence:
                return {
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "total_scenes_with_tokens": 0,
                    "average_tokens_per_scene": 0.0,
                    "model_breakdown": {},
                    "daily_usage": {},
                }
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT structured_tags, timestamp
                FROM scenes
                WHERE structured_tags IS NOT NULL
                ORDER BY timestamp DESC
            """,
            )

            total_tokens = 0
            total_cost = 0.0
            model_usage: dict[str, dict[str, Any]] = {}
            daily_usage: dict[str, dict[str, int]] = {}
            scene_count = 0

            for row in rows:
                try:
                    tags = json.loads(row["structured_tags"])
                    tokens = tags.get("tokens_used", 0)
                    cost = tags.get("token_cost", 0.0)
                    model = tags.get("model_used", "unknown")

                    if tokens > 0:
                        total_tokens += tokens
                        total_cost += cost
                        scene_count += 1

                        if model in model_usage:
                            model_usage[model]["tokens"] += tokens
                            model_usage[model]["scenes"] += 1
                            model_usage[model]["cost"] += cost
                        else:
                            model_usage[model] = {"tokens": tokens, "scenes": 1, "cost": cost}

                        if row["timestamp"]:
                            date = row["timestamp"][:10]
                            if date in daily_usage:
                                daily_usage[date]["tokens"] += tokens
                                daily_usage[date]["scenes"] += 1
                            else:
                                daily_usage[date] = {"tokens": tokens, "scenes": 1}

                except (json.JSONDecodeError, TypeError, KeyError):
                    continue

            avg_tokens_per_scene = total_tokens / scene_count if scene_count > 0 else 0

            return {
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "total_scenes_with_tokens": scene_count,
                "average_tokens_per_scene": round(avg_tokens_per_scene, 2),
                "model_breakdown": model_usage,
                "daily_usage": daily_usage,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:  # noqa: BLE001
            log_error_with_context(e, {"operation": "get_token_usage_stats", "story_id": self.story_id})
            return {
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_scenes_with_tokens": 0,
                "average_tokens_per_scene": 0.0,
                "model_breakdown": {},
                "daily_usage": {},
                "error": str(e),
            }

    def get_scene_summary_stats(self) -> dict[str, Any]:
        """Return comprehensive scene statistics."""
        try:
            if not self.persistence:
                return {"error": "No persistence configured"}
            basic_stats = self.persistence.execute_query(
                self.story_id,
                """
                SELECT
                    COUNT(*) as total_scenes,
                    COUNT(scene_label) as labeled_scenes,
                    COUNT(analysis) as scenes_with_analysis,
                    AVG(LENGTH(input)) as avg_input_length,
                    AVG(LENGTH(output)) as avg_output_length,
                    MAX(LENGTH(input)) as max_input_length,
                    MAX(LENGTH(output)) as max_output_length,
                    MIN(timestamp) as first_scene_time,
                    MAX(timestamp) as last_scene_time
                FROM scenes
            """,
            )

            if not basic_stats:
                return {"error": "No scenes found"}

            stats = basic_stats[0]

            label_stats = self.persistence.execute_query(
                self.story_id,
                """
                SELECT scene_label, COUNT(*) as count
                FROM scenes
                WHERE scene_label IS NOT NULL
                GROUP BY scene_label
                ORDER BY count DESC
            """,
            )

            recent_cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            recent_stats = self.persistence.execute_query(
                self.story_id,
                """
                SELECT COUNT(*) as recent_scenes
                FROM scenes
                WHERE timestamp > ?
            """,
                (recent_cutoff,),
            )

            return {
                "total_scenes": stats["total_scenes"],
                "labeled_scenes": stats["labeled_scenes"],
                "scenes_with_analysis": stats["scenes_with_analysis"],
                "labeling_percentage": (
                    round((stats["labeled_scenes"] / stats["total_scenes"]) * 100, 1)
                    if stats["total_scenes"] > 0
                    else 0
                ),
                "analysis_percentage": (
                    round((stats["scenes_with_analysis"] / stats["total_scenes"]) * 100, 1)
                    if stats["total_scenes"] > 0
                    else 0
                ),
                "average_input_length": round(stats["avg_input_length"], 1) if stats["avg_input_length"] else 0,
                "average_output_length": round(stats["avg_output_length"], 1) if stats["avg_output_length"] else 0,
                "max_input_length": stats["max_input_length"] or 0,
                "max_output_length": stats["max_output_length"] or 0,
                "first_scene_time": stats["first_scene_time"],
                "last_scene_time": stats["last_scene_time"],
                "recent_scenes_7_days": (recent_stats[0]["recent_scenes"] if recent_stats else 0),
                "label_distribution": {row["scene_label"]: row["count"] for row in label_stats},
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:  # noqa: BLE001
            log_error_with_context(e, {"operation": "get_scene_summary_stats", "story_id": self.story_id})
            return {"error": str(e)}

    def get_content_length_distribution(self) -> dict[str, Any]:
        """Return distribution of content lengths across scenes."""
        try:
            if not self.persistence:
                return {"error": "No persistence configured"}
            rows = self.persistence.execute_query(
                self.story_id,
                """
                SELECT
                    LENGTH(input) as input_length,
                    LENGTH(output) as output_length,
                    LENGTH(input) + LENGTH(output) as total_length
                FROM scenes
                ORDER BY total_length
            """,
            )

            if not rows:
                return {"error": "No scenes found"}

            short_scenes = 0
            medium_scenes = 0
            long_scenes = 0
            very_long_scenes = 0

            input_lengths: list[int] = []
            output_lengths: list[int] = []
            total_lengths: list[int] = []

            for row in rows:
                input_len = row["input_length"]
                output_len = row["output_length"]
                total_len = row["total_length"]

                input_lengths.append(input_len)
                output_lengths.append(output_len)
                total_lengths.append(total_len)

                if total_len < 500:
                    short_scenes += 1
                elif total_len < 2000:
                    medium_scenes += 1
                elif total_len < 5000:
                    long_scenes += 1
                else:
                    very_long_scenes += 1

            total_scenes = len(rows)

            def pct(x: int) -> float:
                return round((x / total_scenes) * 100, 1) if total_scenes else 0.0

            return {
                "total_scenes": total_scenes,
                "length_categories": {
                    "short_scenes": {"count": short_scenes, "percentage": pct(short_scenes)},
                    "medium_scenes": {"count": medium_scenes, "percentage": pct(medium_scenes)},
                    "long_scenes": {"count": long_scenes, "percentage": pct(long_scenes)},
                    "very_long_scenes": {"count": very_long_scenes, "percentage": pct(very_long_scenes)},
                },
                "length_statistics": {
                    "median_input_length": (sorted(input_lengths)[total_scenes // 2] if total_scenes > 0 else 0),
                    "median_output_length": (sorted(output_lengths)[total_scenes // 2] if total_scenes > 0 else 0),
                    "median_total_length": (sorted(total_lengths)[total_scenes // 2] if total_scenes > 0 else 0),
                    "max_total_length": max(total_lengths) if total_lengths else 0,
                    "min_total_length": min(total_lengths) if total_lengths else 0,
                },
            }

        except Exception as e:  # noqa: BLE001
            log_error_with_context(e, {"operation": "get_content_length_distribution", "story_id": self.story_id})
            return {"error": str(e)}

    def get_status(self) -> str:
        """Return statistics engine status string."""
        try:
            stats = self.get_scene_summary_stats()
            if "error" in stats:
                return "error"
            return f"active ({stats['total_scenes']} scenes analyzed)"
        except Exception as e:  # noqa: BLE001
            log_error_with_context(e, {"operation": "get_status", "story_id": self.story_id})
            return "error"
