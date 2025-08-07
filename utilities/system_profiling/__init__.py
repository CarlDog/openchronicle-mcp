#!/usr/bin/env python3
"""
OpenChronicle System Profiling Package

Modular system profiling system following SOLID principles.
Clean replacement for the monolithic system_profiler.py utility.

Architecture:
- Hardware specs collection (SystemSpecsCollector)
- Model benchmarking (ModelBenchmarkRunner)  
- Recommendation generation (RecommendationEngine)
- System analysis (SystemAnalyzer)
- Profile storage (ProfileDataStorage)
- Orchestration (SystemProfilingOrchestrator)

Example Usage:
    # Basic usage with defaults
    orchestrator = SystemProfilingOrchestrator()
    profile = await orchestrator.run_complete_profile(model_manager)
    
    # Quick system check
    summary = orchestrator.get_system_summary()
    
    # Custom configuration
    config = BenchmarkConfig(timeout_seconds=30, max_models_parallel=2)
    profile = await orchestrator.run_complete_profile(model_manager, config)
    
    # Hardware specs only
    specs = await orchestrator.run_hardware_profile_only()
"""

# Core orchestrator and interfaces
from .orchestrator import SystemProfilingOrchestrator, MockSystemProfilingOrchestrator
from .interfaces import (
    # Data classes
    SystemSpecs,
    ModelBenchmark,
    ModelRecommendation,
    SystemProfile,
    BenchmarkConfig,
    
    # Interfaces
    ISystemSpecsCollector,
    IModelBenchmarkRunner,
    IRecommendationEngine,
    IProfileDataStorage,
    ISystemAnalyzer,
    ISystemProfilingOrchestrator,
)

# Individual components (for advanced usage)
from .hardware import SystemSpecsCollector, MockSystemSpecsCollector
from .benchmarking import ModelBenchmarkRunner, MockModelBenchmarkRunner
from .analysis import RecommendationEngine, MockRecommendationEngine, SystemAnalyzer, MockSystemAnalyzer
from .storage import ProfileDataStorage, MockProfileDataStorage

# Primary exports for typical usage
__all__ = [
    # Main orchestrator (primary interface)
    'SystemProfilingOrchestrator',
    'MockSystemProfilingOrchestrator',
    
    # Data classes
    'SystemSpecs',
    'ModelBenchmark',
    'ModelRecommendation',
    'SystemProfile',
    'BenchmarkConfig',
    
    # Core interfaces (for dependency injection)
    'ISystemSpecsCollector',
    'IModelBenchmarkRunner',
    'IRecommendationEngine',
    'IProfileDataStorage',
    'ISystemAnalyzer',
    'ISystemProfilingOrchestrator',
    
    # Production implementations
    'SystemSpecsCollector',
    'ModelBenchmarkRunner',
    'RecommendationEngine',
    'SystemAnalyzer',
    'ProfileDataStorage',
    
    # Mock implementations (for testing)
    'MockSystemSpecsCollector',
    'MockModelBenchmarkRunner',
    'MockRecommendationEngine',
    'MockSystemAnalyzer',
    'MockProfileDataStorage',
]


# Convenience factory function
def create_system_profiler(**kwargs) -> SystemProfilingOrchestrator:
    """
    Factory function to create a SystemProfilingOrchestrator with optional custom components.
    
    Args:
        **kwargs: Optional component implementations for dependency injection
            - specs_collector: ISystemSpecsCollector implementation
            - benchmark_runner: IModelBenchmarkRunner implementation  
            - recommendation_engine: IRecommendationEngine implementation
            - system_analyzer: ISystemAnalyzer implementation
            - profile_storage: IProfileDataStorage implementation
    
    Returns:
        Configured SystemProfilingOrchestrator instance
    """
    return SystemProfilingOrchestrator(**kwargs)


def create_mock_system_profiler() -> MockSystemProfilingOrchestrator:
    """
    Factory function to create a mock SystemProfilingOrchestrator for testing.
    
    Returns:
        MockSystemProfilingOrchestrator instance with all mock components
    """
    return MockSystemProfilingOrchestrator()


# Package metadata
__version__ = "1.0.0"
__author__ = "OpenChronicle Development Team"
__description__ = "Modular system profiling for AI model performance analysis"
