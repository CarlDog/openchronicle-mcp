#!/usr/bin/env python3
"""
OpenChronicle System Profiling Interfaces

Interface definitions for the modular system profiling system.
Follows SOLID principles with focused, segregated interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SystemSpecs:
    """System hardware specifications."""
    cpu_cores: int
    cpu_physical_cores: int
    cpu_frequency_max: float  # MHz
    cpu_frequency_current: float  # MHz
    cpu_brand: str
    total_memory: float  # GB
    available_memory: float  # GB
    memory_usage_percent: float
    platform: str
    architecture: str
    python_version: str
    disk_space_gb: float
    disk_usage_percent: float


@dataclass
class ModelBenchmark:
    """Benchmark results for a specific model."""
    model_name: str
    adapter_type: str
    initialization_time: float  # seconds
    response_time: float  # seconds for standard test
    memory_usage_mb: float  # Peak memory during test
    success: bool
    error_message: Optional[str] = None
    tokens_per_second: Optional[float] = None
    quality_score: Optional[float] = None


@dataclass
class ModelRecommendation:
    """Model recommendation with rationale."""
    model_name: str
    adapter_type: str
    confidence_score: float  # 0.0 to 1.0
    recommended_for: List[str]  # ["fast_responses", "analysis", "creative"]
    rationale: str
    estimated_performance: Dict[str, Any]
    configuration_suggestions: Dict[str, Any]


@dataclass
class SystemProfile:
    """Complete system profiling results."""
    profile_timestamp: datetime
    system_specs: SystemSpecs
    benchmarks: List[ModelBenchmark]
    recommendations: List[ModelRecommendation]
    system_tier: str
    profile_metadata: Dict[str, Any]


@dataclass
class BenchmarkConfig:
    """Configuration for model benchmarking."""
    timeout_seconds: int = 60
    test_prompt: str = "Analyze this system and provide recommendations."
    memory_sampling_interval: float = 0.1
    max_models_parallel: int = 3
    include_quality_test: bool = True


class ISystemSpecsCollector(ABC):
    """Interface for collecting system hardware specifications."""
    
    @abstractmethod
    def collect_system_specs(self) -> SystemSpecs:
        """Collect comprehensive system hardware specifications."""
        pass
    
    @abstractmethod
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get detailed CPU information."""
        pass
    
    @abstractmethod
    def get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information."""
        pass
    
    @abstractmethod
    def get_disk_info(self) -> Dict[str, Any]:
        """Get disk usage information."""
        pass
    
    @abstractmethod
    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform and architecture information."""
        pass


class IModelBenchmarkRunner(ABC):
    """Interface for running model performance benchmarks."""
    
    @abstractmethod
    async def benchmark_model(self, model_manager: Any, adapter_name: str, 
                            config: BenchmarkConfig) -> ModelBenchmark:
        """Benchmark a specific model adapter."""
        pass
    
    @abstractmethod
    async def benchmark_all_models(self, model_manager: Any, 
                                 config: BenchmarkConfig) -> List[ModelBenchmark]:
        """Benchmark all available models."""
        pass
    
    @abstractmethod
    async def quick_benchmark(self, model_manager: Any, adapter_name: str) -> ModelBenchmark:
        """Run a quick benchmark with minimal overhead."""
        pass
    
    @abstractmethod
    def validate_model_availability(self, model_manager: Any, adapter_name: str) -> bool:
        """Check if a model is available for benchmarking."""
        pass


class IRecommendationEngine(ABC):
    """Interface for generating model recommendations based on system specs and benchmarks."""
    
    @abstractmethod
    def generate_recommendations(self, system_specs: SystemSpecs, 
                               benchmarks: List[ModelBenchmark]) -> List[ModelRecommendation]:
        """Generate model recommendations based on system analysis."""
        pass
    
    @abstractmethod
    def recommend_for_use_case(self, use_case: str, system_specs: SystemSpecs,
                             benchmarks: List[ModelBenchmark]) -> List[ModelRecommendation]:
        """Generate recommendations for specific use cases."""
        pass
    
    @abstractmethod
    def categorize_system_tier(self, system_specs: SystemSpecs) -> str:
        """Categorize system into performance tiers (low, medium, high, premium)."""
        pass
    
    @abstractmethod
    def analyze_performance_bottlenecks(self, system_specs: SystemSpecs, 
                                      benchmarks: List[ModelBenchmark]) -> List[str]:
        """Identify potential performance bottlenecks."""
        pass


class IProfileDataStorage(ABC):
    """Interface for storing and retrieving system profile data."""
    
    @abstractmethod
    def save_profile(self, profile: SystemProfile, filepath: Optional[str] = None) -> str:
        """Save system profile to storage."""
        pass
    
    @abstractmethod
    def load_profile(self, filepath: str) -> Optional[SystemProfile]:
        """Load system profile from storage."""
        pass
    
    @abstractmethod
    def list_saved_profiles(self) -> List[str]:
        """List all saved profile files."""
        pass
    
    @abstractmethod
    def delete_profile(self, filepath: str) -> bool:
        """Delete a saved profile."""
        pass
    
    @abstractmethod
    def get_profile_metadata(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a saved profile without loading full data."""
        pass


class ISystemAnalyzer(ABC):
    """Interface for analyzing system capabilities and performance characteristics."""
    
    @abstractmethod
    def analyze_system_capabilities(self, system_specs: SystemSpecs) -> Dict[str, Any]:
        """Analyze overall system capabilities."""
        pass
    
    @abstractmethod
    def predict_model_performance(self, system_specs: SystemSpecs, 
                                model_requirements: Dict[str, Any]) -> Dict[str, float]:
        """Predict model performance based on system specs."""
        pass
    
    @abstractmethod
    def compare_with_baseline(self, system_specs: SystemSpecs) -> Dict[str, str]:
        """Compare system specs with baseline configurations."""
        pass
    
    @abstractmethod
    def generate_optimization_suggestions(self, system_specs: SystemSpecs, 
                                        benchmarks: List[ModelBenchmark]) -> List[str]:
        """Generate system optimization suggestions."""
        pass


class ISystemProfilingOrchestrator(ABC):
    """Interface for the main system profiling orchestrator."""
    
    @abstractmethod
    async def run_complete_profile(self, model_manager: Any, 
                                 config: Optional[BenchmarkConfig] = None) -> SystemProfile:
        """Run complete system profiling including hardware specs and model benchmarks."""
        pass
    
    @abstractmethod
    async def run_hardware_profile_only(self) -> SystemSpecs:
        """Run hardware profiling only without model benchmarks."""
        pass
    
    @abstractmethod
    async def run_model_benchmarks_only(self, model_manager: Any, 
                                      config: Optional[BenchmarkConfig] = None) -> List[ModelBenchmark]:
        """Run model benchmarks only using cached hardware specs."""
        pass
    
    @abstractmethod
    def get_cached_profile(self) -> Optional[SystemProfile]:
        """Get the most recent cached profile."""
        pass
    
    @abstractmethod
    def get_system_summary(self) -> Dict[str, Any]:
        """Get a summary of system capabilities and recommendations."""
        pass
