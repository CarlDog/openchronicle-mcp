"""
Service Interfaces for OpenChronicle Dependency Injection

Defines clean interfaces for all major system components to enable
proper dependency injection and loose coupling.

Part of Phase 2, Week 5-6: Dependency Injection Framework
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import AsyncContextManager


# =============================================================================
# Database Service Interfaces
# =============================================================================


class IDatabaseConnection(ABC):
    """Interface for database connection management."""

    @abstractmethod
    async def get_connection(self, db_path: str) -> AsyncContextManager:
        """Get a database connection."""

    @abstractmethod
    async def execute_query(self, db_path: str, query: str, params: tuple = ()) -> Any:
        """Execute a database query."""


class IDatabaseOperations(ABC):
    """Interface for database operations."""

    @abstractmethod
    async def create_tables(self, db_path: str) -> bool:
        """Create database tables."""

    @abstractmethod
    async def get_character_data(self, db_path: str, character_id: str) -> dict[str, Any] | None:
        """Get character data from database."""


class IDatabaseOrchestrator(ABC):
    """Interface for database orchestration."""

    @abstractmethod
    async def startup_health_check(self) -> dict[str, Any]:
        """Perform startup health check."""

    @abstractmethod
    async def get_all_databases(self) -> list[str]:
        """Get all database paths."""


# =============================================================================
# Model Management Service Interfaces
# =============================================================================


class IModelAdapter(ABC):
    """Interface for model adapters."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the adapter."""

    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the model."""


class ILifecycleManager(ABC):
    """Interface for adapter lifecycle management."""

    @abstractmethod
    async def initialize_adapter(self, name: str, max_retries: int = 2, graceful_degradation: bool = True) -> bool:
        """Initialize a specific adapter."""

    @abstractmethod
    def get_adapter_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all adapters."""


class IPerformanceMonitor(ABC):
    """Interface for performance monitoring."""

    @abstractmethod
    def record_response_time(self, adapter_name: str, response_time: float) -> None:
        """Record response time for an adapter."""

    @abstractmethod
    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics."""


class IResponseGenerator(ABC):
    """Interface for response generation."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        adapter_name: str | None = None,
        story_id: str | None = None,
        **kwargs,
    ) -> str:
        """Generate response using specified adapter."""


class IModelOrchestrator(ABC):
    """Interface for model orchestration."""

    @abstractmethod
    async def initialize_adapter(self, name: str, max_retries: int = 2, graceful_degradation: bool = True) -> bool:
        """Initialize a specific adapter."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        adapter_name: str | None = None,
        story_id: str | None = None,
        **kwargs,
    ) -> str:
        """Generate response using the ResponseGenerator component."""


# =============================================================================
# Memory Management Service Interfaces
# =============================================================================


class IMemoryRepository(ABC):
    """Interface for memory storage operations."""

    @abstractmethod
    async def get_character_memory(self, character_id: str) -> dict[str, Any]:
        """Get character memory data."""

    @abstractmethod
    async def update_character_memory(self, character_id: str, updates: dict[str, Any]) -> bool:
        """Update character memory."""


class ICharacterManager(ABC):
    """Interface for character management."""

    @abstractmethod
    def get_character_data(self, character_id: str) -> dict[str, Any] | None:
        """Get character data."""

    @abstractmethod
    def update_character_state(self, character_id: str, updates: dict[str, Any]) -> bool:
        """Update character state."""


class IContextBuilder(ABC):
    """Interface for context building."""

    @abstractmethod
    async def build_scene_context(self, story_id: str, scene_data: dict[str, Any]) -> dict[str, Any]:
        """Build context for a scene."""


class IMemoryOrchestrator(ABC):
    """Interface for memory orchestration."""

    @abstractmethod
    async def get_character_memory(self, character_id: str) -> dict[str, Any]:
        """Get character memory."""

    @abstractmethod
    async def create_scene_context(self, story_id: str, scene_data: dict[str, Any]) -> dict[str, Any]:
        """Create scene context."""


# =============================================================================
# Scene Management Service Interfaces
# =============================================================================


class ISceneRepository(ABC):
    """Interface for scene storage operations."""

    @abstractmethod
    async def save_scene(self, story_id: str, scene_data: dict[str, Any]) -> str:
        """Save scene data."""

    @abstractmethod
    async def get_scene(self, story_id: str, scene_id: str) -> dict[str, Any] | None:
        """Get scene data."""


class ISceneOrchestrator(ABC):
    """Interface for scene orchestration."""

    @abstractmethod
    async def generate_scene(self, story_id: str, user_input: str) -> dict[str, Any]:
        """Generate a new scene."""


# =============================================================================
# Content Analysis Service Interfaces
# =============================================================================


class IContentAnalyzer(ABC):
    """Interface for content analysis."""

    @abstractmethod
    async def analyze_content(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Analyze content and return insights."""


class IContextOrchestrator(ABC):
    """Interface for context orchestration."""

    @abstractmethod
    async def build_context_with_analysis(self, content: str, story_id: str) -> dict[str, Any]:
        """Build context with analysis."""


# =============================================================================
# Narrative System Service Interfaces
# =============================================================================


class INarrativeOrchestrator(ABC):
    """Interface for narrative orchestration."""

    @abstractmethod
    async def process_narrative_request(self, story_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Process narrative request."""


class IMechanicsOrchestrator(ABC):
    """Interface for narrative mechanics."""

    @abstractmethod
    async def resolve_action(self, request: dict[str, Any]) -> dict[str, Any]:
        """Resolve a narrative action."""


# =============================================================================
# Configuration Service Interfaces
# =============================================================================


class IConfigurationManager(ABC):
    """Interface for configuration management."""

    @abstractmethod
    def get_config(self, section: str) -> dict[str, Any]:
        """Get configuration section."""

    @abstractmethod
    def update_config(self, section: str, updates: dict[str, Any]) -> bool:
        """Update configuration."""


# =============================================================================
# Logging Service Interfaces
# =============================================================================


class ILogger(ABC):
    """Interface for logging services."""

    @abstractmethod
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message."""

    @abstractmethod
    def log_error(self, message: str, **kwargs) -> None:
        """Log error message."""

    @abstractmethod
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message."""


# =============================================================================
# Service Registration Helpers
# =============================================================================


def get_core_service_interfaces() -> dict[str, type]:
    """Get all core service interfaces for registration."""
    return {
        # Database services
        "IDatabaseConnection": IDatabaseConnection,
        "IDatabaseOperations": IDatabaseOperations,
        "IDatabaseOrchestrator": IDatabaseOrchestrator,
        # Model management services
        "IModelAdapter": IModelAdapter,
        "ILifecycleManager": ILifecycleManager,
        "IPerformanceMonitor": IPerformanceMonitor,
        "IResponseGenerator": IResponseGenerator,
        "IModelOrchestrator": IModelOrchestrator,
        # Memory management services
        "IMemoryRepository": IMemoryRepository,
        "ICharacterManager": ICharacterManager,
        "IContextBuilder": IContextBuilder,
        "IMemoryOrchestrator": IMemoryOrchestrator,
        # Scene management services
        "ISceneRepository": ISceneRepository,
        "ISceneOrchestrator": ISceneOrchestrator,
        # Content analysis services
        "IContentAnalyzer": IContentAnalyzer,
        "IContextOrchestrator": IContextOrchestrator,
        # Narrative system services
        "INarrativeOrchestrator": INarrativeOrchestrator,
        "IMechanicsOrchestrator": IMechanicsOrchestrator,
        # Configuration services
        "IConfigurationManager": IConfigurationManager,
        # Logging services
        "ILogger": ILogger,
    }
