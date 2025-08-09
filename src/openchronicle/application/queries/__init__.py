"""
Application queries for OpenChronicle.

Queries represent read operations that retrieve information from the system
without changing state. They encapsulate data access patterns and provide
a clean interface for retrieving domain objects.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from abc import ABC, abstractmethod

from ...domain import Story, Character, Scene, StoryStatus, MemoryState


class Query(ABC):
    """Base class for all queries."""
    pass


class QueryResult:
    """Result of query execution."""
    
    def __init__(self, success: bool, data: Any = None, message: str = "", errors: List[str] = None):
        self.success = success
        self.data = data
        self.message = message
        self.errors = errors or []
        self.timestamp = datetime.now()
    
    @classmethod
    def success(cls, data: Any, message: str = "Query executed successfully") -> "QueryResult":
        """Create a successful result."""
        return cls(True, data, message)
    
    @classmethod
    def failure(cls, message: str, errors: List[str] = None) -> "QueryResult":
        """Create a failed result."""
        return cls(False, None, message, errors)


@dataclass
class GetStoryQuery(Query):
    """Query to retrieve a story by ID."""
    story_id: str
    include_characters: bool = True
    include_scenes: bool = False
    include_memory: bool = False


@dataclass
class ListStoriesQuery(Query):
    """Query to list stories with filtering options."""
    status_filter: Optional[List[StoryStatus]] = None
    search_term: Optional[str] = None
    limit: int = 50
    offset: int = 0
    sort_by: str = "updated_at"
    sort_order: str = "desc"  # "asc" or "desc"
    
    def __post_init__(self):
        if self.status_filter is None:
            self.status_filter = []


@dataclass
class GetCharacterQuery(Query):
    """Query to retrieve a character by ID."""
    character_id: str
    include_relationships: bool = True
    include_memory_profile: bool = False


@dataclass
class ListCharactersQuery(Query):
    """Query to list characters in a story."""
    story_id: str
    active_only: bool = True
    include_relationships: bool = False
    search_term: Optional[str] = None


@dataclass
class GetSceneQuery(Query):
    """Query to retrieve a scene by ID."""
    scene_id: str
    include_character_states: bool = True
    include_context: bool = False


@dataclass
class ListScenesQuery(Query):
    """Query to list scenes in a story."""
    story_id: str
    limit: int = 50
    offset: int = 0
    scene_type_filter: Optional[str] = None
    participant_filter: Optional[List[str]] = None
    sort_by: str = "created_at"
    sort_order: str = "asc"
    
    def __post_init__(self):
        if self.participant_filter is None:
            self.participant_filter = []


@dataclass
class GetMemoryStateQuery(Query):
    """Query to retrieve current memory state."""
    story_id: str
    include_character_memories: bool = True
    include_world_state: bool = True
    include_flags: bool = True
    include_events: bool = False


@dataclass
class SearchMemoryQuery(Query):
    """Query to search memory content."""
    story_id: str
    search_term: str
    search_scope: List[str] = None  # ["characters", "events", "world_state", "flags"]
    limit: int = 20
    
    def __post_init__(self):
        if self.search_scope is None:
            self.search_scope = ["characters", "events", "world_state"]


@dataclass
class GetCharacterRelationshipsQuery(Query):
    """Query to get character relationship graph."""
    story_id: str
    character_id: Optional[str] = None  # If None, gets all relationships
    relationship_types: Optional[List[str]] = None
    include_inactive: bool = False


@dataclass
class GetStoryTimelineQuery(Query):
    """Query to get story timeline/chronology."""
    story_id: str
    limit: int = 100
    offset: int = 0
    event_types: Optional[List[str]] = None
    participant_filter: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.event_types is None:
            self.event_types = []
        if self.participant_filter is None:
            self.participant_filter = []


@dataclass
class GetStoryStatisticsQuery(Query):
    """Query to get story statistics and metrics."""
    story_id: str
    include_character_stats: bool = True
    include_scene_stats: bool = True
    include_model_usage: bool = False


@dataclass
class SearchContentQuery(Query):
    """Query to search across story content."""
    search_term: str
    story_ids: Optional[List[str]] = None
    content_types: List[str] = None  # ["scenes", "characters", "descriptions"]
    limit: int = 50
    include_highlights: bool = True
    
    def __post_init__(self):
        if self.story_ids is None:
            self.story_ids = []
        if self.content_types is None:
            self.content_types = ["scenes", "characters"]


@dataclass
class GetModelUsageQuery(Query):
    """Query to get model usage statistics."""
    story_id: Optional[str] = None
    time_range: Optional[tuple] = None  # (start_date, end_date)
    model_names: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.model_names is None:
            self.model_names = []


@dataclass
class ValidateStoryConsistencyQuery(Query):
    """Query to validate story consistency."""
    story_id: str
    check_character_consistency: bool = True
    check_plot_consistency: bool = True
    check_world_consistency: bool = True
    detailed_report: bool = False


# Pagination helper
@dataclass
class PaginationInfo:
    """Pagination information for query results."""
    total_count: int
    page_size: int
    current_page: int
    total_pages: int
    has_next: bool
    has_previous: bool


# Export all queries
__all__ = [
    "Query",
    "QueryResult",
    "PaginationInfo",
    "GetStoryQuery",
    "ListStoriesQuery", 
    "GetCharacterQuery",
    "ListCharactersQuery",
    "GetSceneQuery",
    "ListScenesQuery",
    "GetMemoryStateQuery",
    "SearchMemoryQuery",
    "GetCharacterRelationshipsQuery", 
    "GetStoryTimelineQuery",
    "GetStoryStatisticsQuery",
    "SearchContentQuery",
    "GetModelUsageQuery",
    "ValidateStoryConsistencyQuery"
]
