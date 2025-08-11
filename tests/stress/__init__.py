"""
OpenChronicle Stress Testing Module.

This module provides comprehensive stress testing capabilities for validating
production-grade reliability and performance of the OpenChronicle system.

Features:
- Orchestrator stress testing
- Database integrity validation under load
- Memory pressure testing  
- Performance regression detection
- Chaos engineering scenarios
- Production readiness validation

Usage:
    # Run all stress tests
    python -m pytest tests/stress/ -v -m stress
    
    # Run production tests only
    python -m pytest tests/stress/ -v -m production
    
    # Run quick validation
    python -m pytest tests/stress/ -v -m "stress and not chaos and not production"

Marks:
    stress: All stress tests
    performance: Performance regression tests
    chaos: Chaos engineering tests
    production: Production readiness tests
"""

from .stress_testing_framework import StressTestConfig
from .stress_testing_framework import StressTestingFramework
from .stress_testing_framework import StressTestResult
from .stress_testing_framework import create_stress_test_config
from .stress_testing_framework import create_stress_testing_framework
from .test_stress_comprehensive import run_production_stress_tests
from .test_stress_comprehensive import run_quick_stress_validation


__all__ = [
    'StressTestConfig',
    'StressTestResult',
    'StressTestingFramework',
    'create_stress_test_config',
    'create_stress_testing_framework',
    'run_production_stress_tests',
    'run_quick_stress_validation'
]

# Module version
__version__ = '1.0.0'
