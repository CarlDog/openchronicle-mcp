"""
Management Systems - Shared Data Models

Consolidates shared functionality from token_manager.py and bookmark_manager.py
providing common data structures, enums, and base classes for management operations.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from enum import Enum
from typing import Any


class BookmarkType(Enum):
    """Bookmark types for story navigation."""

    USER = "user"
    AUTO = "auto"
    CHAPTER = "chapter"
    SYSTEM = "system"


class TokenUsageType(Enum):
    """Token usage categories for tracking."""

    PROMPT = "prompt"
    RESPONSE = "response"
    CONTINUATION = "continuation"


@dataclass
class TokenUsageRecord:
    """Record of token usage for a specific operation."""

    model_name: str
    prompt_tokens: int
    response_tokens: int
    usage_type: TokenUsageType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def total_tokens(self) -> int:
        """Calculate total tokens used."""
        return self.prompt_tokens + self.response_tokens

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "usage_type": self.usage_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "total_tokens": self.total_tokens(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenUsageRecord":
        """Create from dictionary."""
        return cls(
            model_name=data["model_name"],
            prompt_tokens=data["prompt_tokens"],
            response_tokens=data["response_tokens"],
            usage_type=TokenUsageType(data["usage_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BookmarkRecord:
    """Record of a story bookmark."""

    id: int | None
    story_id: str
    scene_id: str
    label: str
    description: str | None = None
    bookmark_type: BookmarkType = BookmarkType.USER
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "story_id": self.story_id,
            "scene_id": self.scene_id,
            "label": self.label,
            "description": self.description,
            "bookmark_type": self.bookmark_type.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BookmarkRecord":
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            story_id=data["story_id"],
            scene_id=data["scene_id"],
            label=data["label"],
            description=data.get("description"),
            bookmark_type=BookmarkType(data.get("bookmark_type", "user")),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now(UTC)
            ),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TokenOptimizationResult:
    """Result of token optimization operations."""

    recommended_model: str | None = None
    truncation_risk: bool = False
    trimmed_context: dict[str, str] | None = None
    estimated_tokens: int = 0
    optimization_applied: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "recommended_model": self.recommended_model,
            "truncation_risk": self.truncation_risk,
            "trimmed_context": self.trimmed_context,
            "estimated_tokens": self.estimated_tokens,
            "optimization_applied": self.optimization_applied,
            "reasons": self.reasons,
        }


@dataclass
class BookmarkSearchOptions:
    """Options for bookmark search operations."""

    query: str | None = None
    bookmark_type: BookmarkType | None = None
    scene_id: str | None = None
    limit: int = 100
    offset: int = 0
    include_scenes: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database queries."""
        return {
            "query": self.query,
            "bookmark_type": self.bookmark_type.value if self.bookmark_type else None,
            "scene_id": self.scene_id,
            "limit": self.limit,
            "offset": self.offset,
            "include_scenes": self.include_scenes,
        }


class ManagementException(Exception):
    """Base exception for management system operations."""



class TokenManagerException(ManagementException):
    """Exception specific to token management operations."""



class BookmarkManagerException(ManagementException):
    """Exception specific to bookmark management operations."""

