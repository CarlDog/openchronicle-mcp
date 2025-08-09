#!/usr/bin/env python3
"""
OpenChronicle System Profiling Tests

Comprehensive test suite for the modular system profiling system.
Tests all components following the SOLID architecture pattern.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from typing import Dict, Any

# Import system profiling components
from utilities.system_profiling import (
    SystemProfilingOrchestrator,
    MockSystemProfilingOrchestrator,
    SystemSpecsCollector,
    MockSystemSpecsCollector,
    ModelBenchmarkRunner,
    MockModelBenchmarkRunner,
    RecommendationEngine,
    MockRecommendationEngine,
    SystemAnalyzer,
    MockSystemAnalyzer,
    ProfileDataStorage,
    MockProfileDataStorage,
    SystemSpecs,
    ModelBenchmark,
    ModelRecommendation,
    SystemProfile,
    BenchmarkConfig,
    create_system_profiler,
    create_mock_system_profiler
)


class TestSystemSpecsCollector:
    """Test system hardware specification collection."""
    
    def test_specs_collector_initialization(self):
        """Test SystemSpecsCollector initialization."""
        collector = SystemSpecsCollector()
        assert collector is not None
        assert collector._cache_duration_seconds == 60
    
    def test_collect_system_specs(self):
        """Test basic system specs collection."""
        collector = SystemSpecsCollector()
        specs = collector.collect_system_specs()
        
        assert isinstance(specs, SystemSpecs)
        assert specs.cpu_cores >= 1
        assert specs.total_memory >= 0.0
        assert specs.platform in ['Windows', 'Linux', 'Darwin', 'Unknown']
        assert specs.python_version is not None
    
    def test_specs_caching(self):
        """Test that specs are cached properly."""
        collector = SystemSpecsCollector()
        
        # First call
        specs1 = collector.collect_system_specs()
        
        # Second call should use cache
        specs2 = collector.collect_system_specs()
        
        assert specs1 == specs2
        assert collector._cached_specs is not None
    
    def test_mock_specs_collector(self):
        """Test mock implementation."""
        mock_collector = MockSystemSpecsCollector()
        specs = mock_collector.collect_system_specs()
        
        assert isinstance(specs, SystemSpecs)
        assert specs.cpu_cores == 8
        assert specs.total_memory == 16.0
        assert specs.cpu_brand == "Mock CPU"


class TestModelBenchmarkRunner:
    """Test model performance benchmarking."""
    
    @pytest.fixture
    def mock_model_manager(self):
        """Create a mock model manager for testing."""
        manager = Mock()
        manager.adapters = {'test_model': Mock()}
        manager.registry = Mock()
        manager.registry.list_models.return_value = ['test_model']
        
        # Mock adapter with async generate_response
        adapter = Mock()
        async def mock_generate_response(prompt):
            return "Test response"
        adapter.generate_response = Mock(side_effect=mock_generate_response)
        manager.adapters['test_model'] = adapter
        
        return manager
    
    @pytest.fixture
    def benchmark_config(self):
        """Create test benchmark configuration."""
        return BenchmarkConfig(
            timeout_seconds=30,
            test_prompt="Test prompt",
            max_models_parallel=1,
            include_quality_test=True
        )
    
    def test_benchmark_runner_initialization(self):
        """Test ModelBenchmarkRunner initialization."""
        runner = ModelBenchmarkRunner()
        assert runner is not None
        assert isinstance(runner._default_config, BenchmarkConfig)
    
    @pytest.mark.asyncio
    async def test_benchmark_single_model(self, mock_model_manager, benchmark_config):
        """Test benchmarking a single model."""
        runner = ModelBenchmarkRunner()
        
        with patch.object(runner, '_get_current_memory_mb', return_value=100.0):
            benchmark = await runner.benchmark_model(
                mock_model_manager, 'test_model', benchmark_config
            )
        
        assert isinstance(benchmark, ModelBenchmark)
        assert benchmark.model_name == 'test_model'
        assert benchmark.success == True
        assert benchmark.response_time >= 0
        assert benchmark.memory_usage_mb >= 0
    
    @pytest.mark.asyncio
    async def test_benchmark_all_models(self, mock_model_manager, benchmark_config):
        """Test benchmarking all available models."""
        runner = ModelBenchmarkRunner()
        
        with patch.object(runner, '_get_current_memory_mb', return_value=100.0):
            benchmarks = await runner.benchmark_all_models(
                mock_model_manager, benchmark_config
            )
        
        assert isinstance(benchmarks, list)
        assert len(benchmarks) > 0
        assert all(isinstance(b, ModelBenchmark) for b in benchmarks)
    
    @pytest.mark.asyncio
    async def test_quick_benchmark(self, mock_model_manager):
        """Test quick benchmarking."""
        runner = ModelBenchmarkRunner()
        
        with patch.object(runner, '_get_current_memory_mb', return_value=50.0):
            benchmark = await runner.quick_benchmark(mock_model_manager, 'test_model')
        
        assert isinstance(benchmark, ModelBenchmark)
        assert benchmark.model_name == 'test_model'
    
    def test_validate_model_availability(self, mock_model_manager):
        """Test model availability validation."""
        runner = ModelBenchmarkRunner()
        
        assert runner.validate_model_availability(mock_model_manager, 'test_model') == True
        assert runner.validate_model_availability(mock_model_manager, 'nonexistent') == False  # Not in adapters
    
    def test_mock_benchmark_runner(self):
        """Test mock implementation."""
        mock_runner = MockModelBenchmarkRunner()
        
        @pytest.mark.asyncio
        async def run_test():
            benchmark = await mock_runner.benchmark_model(None, 'test', BenchmarkConfig())
            assert isinstance(benchmark, ModelBenchmark)
            assert benchmark.success == True
        
        asyncio.run(run_test())


class TestRecommendationEngine:
    """Test model recommendation generation."""
    
    @pytest.fixture
    def sample_system_specs(self):
        """Create sample system specifications."""
        return SystemSpecs(
            cpu_cores=8,
            cpu_physical_cores=4,
            cpu_frequency_max=3000.0,
            cpu_frequency_current=2800.0,
            cpu_brand="Test CPU",
            total_memory=16.0,
            available_memory=8.0,
            memory_usage_percent=50.0,
            platform="Linux",
            architecture="x86_64",
            python_version="3.9.0",
            disk_space_gb=500.0,
            disk_usage_percent=60.0
        )
    
    @pytest.fixture
    def sample_benchmarks(self):
        """Create sample benchmark results."""
        return [
            ModelBenchmark(
                model_name="fast_model",
                adapter_type="FastAdapter",
                initialization_time=0.5,
                response_time=2.0,
                memory_usage_mb=100.0,
                success=True,
                tokens_per_second=20.0,
                quality_score=0.8
            ),
            ModelBenchmark(
                model_name="slow_model",
                adapter_type="SlowAdapter",
                initialization_time=2.0,
                response_time=8.0,
                memory_usage_mb=300.0,
                success=True,
                tokens_per_second=5.0,
                quality_score=0.9
            )
        ]
    
    def test_recommendation_engine_initialization(self):
        """Test RecommendationEngine initialization."""
        engine = RecommendationEngine()
        assert engine is not None
        assert 'premium' in engine.tier_criteria
        assert 'fast_responses' in engine.use_case_requirements
    
    def test_generate_recommendations(self, sample_system_specs, sample_benchmarks):
        """Test generating general recommendations."""
        engine = RecommendationEngine()
        recommendations = engine.generate_recommendations(sample_system_specs, sample_benchmarks)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert all(isinstance(r, ModelRecommendation) for r in recommendations)
        
        # Should be sorted by confidence (highest first)
        if len(recommendations) > 1:
            assert recommendations[0].confidence_score >= recommendations[1].confidence_score
    
    def test_recommend_for_use_case(self, sample_system_specs, sample_benchmarks):
        """Test use case specific recommendations."""
        engine = RecommendationEngine()
        recommendations = engine.recommend_for_use_case(
            'fast_responses', sample_system_specs, sample_benchmarks
        )
        
        assert isinstance(recommendations, list)
        # Fast model should be recommended for fast responses
        fast_recs = [r for r in recommendations if r.model_name == 'fast_model']
        assert len(fast_recs) > 0
    
    def test_categorize_system_tier(self, sample_system_specs):
        """Test system tier categorization."""
        engine = RecommendationEngine()
        tier = engine.categorize_system_tier(sample_system_specs)
        
        assert tier in ['low', 'medium', 'high', 'premium']
        assert tier == 'high'  # Based on sample specs
    
    def test_analyze_performance_bottlenecks(self, sample_system_specs, sample_benchmarks):
        """Test bottleneck analysis."""
        engine = RecommendationEngine()
        bottlenecks = engine.analyze_performance_bottlenecks(sample_system_specs, sample_benchmarks)
        
        assert isinstance(bottlenecks, list)
        # Should detect no major bottlenecks for good system
        assert len(bottlenecks) == 0 or all(isinstance(b, str) for b in bottlenecks)
    
    def test_mock_recommendation_engine(self, sample_system_specs):
        """Test mock implementation."""
        mock_engine = MockRecommendationEngine()
        recommendations = mock_engine.generate_recommendations(sample_system_specs, [])
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0


class TestSystemAnalyzer:
    """Test system capability analysis."""
    
    @pytest.fixture
    def sample_system_specs(self):
        """Create sample system specifications."""
        return SystemSpecs(
            cpu_cores=4,
            cpu_physical_cores=4,
            cpu_frequency_max=2500.0,
            cpu_frequency_current=2400.0,
            cpu_brand="Test CPU",
            total_memory=8.0,
            available_memory=4.0,
            memory_usage_percent=50.0,
            platform="Windows",
            architecture="x64",
            python_version="3.9.0",
            disk_space_gb=250.0,
            disk_usage_percent=70.0
        )
    
    def test_analyzer_initialization(self):
        """Test SystemAnalyzer initialization."""
        analyzer = SystemAnalyzer()
        assert analyzer is not None
        assert 'minimum' in analyzer.baseline_systems
        assert 'cpu_cores' in analyzer.performance_weights
    
    def test_analyze_system_capabilities(self, sample_system_specs):
        """Test comprehensive system analysis."""
        analyzer = SystemAnalyzer()
        analysis = analyzer.analyze_system_capabilities(sample_system_specs)
        
        assert isinstance(analysis, dict)
        assert 'overall_score' in analysis
        assert 'cpu_analysis' in analysis
        assert 'memory_analysis' in analysis
        assert 'performance_class' in analysis
        
        assert 0.0 <= analysis['overall_score'] <= 1.0
        assert analysis['performance_class'] in ['Minimal', 'Low', 'Medium', 'High', 'Premium']
    
    def test_predict_model_performance(self, sample_system_specs):
        """Test model performance prediction."""
        analyzer = SystemAnalyzer()
        requirements = {
            'min_cpu_score': 0.5,
            'min_memory_gb': 4.0,
            'base_response_time': 5.0,
            'base_throughput': 10.0,
            'base_memory_mb': 200.0
        }
        
        predictions = analyzer.predict_model_performance(sample_system_specs, requirements)
        
        assert isinstance(predictions, dict)
        assert 'cpu_performance' in predictions
        assert 'memory_performance' in predictions
        assert 'predicted_response_time' in predictions
        assert 'overall_performance' in predictions
        
        assert all(isinstance(v, (int, float)) for v in predictions.values())
    
    def test_compare_with_baseline(self, sample_system_specs):
        """Test baseline comparison."""
        analyzer = SystemAnalyzer()
        comparison = analyzer.compare_with_baseline(sample_system_specs)
        
        assert isinstance(comparison, dict)
        assert 'minimum' in comparison
        assert 'recommended' in comparison
        assert 'best_match' in comparison
        assert 'match_score' in comparison
        
        # Check that baseline comparisons are strings (except match_score)
        for key, value in comparison.items():
            if key != 'match_score':
                assert isinstance(value, str)
            else:
                assert isinstance(value, (int, float))
    
    def test_generate_optimization_suggestions(self, sample_system_specs):
        """Test optimization suggestions."""
        analyzer = SystemAnalyzer()
        suggestions = analyzer.generate_optimization_suggestions(sample_system_specs, [])
        
        assert isinstance(suggestions, list)
        assert all(isinstance(s, str) for s in suggestions)
    
    def test_mock_analyzer(self, sample_system_specs):
        """Test mock implementation."""
        mock_analyzer = MockSystemAnalyzer()
        analysis = mock_analyzer.analyze_system_capabilities(sample_system_specs)
        
        assert isinstance(analysis, dict)
        assert 'overall_score' in analysis


class TestProfileDataStorage:
    """Test profile data storage and retrieval."""
    
    @pytest.fixture
    def sample_profile(self):
        """Create sample system profile."""
        specs = SystemSpecs(
            cpu_cores=4, cpu_physical_cores=4, cpu_frequency_max=2500.0,
            cpu_frequency_current=2400.0, cpu_brand="Test CPU", total_memory=8.0,
            available_memory=4.0, memory_usage_percent=50.0, platform="Test OS",
            architecture="x64", python_version="3.9.0", disk_space_gb=250.0,
            disk_usage_percent=70.0
        )
        
        benchmark = ModelBenchmark(
            model_name="test_model", adapter_type="TestAdapter",
            initialization_time=1.0, response_time=3.0, memory_usage_mb=150.0,
            success=True, tokens_per_second=15.0, quality_score=0.7
        )
        
        recommendation = ModelRecommendation(
            model_name="test_model", adapter_type="TestAdapter",
            confidence_score=0.8, recommended_for=["testing"],
            rationale="Good for testing", estimated_performance={},
            configuration_suggestions={}
        )
        
        return SystemProfile(
            profile_timestamp=datetime.now(),
            system_specs=specs,
            benchmarks=[benchmark],
            recommendations=[recommendation],
            system_tier="medium",
            profile_metadata={"test": True}
        )
    
    def test_mock_storage_initialization(self):
        """Test mock storage initialization."""
        storage = MockProfileDataStorage()
        assert storage is not None
        assert storage.profiles == {}
    
    def test_mock_save_and_load_profile(self, sample_profile):
        """Test saving and loading profiles with mock storage."""
        storage = MockProfileDataStorage()
        
        # Save profile
        filepath = storage.save_profile(sample_profile)
        assert filepath is not None
        
        # Load profile
        loaded_profile = storage.load_profile(filepath)
        assert loaded_profile is not None
        assert loaded_profile.system_tier == sample_profile.system_tier
        assert len(loaded_profile.benchmarks) == len(sample_profile.benchmarks)
    
    def test_mock_list_and_delete_profiles(self, sample_profile):
        """Test listing and deleting profiles with mock storage."""
        storage = MockProfileDataStorage()
        
        # Save multiple profiles
        filepath1 = storage.save_profile(sample_profile)
        filepath2 = storage.save_profile(sample_profile)
        
        # List profiles
        profiles = storage.list_saved_profiles()
        assert len(profiles) == 2
        assert filepath1 in profiles
        assert filepath2 in profiles
        
        # Delete profile
        assert storage.delete_profile(filepath1) == True
        assert storage.delete_profile(filepath1) == False  # Already deleted
        
        # Check list again
        profiles = storage.list_saved_profiles()
        assert len(profiles) == 1
    
    def test_mock_get_profile_metadata(self, sample_profile):
        """Test getting profile metadata with mock storage."""
        storage = MockProfileDataStorage()
        
        filepath = storage.save_profile(sample_profile)
        metadata = storage.get_profile_metadata(filepath)
        
        assert metadata is not None
        assert 'system_tier' in metadata
        assert metadata['system_tier'] == 'medium'


class TestSystemProfilingOrchestrator:
    """Test the main system profiling orchestrator."""
    
    @pytest.fixture
    def mock_model_manager(self):
        """Create a mock model manager."""
        manager = Mock()
        manager.adapters = {'test_model': Mock()}
        manager.registry = Mock()
        manager.registry.list_models.return_value = ['test_model']
        
        adapter = Mock()
        adapter.generate_response = Mock(return_value="Test response")
        manager.adapters['test_model'] = adapter
        
        return manager
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization with defaults."""
        orchestrator = SystemProfilingOrchestrator()
        
        assert orchestrator is not None
        assert orchestrator.specs_collector is not None
        assert orchestrator.benchmark_runner is not None
        assert orchestrator.recommendation_engine is not None
        assert orchestrator.system_analyzer is not None
        assert orchestrator.profile_storage is not None
    
    def test_orchestrator_dependency_injection(self):
        """Test orchestrator with custom components."""
        mock_collector = MockSystemSpecsCollector()
        mock_runner = MockModelBenchmarkRunner()
        mock_engine = MockRecommendationEngine()
        mock_analyzer = MockSystemAnalyzer()
        mock_storage = MockProfileDataStorage()
        
        orchestrator = SystemProfilingOrchestrator(
            specs_collector=mock_collector,
            benchmark_runner=mock_runner,
            recommendation_engine=mock_engine,
            system_analyzer=mock_analyzer,
            profile_storage=mock_storage
        )
        
        assert orchestrator.specs_collector == mock_collector
        assert orchestrator.benchmark_runner == mock_runner
        assert orchestrator.recommendation_engine == mock_engine
        assert orchestrator.system_analyzer == mock_analyzer
        assert orchestrator.profile_storage == mock_storage
    
    @pytest.mark.asyncio
    async def test_run_complete_profile(self, mock_model_manager):
        """Test running complete profile."""
        orchestrator = MockSystemProfilingOrchestrator()
        
        profile = await orchestrator.run_complete_profile(mock_model_manager)
        
        assert isinstance(profile, SystemProfile)
        assert profile.system_specs is not None
        assert isinstance(profile.benchmarks, list)
        assert isinstance(profile.recommendations, list)
        assert profile.system_tier is not None
    
    @pytest.mark.asyncio
    async def test_run_hardware_profile_only(self):
        """Test hardware-only profiling."""
        orchestrator = MockSystemProfilingOrchestrator()
        
        specs = await orchestrator.run_hardware_profile_only()
        
        assert isinstance(specs, SystemSpecs)
        assert specs.cpu_cores > 0
        assert specs.total_memory > 0
    
    @pytest.mark.asyncio
    async def test_run_model_benchmarks_only(self, mock_model_manager):
        """Test model benchmarking only."""
        orchestrator = MockSystemProfilingOrchestrator()
        
        benchmarks = await orchestrator.run_model_benchmarks_only(mock_model_manager)
        
        assert isinstance(benchmarks, list)
        assert len(benchmarks) > 0
        assert all(isinstance(b, ModelBenchmark) for b in benchmarks)
    
    def test_get_system_summary(self):
        """Test system summary generation."""
        orchestrator = MockSystemProfilingOrchestrator()
        
        summary = orchestrator.get_system_summary()
        
        assert isinstance(summary, dict)
        assert 'system_overview' in summary
        assert 'performance_analysis' in summary
        assert 'summary_metadata' in summary
    
    def test_mock_orchestrator(self):
        """Test mock orchestrator implementation."""
        mock_orchestrator = MockSystemProfilingOrchestrator()
        
        assert mock_orchestrator is not None
        assert isinstance(mock_orchestrator.specs_collector, MockSystemSpecsCollector)
        assert isinstance(mock_orchestrator.benchmark_runner, MockModelBenchmarkRunner)


class TestFactoryFunctions:
    """Test package factory functions."""
    
    def test_create_system_profiler(self):
        """Test factory function for system profiler."""
        profiler = create_system_profiler()
        
        assert isinstance(profiler, SystemProfilingOrchestrator)
        assert profiler.specs_collector is not None
    
    def test_create_mock_system_profiler(self):
        """Test factory function for mock system profiler."""
        mock_profiler = create_mock_system_profiler()
        
        assert isinstance(mock_profiler, MockSystemProfilingOrchestrator)
        assert isinstance(mock_profiler.specs_collector, MockSystemSpecsCollector)


class TestDataClasses:
    """Test data class functionality."""
    
    def test_system_specs_creation(self):
        """Test SystemSpecs data class."""
        specs = SystemSpecs(
            cpu_cores=4, cpu_physical_cores=4, cpu_frequency_max=2500.0,
            cpu_frequency_current=2400.0, cpu_brand="Test CPU", total_memory=8.0,
            available_memory=4.0, memory_usage_percent=50.0, platform="Test OS",
            architecture="x64", python_version="3.9.0", disk_space_gb=250.0,
            disk_usage_percent=70.0
        )
        
        assert specs.cpu_cores == 4
        assert specs.cpu_brand == "Test CPU"
        assert specs.platform == "Test OS"
    
    def test_model_benchmark_creation(self):
        """Test ModelBenchmark data class."""
        benchmark = ModelBenchmark(
            model_name="test_model", adapter_type="TestAdapter",
            initialization_time=1.0, response_time=3.0, memory_usage_mb=150.0,
            success=True, tokens_per_second=15.0, quality_score=0.7
        )
        
        assert benchmark.model_name == "test_model"
        assert benchmark.success == True
        assert benchmark.response_time == 3.0
    
    def test_benchmark_config_creation(self):
        """Test BenchmarkConfig data class."""
        config = BenchmarkConfig(
            timeout_seconds=30,
            test_prompt="Test prompt",
            max_models_parallel=2,
            include_quality_test=True
        )
        
        assert config.timeout_seconds == 30
        assert config.test_prompt == "Test prompt"
        assert config.max_models_parallel == 2


# Integration tests
class TestSystemProfilingIntegration:
    """Integration tests for the complete system profiling workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow_with_mocks(self):
        """Test complete workflow using mock components."""
        # Create orchestrator with all mock components
        orchestrator = create_mock_system_profiler()
        
        # Create mock model manager
        mock_manager = Mock()
        mock_manager.adapters = {'test_model': Mock()}
        mock_manager.registry = Mock()
        mock_manager.registry.list_models.return_value = ['test_model']
        
        # Run complete profile
        profile = await orchestrator.run_complete_profile(mock_manager)
        
        # Verify complete workflow
        assert isinstance(profile, SystemProfile)
        assert profile.system_specs is not None
        assert len(profile.benchmarks) > 0
        assert len(profile.recommendations) > 0
        assert profile.system_tier in ['low', 'medium', 'high', 'premium']
        
        # Test individual components
        specs = await orchestrator.run_hardware_profile_only()
        assert isinstance(specs, SystemSpecs)
        
        benchmarks = await orchestrator.run_model_benchmarks_only(mock_manager)
        assert isinstance(benchmarks, list)
        
        summary = orchestrator.get_system_summary()
        assert isinstance(summary, dict)
    
    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test with None inputs
        orchestrator = create_mock_system_profiler()
        
        # Should handle None gracefully
        summary = orchestrator.get_system_summary()
        assert summary is not None
        
        # Test caching behavior
        cached = orchestrator.get_cached_profile()
        assert cached is None  # Mock doesn't cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
