"""
System Profiler for OpenChronicle.
Profiles hardware capabilities and provides model recommendations.
"""

import asyncio
import json
import os
import platform
import psutil
import time
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import concurrent.futures

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error

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

class SystemProfiler:
    """Profiles system capabilities and recommends optimal models."""
    
    def __init__(self):
        self.system_specs: Optional[SystemSpecs] = None
        self.benchmarks: List[ModelBenchmark] = []
        self.recommendations: List[ModelRecommendation] = []
        self.profile_timestamp: Optional[str] = None
        
    def profile_system_hardware(self) -> SystemSpecs:
        """Profile the current system's hardware capabilities."""
        log_info("Starting system hardware profiling...")
        
        try:
            # CPU Information
            cpu_info = psutil.cpu_freq()
            cpu_cores = psutil.cpu_count(logical=True)
            cpu_physical_cores = psutil.cpu_count(logical=False)
            
            # Memory Information  
            memory = psutil.virtual_memory()
            total_memory_gb = memory.total / (1024**3)
            available_memory_gb = memory.available / (1024**3)
            
            # Disk Information
            disk = psutil.disk_usage('/')
            disk_space_gb = disk.total / (1024**3)
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # CPU brand detection (basic)
            cpu_brand = platform.processor() or "Unknown"
            if not cpu_brand or cpu_brand == "Unknown":
                try:
                    # Try alternative method
                    if platform.system() == "Windows":
                        import subprocess
                        result = subprocess.run(
                            ["wmic", "cpu", "get", "name"], 
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            if len(lines) > 1:
                                cpu_brand = lines[1].strip()
                except Exception:
                    pass
            
            specs = SystemSpecs(
                cpu_cores=cpu_cores,
                cpu_physical_cores=cpu_physical_cores,
                cpu_frequency_max=cpu_info.max if cpu_info else 0.0,
                cpu_frequency_current=cpu_info.current if cpu_info else 0.0,
                cpu_brand=cpu_brand,
                total_memory=total_memory_gb,
                available_memory=available_memory_gb,
                memory_usage_percent=memory.percent,
                platform=platform.platform(),
                architecture=platform.architecture()[0],
                python_version=platform.python_version(),
                disk_space_gb=disk_space_gb,
                disk_usage_percent=disk_usage_percent
            )
            
            self.system_specs = specs
            self.profile_timestamp = datetime.now(UTC).isoformat()
            
            log_system_event("system_profile_completed", 
                           f"System profile completed: {cpu_cores} cores, {total_memory_gb:.1f}GB RAM, {platform.platform()}")
            
            log_info(f"System profiling complete: {cpu_cores} cores, {total_memory_gb:.1f}GB RAM")
            return specs
            
        except Exception as e:
            log_error(f"System profiling failed: {e}")
            raise
    
    async def benchmark_model_adapter(self, model_manager, adapter_name: str) -> ModelBenchmark:
        """Benchmark a specific model adapter's performance."""
        log_info(f"Benchmarking model adapter: {adapter_name}")
        
        start_time = time.time()
        memory_before = psutil.Process().memory_info().rss / (1024*1024)  # MB
        
        try:
            # Initialize the adapter
            init_start = time.time()
            initialized = await model_manager.initialize_adapter_safe(adapter_name)
            init_time = time.time() - init_start
            
            if not initialized:
                return ModelBenchmark(
                    model_name=adapter_name,
                    adapter_type="unknown",
                    initialization_time=init_time,
                    response_time=0.0,
                    memory_usage_mb=0.0,
                    success=False,
                    error_message="Failed to initialize adapter"
                )
            
            # Get adapter info
            adapter_info = model_manager.get_adapter_info(adapter_name)
            adapter_type = adapter_info.get("type", "text")
            
            # Test response generation for text models
            response_time = 0.0
            tokens_per_second = None
            
            if adapter_type == "text":
                test_prompt = "Write a short creative description of a sunset."
                
                response_start = time.time()
                try:
                    response = await model_manager.generate_response(
                        test_prompt,
                        adapter_name=adapter_name,
                        max_tokens=100,
                        timeout=30
                    )
                    response_time = time.time() - response_start
                    
                    # Estimate tokens per second (rough approximation)
                    if response and response_time > 0:
                        estimated_tokens = len(response.split()) * 1.3  # Words to tokens approximation
                        tokens_per_second = estimated_tokens / response_time
                        
                except Exception as e:
                    log_warning(f"Response generation test failed for {adapter_name}: {e}")
                    response_time = 999.0  # High penalty for failure
            
            # Measure peak memory usage
            memory_after = psutil.Process().memory_info().rss / (1024*1024)  # MB
            memory_usage = max(0, memory_after - memory_before)
            
            benchmark = ModelBenchmark(
                model_name=adapter_name,
                adapter_type=adapter_type,
                initialization_time=init_time,
                response_time=response_time,
                memory_usage_mb=memory_usage,
                success=True,
                tokens_per_second=tokens_per_second
            )
            
            log_info(f"Benchmark complete for {adapter_name}: "
                    f"init={init_time:.2f}s, response={response_time:.2f}s")
            
            return benchmark
            
        except Exception as e:
            error_msg = str(e)
            log_error(f"Benchmarking failed for {adapter_name}: {error_msg}")
            
            return ModelBenchmark(
                model_name=adapter_name,
                adapter_type="unknown",
                initialization_time=time.time() - start_time,
                response_time=0.0,
                memory_usage_mb=0.0,
                success=False,
                error_message=error_msg
            )
    
    async def benchmark_available_models(self, model_manager) -> List[ModelBenchmark]:
        """Benchmark all available model adapters."""
        log_info("Starting model benchmarking...")
        
        available_adapters = model_manager.get_available_adapters()
        log_info(f"Found {len(available_adapters)} adapters to benchmark")
        
        benchmarks = []
        
        # Benchmark adapters sequentially to avoid resource conflicts
        for adapter_name in available_adapters:
            try:
                benchmark = await self.benchmark_model_adapter(model_manager, adapter_name)
                benchmarks.append(benchmark)
                
                # Small delay between benchmarks
                await asyncio.sleep(0.5)
                
            except Exception as e:
                log_error(f"Failed to benchmark {adapter_name}: {e}")
                # Continue with other adapters
                continue
        
        self.benchmarks = benchmarks
        
        log_system_event("model_benchmarking_completed", 
                       f"Benchmarking completed: {len(available_adapters)} total adapters, "
                       f"{len([b for b in benchmarks if b.success])} successful, "
                       f"{len([b for b in benchmarks if not b.success])} failed")
        
        log_info(f"Benchmarking complete: {len(benchmarks)} results")
        return benchmarks
    
    def generate_model_recommendations(self) -> List[ModelRecommendation]:
        """Generate personalized model recommendations based on system profile and benchmarks."""
        if not self.system_specs or not self.benchmarks:
            log_warning("Cannot generate recommendations without system specs and benchmarks")
            return []
        
        log_info("Generating personalized model recommendations...")
        
        recommendations = []
        successful_benchmarks = [b for b in self.benchmarks if b.success]
        
        if not successful_benchmarks:
            log_warning("No successful benchmarks found for recommendations")
            return []
        
        # Categorize system capability
        system_tier = self._categorize_system_tier()
        
        # Generate recommendations for different use cases
        recommendations.extend(self._recommend_for_fast_responses(successful_benchmarks, system_tier))
        recommendations.extend(self._recommend_for_analysis_tasks(successful_benchmarks, system_tier))
        recommendations.extend(self._recommend_for_creative_tasks(successful_benchmarks, system_tier))
        recommendations.extend(self._recommend_for_general_use(successful_benchmarks, system_tier))
        
        # Sort by confidence score
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
        
        self.recommendations = recommendations[:10]  # Top 10 recommendations
        
        log_system_event("model_recommendations_generated", 
                       f"Generated {len(self.recommendations)} recommendations for {system_tier} tier system, "
                       f"top recommendation: {self.recommendations[0].model_name if self.recommendations else 'none'}")
        
        log_info(f"Generated {len(self.recommendations)} model recommendations")
        return self.recommendations
    
    def _categorize_system_tier(self) -> str:
        """Categorize system into performance tiers."""
        if not self.system_specs:
            return "unknown"
        
        # High-end system
        if (self.system_specs.cpu_cores >= 8 and 
            self.system_specs.total_memory >= 16 and
            self.system_specs.cpu_frequency_max >= 3000):
            return "high_end"
        
        # Mid-range system
        if (self.system_specs.cpu_cores >= 4 and 
            self.system_specs.total_memory >= 8):
            return "mid_range"
        
        # Low-end system
        return "low_end"
    
    def _recommend_for_fast_responses(self, benchmarks: List[ModelBenchmark], system_tier: str) -> List[ModelRecommendation]:
        """Generate recommendations for fast response scenarios."""
        recommendations = []
        
        # Sort by response time (fastest first)
        fast_models = sorted(
            [b for b in benchmarks if b.response_time > 0],
            key=lambda b: b.response_time
        )
        
        for i, benchmark in enumerate(fast_models[:3]):  # Top 3 fastest
            confidence = 0.9 - (i * 0.15)  # Decreasing confidence
            
            # Adjust confidence based on system tier
            if system_tier == "low_end" and benchmark.memory_usage_mb > 500:
                confidence *= 0.7  # Penalty for high memory usage on low-end systems
            
            config_suggestions = {
                "max_tokens": 150 if system_tier == "low_end" else 300,
                "temperature": 0.7,
                "timeout": 15 if system_tier == "low_end" else 30
            }
            
            estimated_performance = {
                "response_time": benchmark.response_time,
                "memory_usage": benchmark.memory_usage_mb,
                "tokens_per_second": benchmark.tokens_per_second
            }
            
            recommendations.append(ModelRecommendation(
                model_name=benchmark.model_name,
                adapter_type=benchmark.adapter_type,
                confidence_score=confidence,
                recommended_for=["fast_responses"],
                rationale=f"Fast response time ({benchmark.response_time:.2f}s) with reasonable resource usage",
                estimated_performance=estimated_performance,
                configuration_suggestions=config_suggestions
            ))
        
        return recommendations
    
    def _recommend_for_analysis_tasks(self, benchmarks: List[ModelBenchmark], system_tier: str) -> List[ModelRecommendation]:
        """Generate recommendations for analysis-heavy tasks."""
        recommendations = []
        
        # Prefer models with good balance of performance and capability
        analysis_models = []
        
        for benchmark in benchmarks:
            # Score based on multiple factors
            score = 0.0
            
            # Response time factor (not too slow)
            if 0 < benchmark.response_time <= 5.0:
                score += 0.4
            elif 5.0 < benchmark.response_time <= 10.0:
                score += 0.2
            
            # Memory efficiency factor
            if benchmark.memory_usage_mb < 200:
                score += 0.3
            elif benchmark.memory_usage_mb < 500:
                score += 0.15
            
            # Model name heuristics (better models for analysis)
            model_lower = benchmark.model_name.lower()
            if any(term in model_lower for term in ["gpt-4", "claude", "gemini", "llama-2", "mistral"]):
                score += 0.3
            
            analysis_models.append((benchmark, score))
        
        # Sort by score
        analysis_models.sort(key=lambda x: x[1], reverse=True)
        
        for i, (benchmark, score) in enumerate(analysis_models[:2]):  # Top 2
            confidence = min(0.85, score) - (i * 0.1)
            
            config_suggestions = {
                "max_tokens": 1000 if system_tier != "low_end" else 500,
                "temperature": 0.3,  # Lower temperature for analysis
                "timeout": 60 if system_tier != "low_end" else 30
            }
            
            recommendations.append(ModelRecommendation(
                model_name=benchmark.model_name,
                adapter_type=benchmark.adapter_type,
                confidence_score=confidence,
                recommended_for=["analysis"],
                rationale=f"Good balance of capability and performance for analysis tasks (score: {score:.2f})",
                estimated_performance={
                    "response_time": benchmark.response_time,
                    "memory_usage": benchmark.memory_usage_mb
                },
                configuration_suggestions=config_suggestions
            ))
        
        return recommendations
    
    def _recommend_for_creative_tasks(self, benchmarks: List[ModelBenchmark], system_tier: str) -> List[ModelRecommendation]:
        """Generate recommendations for creative writing tasks."""
        recommendations = []
        
        # For creative tasks, prefer models with good quality potential
        creative_models = []
        
        for benchmark in benchmarks:
            score = 0.0
            
            # Accept slower response times for better quality
            if benchmark.response_time <= 15.0:
                score += 0.3
            
            # Memory usage consideration
            if benchmark.memory_usage_mb < 300:
                score += 0.2
            
            # Model capability heuristics
            model_lower = benchmark.model_name.lower()
            if any(term in model_lower for term in ["gpt", "claude", "gemini"]):
                score += 0.4
            elif any(term in model_lower for term in ["llama", "mistral", "phi"]):
                score += 0.2
            
            # Tokens per second bonus
            if benchmark.tokens_per_second and benchmark.tokens_per_second > 5:
                score += 0.1
            
            creative_models.append((benchmark, score))
        
        creative_models.sort(key=lambda x: x[1], reverse=True)
        
        for i, (benchmark, score) in enumerate(creative_models[:2]):
            confidence = min(0.8, score) - (i * 0.1)
            
            config_suggestions = {
                "max_tokens": 1500 if system_tier == "high_end" else 800,
                "temperature": 0.8,  # Higher temperature for creativity
                "timeout": 90 if system_tier != "low_end" else 45
            }
            
            recommendations.append(ModelRecommendation(
                model_name=benchmark.model_name,
                adapter_type=benchmark.adapter_type,
                confidence_score=confidence,
                recommended_for=["creative"],
                rationale=f"Good creative potential with acceptable performance (score: {score:.2f})",
                estimated_performance={
                    "response_time": benchmark.response_time,
                    "memory_usage": benchmark.memory_usage_mb,
                    "tokens_per_second": benchmark.tokens_per_second
                },
                configuration_suggestions=config_suggestions
            ))
        
        return recommendations
    
    def _recommend_for_general_use(self, benchmarks: List[ModelBenchmark], system_tier: str) -> List[ModelRecommendation]:
        """Generate recommendations for general-purpose use."""
        recommendations = []
        
        # Overall best balance
        general_models = []
        
        for benchmark in benchmarks:
            score = 0.0
            
            # Balanced scoring
            if 0 < benchmark.response_time <= 8.0:
                score += 0.3
            
            if benchmark.memory_usage_mb < 400:
                score += 0.25
            
            # Initialization time factor
            if benchmark.initialization_time < 5.0:
                score += 0.15
            
            # General capability heuristics
            model_lower = benchmark.model_name.lower()
            if "gpt" in model_lower or "claude" in model_lower:
                score += 0.3
            elif any(term in model_lower for term in ["llama", "mistral", "gemini"]):
                score += 0.2
            
            general_models.append((benchmark, score))
        
        general_models.sort(key=lambda x: x[1], reverse=True)
        
        # Take the top performer for general use
        if general_models:
            benchmark, score = general_models[0]
            
            config_suggestions = {
                "max_tokens": 800 if system_tier != "low_end" else 400,
                "temperature": 0.7,
                "timeout": 45 if system_tier != "low_end" else 30
            }
            
            recommendations.append(ModelRecommendation(
                model_name=benchmark.model_name,
                adapter_type=benchmark.adapter_type,
                confidence_score=min(0.9, score),
                recommended_for=["general"],
                rationale=f"Best overall balance of performance and capability (score: {score:.2f})",
                estimated_performance={
                    "response_time": benchmark.response_time,
                    "memory_usage": benchmark.memory_usage_mb,
                    "initialization_time": benchmark.initialization_time
                },
                configuration_suggestions=config_suggestions
            ))
        
        return recommendations
    
    def save_profile_results(self, filepath: Optional[str] = None) -> str:
        """Save profiling results to JSON file."""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"storage/data/profiles/system_profile_{timestamp}.json"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        profile_data = {
            "timestamp": self.profile_timestamp,
            "system_specs": asdict(self.system_specs) if self.system_specs else None,
            "benchmarks": [asdict(b) for b in self.benchmarks],
            "recommendations": [asdict(r) for r in self.recommendations],
            "summary": {
                "system_tier": self._categorize_system_tier() if self.system_specs else "unknown",
                "total_adapters_tested": len(self.benchmarks),
                "successful_tests": len([b for b in self.benchmarks if b.success]),
                "fastest_model": min(self.benchmarks, key=lambda b: b.response_time if b.success and b.response_time > 0 else 999).model_name if self.benchmarks else None,
                "recommended_general_model": self.recommendations[0].model_name if self.recommendations else None
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(profile_data, f, indent=2)
        
        log_system_event("system_profile_saved", f"System profile saved to {filepath}")
        log_info(f"System profile saved to: {filepath}")
        
        return filepath
    
    def load_profile_results(self, filepath: str) -> bool:
        """Load previously saved profiling results."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.profile_timestamp = data.get("timestamp")
            
            # Load system specs
            if data.get("system_specs"):
                self.system_specs = SystemSpecs(**data["system_specs"])
            
            # Load benchmarks
            self.benchmarks = [ModelBenchmark(**b) for b in data.get("benchmarks", [])]
            
            # Load recommendations
            self.recommendations = [ModelRecommendation(**r) for r in data.get("recommendations", [])]
            
            log_info(f"System profile loaded from: {filepath}")
            return True
            
        except Exception as e:
            log_error(f"Failed to load system profile from {filepath}: {e}")
            return False
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get a summary of system capabilities and recommendations."""
        if not self.system_specs:
            return {"error": "No system profile available"}
        
        summary = {
            "system_info": {
                "cpu_cores": self.system_specs.cpu_cores,
                "memory_gb": round(self.system_specs.total_memory, 1),
                "platform": self.system_specs.platform,
                "tier": self._categorize_system_tier()
            },
            "performance_summary": {
                "total_models_tested": len(self.benchmarks),
                "successful_tests": len([b for b in self.benchmarks if b.success]),
                "average_response_time": round(
                    sum(b.response_time for b in self.benchmarks if b.success and b.response_time > 0) / 
                    max(1, len([b for b in self.benchmarks if b.success and b.response_time > 0])), 2
                ) if self.benchmarks else 0
            },
            "recommendations": {
                "fastest": next((r.model_name for r in self.recommendations if "fast_responses" in r.recommended_for), None),
                "best_analysis": next((r.model_name for r in self.recommendations if "analysis" in r.recommended_for), None),
                "best_creative": next((r.model_name for r in self.recommendations if "creative" in r.recommended_for), None),
                "general_purpose": next((r.model_name for r in self.recommendations if "general" in r.recommended_for), None)
            },
            "profile_timestamp": self.profile_timestamp
        }
        
        return summary

# Convenience functions for use by other modules

async def profile_system_and_models(model_manager) -> SystemProfiler:
    """Complete system profiling workflow."""
    profiler = SystemProfiler()
    
    # Profile hardware
    profiler.profile_system_hardware()
    
    # Benchmark models
    await profiler.benchmark_available_models(model_manager)
    
    # Generate recommendations
    profiler.generate_model_recommendations()
    
    # Save results
    profiler.save_profile_results()
    
    return profiler

def get_quick_system_info() -> Dict[str, Any]:
    """Get basic system information quickly without full profiling."""
    try:
        return {
            "cpu_cores": psutil.cpu_count(logical=True),
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
            "platform": platform.platform(),
            "python_version": platform.python_version()
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Simple test
    profiler = SystemProfiler()
    specs = profiler.profile_system_hardware()
    print(f"System Specs: {specs}")
    
    quick_info = get_quick_system_info()
    print(f"Quick Info: {quick_info}")
