#!/usr/bin/env python3
"""
OpenChronicle Model Benchmark Runner

Model performance benchmarking implementation following SOLID principles.
Focused responsibility: Execute and measure model adapter performance.
"""

import asyncio
import time
import tracemalloc
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..interfaces import IModelBenchmarkRunner, ModelBenchmark, BenchmarkConfig

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class ModelBenchmarkRunner(IModelBenchmarkRunner):
    """Production implementation of model performance benchmarking."""
    
    def __init__(self):
        self._default_config = BenchmarkConfig()
        self._benchmark_cache = {}  # Simple in-memory cache
        
    async def benchmark_model(self, model_manager: Any, adapter_name: str, 
                            config: BenchmarkConfig) -> ModelBenchmark:
        """
        Benchmark a specific model adapter with comprehensive metrics.
        
        Args:
            model_manager: The model manager instance
            adapter_name: Name of the adapter to benchmark
            config: Benchmark configuration parameters
            
        Returns:
            ModelBenchmark with performance metrics
        """
        benchmark_start = time.time()
        
        # Validate model availability
        if not self.validate_model_availability(model_manager, adapter_name):
            return ModelBenchmark(
                model_name=adapter_name,
                adapter_type="unknown",
                initialization_time=0.0,
                response_time=0.0,
                memory_usage_mb=0.0,
                success=False,
                error_message=f"Model {adapter_name} not available"
            )
        
        try:
            # Start memory tracking
            tracemalloc.start()
            initial_memory = self._get_current_memory_mb()
            
            # Initialize adapter (measure initialization time)
            init_start = time.time()
            
            # Check if adapter is already initialized
            if adapter_name not in model_manager.adapters:
                await model_manager.initialize_adapter(adapter_name)
            
            adapter = model_manager.adapters[adapter_name]
            init_time = time.time() - init_start
            
            # Prepare test prompt
            test_prompt = config.test_prompt
            
            # Measure response time
            response_start = time.time()
            
            # Use timeout for the actual generation
            try:
                response = await asyncio.wait_for(
                    adapter.generate_response(test_prompt),
                    timeout=config.timeout_seconds
                )
                success = True
                error_message = None
            except asyncio.TimeoutError:
                success = False
                error_message = f"Timeout after {config.timeout_seconds} seconds"
                response = None
            except Exception as e:
                success = False
                error_message = f"Generation error: {str(e)}"
                response = None
            
            response_time = time.time() - response_start
            
            # Measure memory usage
            peak_memory = self._get_current_memory_mb()
            memory_usage = max(0.0, peak_memory - initial_memory)
            
            # Calculate tokens per second (if response available)
            tokens_per_second = None
            if success and response:
                estimated_tokens = len(str(response).split())  # Rough token estimate
                if response_time > 0:
                    tokens_per_second = estimated_tokens / response_time
            
            # Quality score (basic implementation)
            quality_score = None
            if success and response and config.include_quality_test:
                quality_score = self._calculate_quality_score(response, test_prompt)
            
            # Get adapter type
            adapter_type = getattr(adapter, '__class__', type(adapter)).__name__
            
            return ModelBenchmark(
                model_name=adapter_name,
                adapter_type=adapter_type,
                initialization_time=init_time,
                response_time=response_time,
                memory_usage_mb=memory_usage,
                success=success,
                error_message=error_message,
                tokens_per_second=tokens_per_second,
                quality_score=quality_score
            )
            
        except Exception as e:
            return ModelBenchmark(
                model_name=adapter_name,
                adapter_type="unknown",
                initialization_time=0.0,
                response_time=0.0,
                memory_usage_mb=0.0,
                success=False,
                error_message=f"Benchmark error: {str(e)}"
            )
        finally:
            # Clean up memory tracking
            try:
                tracemalloc.stop()
            except Exception:
                pass
    
    async def benchmark_all_models(self, model_manager: Any, 
                                 config: BenchmarkConfig) -> List[ModelBenchmark]:
        """
        Benchmark all available models with controlled parallelism.
        
        Args:
            model_manager: The model manager instance
            config: Benchmark configuration parameters
            
        Returns:
            List of ModelBenchmark results
        """
        available_models = self._get_available_models(model_manager)
        results = []
        
        # Process models in batches to control resource usage
        batch_size = min(config.max_models_parallel, len(available_models))
        
        for i in range(0, len(available_models), batch_size):
            batch = available_models[i:i + batch_size]
            
            # Create benchmark tasks for this batch
            tasks = [
                self.benchmark_model(model_manager, model_name, config)
                for model_name in batch
            ]
            
            # Execute batch with timeout
            try:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results, handling exceptions
                for result in batch_results:
                    if isinstance(result, Exception):
                        # Create failed benchmark for exception
                        results.append(ModelBenchmark(
                            model_name="unknown",
                            adapter_type="unknown", 
                            initialization_time=0.0,
                            response_time=0.0,
                            memory_usage_mb=0.0,
                            success=False,
                            error_message=f"Batch error: {str(result)}"
                        ))
                    else:
                        results.append(result)
                        
            except Exception as e:
                # If entire batch fails, create failed benchmarks
                for model_name in batch:
                    results.append(ModelBenchmark(
                        model_name=model_name,
                        adapter_type="unknown",
                        initialization_time=0.0,
                        response_time=0.0,
                        memory_usage_mb=0.0,
                        success=False,
                        error_message=f"Batch execution error: {str(e)}"
                    ))
        
        return results
    
    async def quick_benchmark(self, model_manager: Any, adapter_name: str) -> ModelBenchmark:
        """
        Run a quick benchmark with minimal overhead and shorter timeout.
        
        Args:
            model_manager: The model manager instance
            adapter_name: Name of the adapter to benchmark
            
        Returns:
            ModelBenchmark with basic performance metrics
        """
        quick_config = BenchmarkConfig(
            timeout_seconds=30,
            test_prompt="Test response.",
            memory_sampling_interval=0.5,
            max_models_parallel=1,
            include_quality_test=False
        )
        
        return await self.benchmark_model(model_manager, adapter_name, quick_config)
    
    def validate_model_availability(self, model_manager: Any, adapter_name: str) -> bool:
        """
        Check if a model is available for benchmarking.
        
        Args:
            model_manager: The model manager instance
            adapter_name: Name of the adapter to check
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            # Check if adapter is in registry
            if hasattr(model_manager, 'registry') and model_manager.registry:
                return adapter_name in model_manager.registry.list_models()
            
            # Check if adapter is already loaded
            if hasattr(model_manager, 'adapters') and model_manager.adapters:
                return adapter_name in model_manager.adapters
            
            # Fallback: assume available if we can't determine
            return True
            
        except Exception:
            return False
    
    def _get_available_models(self, model_manager: Any) -> List[str]:
        """Get list of available model names."""
        try:
            if hasattr(model_manager, 'registry') and model_manager.registry:
                return model_manager.registry.list_models()
            elif hasattr(model_manager, 'adapters') and model_manager.adapters:
                return list(model_manager.adapters.keys())
            else:
                return []
        except Exception:
            return []
    
    def _get_current_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                return process.memory_info().rss / (1024 * 1024)
            else:
                # Fallback without psutil
                return 0.0
        except Exception:
            return 0.0
    
    def _calculate_quality_score(self, response: Any, prompt: str) -> float:
        """
        Calculate a basic quality score for the response.
        
        Args:
            response: The model's response
            prompt: The original prompt
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        try:
            response_str = str(response) if response else ""
            
            # Basic quality metrics
            score = 0.0
            
            # Length appropriateness (not too short, not too long)
            response_length = len(response_str)
            if 10 <= response_length <= 1000:
                score += 0.3
            elif response_length > 1000:
                score += 0.2  # Penalize overly long responses
            
            # Contains meaningful content (not just errors or empty)
            if response_str and not any(error_term in response_str.lower() for error_term in 
                                      ['error', 'failed', 'cannot', 'unable', 'sorry']):
                score += 0.4
            
            # Coherence check (very basic)
            if response_str and len(response_str.split()) >= 3:
                score += 0.3
            
            return min(1.0, score)
            
        except Exception:
            return 0.0


class MockModelBenchmarkRunner(IModelBenchmarkRunner):
    """Mock implementation for testing purposes."""
    
    def __init__(self, mock_results: Optional[Dict[str, ModelBenchmark]] = None):
        self.mock_results = mock_results or {}
        self.default_benchmark = ModelBenchmark(
            model_name="mock_model",
            adapter_type="MockAdapter",
            initialization_time=0.5,
            response_time=1.2,
            memory_usage_mb=150.0,
            success=True,
            tokens_per_second=25.0,
            quality_score=0.8
        )
    
    async def benchmark_model(self, model_manager: Any, adapter_name: str, 
                            config: BenchmarkConfig) -> ModelBenchmark:
        """Return mock benchmark result."""
        if adapter_name in self.mock_results:
            return self.mock_results[adapter_name]
        
        # Create a mock result based on the adapter name
        mock = ModelBenchmark(
            model_name=adapter_name,
            adapter_type="MockAdapter",
            initialization_time=0.5,
            response_time=1.0,
            memory_usage_mb=100.0,
            success=True,
            tokens_per_second=20.0,
            quality_score=0.75
        )
        return mock
    
    async def benchmark_all_models(self, model_manager: Any, 
                                 config: BenchmarkConfig) -> List[ModelBenchmark]:
        """Return list of mock benchmark results."""
        mock_models = ["mock_model_1", "mock_model_2", "mock_model_3"]
        results = []
        
        for model_name in mock_models:
            benchmark = await self.benchmark_model(model_manager, model_name, config)
            results.append(benchmark)
        
        return results
    
    async def quick_benchmark(self, model_manager: Any, adapter_name: str) -> ModelBenchmark:
        """Return quick mock benchmark."""
        return await self.benchmark_model(model_manager, adapter_name, BenchmarkConfig())
    
    def validate_model_availability(self, model_manager: Any, adapter_name: str) -> bool:
        """Always return True for mock."""
        return True
