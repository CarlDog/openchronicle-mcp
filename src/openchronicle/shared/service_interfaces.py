"""
Service Interfaces for OpenChronicle Dependency Injection

Defines clean interfaces for all major system components to enable
proper dependency injection and loose coupling.

Part of Phase 2, Week 5-6: Dependency Injection Framework
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, AsyncContextManager
from pathlib import Path


# =============================================================================
# Database Service Interfaces
# =============================================================================


class IDatabaseConnection(ABC):
    """Interface for database connection management."""

    @abstractmethod
    async def get_connection(self, db_path: str) -> AsyncContextManager:
        """Get a database connection."""
        pass

    @abstractmethod
    async def execute_query(self, db_path: str, query: str, params: tuple = ()) -> Any:
        """Execute a database query."""
        pass


class IDatabaseOperations(ABC):
    """Interface for database operations."""

    @abstractmethod
    async def create_tables(self, db_path: str) -> bool:
        """Create database tables."""
        pass

    @abstractmethod
    async def get_character_data(
        self, db_path: str, character_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get character data from database."""
        pass


class IDatabaseOrchestrator(ABC):
    """Interface for database orchestration."""

    @abstractmethod
    async def startup_health_check(self) -> Dict[str, Any]:
        """Perform startup health check."""
        pass

    @abstractmethod
    async def get_all_databases(self) -> List[str]:
        """Get all database paths."""
        pass


# =============================================================================
# Model Management Service Interfaces
# =============================================================================


class IModelAdapter(ABC):
    """Interface for model adapters."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the adapter."""
        pass

    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the model."""
        pass


class ILifecycleManager(ABC):
    """Interface for adapter lifecycle management."""

    @abstractmethod
    async def initialize_adapter(
        self, name: str, max_retries: int = 2, graceful_degradation: bool = True
    ) -> bool:
        """Initialize a specific adapter."""
        pass

    @abstractmethod
    def get_adapter_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all adapters."""
        pass


class IPerformanceMonitor(ABC):
    """Interface for performance monitoring."""

    @abstractmethod
    def record_response_time(self, adapter_name: str, response_time: float) -> None:
        """Record response time for an adapter."""
        pass

    @abstractmethod
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        pass


class IResponseGenerator(ABC):
    """Interface for response generation."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        adapter_name: Optional[str] = None,
        story_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate response using specified adapter."""
        pass


class IModelOrchestrator(ABC):
    """Interface for model orchestration."""

    @abstractmethod
    async def initialize_adapter(
        self, name: str, max_retries: int = 2, graceful_degradation: bool = True
    ) -> bool:
        """Initialize a specific adapter."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        adapter_name: Optional[str] = None,
        story_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate response using the ResponseGenerator component."""
        pass


# =============================================================================
# Memory Management Service Interfaces
# =============================================================================


class IMemoryRepository(ABC):
    """Interface for memory storage operations."""

    @abstractmethod
    async def get_character_memory(self, character_id: str) -> Dict[str, Any]:
        """Get character memory data."""
        pass

    @abstractmethod
    async def update_character_memory(
        self, character_id: str, updates: Dict[str, Any]
    ) -> bool:
        """Update character memory."""
        pass


class ICharacterManager(ABC):
    """Interface for character management."""

    @abstractmethod
    def get_character_data(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get character data."""
        pass

    @abstractmethod
    def update_character_state(
        self, character_id: str, updates: Dict[str, Any]
    ) -> bool:
        """Update character state."""
        pass


class IContextBuilder(ABC):
    """Interface for context building."""

    @abstractmethod
    async def build_scene_context(
        self, story_id: str, scene_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build context for a scene."""
        pass


class IMemoryOrchestrator(ABC):
    """Interface for memory orchestration."""

    @abstractmethod
    async def get_character_memory(self, character_id: str) -> Dict[str, Any]:
        """Get character memory."""
        pass

    @abstractmethod
    async def create_scene_context(
        self, story_id: str, scene_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create scene context."""
        pass


# =============================================================================
# Scene Management Service Interfaces
# =============================================================================


class ISceneRepository(ABC):
    """Interface for scene storage operations."""

    @abstractmethod
    async def save_scene(self, story_id: str, scene_data: Dict[str, Any]) -> str:
        """Save scene data."""
        pass

    @abstractmethod
    async def get_scene(self, story_id: str, scene_id: str) -> Optional[Dict[str, Any]]:
        """Get scene data."""
        pass


class ISceneOrchestrator(ABC):
    """Interface for scene orchestration."""

    @abstractmethod
    async def generate_scene(self, story_id: str, user_input: str) -> Dict[str, Any]:
        """Generate a new scene."""
        pass


# =============================================================================
# Content Analysis Service Interfaces
# =============================================================================


class IContentAnalyzer(ABC):
    """Interface for content analysis."""

    @abstractmethod
    async def analyze_content(
        self, content: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze content and return insights."""
        pass


class IContextOrchestrator(ABC):
    """Interface for context orchestration."""

    @abstractmethod
    async def build_context_with_analysis(
        self, content: str, story_id: str
    ) -> Dict[str, Any]:
        """Build context with analysis."""
        pass


# =============================================================================
# Narrative System Service Interfaces
# =============================================================================


class INarrativeOrchestrator(ABC):
    """Interface for narrative orchestration."""

    @abstractmethod
    async def process_narrative_request(
        self, story_id: str, request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process narrative request."""
        pass


class IMechanicsOrchestrator(ABC):
    """Interface for narrative mechanics."""

    @abstractmethod
    async def resolve_action(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a narrative action."""
        pass


# =============================================================================
# Configuration Service Interfaces
# =============================================================================


class IConfigurationManager(ABC):
    """Interface for configuration management."""

    @abstractmethod
    def get_config(self, section: str) -> Dict[str, Any]:
        """Get configuration section."""
        pass

    @abstractmethod
    def update_config(self, section: str, updates: Dict[str, Any]) -> bool:
        """Update configuration."""
        pass


# =============================================================================
# Logging Service Interfaces
# =============================================================================


class ILogger(ABC):
    """Interface for logging services."""

    @abstractmethod
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message."""
        pass

    @abstractmethod
    def log_error(self, message: str, **kwargs) -> None:
        """Log error message."""
        pass

    @abstractmethod
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        pass


# =============================================================================
# Service Registration Helpers
# =============================================================================


def get_core_service_interfaces() -> Dict[str, type]:
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
