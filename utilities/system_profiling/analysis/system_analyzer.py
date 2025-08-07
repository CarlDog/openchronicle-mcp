#!/usr/bin/env python3
"""
OpenChronicle System Analyzer

System capability analysis implementation following SOLID principles.
Focused responsibility: Analyze system capabilities and performance characteristics.
"""

from typing import Dict, List, Any
import math

from ..interfaces import ISystemAnalyzer, SystemSpecs, ModelBenchmark


class SystemAnalyzer(ISystemAnalyzer):
    """Production implementation of system capability analysis."""
    
    def __init__(self):
        # Baseline system configurations for comparison
        self.baseline_systems = {
            'minimum': {
                'cpu_cores': 2,
                'total_memory': 4.0,
                'cpu_frequency_max': 1500.0,
                'description': 'Minimum viable system'
            },
            'recommended': {
                'cpu_cores': 4,
                'total_memory': 8.0,
                'cpu_frequency_max': 2500.0,
                'description': 'Recommended baseline system'
            },
            'optimal': {
                'cpu_cores': 8,
                'total_memory': 16.0,
                'cpu_frequency_max': 3000.0,
                'description': 'Optimal performance system'
            },
            'premium': {
                'cpu_cores': 16,
                'total_memory': 32.0,
                'cpu_frequency_max': 3500.0,
                'description': 'Premium high-end system'
            }
        }
        
        # Performance weight factors
        self.performance_weights = {
            'cpu_cores': 0.3,
            'cpu_frequency': 0.25,
            'memory': 0.35,
            'disk_space': 0.1
        }
    
    def analyze_system_capabilities(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """
        Analyze overall system capabilities with detailed breakdown.
        
        Args:
            system_specs: System hardware specifications
            
        Returns:
            Dictionary with comprehensive capability analysis
        """
        analysis = {
            'overall_score': self._calculate_overall_performance_score(system_specs),
            'cpu_analysis': self._analyze_cpu_capabilities(system_specs),
            'memory_analysis': self._analyze_memory_capabilities(system_specs),
            'storage_analysis': self._analyze_storage_capabilities(system_specs),
            'platform_analysis': self._analyze_platform_characteristics(system_specs),
            'model_suitability': self._analyze_model_suitability(system_specs),
            'performance_class': self._classify_performance_level(system_specs),
            'capability_summary': self._generate_capability_summary(system_specs)
        }
        
        return analysis
    
    def predict_model_performance(self, system_specs: SystemSpecs, 
                                model_requirements: Dict[str, Any]) -> Dict[str, float]:
        """
        Predict model performance based on system specs and model requirements.
        
        Args:
            system_specs: System hardware specifications
            model_requirements: Model resource requirements
            
        Returns:
            Dictionary with performance predictions
        """
        predictions = {}
        
        # CPU performance prediction
        cpu_score = self._calculate_cpu_score(system_specs)
        required_cpu = model_requirements.get('min_cpu_score', 0.5)
        predictions['cpu_performance'] = min(1.0, cpu_score / required_cpu)
        
        # Memory performance prediction
        memory_score = self._calculate_memory_score(system_specs)
        required_memory = model_requirements.get('min_memory_gb', 4.0)
        available_ratio = system_specs.available_memory / required_memory
        predictions['memory_performance'] = min(1.0, available_ratio)
        
        # Response time prediction
        base_response_time = model_requirements.get('base_response_time', 5.0)
        performance_factor = self._calculate_overall_performance_score(system_specs)
        predicted_response_time = base_response_time / max(0.1, performance_factor)
        predictions['predicted_response_time'] = predicted_response_time
        
        # Throughput prediction
        base_throughput = model_requirements.get('base_throughput', 10.0)
        predictions['predicted_throughput'] = base_throughput * performance_factor
        
        # Memory usage prediction
        base_memory_usage = model_requirements.get('base_memory_mb', 200.0)
        memory_efficiency = min(1.0, system_specs.available_memory / 8.0)  # Normalize to 8GB
        predictions['predicted_memory_usage'] = base_memory_usage / max(0.5, memory_efficiency)
        
        # Overall performance prediction
        predictions['overall_performance'] = (
            predictions['cpu_performance'] * 0.3 +
            predictions['memory_performance'] * 0.4 +
            min(1.0, 5.0 / predictions['predicted_response_time']) * 0.3
        )
        
        return predictions
    
    def compare_with_baseline(self, system_specs: SystemSpecs) -> Dict[str, str]:
        """
        Compare system specs with baseline configurations.
        
        Args:
            system_specs: System hardware specifications
            
        Returns:
            Dictionary with comparison results
        """
        comparisons = {}
        
        for baseline_name, baseline_config in self.baseline_systems.items():
            comparison_score = self._compare_with_baseline_config(system_specs, baseline_config)
            
            if comparison_score >= 1.0:
                status = "exceeds"
            elif comparison_score >= 0.8:
                status = "meets"
            elif comparison_score >= 0.6:
                status = "approaches"
            else:
                status = "below"
            
            comparisons[baseline_name] = f"{status} ({comparison_score:.2f}x)"
        
        # Find best matching baseline
        scores = {}
        for baseline_name, baseline_config in self.baseline_systems.items():
            scores[baseline_name] = self._compare_with_baseline_config(system_specs, baseline_config)
        
        best_match = max(scores.items(), key=lambda x: x[1] if x[1] <= 1.2 else 0)
        comparisons['best_match'] = best_match[0]
        comparisons['match_score'] = best_match[1]
        
        return comparisons
    
    def generate_optimization_suggestions(self, system_specs: SystemSpecs, 
                                        benchmarks: List[ModelBenchmark]) -> List[str]:
        """
        Generate system optimization suggestions based on specs and benchmarks.
        
        Args:
            system_specs: System hardware specifications
            benchmarks: List of model benchmark results
            
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        
        # Memory optimization suggestions
        if system_specs.memory_usage_percent > 80:
            suggestions.append("High memory usage detected - close unnecessary applications to free RAM")
        
        if system_specs.available_memory < 2.0:
            suggestions.append("Very low available memory - consider upgrading RAM or enabling swap")
        
        if system_specs.total_memory < 8.0:
            suggestions.append("Limited total memory - consider upgrading to at least 8GB RAM")
        
        # CPU optimization suggestions
        if system_specs.cpu_cores < 4:
            suggestions.append("Limited CPU cores - consider upgrading to a multi-core processor")
        
        if system_specs.cpu_frequency_max < 2000:
            suggestions.append("Low CPU frequency - check power settings and thermal throttling")
        
        # Storage optimization suggestions
        if system_specs.disk_usage_percent > 90:
            suggestions.append("Very low disk space - free up storage to improve performance")
        elif system_specs.disk_usage_percent > 75:
            suggestions.append("Limited disk space - consider cleaning up unnecessary files")
        
        # Benchmark-based suggestions
        if benchmarks:
            successful_benchmarks = [b for b in benchmarks if b.success]
            
            if successful_benchmarks:
                avg_response_time = sum(b.response_time for b in successful_benchmarks) / len(successful_benchmarks)
                avg_memory_usage = sum(b.memory_usage_mb for b in successful_benchmarks) / len(successful_benchmarks)
                
                if avg_response_time > 10.0:
                    suggestions.append("Slow model response times - consider using lighter models or GPU acceleration")
                
                if avg_memory_usage > system_specs.available_memory * 1024 * 0.8:
                    suggestions.append("Models using too much memory - reduce batch sizes or use memory-efficient models")
                
                failed_benchmarks = [b for b in benchmarks if not b.success]
                if len(failed_benchmarks) > len(benchmarks) * 0.3:
                    suggestions.append("Many model failures detected - check model configurations and dependencies")
        
        # Platform-specific suggestions
        if system_specs.platform == "Windows":
            if system_specs.memory_usage_percent > 75:
                suggestions.append("Windows: Consider disabling unnecessary startup programs and services")
        elif system_specs.platform == "Linux":
            suggestions.append("Linux: Consider using lightweight models and optimizing kernel parameters")
        elif system_specs.platform == "Darwin":  # macOS
            suggestions.append("macOS: Check Activity Monitor for memory pressure and CPU usage")
        
        # Python-specific suggestions
        python_version = system_specs.python_version
        if python_version.startswith("3.7") or python_version.startswith("3.6"):
            suggestions.append("Consider upgrading Python to version 3.8+ for better performance")
        
        return suggestions
    
    def _calculate_overall_performance_score(self, system_specs: SystemSpecs) -> float:
        """Calculate overall system performance score (0.0 to 1.0+)."""
        cpu_score = self._calculate_cpu_score(system_specs)
        memory_score = self._calculate_memory_score(system_specs)
        storage_score = self._calculate_storage_score(system_specs)
        
        # Weighted average
        overall_score = (
            cpu_score * (self.performance_weights['cpu_cores'] + self.performance_weights['cpu_frequency']) +
            memory_score * self.performance_weights['memory'] +
            storage_score * self.performance_weights['disk_space']
        )
        
        return overall_score
    
    def _calculate_cpu_score(self, system_specs: SystemSpecs) -> float:
        """Calculate CPU performance score."""
        # Normalize cores (1-16+ range)
        core_score = min(1.0, system_specs.cpu_cores / 8.0)
        
        # Normalize frequency (1500-4000+ MHz range)
        freq_score = min(1.0, system_specs.cpu_frequency_max / 3000.0)
        
        # Combine with weights
        cpu_score = (core_score * 0.6 + freq_score * 0.4)
        
        return cpu_score
    
    def _calculate_memory_score(self, system_specs: SystemSpecs) -> float:
        """Calculate memory performance score."""
        # Normalize total memory (4-32+ GB range)
        total_score = min(1.0, system_specs.total_memory / 16.0)
        
        # Available memory efficiency
        available_ratio = system_specs.available_memory / system_specs.total_memory
        efficiency_score = available_ratio  # Higher available ratio is better
        
        # Combine scores
        memory_score = (total_score * 0.7 + efficiency_score * 0.3)
        
        return memory_score
    
    def _calculate_storage_score(self, system_specs: SystemSpecs) -> float:
        """Calculate storage performance score."""
        # Available space score (more available space is better)
        usage_score = max(0.0, 1.0 - (system_specs.disk_usage_percent / 100.0))
        
        # Total space adequacy (500+ GB is optimal)
        space_score = min(1.0, system_specs.disk_space_gb / 500.0)
        
        # Combine scores
        storage_score = (usage_score * 0.6 + space_score * 0.4)
        
        return storage_score
    
    def _analyze_cpu_capabilities(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Analyze CPU-specific capabilities."""
        cpu_score = self._calculate_cpu_score(system_specs)
        
        analysis = {
            'score': cpu_score,
            'cores': system_specs.cpu_cores,
            'physical_cores': system_specs.cpu_physical_cores,
            'max_frequency_ghz': round(system_specs.cpu_frequency_max / 1000.0, 2),
            'current_frequency_ghz': round(system_specs.cpu_frequency_current / 1000.0, 2),
            'brand': system_specs.cpu_brand,
            'multithreading': system_specs.cpu_cores > system_specs.cpu_physical_cores,
            'performance_level': self._classify_cpu_performance(system_specs),
            'recommendations': self._get_cpu_recommendations(system_specs)
        }
        
        return analysis
    
    def _analyze_memory_capabilities(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Analyze memory-specific capabilities."""
        memory_score = self._calculate_memory_score(system_specs)
        
        analysis = {
            'score': memory_score,
            'total_gb': system_specs.total_memory,
            'available_gb': system_specs.available_memory,
            'used_gb': system_specs.total_memory - system_specs.available_memory,
            'usage_percent': system_specs.memory_usage_percent,
            'efficiency': system_specs.available_memory / system_specs.total_memory,
            'adequacy_level': self._classify_memory_adequacy(system_specs),
            'recommendations': self._get_memory_recommendations(system_specs)
        }
        
        return analysis
    
    def _analyze_storage_capabilities(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Analyze storage-specific capabilities."""
        storage_score = self._calculate_storage_score(system_specs)
        
        analysis = {
            'score': storage_score,
            'total_gb': system_specs.disk_space_gb,
            'used_percent': system_specs.disk_usage_percent,
            'free_gb': system_specs.disk_space_gb * (1 - system_specs.disk_usage_percent / 100),
            'space_level': self._classify_storage_adequacy(system_specs),
            'recommendations': self._get_storage_recommendations(system_specs)
        }
        
        return analysis
    
    def _analyze_platform_characteristics(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Analyze platform-specific characteristics."""
        analysis = {
            'platform': system_specs.platform,
            'architecture': system_specs.architecture,
            'python_version': system_specs.python_version,
            'platform_suitability': self._assess_platform_suitability(system_specs),
            'platform_optimizations': self._get_platform_optimizations(system_specs)
        }
        
        return analysis
    
    def _analyze_model_suitability(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Analyze suitability for different types of models."""
        overall_score = self._calculate_overall_performance_score(system_specs)
        
        suitability = {
            'lightweight_models': min(1.0, overall_score * 2.0),  # Can handle with lower specs
            'standard_models': overall_score,
            'large_models': max(0.0, overall_score - 0.2),  # Needs higher specs
            'premium_models': max(0.0, overall_score - 0.5),  # Needs premium specs
            'recommended_model_sizes': self._recommend_model_sizes(system_specs)
        }
        
        return suitability
    
    def _classify_performance_level(self, system_specs: SystemSpecs) -> str:
        """Classify overall system performance level."""
        score = self._calculate_overall_performance_score(system_specs)
        
        if score >= 0.9:
            return "Premium"
        elif score >= 0.7:
            return "High"
        elif score >= 0.5:
            return "Medium"
        elif score >= 0.3:
            return "Low"
        else:
            return "Minimal"
    
    def _generate_capability_summary(self, system_specs: SystemSpecs) -> str:
        """Generate a human-readable capability summary."""
        performance_level = self._classify_performance_level(system_specs)
        cpu_level = self._classify_cpu_performance(system_specs)
        memory_level = self._classify_memory_adequacy(system_specs)
        
        summary = f"{performance_level} performance system with {cpu_level} CPU and {memory_level} memory. "
        summary += f"Suitable for {self._get_suitability_description(system_specs)}."
        
        return summary
    
    def _compare_with_baseline_config(self, system_specs: SystemSpecs, baseline_config: Dict) -> float:
        """Compare system specs with a baseline configuration."""
        cpu_ratio = system_specs.cpu_cores / baseline_config['cpu_cores']
        memory_ratio = system_specs.total_memory / baseline_config['total_memory']
        freq_ratio = system_specs.cpu_frequency_max / baseline_config['cpu_frequency_max']
        
        # Geometric mean for balanced comparison
        comparison_score = (cpu_ratio * memory_ratio * freq_ratio) ** (1/3)
        
        return comparison_score
    
    # Helper classification methods
    def _classify_cpu_performance(self, system_specs: SystemSpecs) -> str:
        score = self._calculate_cpu_score(system_specs)
        if score >= 0.8: return "excellent"
        elif score >= 0.6: return "good"
        elif score >= 0.4: return "adequate"
        else: return "limited"
    
    def _classify_memory_adequacy(self, system_specs: SystemSpecs) -> str:
        if system_specs.total_memory >= 16: return "ample"
        elif system_specs.total_memory >= 8: return "adequate"
        elif system_specs.total_memory >= 4: return "minimal"
        else: return "insufficient"
    
    def _classify_storage_adequacy(self, system_specs: SystemSpecs) -> str:
        if system_specs.disk_usage_percent < 50: return "abundant"
        elif system_specs.disk_usage_percent < 75: return "adequate"
        elif system_specs.disk_usage_percent < 90: return "limited"
        else: return "critical"
    
    def _assess_platform_suitability(self, system_specs: SystemSpecs) -> str:
        platform = system_specs.platform.lower()
        if platform in ['linux', 'darwin']: return "excellent"
        elif platform == 'windows': return "good"
        else: return "unknown"
    
    # Recommendation helper methods
    def _get_cpu_recommendations(self, system_specs: SystemSpecs) -> List[str]:
        recommendations = []
        if system_specs.cpu_cores < 4:
            recommendations.append("Consider upgrading to at least 4 CPU cores")
        if system_specs.cpu_frequency_max < 2500:
            recommendations.append("Higher CPU frequency would improve performance")
        return recommendations
    
    def _get_memory_recommendations(self, system_specs: SystemSpecs) -> List[str]:
        recommendations = []
        if system_specs.total_memory < 8:
            recommendations.append("Upgrade to at least 8GB RAM for better model performance")
        if system_specs.memory_usage_percent > 80:
            recommendations.append("High memory usage - close unnecessary applications")
        return recommendations
    
    def _get_storage_recommendations(self, system_specs: SystemSpecs) -> List[str]:
        recommendations = []
        if system_specs.disk_usage_percent > 85:
            recommendations.append("Free up disk space for optimal performance")
        return recommendations
    
    def _get_platform_optimizations(self, system_specs: SystemSpecs) -> List[str]:
        platform = system_specs.platform.lower()
        if platform == 'windows':
            return ["Enable hardware acceleration", "Use Windows optimized models"]
        elif platform == 'linux':
            return ["Consider CUDA/ROCm for GPU acceleration", "Use compiled models"]
        elif platform == 'darwin':
            return ["Use Metal performance shaders", "Optimize for Apple Silicon if available"]
        else:
            return ["Use platform-appropriate optimizations"]
    
    def _recommend_model_sizes(self, system_specs: SystemSpecs) -> List[str]:
        score = self._calculate_overall_performance_score(system_specs)
        
        if score >= 0.8:
            return ["small", "medium", "large", "extra-large"]
        elif score >= 0.6:
            return ["small", "medium", "large"]
        elif score >= 0.4:
            return ["small", "medium"]
        else:
            return ["small"]
    
    def _get_suitability_description(self, system_specs: SystemSpecs) -> str:
        score = self._calculate_overall_performance_score(system_specs)
        
        if score >= 0.8:
            return "all model types and intensive AI workloads"
        elif score >= 0.6:
            return "most standard models and moderate AI tasks"
        elif score >= 0.4:
            return "lightweight models and basic AI functionality"
        else:
            return "minimal AI tasks with optimized models"


class MockSystemAnalyzer(ISystemAnalyzer):
    """Mock implementation for testing purposes."""
    
    def analyze_system_capabilities(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        return {
            'overall_score': 0.75,
            'performance_class': 'Medium',
            'capability_summary': 'Mock system analysis'
        }
    
    def predict_model_performance(self, system_specs: SystemSpecs, 
                                model_requirements: Dict[str, Any]) -> Dict[str, float]:
        return {
            'cpu_performance': 0.8,
            'memory_performance': 0.7,
            'predicted_response_time': 3.5,
            'overall_performance': 0.75
        }
    
    def compare_with_baseline(self, system_specs: SystemSpecs) -> Dict[str, str]:
        return {
            'minimum': 'exceeds (1.5x)',
            'recommended': 'meets (0.9x)',
            'best_match': 'recommended'
        }
    
    def generate_optimization_suggestions(self, system_specs: SystemSpecs, 
                                        benchmarks: List[ModelBenchmark]) -> List[str]:
        return ["Mock optimization suggestion"]
