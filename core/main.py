"""
OpenChronicle Core - Main Entry Point

Professional API for OpenChronicle's core narrative AI engine.
Provides clean, centralized access to all core orchestrators and services
following enterprise software best practices.

Usage:
    from core import ModelOrchestrator, MemoryOrchestrator, SceneOrchestrator
    from core import initialize_core, health_check
    
Architecture:
    - Primary Orchestrators: Main workflow components (Model, Scene, Memory, etc.)
    - Secondary Services: Specialized components (Character, Timeline, Database, etc.)
    - Utility Functions: System initialization, health checks, version info
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

# Ensure core module can find its dependencies
core_dir = Path(__file__).parent
if str(core_dir.parent) not in sys.path:
    sys.path.insert(0, str(core_dir.parent))

# Core infrastructure
from .shared.logging_system import log_system_event, log_info, log_error, log_warning
from .shared.error_handling import OpenChronicleError
from .shared.dependency_injection import get_container
from .shared.centralized_config import CentralizedConfigManager

# === PRIMARY ORCHESTRATORS ===
# Main workflow components - most commonly used

try:
    from .models.model_orchestrator import ModelOrchestrator
    MODEL_AVAILABLE = True
except ImportError as e:
    log_warning(f"ModelOrchestrator not available: {e}")
    MODEL_AVAILABLE = False
    ModelOrchestrator = None

try:
    from .memory.memory_orchestrator import MemoryOrchestrator
    MEMORY_AVAILABLE = True
except ImportError as e:
    log_warning(f"MemoryOrchestrator not available: {e}")
    MEMORY_AVAILABLE = False
    MemoryOrchestrator = None

try:
    from .scenes.scene_orchestrator import SceneOrchestrator
    SCENE_AVAILABLE = True
except ImportError as e:
    log_warning(f"SceneOrchestrator not available: {e}")
    SCENE_AVAILABLE = False
    SceneOrchestrator = None

try:
    from .narrative.narrative_orchestrator import NarrativeOrchestrator
    NARRATIVE_AVAILABLE = True
except ImportError as e:
    log_warning(f"NarrativeOrchestrator not available: {e}")
    NARRATIVE_AVAILABLE = False
    NarrativeOrchestrator = None

# === SECONDARY SERVICES ===
# Specialized components for specific workflows

try:
    from .characters.character_orchestrator import CharacterOrchestrator
    CHARACTER_AVAILABLE = True
except ImportError as e:
    log_warning(f"CharacterOrchestrator not available: {e}")
    CHARACTER_AVAILABLE = False
    CharacterOrchestrator = None

try:
    from .timeline.timeline_orchestrator import TimelineOrchestrator
    TIMELINE_AVAILABLE = True
except ImportError as e:
    log_warning(f"TimelineOrchestrator not available: {e}")
    TIMELINE_AVAILABLE = False
    TimelineOrchestrator = None

try:
    from .database.database_orchestrator import DatabaseOrchestrator
    DATABASE_AVAILABLE = True
except ImportError as e:
    log_warning(f"DatabaseOrchestrator not available: {e}")
    DATABASE_AVAILABLE = False
    DatabaseOrchestrator = None

try:
    from .images.image_orchestrator import ImageOrchestrator
    IMAGE_AVAILABLE = True
except ImportError as e:
    log_warning(f"ImageOrchestrator not available: {e}")
    IMAGE_AVAILABLE = False
    ImageOrchestrator = None

try:
    from .content.context import ContextOrchestrator
    CONTEXT_AVAILABLE = True
except ImportError as e:
    log_warning(f"ContextOrchestrator not available: {e}")
    CONTEXT_AVAILABLE = False
    ContextOrchestrator = None

try:
    from .content.analysis import ContentAnalysisOrchestrator
    ANALYSIS_AVAILABLE = True
except ImportError as e:
    log_warning(f"ContentAnalysisOrchestrator not available: {e}")
    ANALYSIS_AVAILABLE = False
    ContentAnalysisOrchestrator = None

try:
    from .performance import PerformanceOrchestrator, ModelPerformanceMonitor
    PERFORMANCE_AVAILABLE = True
except ImportError as e:
    log_warning(f"Performance modules not available: {e}")
    PERFORMANCE_AVAILABLE = False
    PerformanceOrchestrator = None
    ModelPerformanceMonitor = None

# === UTILITY FUNCTIONS ===

@dataclass
class CoreStatus:
    """System health status for core components."""
    available_orchestrators: List[str]
    unavailable_orchestrators: List[str]
    total_count: int
    availability_percentage: float
    core_initialized: bool = False
    

def get_version() -> str:
    """Get OpenChronicle core version."""
    try:
        from .. import __version__
        return __version__
    except ImportError:
        return "development"


def get_available_orchestrators() -> Dict[str, bool]:
    """Get availability status of all orchestrators."""
    return {
        'ModelOrchestrator': MODEL_AVAILABLE,
        'MemoryOrchestrator': MEMORY_AVAILABLE,
        'SceneOrchestrator': SCENE_AVAILABLE,
        'NarrativeOrchestrator': NARRATIVE_AVAILABLE,
        'ContextOrchestrator': CONTEXT_AVAILABLE,
        'CharacterOrchestrator': CHARACTER_AVAILABLE,
        'TimelineOrchestrator': TIMELINE_AVAILABLE,
        'DatabaseOrchestrator': DATABASE_AVAILABLE,
        'ImageOrchestrator': IMAGE_AVAILABLE,
        'ContextOrchestrator': CONTEXT_AVAILABLE,
        'ContentAnalysisOrchestrator': ANALYSIS_AVAILABLE,
        'PerformanceOrchestrator': PERFORMANCE_AVAILABLE,
        'ModelPerformanceMonitor': PERFORMANCE_AVAILABLE,
    }


async def health_check() -> CoreStatus:
    """
    Perform comprehensive health check of core systems.
    
    Returns:
        CoreStatus: Detailed health information
    """
    log_system_event("system", "Core health check initiated")
    
    orchestrators = get_available_orchestrators()
    available = [name for name, status in orchestrators.items() if status]
    unavailable = [name for name, status in orchestrators.items() if not status]
    
    total = len(orchestrators)
    availability = (len(available) / total) * 100 if total > 0 else 0
    
    status = CoreStatus(
        available_orchestrators=available,
        unavailable_orchestrators=unavailable,
        total_count=total,
        availability_percentage=availability,
        core_initialized=True
    )
    
    if availability < 50:
        log_error(f"Core system health critical: {availability:.1f}% availability")
    elif availability < 80:
        log_warning(f"Core system health degraded: {availability:.1f}% availability")
    else:
        log_info(f"Core system health good: {availability:.1f}% availability")
    
    return status


async def initialize_core(config_path: Optional[str] = None) -> bool:
    """
    Initialize core OpenChronicle systems.
    
    Args:
        config_path: Optional path to configuration directory
        
    Returns:
        bool: True if initialization successful
    """
    try:
        log_system_event("system", "Core initialization started")
        
        # Initialize dependency injection container
        container = get_container()
        log_info("Dependency injection container initialized")
        
        # Load centralized configuration
        if config_path:
            config = CentralizedConfigManager(config_path)
        else:
            config = CentralizedConfigManager()
        log_info("Centralized configuration loaded")
        
        # Perform health check
        status = await health_check()
        
        if status.availability_percentage >= 50:
            log_system_event("system", f"Core initialization successful - {status.availability_percentage:.1f}% availability")
            return True
        else:
            log_error(f"Core initialization failed - only {status.availability_percentage:.1f}% availability")
            return False
            
    except Exception as e:
        log_error(f"Core initialization failed: {e}")
        return False


def create_model_orchestrator(*args, **kwargs) -> Optional[ModelOrchestrator]:
    """Factory function for ModelOrchestrator with error handling."""
    if not MODEL_AVAILABLE:
        log_error("ModelOrchestrator not available")
        return None
    return ModelOrchestrator(*args, **kwargs)


def create_scene_orchestrator(*args, **kwargs) -> Optional[SceneOrchestrator]:
    """Factory function for SceneOrchestrator with error handling."""
    if not SCENE_AVAILABLE:
        log_error("SceneOrchestrator not available")
        return None
    return SceneOrchestrator(*args, **kwargs)


def create_memory_orchestrator(*args, **kwargs) -> Optional[MemoryOrchestrator]:
    """Factory function for MemoryOrchestrator with error handling."""
    if not MEMORY_AVAILABLE:
        log_error("MemoryOrchestrator not available")
        return None
    return MemoryOrchestrator(*args, **kwargs)


# === PUBLIC API ===
# What gets exposed when using "from core import ..."

__all__ = [
    # Primary Orchestrators (Most commonly used)
    'ModelOrchestrator',
    'MemoryOrchestrator', 
    'SceneOrchestrator',
    'NarrativeOrchestrator',
    'ContextOrchestrator',
    
    # Secondary Services (Specialized workflows)
    'CharacterOrchestrator',
    'TimelineOrchestrator',
    'DatabaseOrchestrator',
    'ImageOrchestrator',
    'ContextOrchestrator',
    'ContentAnalysisOrchestrator',
    
    # Performance Monitoring
    'PerformanceOrchestrator',
    'ModelPerformanceMonitor',
    
    # Utility Functions
    'initialize_core',
    'health_check',
    'get_version',
    'get_available_orchestrators',
    
    # Factory Functions (Recommended)
    'create_model_orchestrator',
    'create_scene_orchestrator', 
    'create_memory_orchestrator',
    
    # Data Classes
    'CoreStatus',
    
    # Core Infrastructure (from __init__.py)
    'OpenChronicleError',
    'get_container',
]

# Initialize logging
log_system_event("system", f"Core main module loaded - version {get_version()}")
