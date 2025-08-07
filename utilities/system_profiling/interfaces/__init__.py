#!/usr/bin/env python3
"""
OpenChronicle System Profiling Interfaces Package

Clean interface exports for the modular system profiling system.
"""

from .profiling_interfaces import (
    # Data Classes
    SystemSpecs,
    ModelBenchmark,
    ModelRecommendation,
    SystemProfile,
    BenchmarkConfig,
    
    # Core Interfaces
    ISystemSpecsCollector,
    IModelBenchmarkRunner,
    IRecommendationEngine,
    IProfileDataStorage,
    ISystemAnalyzer,
    ISystemProfilingOrchestrator,
)

__all__ = [
    # Data Classes
    'SystemSpecs',
    'ModelBenchmark', 
    'ModelRecommendation',
    'SystemProfile',
    'BenchmarkConfig',
    
    # Core Interfaces
    'ISystemSpecsCollector',
    'IModelBenchmarkRunner',
    'IRecommendationEngine',
    'IProfileDataStorage',
    'ISystemAnalyzer',
    'ISystemProfilingOrchestrator',
]
