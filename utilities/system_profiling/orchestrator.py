#!/usr/bin/env python3
"""
OpenChronicle System Profiling Orchestrator

Main orchestrator for the modular system profiling system.
Coordinates all components following SOLID principles.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from .interfaces import (
    ISystemProfilingOrchestrator,
    ISystemSpecsCollector,
    IModelBenchmarkRunner,
    IRecommendationEngine,
    IProfileDataStorage,
    ISystemAnalyzer,
    SystemProfile,
    SystemSpecs,
    ModelBenchmark,
    BenchmarkConfig
)

from .hardware import SystemSpecsCollector
from .benchmarking import ModelBenchmarkRunner
from .analysis import RecommendationEngine, SystemAnalyzer
from .storage import ProfileDataStorage


class SystemProfilingOrchestrator(ISystemProfilingOrchestrator):
    """
    Production orchestrator that coordinates all system profiling components.
    
    Follows the orchestrator pattern from performance monitoring success.
    """
    
    def __init__(self,
                 specs_collector: Optional[ISystemSpecsCollector] = None,
                 benchmark_runner: Optional[IModelBenchmarkRunner] = None,
                 recommendation_engine: Optional[IRecommendationEngine] = None,
                 system_analyzer: Optional[ISystemAnalyzer] = None,
                 profile_storage: Optional[IProfileDataStorage] = None):
        """
        Initialize orchestrator with dependency injection.
        
        Args:
            specs_collector: Hardware specs collection implementation
            benchmark_runner: Model benchmarking implementation  
            recommendation_engine: Recommendation generation implementation
            system_analyzer: System analysis implementation
            profile_storage: Profile storage implementation
        """
        # Use provided implementations or create defaults
        self.specs_collector = specs_collector or SystemSpecsCollector()
        self.benchmark_runner = benchmark_runner or ModelBenchmarkRunner()
        self.recommendation_engine = recommendation_engine or RecommendationEngine()
        self.system_analyzer = system_analyzer or SystemAnalyzer()
        self.profile_storage = profile_storage or ProfileDataStorage()
        
        # Cache for recent results
        self._cached_profile = None
        self._cache_timestamp = None
        self._cache_duration_minutes = 30
    
    async def run_complete_profile(self, model_manager: Any, 
                                 config: Optional[BenchmarkConfig] = None) -> SystemProfile:
        """
        Run complete system profiling including hardware specs and model benchmarks.
        
        Args:
            model_manager: The model manager instance for benchmarking
            config: Optional benchmark configuration
            
        Returns:
            Complete SystemProfile with specs, benchmarks, and recommendations
        """
        if config is None:
            config = BenchmarkConfig()
        
        profile_start = datetime.now()
        
        try:
            # Step 1: Collect system specifications
            print("Collecting system specifications...")
            system_specs = self.specs_collector.collect_system_specs()
            
            # Step 2: Run model benchmarks
            print("Running model benchmarks...")
            benchmarks = await self.benchmark_runner.benchmark_all_models(model_manager, config)
            
            # Step 3: Generate recommendations
            print("Generating recommendations...")
            recommendations = self.recommendation_engine.generate_recommendations(
                system_specs, benchmarks
            )
            
            # Step 4: Determine system tier
            system_tier = self.recommendation_engine.categorize_system_tier(system_specs)
            
            # Step 5: Create comprehensive profile
            profile = SystemProfile(
                profile_timestamp=profile_start,
                system_specs=system_specs,
                benchmarks=benchmarks,
                recommendations=recommendations,
                system_tier=system_tier,
                profile_metadata={
                    'profile_duration_seconds': (datetime.now() - profile_start).total_seconds(),
                    'successful_benchmarks': len([b for b in benchmarks if b.success]),
                    'failed_benchmarks': len([b for b in benchmarks if not b.success]),
                    'recommendation_count': len(recommendations),
                    'config_used': {
                        'timeout_seconds': config.timeout_seconds,
                        'test_prompt': config.test_prompt,
                        'max_models_parallel': config.max_models_parallel,
                        'include_quality_test': config.include_quality_test
                    }
                }
            )
            
            # Step 6: Cache the profile
            self._cached_profile = profile
            self._cache_timestamp = datetime.now()
            
            # Step 7: Auto-save profile
            try:
                saved_path = self.profile_storage.save_profile(profile)
                profile.profile_metadata['saved_path'] = saved_path
                print(f"Profile saved to: {saved_path}")
            except Exception as e:
                print(f"Warning: Failed to save profile: {str(e)}")
            
            return profile
            
        except Exception as e:
            # Create minimal profile with error information
            system_specs = self.specs_collector.collect_system_specs()
            
            error_profile = SystemProfile(
                profile_timestamp=profile_start,
                system_specs=system_specs,
                benchmarks=[],
                recommendations=[],
                system_tier=self.recommendation_engine.categorize_system_tier(system_specs),
                profile_metadata={
                    'error': str(e),
                    'profile_failed': True,
                    'error_timestamp': datetime.now().isoformat()
                }
            )
            
            return error_profile
    
    async def run_hardware_profile_only(self) -> SystemSpecs:
        """
        Run hardware profiling only without model benchmarks.
        
        Returns:
            SystemSpecs with hardware information
        """
        return self.specs_collector.collect_system_specs()
    
    async def run_model_benchmarks_only(self, model_manager: Any, 
                                      config: Optional[BenchmarkConfig] = None) -> List[ModelBenchmark]:
        """
        Run model benchmarks only using cached hardware specs.
        
        Args:
            model_manager: The model manager instance
            config: Optional benchmark configuration
            
        Returns:
            List of ModelBenchmark results
        """
        if config is None:
            config = BenchmarkConfig()
        
        return await self.benchmark_runner.benchmark_all_models(model_manager, config)
    
    def get_cached_profile(self) -> Optional[SystemProfile]:
        """
        Get the most recent cached profile if still valid.
        
        Returns:
            Cached SystemProfile or None if cache expired/empty
        """
        if not self._cached_profile or not self._cache_timestamp:
            return None
        
        # Check cache validity
        cache_age_minutes = (datetime.now() - self._cache_timestamp).total_seconds() / 60
        if cache_age_minutes > self._cache_duration_minutes:
            return None
        
        return self._cached_profile
    
    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of system capabilities and recommendations.
        
        Returns:
            Dictionary with system summary information
        """
        # Get basic system specs
        system_specs = self.specs_collector.collect_system_specs()
        
        # Run system analysis
        capabilities = self.system_analyzer.analyze_system_capabilities(system_specs)
        baseline_comparison = self.system_analyzer.compare_with_baseline(system_specs)
        
        # Check for cached benchmarks
        cached_profile = self.get_cached_profile()
        if cached_profile:
            recent_benchmarks = cached_profile.benchmarks
            recent_recommendations = cached_profile.recommendations
            optimization_suggestions = self.system_analyzer.generate_optimization_suggestions(
                system_specs, recent_benchmarks
            )
        else:
            recent_benchmarks = []
            recent_recommendations = []
            optimization_suggestions = self.system_analyzer.generate_optimization_suggestions(
                system_specs, []
            )
        
        # Performance bottlenecks
        bottlenecks = self.recommendation_engine.analyze_performance_bottlenecks(
            system_specs, recent_benchmarks
        )
        
        summary = {
            'system_overview': {
                'platform': system_specs.platform,
                'cpu_cores': system_specs.cpu_cores,
                'total_memory_gb': system_specs.total_memory,
                'available_memory_gb': system_specs.available_memory,
                'cpu_brand': system_specs.cpu_brand,
                'system_tier': self.recommendation_engine.categorize_system_tier(system_specs)
            },
            'performance_analysis': {
                'overall_score': capabilities['overall_score'],
                'performance_class': capabilities['performance_class'],
                'cpu_analysis': capabilities['cpu_analysis'],
                'memory_analysis': capabilities['memory_analysis'],
                'capability_summary': capabilities['capability_summary']
            },
            'baseline_comparison': baseline_comparison,
            'model_suitability': capabilities['model_suitability'],
            'recent_benchmarks_summary': {
                'total_benchmarks': len(recent_benchmarks),
                'successful_benchmarks': len([b for b in recent_benchmarks if b.success]),
                'average_response_time': (
                    sum(b.response_time for b in recent_benchmarks if b.success) / 
                    max(1, len([b for b in recent_benchmarks if b.success]))
                ) if recent_benchmarks else None,
                'cache_age_minutes': (
                    (datetime.now() - self._cache_timestamp).total_seconds() / 60
                    if self._cache_timestamp else None
                )
            },
            'recommendations_summary': {
                'total_recommendations': len(recent_recommendations),
                'top_recommendations': [
                    {
                        'model': rec.model_name,
                        'confidence': rec.confidence_score,
                        'use_cases': rec.recommended_for
                    }
                    for rec in sorted(recent_recommendations, 
                                    key=lambda r: r.confidence_score, reverse=True)[:3]
                ]
            },
            'optimization_suggestions': optimization_suggestions,
            'performance_bottlenecks': bottlenecks,
            'summary_metadata': {
                'generated_timestamp': datetime.now().isoformat(),
                'has_recent_benchmarks': len(recent_benchmarks) > 0,
                'cache_status': 'valid' if cached_profile else 'expired_or_empty'
            }
        }
        
        return summary
    
    # Additional utility methods
    async def quick_system_check(self, model_manager: Any) -> Dict[str, Any]:
        """
        Perform a quick system check with minimal benchmarking.
        
        Args:
            model_manager: The model manager instance
            
        Returns:
            Dictionary with quick check results
        """
        # Get system specs
        system_specs = self.specs_collector.collect_system_specs()
        
        # Run quick benchmark on first available model
        available_models = self._get_available_models(model_manager)
        if available_models:
            quick_benchmark = await self.benchmark_runner.quick_benchmark(
                model_manager, available_models[0]
            )
            benchmarks = [quick_benchmark]
        else:
            benchmarks = []
        
        # Generate basic recommendations
        recommendations = self.recommendation_engine.generate_recommendations(
            system_specs, benchmarks
        )
        
        # Analyze capabilities
        capabilities = self.system_analyzer.analyze_system_capabilities(system_specs)
        
        return {
            'system_tier': self.recommendation_engine.categorize_system_tier(system_specs),
            'performance_class': capabilities['performance_class'],
            'overall_score': capabilities['overall_score'],
            'quick_benchmark': {
                'model_tested': benchmarks[0].model_name if benchmarks else None,
                'success': benchmarks[0].success if benchmarks else False,
                'response_time': benchmarks[0].response_time if benchmarks else None
            } if benchmarks else None,
            'top_recommendation': recommendations[0] if recommendations else None,
            'key_specs': {
                'cpu_cores': system_specs.cpu_cores,
                'memory_gb': system_specs.total_memory,
                'platform': system_specs.platform
            }
        }
    
    def _get_available_models(self, model_manager: Any) -> List[str]:
        """Get list of available model names from model manager."""
        try:
            if hasattr(model_manager, 'registry') and model_manager.registry:
                return model_manager.registry.list_models()
            elif hasattr(model_manager, 'adapters') and model_manager.adapters:
                return list(model_manager.adapters.keys())
            else:
                return []
        except Exception:
            return []


class MockSystemProfilingOrchestrator(ISystemProfilingOrchestrator):
    """Mock implementation for testing purposes."""
    
    def __init__(self):
        from .hardware import MockSystemSpecsCollector
        from .benchmarking import MockModelBenchmarkRunner
        from .analysis import MockRecommendationEngine, MockSystemAnalyzer
        from .storage import MockProfileDataStorage
        
        self.specs_collector = MockSystemSpecsCollector()
        self.benchmark_runner = MockModelBenchmarkRunner()
        self.recommendation_engine = MockRecommendationEngine()
        self.system_analyzer = MockSystemAnalyzer()
        self.profile_storage = MockProfileDataStorage()
    
    async def run_complete_profile(self, model_manager: Any, 
                                 config: Optional[BenchmarkConfig] = None) -> SystemProfile:
        """Return mock complete profile."""
        system_specs = self.specs_collector.collect_system_specs()
        benchmarks = await self.benchmark_runner.benchmark_all_models(model_manager, config or BenchmarkConfig())
        recommendations = self.recommendation_engine.generate_recommendations(system_specs, benchmarks)
        
        return SystemProfile(
            profile_timestamp=datetime.now(),
            system_specs=system_specs,
            benchmarks=benchmarks,
            recommendations=recommendations,
            system_tier="medium",
            profile_metadata={'mock': True}
        )
    
    async def run_hardware_profile_only(self) -> SystemSpecs:
        """Return mock hardware specs."""
        return self.specs_collector.collect_system_specs()
    
    async def run_model_benchmarks_only(self, model_manager: Any, 
                                      config: Optional[BenchmarkConfig] = None) -> List[ModelBenchmark]:
        """Return mock benchmarks."""
        return await self.benchmark_runner.benchmark_all_models(model_manager, config or BenchmarkConfig())
    
    def get_cached_profile(self) -> Optional[SystemProfile]:
        """Return None for mock (no caching)."""
        return None
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Return mock system summary."""
        return {
            'system_overview': {'platform': 'Mock OS', 'cpu_cores': 8, 'total_memory_gb': 16.0},
            'performance_analysis': {'overall_score': 0.75, 'performance_class': 'Medium'},
            'summary_metadata': {'generated_timestamp': datetime.now().isoformat()}
        }
