"""
Service Configuration for OpenChronicle Dependency Injection

Configures and registers all services with the DI container.
Replaces manual dependency wiring in orchestrator __init__ methods.

Part of Phase 2, Week 5-6: Dependency Injection Framework
"""

from typing import Dict, Any, Optional
from pathlib import Path

# Import the DI container and interfaces
from .dependency_injection import DIContainer, ServiceLifetime, get_container
from .service_interfaces import *

# Import utilities
from .logging_system import log_system_event, log_info, log_error


class ServiceConfigurator:
    """
    Configures and registers all OpenChronicle services with the DI container.
    
    This replaces the manual dependency wiring pattern used throughout
    the codebase where orchestrators manually instantiate their dependencies.
    """
    
    def __init__(self, container: Optional[DIContainer] = None):
        """Initialize service configurator."""
        self.container = container or get_container()
        self._registered_services = set()
        
    def configure_all_services(self) -> DIContainer:
        """Configure all OpenChronicle services in proper dependency order."""
        log_info("Configuring OpenChronicle services with dependency injection")
        
        # Configure services in dependency order
        self._configure_logging_services()
        self._configure_configuration_services()
        self._configure_database_services()
        self._configure_model_management_services()
        self._configure_memory_services()
        self._configure_content_analysis_services()
        self._configure_scene_services()
        self._configure_narrative_services()
        self._configure_orchestrator_services()
        
        log_system_event(
            "di_services_configured", 
            f"Configured {len(self._registered_services)} services with dependency injection"
        )
        
        return self.container
    
    def _configure_logging_services(self):
        """Configure logging services."""
        log_info("Configuring logging services")
        
        # Register OpenChronicle logging system
        class OpenChronicleLogger(ILogger):
            """Adapter for OpenChronicle logging system."""
            
            def log_info(self, message: str, **kwargs) -> None:
                from .logging_system import log_info
                log_info(message, **kwargs)
            
            def log_error(self, message: str, **kwargs) -> None:
                from .logging_system import log_error
                log_error(message, **kwargs)
            
            def log_warning(self, message: str, **kwargs) -> None:
                from .logging_system import log_warning
                log_warning(message, **kwargs)
        
        self.container.register_singleton(
            ILogger, 
            OpenChronicleLogger, 
            "OpenChronicle logging system adapter"
        )
        
        self._registered_services.add("ILogger")
    
    def _configure_configuration_services(self):
        """Configure configuration management services."""
        log_info("Configuring configuration services")
        
        try:
            from core.model_management.configuration_manager import ConfigurationManager
            
            # Create wrapper that implements interface
            class ConfigurationManagerAdapter(IConfigurationManager):
                def __init__(self):
                    self._config_manager = ConfigurationManager()
                
                def get_config(self, section: str) -> Dict[str, Any]:
                    if hasattr(self._config_manager, 'config'):
                        return self._config_manager.config.get(section, {})
                    return {}
                
                def update_config(self, section: str, updates: Dict[str, Any]) -> bool:
                    # Implementation depends on ConfigurationManager API
                    return True
            
            self.container.register_singleton(
                IConfigurationManager,
                ConfigurationManagerAdapter,
                "Configuration management service"
            )
            
            self._registered_services.add("IConfigurationManager")
            
        except ImportError as e:
            log_error(f"Could not register configuration services: {e}")
    
    def _configure_database_services(self):
        """Configure database services."""
        log_info("Configuring database services")
        
        try:
            from core.database_systems.database_orchestrator import DatabaseOrchestrator
            
            # Create wrapper that implements interface
            class DatabaseOrchestratorAdapter(IDatabaseOrchestrator):
                def __init__(self):
                    self._orchestrator = DatabaseOrchestrator()
                
                async def startup_health_check(self) -> Dict[str, Any]:
                    if hasattr(self._orchestrator, 'startup_health_check'):
                        return await self._orchestrator.startup_health_check()
                    return {"status": "unknown"}
                
                async def get_all_databases(self) -> List[str]:
                    if hasattr(self._orchestrator, 'get_all_databases'):
                        return await self._orchestrator.get_all_databases()
                    return []
            
            self.container.register_singleton(
                IDatabaseOrchestrator,
                DatabaseOrchestratorAdapter,
                "Database orchestration service"
            )
            
            self._registered_services.add("IDatabaseOrchestrator")
            
        except ImportError as e:
            log_error(f"Could not register database services: {e}")
    
    def _configure_model_management_services(self):
        """Configure model management services."""
        log_info("Configuring model management services")
        
        try:
            from core.model_management.model_orchestrator import ModelOrchestrator
            
            # Create wrapper that implements interface
            class ModelOrchestratorAdapter(IModelOrchestrator):
                def __init__(self):
                    self._orchestrator = ModelOrchestrator()
                
                async def initialize_adapter(self, name: str, max_retries: int = 2, graceful_degradation: bool = True) -> bool:
                    return await self._orchestrator.initialize_adapter(name, max_retries, graceful_degradation)
                
                async def generate_response(
                    self, 
                    prompt: str, 
                    adapter_name: Optional[str] = None, 
                    story_id: Optional[str] = None, 
                    **kwargs
                ) -> str:
                    return await self._orchestrator.generate_response(prompt, adapter_name, story_id, **kwargs)
            
            self.container.register_singleton(
                IModelOrchestrator,
                ModelOrchestratorAdapter,
                "Model orchestration service"
            )
            
            self._registered_services.add("IModelOrchestrator")
            
        except ImportError as e:
            log_error(f"Could not register model management services: {e}")
    
    def _configure_memory_services(self):
        """Configure memory management services."""
        log_info("Configuring memory management services")
        
        try:
            from core.memory_management.memory_orchestrator import MemoryOrchestrator
            
            # Create wrapper that implements interface
            class MemoryOrchestratorAdapter(IMemoryOrchestrator):
                def __init__(self):
                    self._orchestrator = MemoryOrchestrator()
                
                async def get_character_memory(self, character_id: str) -> Dict[str, Any]:
                    if hasattr(self._orchestrator, 'get_character_memory'):
                        return self._orchestrator.get_character_memory(character_id)
                    return {}
                
                async def create_scene_context(self, story_id: str, scene_data: Dict[str, Any]) -> Dict[str, Any]:
                    if hasattr(self._orchestrator, 'create_scene_context'):
                        return self._orchestrator.create_scene_context(story_id, scene_data)
                    return {}
            
            self.container.register_singleton(
                IMemoryOrchestrator,
                MemoryOrchestratorAdapter,
                "Memory orchestration service"
            )
            
            self._registered_services.add("IMemoryOrchestrator")
            
        except ImportError as e:
            log_error(f"Could not register memory services: {e}")
    
    def _configure_content_analysis_services(self):
        """Configure content analysis services."""
        log_info("Configuring content analysis services")
        
        try:
            from core.context_systems.context_orchestrator import ContextOrchestrator
            
            # Create wrapper that implements interface
            class ContextOrchestratorAdapter(IContextOrchestrator):
                def __init__(self):
                    self._orchestrator = ContextOrchestrator()
                
                async def build_context_with_analysis(self, content: str, story_id: str) -> Dict[str, Any]:
                    if hasattr(self._orchestrator, 'build_context_with_analysis'):
                        return await self._orchestrator.build_context_with_analysis(content, story_id)
                    return {}
            
            self.container.register_singleton(
                IContextOrchestrator,
                ContextOrchestratorAdapter,
                "Context orchestration service"
            )
            
            self._registered_services.add("IContextOrchestrator")
            
        except ImportError as e:
            log_error(f"Could not register content analysis services: {e}")
    
    def _configure_scene_services(self):
        """Configure scene management services."""
        log_info("Configuring scene management services")
        
        try:
            from core.scene_systems.scene_orchestrator import SceneOrchestrator
            
            # Create wrapper that implements interface  
            class SceneOrchestratorAdapter(ISceneOrchestrator):
                def __init__(self):
                    # SceneOrchestrator requires story_id, so we'll create it on demand
                    self._orchestrators: Dict[str, Any] = {}
                
                def _get_orchestrator(self, story_id: str):
                    if story_id not in self._orchestrators:
                        self._orchestrators[story_id] = SceneOrchestrator(story_id)
                    return self._orchestrators[story_id]
                
                async def generate_scene(self, story_id: str, user_input: str) -> Dict[str, Any]:
                    orchestrator = self._get_orchestrator(story_id)
                    if hasattr(orchestrator, 'generate_scene'):
                        return await orchestrator.generate_scene(user_input)
                    return {}
            
            self.container.register_singleton(
                ISceneOrchestrator,
                SceneOrchestratorAdapter,
                "Scene orchestration service"
            )
            
            self._registered_services.add("ISceneOrchestrator")
            
        except ImportError as e:
            log_error(f"Could not register scene services: {e}")
    
    def _configure_narrative_services(self):
        """Configure narrative system services."""
        log_info("Configuring narrative services")
        
        try:
            from core.narrative_systems.narrative_orchestrator import NarrativeOrchestrator
            
            # Create wrapper that implements interface
            class NarrativeOrchestratorAdapter(INarrativeOrchestrator):
                def __init__(self):
                    self._orchestrator = NarrativeOrchestrator()
                
                async def process_narrative_request(self, story_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
                    # Implementation depends on NarrativeOrchestrator API
                    return {}
            
            self.container.register_singleton(
                INarrativeOrchestrator,
                NarrativeOrchestratorAdapter,
                "Narrative orchestration service"
            )
            
            self._registered_services.add("INarrativeOrchestrator")
            
        except ImportError as e:
            log_error(f"Could not register narrative services: {e}")
    
    def _configure_orchestrator_services(self):
        """Configure high-level orchestrator services."""
        log_info("Configuring orchestrator services")
        
        # Register any cross-cutting orchestrator services here
        # These would be services that coordinate between multiple systems
        pass
    
    def get_registration_summary(self) -> Dict[str, Any]:
        """Get summary of registered services."""
        registrations = self.container.get_registrations()
        
        return {
            "total_services": len(self._registered_services),
            "registered_services": sorted(list(self._registered_services)),
            "container_registrations": len(registrations),
            "registration_details": registrations
        }


def configure_openchronicle_services(container: Optional[DIContainer] = None) -> DIContainer:
    """
    Configure all OpenChronicle services with dependency injection.
    
    This is the main entry point for setting up the DI container
    and replaces all manual dependency wiring.
    
    Args:
        container: Optional existing container to use
        
    Returns:
        Configured DI container
    """
    configurator = ServiceConfigurator(container)
    return configurator.configure_all_services()


if __name__ == "__main__":
    # Test the service configuration
    container = configure_openchronicle_services()
    
    configurator = ServiceConfigurator(container)
    summary = configurator.get_registration_summary()
    
    print("Service Configuration Summary:")
    print(f"Total services: {summary['total_services']}")
    print(f"Registered services: {summary['registered_services']}")
    print(f"Container registrations: {summary['container_registrations']}")
