"""
DI-Enabled Base Classes for OpenChronicle Orchestrators

Provides base classes that use dependency injection instead of manual wiring.
Simplifies migration from manual dependency instantiation to DI pattern.

Part of Phase 2, Week 5-6: Dependency Injection Framework
"""

from abc import ABC
from typing import Type, TypeVar, Optional, Dict, Any
from dataclasses import dataclass

# Import DI components
from .dependency_injection import DIContainer, get_container
from .service_interfaces import *

# Import utilities
from .logging_system import log_system_event, log_info, log_error

T = TypeVar('T')


@dataclass
class OrchestratorConfig:
    """Base configuration for DI-enabled orchestrators."""
    container: Optional[DIContainer] = None
    auto_configure: bool = True
    enable_logging: bool = True


class DIEnabledOrchestrator(ABC):
    """
    Base class for DI-enabled orchestrators.
    
    Replaces the manual dependency instantiation pattern with clean
    dependency injection. All derived orchestrators get their dependencies
    injected rather than manually creating them.
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """Initialize DI-enabled orchestrator."""
        self.config = config or OrchestratorConfig()
        self.container = self.config.container or get_container()
        
        # Auto-configure services if requested
        if self.config.auto_configure:
            self._ensure_services_configured()
        
        # Initialize dependencies through DI
        self._initialize_dependencies()
        
        if hasattr(self.config, 'enable_logging') and getattr(self.config, 'enable_logging', True):
            log_info(f"{self.__class__.__name__} initialized with dependency injection")
    
    def _ensure_services_configured(self):
        """Ensure services are configured in the container."""
        try:
            from .service_configuration import configure_openchronicle_services
            configure_openchronicle_services(self.container)
        except Exception as e:
            log_error(f"Failed to auto-configure services: {e}")
    
    def _initialize_dependencies(self):
        """Initialize dependencies through DI. Override in derived classes."""
        pass
    
    def resolve(self, interface: Type[T]) -> T:
        """Resolve a service from the DI container."""
        return self.container.resolve(interface)
    
    def resolve_optional(self, interface: Type[T]) -> Optional[T]:
        """Resolve a service optionally (returns None if not registered)."""
        try:
            return self.container.resolve(interface)
        except ValueError:
            return None


class DIModelOrchestrator(DIEnabledOrchestrator):
    """DI-enabled replacement for ModelOrchestrator."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """Initialize with dependency injection."""
        super().__init__(config)
    
    def _initialize_dependencies(self):
        """Initialize model management dependencies."""
        # These will be injected via DI instead of manual instantiation
        self.model_orchestrator = self.resolve_optional(IModelOrchestrator)
        self.configuration_manager = self.resolve_optional(IConfigurationManager)
        self.logger = self.resolve_optional(ILogger)
    
    async def initialize_adapter(self, name: str, max_retries: int = 2, graceful_degradation: bool = True) -> bool:
        """Initialize adapter through DI."""
        if self.model_orchestrator:
            return await self.model_orchestrator.initialize_adapter(name, max_retries, graceful_degradation)
        return False
    
    async def generate_response(
        self, 
        prompt: str, 
        adapter_name: Optional[str] = None, 
        story_id: Optional[str] = None, 
        **kwargs
    ) -> str:
        """Generate response through DI."""
        if self.model_orchestrator:
            return await self.model_orchestrator.generate_response(prompt, adapter_name, story_id, **kwargs)
        return ""


class DIMemoryOrchestrator(DIEnabledOrchestrator):
    """DI-enabled replacement for MemoryOrchestrator."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """Initialize with dependency injection."""
        super().__init__(config)
    
    def _initialize_dependencies(self):
        """Initialize memory management dependencies."""
        self.memory_orchestrator = self.resolve_optional(IMemoryOrchestrator)
        self.character_manager = self.resolve_optional(ICharacterManager)
        self.context_builder = self.resolve_optional(IContextBuilder)
        self.logger = self.resolve_optional(ILogger)
    
    async def get_character_memory(self, character_id: str) -> Dict[str, Any]:
        """Get character memory through DI."""
        if self.memory_orchestrator:
            return await self.memory_orchestrator.get_character_memory(character_id)
        return {}
    
    async def create_scene_context(self, story_id: str, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create scene context through DI."""
        if self.memory_orchestrator:
            return await self.memory_orchestrator.create_scene_context(story_id, scene_data)
        return {}


class DISceneOrchestrator(DIEnabledOrchestrator):
    """DI-enabled replacement for SceneOrchestrator."""
    
    def __init__(self, story_id: str, config: Optional[OrchestratorConfig] = None):
        """Initialize with dependency injection."""
        self.story_id = story_id
        super().__init__(config)
    
    def _initialize_dependencies(self):
        """Initialize scene management dependencies."""
        self.scene_orchestrator = self.resolve_optional(ISceneOrchestrator)
        self.memory_orchestrator = self.resolve_optional(IMemoryOrchestrator)
        self.context_orchestrator = self.resolve_optional(IContextOrchestrator)
        self.logger = self.resolve_optional(ILogger)
    
    async def generate_scene(self, user_input: str) -> Dict[str, Any]:
        """Generate scene through DI."""
        if self.scene_orchestrator:
            return await self.scene_orchestrator.generate_scene(self.story_id, user_input)
        return {}


class DINarrativeOrchestrator(DIEnabledOrchestrator):
    """DI-enabled replacement for NarrativeOrchestrator."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """Initialize with dependency injection."""
        super().__init__(config)
    
    def _initialize_dependencies(self):
        """Initialize narrative system dependencies."""
        self.narrative_orchestrator = self.resolve_optional(INarrativeOrchestrator)
        self.mechanics_orchestrator = self.resolve_optional(IMechanicsOrchestrator)
        self.logger = self.resolve_optional(ILogger)
    
    async def process_narrative_request(self, story_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process narrative request through DI."""
        if self.narrative_orchestrator:
            return await self.narrative_orchestrator.process_narrative_request(story_id, request)
        return {}


class DIContextOrchestrator(DIEnabledOrchestrator):
    """DI-enabled replacement for ContextOrchestrator."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """Initialize with dependency injection."""
        super().__init__(config)
    
    def _initialize_dependencies(self):
        """Initialize context system dependencies."""
        self.context_orchestrator = self.resolve_optional(IContextOrchestrator)
        self.memory_orchestrator = self.resolve_optional(IMemoryOrchestrator)
        self.content_analyzer = self.resolve_optional(IContentAnalyzer)
        self.logger = self.resolve_optional(ILogger)
    
    async def build_context_with_analysis(self, content: str, story_id: str) -> Dict[str, Any]:
        """Build context with analysis through DI."""
        if self.context_orchestrator:
            return await self.context_orchestrator.build_context_with_analysis(content, story_id)
        return {}


# Factory functions for creating DI-enabled orchestrators
def create_di_model_orchestrator(container: Optional[DIContainer] = None) -> DIModelOrchestrator:
    """Create DI-enabled model orchestrator."""
    config = OrchestratorConfig(container=container)
    return DIModelOrchestrator(config)


def create_di_memory_orchestrator(container: Optional[DIContainer] = None) -> DIMemoryOrchestrator:
    """Create DI-enabled memory orchestrator."""
    config = OrchestratorConfig(container=container)
    return DIMemoryOrchestrator(config)


def create_di_scene_orchestrator(story_id: str, container: Optional[DIContainer] = None) -> DISceneOrchestrator:
    """Create DI-enabled scene orchestrator."""
    config = OrchestratorConfig(container=container)
    return DISceneOrchestrator(story_id, config)


def create_di_narrative_orchestrator(container: Optional[DIContainer] = None) -> DINarrativeOrchestrator:
    """Create DI-enabled narrative orchestrator."""
    config = OrchestratorConfig(container=container)
    return DINarrativeOrchestrator(config)


def create_di_context_orchestrator(container: Optional[DIContainer] = None) -> DIContextOrchestrator:
    """Create DI-enabled context orchestrator."""
    config = OrchestratorConfig(container=container)
    return DIContextOrchestrator(config)


# Migration utilities
class OrchestratorMigration:
    """Utilities for migrating from manual DI to container-based DI."""
    
    @staticmethod
    def migrate_orchestrator_creation() -> Dict[str, str]:
        """Provide migration examples for orchestrator creation."""
        return {
            "ModelOrchestrator": """
# OLD: Manual dependency wiring
orchestrator = ModelOrchestrator()  # Manually creates all dependencies

# NEW: DI container
orchestrator = create_di_model_orchestrator()  # Dependencies injected
""",
            "MemoryOrchestrator": """
# OLD: Manual dependency wiring
orchestrator = MemoryOrchestrator()  # Manually creates all dependencies

# NEW: DI container
orchestrator = create_di_memory_orchestrator()  # Dependencies injected
""",
            "SceneOrchestrator": """
# OLD: Manual dependency wiring
orchestrator = SceneOrchestrator(story_id)  # Manually creates all dependencies

# NEW: DI container
orchestrator = create_di_scene_orchestrator(story_id)  # Dependencies injected
"""
        }


if __name__ == "__main__":
    # Test DI-enabled orchestrators
    print("Testing DI-enabled orchestrators...")
    
    # Test model orchestrator
    model_orch = create_di_model_orchestrator()
    print(f"Model orchestrator created: {model_orch.__class__.__name__}")
    
    # Test memory orchestrator
    memory_orch = create_di_memory_orchestrator()
    print(f"Memory orchestrator created: {memory_orch.__class__.__name__}")
    
    # Show migration examples
    migration = OrchestratorMigration()
    examples = migration.migrate_orchestrator_creation()
    
    print("\nMigration Examples:")
    for name, example in examples.items():
        print(f"\n{name}:")
        print(example)
