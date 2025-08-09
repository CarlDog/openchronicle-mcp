"""
Management Systems - Shared Utilities

Consolidates common utility functions from token_manager.py and bookmark_manager.py
providing unified operations for statistics, caching, and data formatting.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable
import json

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
from core.shared.logging_system import log_system_event, log_info, log_warning, log_error

from .management_models import TokenUsageRecord, BookmarkRecord, TokenUsageType


class StatisticsCalculator:
    """Calculates statistics for management systems."""
    
    @staticmethod
    def calculate_token_stats(usage_records: List[TokenUsageRecord]) -> Dict[str, Any]:
        """Calculate comprehensive token usage statistics."""
        if not usage_records:
            return {
                'total_tokens': 0,
                'total_prompt_tokens': 0,
                'total_response_tokens': 0,
                'average_tokens_per_request': 0,
                'models_used': [],
                'usage_by_model': {},
                'usage_by_type': {},
                'cost_estimation': 0.0,
                'peak_usage_period': None
            }
        
        total_tokens = sum(record.total_tokens() for record in usage_records)
        total_prompt_tokens = sum(record.prompt_tokens for record in usage_records)
        total_response_tokens = sum(record.response_tokens for record in usage_records)
        
        # Models used
        models_used = list(set(record.model_name for record in usage_records))
        
        # Usage by model
        usage_by_model = {}
        for record in usage_records:
            model = record.model_name
            if model not in usage_by_model:
                usage_by_model[model] = {
                    'total_tokens': 0,
                    'prompt_tokens': 0,
                    'response_tokens': 0,
                    'request_count': 0
                }
            
            usage_by_model[model]['total_tokens'] += record.total_tokens()
            usage_by_model[model]['prompt_tokens'] += record.prompt_tokens
            usage_by_model[model]['response_tokens'] += record.response_tokens
            usage_by_model[model]['request_count'] += 1
        
        # Usage by type
        usage_by_type = {}
        for record in usage_records:
            usage_type = record.usage_type.value
            if usage_type not in usage_by_type:
                usage_by_type[usage_type] = 0
            usage_by_type[usage_type] += record.total_tokens()
        
        return {
            'total_tokens': total_tokens,
            'total_prompt_tokens': total_prompt_tokens,
            'total_response_tokens': total_response_tokens,
            'average_tokens_per_request': total_tokens / len(usage_records),
            'request_count': len(usage_records),
            'models_used': models_used,
            'usage_by_model': usage_by_model,
            'usage_by_type': usage_by_type,
            'cost_estimation': StatisticsCalculator._estimate_cost(usage_by_model),
            'peak_usage_period': StatisticsCalculator._find_peak_usage_period(usage_records)
        }
    
    @staticmethod
    def calculate_bookmark_stats(bookmark_records: List[BookmarkRecord]) -> Dict[str, Any]:
        """Calculate comprehensive bookmark statistics."""
        if not bookmark_records:
            return {
                'total_bookmarks': 0,
                'bookmarks_by_type': {},
                'bookmarks_by_scene': {},
                'average_bookmarks_per_scene': 0,
                'most_bookmarked_scenes': [],
                'creation_timeline': {}
            }
        
        # Bookmarks by type
        bookmarks_by_type = {}
        for record in bookmark_records:
            bookmark_type = record.bookmark_type.value
            bookmarks_by_type[bookmark_type] = bookmarks_by_type.get(bookmark_type, 0) + 1
        
        # Bookmarks by scene
        bookmarks_by_scene = {}
        for record in bookmark_records:
            scene_id = record.scene_id
            bookmarks_by_scene[scene_id] = bookmarks_by_scene.get(scene_id, 0) + 1
        
        # Most bookmarked scenes
        most_bookmarked_scenes = sorted(
            bookmarks_by_scene.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Creation timeline (by day)
        creation_timeline = {}
        for record in bookmark_records:
            date_key = record.created_at.date().isoformat()
            creation_timeline[date_key] = creation_timeline.get(date_key, 0) + 1
        
        unique_scenes = len(set(record.scene_id for record in bookmark_records))
        
        return {
            'total_bookmarks': len(bookmark_records),
            'unique_scenes': unique_scenes,
            'bookmarks_by_type': bookmarks_by_type,
            'bookmarks_by_scene': bookmarks_by_scene,
            'average_bookmarks_per_scene': len(bookmark_records) / max(unique_scenes, 1),
            'most_bookmarked_scenes': most_bookmarked_scenes,
            'creation_timeline': creation_timeline
        }
    
    @staticmethod
    def _estimate_cost(usage_by_model: Dict[str, Dict[str, Any]]) -> float:
        """Estimate cost based on usage (simplified pricing)."""
        # Simplified cost estimation - can be made more sophisticated
        cost_per_1k_tokens = {
            'gpt-4': 0.03,
            'gpt-3.5-turbo': 0.002,
            'claude': 0.008,
            'default': 0.01
        }
        
        total_cost = 0.0
        for model, usage in usage_by_model.items():
            rate = cost_per_1k_tokens.get(model.lower(), cost_per_1k_tokens['default'])
            total_cost += (usage['total_tokens'] / 1000) * rate
        
        return round(total_cost, 4)
    
    @staticmethod
    def _find_peak_usage_period(usage_records: List[TokenUsageRecord]) -> Optional[str]:
        """Find the hour with peak usage."""
        if not usage_records:
            return None
        
        hourly_usage = {}
        for record in usage_records:
            hour_key = record.timestamp.strftime('%Y-%m-%d %H:00')
            hourly_usage[hour_key] = hourly_usage.get(hour_key, 0) + record.total_tokens()
        
        if not hourly_usage:
            return None
        
        peak_hour = max(hourly_usage.items(), key=lambda x: x[1])
        return peak_hour[0]


class CacheManager:
    """Manages caching for management systems."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.access_order = []
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        if key in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        if key in self.cache:
            # Update existing item
            self.cache[key] = value
            self.access_order.remove(key)
            self.access_order.append(key)
        else:
            # Add new item
            if len(self.cache) >= self.max_size:
                # Remove least recently used item
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]
            
            self.cache[key] = value
            self.access_order.append(key)
    
    def clear(self) -> None:
        """Clear cache."""
        self.cache.clear()
        self.access_order.clear()
    
    def size(self) -> int:
        """Get cache size."""
        return len(self.cache)


class DataFormatter:
    """Formats data for different output types."""
    
    @staticmethod
    def format_timestamp(timestamp: datetime) -> str:
        """Format timestamp for display."""
        return timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    @staticmethod
    def format_token_count(tokens: int) -> str:
        """Format token count with appropriate units."""
        if tokens < 1000:
            return f"{tokens} tokens"
        elif tokens < 1000000:
            return f"{tokens/1000:.1f}K tokens"
        else:
            return f"{tokens/1000000:.1f}M tokens"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            return f"{seconds/60:.1f} minutes"
        else:
            return f"{seconds/3600:.1f} hours"
    
    @staticmethod
    def format_percentage(value: float, total: float) -> str:
        """Format percentage."""
        if total == 0:
            return "0%"
        percentage = (value / total) * 100
        return f"{percentage:.1f}%"
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."


class ErrorHandler:
    """Centralized error handling for management systems."""
    
    @staticmethod
    def log_and_raise(error_type: type, message: str, context: Optional[Dict[str, Any]] = None):
        """Log error and raise exception."""
        log_error(f"Management System Error: {message}")
        if context:
            log_error(f"Context: {json.dumps(context, default=str)}")
        raise error_type(message)
    
    @staticmethod
    def log_warning(message: str, context: Optional[Dict[str, Any]] = None):
        """Log warning with context."""
        log_warning(f"Management System Warning: {message}")
        if context:
            log_warning(f"Context: {json.dumps(context, default=str)}")
    
    @staticmethod
    def safe_execute(func: Callable, *args, default_return=None, **kwargs):
        """Safely execute function with error handling."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_error(f"Safe execution failed for {func.__name__}: {e}")
            return default_return
