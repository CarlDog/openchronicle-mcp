"""
DI-Enabled Timeline Orchestrator Example

Demonstrates migration from manual dependency injection to DI container pattern.
This shows the "before and after" for how the DI framework replaces manual wiring.

Part of Phase 2, Week 5-6: Dependency Injection Framework
"""

from typing import Dict, Any, Optional
from pathlib import Path

# Import DI framework
from core.shared.di_orchestrators import DIEnabledOrchestrator, OrchestratorConfig
from core.shared.service_interfaces import *

# Import utilities
from utilities.logging_system import log_system_event, log_info, log_warning, log_error


class DITimelineOrchestrator(DIEnabledOrchestrator):
    """
    DI-enabled Timeline Orchestrator.
    
    BEFORE (Manual DI):
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.config = TimelineConfiguration()
        self.metrics = TimelineMetrics()
        
        # Lazy-loaded components - MANUAL INSTANTIATION
        self._timeline_manager = None
        self._state_manager = None
        self._navigation_manager = None
    
    def _get_timeline_manager(self):
        if self._timeline_manager is None:
            from .timeline.timeline_manager import TimelineManager
            self._timeline_manager = TimelineManager(self.story_id)
        return self._timeline_manager
    
    AFTER (DI Container):
    def __init__(self, story_id: str, config: Optional[OrchestratorConfig] = None):
        self.story_id = story_id
        super().__init__(config)
        # Dependencies are injected via DI container
    """
    
    def __init__(self, story_id: str, config: Optional[OrchestratorConfig] = None):
        """Initialize timeline orchestrator with DI."""
        self.story_id = story_id
        super().__init__(config)
        
        log_system_event("di_timeline_orchestrator_init", f"DI Timeline orchestrator initialized for story {story_id}")
    
    def _initialize_dependencies(self):
        """Initialize timeline dependencies via DI."""
        # These are resolved from the DI container instead of manual instantiation
        self.database_orchestrator = self.resolve_optional(IDatabaseOrchestrator)
        self.memory_orchestrator = self.resolve_optional(IMemoryOrchestrator)
        self.context_orchestrator = self.resolve_optional(IContextOrchestrator)
        self.logger = self.resolve_optional(ILogger)
        
        # Configuration and metrics can still be created locally
        from core.timeline_systems.timeline_orchestrator import TimelineConfiguration, TimelineMetrics
        self.config = TimelineConfiguration()
        self.metrics = TimelineMetrics()
        
        log_info(f"Timeline orchestrator dependencies initialized via DI for story {self.story_id}")
    
    async def create_timeline_entry(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create timeline entry using DI dependencies."""
        try:
            # Use injected services instead of manual instantiation
            timeline_entry = {
                "scene_id": scene_data.get("scene_id"),
                "timestamp": scene_data.get("timestamp"),
                "content": scene_data.get("content", ""),
                "story_id": self.story_id
            }
            
            # Use memory orchestrator for context if available
            if self.memory_orchestrator:
                context = await self.memory_orchestrator.create_scene_context(self.story_id, scene_data)
                timeline_entry["context"] = context
            
            # Log via DI logger if available
            if self.logger:
                self.logger.log_info(f"Created timeline entry for scene {scene_data.get('scene_id')}")
            
            self.metrics.record_operation("timeline_entry_created")
            return timeline_entry
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to create timeline entry: {e}")
            self.metrics.record_operation("timeline_entry_created", success=False)
            return {}
    
    async def get_timeline_summary(self) -> Dict[str, Any]:
        """Get timeline summary using DI dependencies."""
        try:
            # Use database orchestrator if available
            if self.database_orchestrator:
                # Simulated timeline data retrieval
                summary = {
                    "story_id": self.story_id,
                    "total_scenes": 0,
                    "last_updated": "",
                    "status": "available"
                }
                
                if self.logger:
                    self.logger.log_info(f"Retrieved timeline summary for story {self.story_id}")
                
                return summary
            
            return {"status": "unavailable", "reason": "Database orchestrator not available"}
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to get timeline summary: {e}")
            return {"status": "error", "error": str(e)}


# Comparison examples
class ManualDependencyExample:
    """Example of OLD manual dependency injection pattern."""
    
    def __init__(self, story_id: str):
        """OLD WAY: Manual dependency instantiation."""
        self.story_id = story_id
        
        # Manual instantiation - BAD
        self._database_orchestrator = None
        self._memory_orchestrator = None
        self._context_orchestrator = None
        
        log_info("Initialized with manual dependency management")
    
    def _get_database_orchestrator(self):
        """Lazy loading with manual instantiation."""
        if self._database_orchestrator is None:
            # Manual import and instantiation
            from core.database_systems.database_orchestrator import DatabaseOrchestrator
            self._database_orchestrator = DatabaseOrchestrator()
        return self._database_orchestrator
    
    def _get_memory_orchestrator(self):
        """Lazy loading with manual instantiation."""
        if self._memory_orchestrator is None:
            # Manual import and instantiation
            from core.memory_management.memory_orchestrator import MemoryOrchestrator
            self._memory_orchestrator = MemoryOrchestrator()
        return self._memory_orchestrator


class DIContainerExample:
    """Example of NEW DI container pattern."""
    
    def __init__(self, story_id: str, container):
        """NEW WAY: Dependencies injected via container."""
        self.story_id = story_id
        self.container = container
        
        # Dependencies resolved via DI container - GOOD
        self.database_orchestrator = container.resolve_optional(IDatabaseOrchestrator)
        self.memory_orchestrator = container.resolve_optional(IMemoryOrchestrator)
        self.context_orchestrator = container.resolve_optional(IContextOrchestrator)
        
        log_info("Initialized with dependency injection")


def demonstrate_migration():
    """Demonstrate the migration from manual DI to container DI."""
    
    print("=== DEPENDENCY INJECTION MIGRATION DEMO ===")
    
    # OLD WAY: Manual dependency management
    print("\n1. OLD WAY: Manual Dependency Management")
    manual_example = ManualDependencyExample("test_story")
    print(f"   Created {manual_example.__class__.__name__}")
    print(f"   Database orchestrator: {manual_example._database_orchestrator}")  # None until accessed
    
    # NEW WAY: DI Container
    print("\n2. NEW WAY: DI Container")
    from core.shared.service_configuration import configure_openchronicle_services
    container = configure_openchronicle_services()
    
    di_example = DIContainerExample("test_story", container)
    print(f"   Created {di_example.__class__.__name__}")
    print(f"   Database orchestrator: {di_example.database_orchestrator is not None}")
    print(f"   Memory orchestrator: {di_example.memory_orchestrator is not None}")
    print(f"   Context orchestrator: {di_example.context_orchestrator is not None}")
    
    # DI-Enabled Orchestrator
    print("\n3. BEST: DI-Enabled Orchestrator")
    config = OrchestratorConfig(container=container)
    di_timeline = DITimelineOrchestrator("test_story", config)
    print(f"   Created {di_timeline.__class__.__name__}")
    print(f"   Database orchestrator: {di_timeline.database_orchestrator is not None}")
    print(f"   Memory orchestrator: {di_timeline.memory_orchestrator is not None}")
    print(f"   Logger: {di_timeline.logger is not None}")
    
    return di_timeline


# Factory function for creating DI-enabled timeline orchestrator
def create_di_timeline_orchestrator(story_id: str, container=None) -> DITimelineOrchestrator:
    """Create DI-enabled timeline orchestrator."""
    config = OrchestratorConfig(container=container)
    return DITimelineOrchestrator(story_id, config)


if __name__ == "__main__":
    # Demonstrate the migration
    timeline_orch = demonstrate_migration()
    
    print("\n=== TESTING DI TIMELINE ORCHESTRATOR ===")
    
    # Test timeline operations
    import asyncio
    
    async def test_operations():
        scene_data = {
            "scene_id": "test_scene_001",
            "timestamp": "2025-08-05T23:20:00Z",
            "content": "The hero enters the mysterious forest..."
        }
        
        # Test timeline entry creation
        entry = await timeline_orch.create_timeline_entry(scene_data)
        print(f"Timeline entry created: {entry.get('scene_id')}")
        
        # Test timeline summary
        summary = await timeline_orch.get_timeline_summary()
        print(f"Timeline summary status: {summary.get('status')}")
    
    asyncio.run(test_operations())
