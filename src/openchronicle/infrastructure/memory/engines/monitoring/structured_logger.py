"""
Structured Logger

Structured logging for production monitoring.
Extracted from production_monitoring.py for better modularity.
"""

import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...cache_orchestrator import DistributedMultiTierCache


class StructuredLogger:
    """Structured logging for production monitoring."""

    def __init__(self, cache: "DistributedMultiTierCache"):
        self.cache = cache
        self.logger = logging.getLogger("openchronicle.cache.structured")

        # Setup structured logging format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create file handler for cache events
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(log_dir / "cache_events.jsonl")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

    def log_cache_event(self, event_type: str, details: dict[str, Any]):
        """Log structured cache event."""
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "details": details,
            "source": "openchronicle_cache",
        }

        self.logger.info(json.dumps(event))

    def log_performance_metrics(self, metrics: dict[str, Any]):
        """Log performance metrics as structured event."""
        self.log_cache_event(
            "performance_metrics",
            {
                "hit_rate": metrics.get("overall_hit_rate", 0),
                "response_time_ms": metrics.get("avg_redis_response_ms", 0),
                "operations": metrics.get("total_operations", 0),
                "uptime_seconds": metrics.get("uptime_seconds", 0),
                "cluster_nodes": len(metrics.get("cluster_nodes", {})),
                "partitions": len(metrics.get("partitions", {})),
            },
        )

    def log_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] = None,
    ):
        """Log performance alert."""
        self.log_cache_event(
            "performance_alert",
            {
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "details": details or {},
            },
        )

    def log_cache_warming(self, story_ids: list[str], results: dict[str, Any]):
        """Log cache warming operation."""
        self.log_cache_event(
            "cache_warming",
            {"story_count": len(story_ids), "story_ids": story_ids, "results": results},
        )
