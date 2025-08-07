#!/usr/bin/env python3
"""
OpenChronicle Recommendation Engine

Model recommendation generation implementation following SOLID principles.
Focused responsibility: Analyze system specs and benchmarks to generate recommendations.
"""

from typing import Dict, List, Any
from dataclasses import dataclass

from ..interfaces import IRecommendationEngine, SystemSpecs, ModelBenchmark, ModelRecommendation


@dataclass
class SystemTierCriteria:
    """Criteria for categorizing system performance tiers."""
    min_cpu_cores: int
    min_memory_gb: float
    min_cpu_frequency_mhz: float


class RecommendationEngine(IRecommendationEngine):
    """Production implementation of model recommendation generation."""
    
    def __init__(self):
        # Define system tier criteria
        self.tier_criteria = {
            'premium': SystemTierCriteria(min_cpu_cores=12, min_memory_gb=32.0, min_cpu_frequency_mhz=3000.0),
            'high': SystemTierCriteria(min_cpu_cores=8, min_memory_gb=16.0, min_cpu_frequency_mhz=2500.0),
            'medium': SystemTierCriteria(min_cpu_cores=4, min_memory_gb=8.0, min_cpu_frequency_mhz=2000.0),
            'low': SystemTierCriteria(min_cpu_cores=2, min_memory_gb=4.0, min_cpu_frequency_mhz=1500.0)
        }
        
        # Use case performance requirements
        self.use_case_requirements = {
            'fast_responses': {'max_response_time': 3.0, 'min_tokens_per_second': 15.0},
            'analysis': {'min_quality_score': 0.7, 'max_memory_usage': 500.0},
            'creative': {'min_quality_score': 0.6, 'prefer_variety': True},
            'batch_processing': {'max_memory_usage': 300.0, 'min_tokens_per_second': 10.0},
            'interactive': {'max_response_time': 5.0, 'min_quality_score': 0.5}
        }
    
    def generate_recommendations(self, system_specs: SystemSpecs, 
                               benchmarks: List[ModelBenchmark]) -> List[ModelRecommendation]:
        """
        Generate comprehensive model recommendations based on system analysis.
        
        Args:
            system_specs: System hardware specifications
            benchmarks: List of model benchmark results
            
        Returns:
            List of ModelRecommendation objects sorted by confidence
        """
        recommendations = []
        system_tier = self.categorize_system_tier(system_specs)
        
        # Filter successful benchmarks
        successful_benchmarks = [b for b in benchmarks if b.success]
        
        if not successful_benchmarks:
            return recommendations
        
        # Generate recommendations for each successful model
        for benchmark in successful_benchmarks:
            recommendation = self._create_recommendation_for_model(
                benchmark, system_specs, system_tier
            )
            if recommendation:
                recommendations.append(recommendation)
        
        # Sort by confidence score (highest first)
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
        
        return recommendations
    
    def recommend_for_use_case(self, use_case: str, system_specs: SystemSpecs,
                             benchmarks: List[ModelBenchmark]) -> List[ModelRecommendation]:
        """
        Generate recommendations optimized for a specific use case.
        
        Args:
            use_case: The target use case (e.g., 'fast_responses', 'analysis')
            system_specs: System hardware specifications
            benchmarks: List of model benchmark results
            
        Returns:
            List of ModelRecommendation objects for the use case
        """
        if use_case not in self.use_case_requirements:
            # Fallback to general recommendations
            return self.generate_recommendations(system_specs, benchmarks)
        
        requirements = self.use_case_requirements[use_case]
        successful_benchmarks = [b for b in benchmarks if b.success]
        recommendations = []
        
        for benchmark in successful_benchmarks:
            if self._meets_use_case_requirements(benchmark, requirements):
                recommendation = self._create_use_case_recommendation(
                    benchmark, use_case, requirements, system_specs
                )
                if recommendation:
                    recommendations.append(recommendation)
        
        # Sort by confidence score
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
        
        return recommendations
    
    def categorize_system_tier(self, system_specs: SystemSpecs) -> str:
        """
        Categorize system into performance tiers.
        
        Args:
            system_specs: System hardware specifications
            
        Returns:
            System tier: 'low', 'medium', 'high', or 'premium'
        """
        # Check tiers from highest to lowest
        for tier_name in ['premium', 'high', 'medium', 'low']:
            criteria = self.tier_criteria[tier_name]
            
            if (system_specs.cpu_cores >= criteria.min_cpu_cores and
                system_specs.total_memory >= criteria.min_memory_gb and
                system_specs.cpu_frequency_max >= criteria.min_cpu_frequency_mhz):
                return tier_name
        
        return 'low'  # Default fallback
    
    def analyze_performance_bottlenecks(self, system_specs: SystemSpecs, 
                                      benchmarks: List[ModelBenchmark]) -> List[str]:
        """
        Identify potential performance bottlenecks.
        
        Args:
            system_specs: System hardware specifications
            benchmarks: List of model benchmark results
            
        Returns:
            List of bottleneck descriptions
        """
        bottlenecks = []
        
        # Memory analysis
        if system_specs.memory_usage_percent > 80:
            bottlenecks.append("High memory usage detected - consider closing other applications")
        
        if system_specs.total_memory < 8.0:
            bottlenecks.append("Limited RAM (< 8GB) may affect model performance")
        
        # CPU analysis
        if system_specs.cpu_cores < 4:
            bottlenecks.append("Limited CPU cores may slow down model initialization")
        
        if system_specs.cpu_frequency_max < 2000:
            bottlenecks.append("Low CPU frequency may impact response times")
        
        # Disk analysis
        if system_specs.disk_usage_percent > 90:
            bottlenecks.append("Low disk space may affect model caching and performance")
        
        # Benchmark analysis
        successful_benchmarks = [b for b in benchmarks if b.success]
        if successful_benchmarks:
            avg_response_time = sum(b.response_time for b in successful_benchmarks) / len(successful_benchmarks)
            if avg_response_time > 10.0:
                bottlenecks.append("Slow average response times detected across models")
            
            high_memory_models = [b for b in successful_benchmarks if b.memory_usage_mb > 1000]
            if len(high_memory_models) > len(successful_benchmarks) * 0.5:
                bottlenecks.append("Many models require high memory - consider lighter alternatives")
        
        return bottlenecks
    
    def _create_recommendation_for_model(self, benchmark: ModelBenchmark, 
                                       system_specs: SystemSpecs, 
                                       system_tier: str) -> ModelRecommendation:
        """Create a general recommendation for a model."""
        confidence_score = self._calculate_confidence_score(benchmark, system_specs)
        
        # Determine what this model is recommended for
        recommended_for = []
        
        if benchmark.response_time <= 3.0:
            recommended_for.append("fast_responses")
        
        if benchmark.quality_score and benchmark.quality_score >= 0.7:
            recommended_for.append("analysis")
        
        if benchmark.quality_score and benchmark.quality_score >= 0.6:
            recommended_for.append("creative")
        
        if benchmark.memory_usage_mb <= 300.0:
            recommended_for.append("batch_processing")
        
        if benchmark.response_time <= 5.0:
            recommended_for.append("interactive")
        
        # Create rationale
        rationale_parts = []
        rationale_parts.append(f"Suitable for {system_tier} tier systems")
        
        if benchmark.response_time <= 3.0:
            rationale_parts.append("fast response times")
        
        if benchmark.memory_usage_mb <= 200.0:
            rationale_parts.append("low memory usage")
        
        if benchmark.quality_score and benchmark.quality_score >= 0.7:
            rationale_parts.append("high quality output")
        
        rationale = f"{benchmark.model_name}: " + ", ".join(rationale_parts)
        
        # Estimated performance
        estimated_performance = {
            'response_time_seconds': benchmark.response_time,
            'memory_usage_mb': benchmark.memory_usage_mb,
            'quality_score': benchmark.quality_score or 0.0,
            'tokens_per_second': benchmark.tokens_per_second or 0.0
        }
        
        # Configuration suggestions
        config_suggestions = self._generate_config_suggestions(benchmark, system_specs)
        
        return ModelRecommendation(
            model_name=benchmark.model_name,
            adapter_type=benchmark.adapter_type,
            confidence_score=confidence_score,
            recommended_for=recommended_for,
            rationale=rationale,
            estimated_performance=estimated_performance,
            configuration_suggestions=config_suggestions
        )
    
    def _create_use_case_recommendation(self, benchmark: ModelBenchmark, use_case: str,
                                      requirements: Dict, system_specs: SystemSpecs) -> ModelRecommendation:
        """Create a use case specific recommendation."""
        # Calculate confidence based on how well it meets requirements
        confidence_score = self._calculate_use_case_confidence(benchmark, requirements)
        
        rationale = f"Optimized for {use_case}: meets "
        rationale_parts = []
        
        if 'max_response_time' in requirements and benchmark.response_time <= requirements['max_response_time']:
            rationale_parts.append("response time requirements")
        
        if 'min_quality_score' in requirements and benchmark.quality_score and benchmark.quality_score >= requirements['min_quality_score']:
            rationale_parts.append("quality standards")
        
        if 'max_memory_usage' in requirements and benchmark.memory_usage_mb <= requirements['max_memory_usage']:
            rationale_parts.append("memory constraints")
        
        rationale += ", ".join(rationale_parts)
        
        estimated_performance = {
            'response_time_seconds': benchmark.response_time,
            'memory_usage_mb': benchmark.memory_usage_mb,
            'quality_score': benchmark.quality_score or 0.0,
            'tokens_per_second': benchmark.tokens_per_second or 0.0,
            'use_case_fit': confidence_score
        }
        
        config_suggestions = self._generate_use_case_config(use_case, benchmark, system_specs)
        
        return ModelRecommendation(
            model_name=benchmark.model_name,
            adapter_type=benchmark.adapter_type,
            confidence_score=confidence_score,
            recommended_for=[use_case],
            rationale=rationale,
            estimated_performance=estimated_performance,
            configuration_suggestions=config_suggestions
        )
    
    def _calculate_confidence_score(self, benchmark: ModelBenchmark, system_specs: SystemSpecs) -> float:
        """Calculate confidence score for general recommendation."""
        score = 0.0
        
        # Base score for successful execution
        if benchmark.success:
            score += 0.3
        
        # Performance score
        if benchmark.response_time <= 5.0:
            score += 0.2
        elif benchmark.response_time <= 10.0:
            score += 0.1
        
        # Memory efficiency score
        memory_ratio = benchmark.memory_usage_mb / (system_specs.total_memory * 1024)
        if memory_ratio <= 0.1:  # Less than 10% of total memory
            score += 0.2
        elif memory_ratio <= 0.2:
            score += 0.1
        
        # Quality score (if available)
        if benchmark.quality_score:
            score += benchmark.quality_score * 0.3
        
        return min(1.0, score)
    
    def _calculate_use_case_confidence(self, benchmark: ModelBenchmark, requirements: Dict) -> float:
        """Calculate confidence score for use case specific recommendation."""
        score = 0.0
        met_requirements = 0
        total_requirements = len(requirements)
        
        if 'max_response_time' in requirements:
            if benchmark.response_time <= requirements['max_response_time']:
                met_requirements += 1
                score += 0.25
        
        if 'min_quality_score' in requirements:
            if benchmark.quality_score and benchmark.quality_score >= requirements['min_quality_score']:
                met_requirements += 1
                score += 0.25
        
        if 'max_memory_usage' in requirements:
            if benchmark.memory_usage_mb <= requirements['max_memory_usage']:
                met_requirements += 1
                score += 0.25
        
        if 'min_tokens_per_second' in requirements:
            if benchmark.tokens_per_second and benchmark.tokens_per_second >= requirements['min_tokens_per_second']:
                met_requirements += 1
                score += 0.25
        
        # Bonus for meeting all requirements
        if met_requirements == total_requirements:
            score += 0.2
        
        return min(1.0, score)
    
    def _meets_use_case_requirements(self, benchmark: ModelBenchmark, requirements: Dict) -> bool:
        """Check if benchmark meets use case requirements."""
        if 'max_response_time' in requirements and benchmark.response_time > requirements['max_response_time']:
            return False
        
        if 'min_quality_score' in requirements:
            if not benchmark.quality_score or benchmark.quality_score < requirements['min_quality_score']:
                return False
        
        if 'max_memory_usage' in requirements and benchmark.memory_usage_mb > requirements['max_memory_usage']:
            return False
        
        if 'min_tokens_per_second' in requirements:
            if not benchmark.tokens_per_second or benchmark.tokens_per_second < requirements['min_tokens_per_second']:
                return False
        
        return True
    
    def _generate_config_suggestions(self, benchmark: ModelBenchmark, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Generate configuration suggestions for a model."""
        suggestions = {}
        
        # Memory-based suggestions
        if benchmark.memory_usage_mb > 500:
            suggestions['memory_optimization'] = 'Consider reducing batch size or context length'
        
        # Performance-based suggestions
        if benchmark.response_time > 10.0:
            suggestions['performance_tuning'] = 'Consider using GPU acceleration if available'
        
        # System-specific suggestions
        if system_specs.total_memory < 8.0:
            suggestions['low_memory_mode'] = 'Enable memory-efficient settings'
        
        if system_specs.cpu_cores < 4:
            suggestions['cpu_optimization'] = 'Reduce concurrent operations'
        
        return suggestions
    
    def _generate_use_case_config(self, use_case: str, benchmark: ModelBenchmark, 
                                system_specs: SystemSpecs) -> Dict[str, Any]:
        """Generate use case specific configuration suggestions."""
        suggestions = {}
        
        if use_case == 'fast_responses':
            suggestions['response_optimization'] = 'Reduce max_tokens for faster responses'
            suggestions['caching'] = 'Enable response caching for repeated queries'
        
        elif use_case == 'analysis':
            suggestions['quality_settings'] = 'Use higher temperature for diverse analysis'
            suggestions['context_length'] = 'Increase context window for comprehensive analysis'
        
        elif use_case == 'creative':
            suggestions['creativity_settings'] = 'Increase temperature and top_p for creativity'
            suggestions['sampling'] = 'Enable nucleus sampling'
        
        elif use_case == 'batch_processing':
            suggestions['batch_optimization'] = 'Process multiple requests in parallel'
            suggestions['memory_management'] = 'Clear model cache between batches'
        
        elif use_case == 'interactive':
            suggestions['interaction_tuning'] = 'Balance speed and quality for user experience'
            suggestions['timeout_settings'] = 'Set reasonable timeouts for interactive use'
        
        return suggestions


class MockRecommendationEngine(IRecommendationEngine):
    """Mock implementation for testing purposes."""
    
    def generate_recommendations(self, system_specs: SystemSpecs, 
                               benchmarks: List[ModelBenchmark]) -> List[ModelRecommendation]:
        """Return mock recommendations."""
        return [
            ModelRecommendation(
                model_name="mock_model_1",
                adapter_type="MockAdapter",
                confidence_score=0.9,
                recommended_for=["fast_responses", "interactive"],
                rationale="High performance mock model",
                estimated_performance={"response_time": 1.0, "quality": 0.8},
                configuration_suggestions={"setting": "optimized"}
            )
        ]
    
    def recommend_for_use_case(self, use_case: str, system_specs: SystemSpecs,
                             benchmarks: List[ModelBenchmark]) -> List[ModelRecommendation]:
        """Return mock use case recommendations."""
        return self.generate_recommendations(system_specs, benchmarks)
    
    def categorize_system_tier(self, system_specs: SystemSpecs) -> str:
        """Return mock system tier."""
        return "medium"
    
    def analyze_performance_bottlenecks(self, system_specs: SystemSpecs, 
                                      benchmarks: List[ModelBenchmark]) -> List[str]:
        """Return mock bottlenecks."""
        return ["Mock bottleneck: Limited memory"]
