"""
Performance Benchmarking for Redis Caching
Week 16: Performance Optimization Advanced

Provides comprehensive benchmarking and monitoring for cache performance.
"""

import asyncio
import logging
import statistics
import time
from datetime import UTC
from datetime import datetime
from typing import Any

from ...core.memory_orchestrator import MemoryOrchestrator
from .redis_cache import CacheConfig
from .redis_cache import CachedMemoryOrchestrator


class CachePerformanceBenchmark:
    """Benchmark cache performance vs non-cached operations."""

    def __init__(self, story_id: str = "benchmark_story"):
        self.story_id = story_id
        self.logger = logging.getLogger("openchronicle.benchmark")

        # Create orchestrators
        self.original_orchestrator = MemoryOrchestrator()
        self.cached_orchestrator = CachedMemoryOrchestrator(
            self.original_orchestrator,
            CacheConfig(
                character_ttl=300,  # 5 minutes for benchmarking
                memory_ttl=180,  # 3 minutes for benchmarking
                default_ttl=240,  # 4 minutes for benchmarking
            ),
        )

    async def benchmark_character_operations(self, num_operations: int = 100) -> dict[str, Any]:
        """Benchmark character read operations."""
        self.logger.info(f"Benchmarking {num_operations} character operations...")

        # Prepare test data
        character_name = "BenchmarkCharacter"
        test_character = {
            "name": character_name,
            "traits": {"speed": 8, "intelligence": 9},
            "background": "A character used for performance benchmarking",
            "dialogue_style": "analytical and precise",
        }

        # Store initial character
        self.original_orchestrator.update_character_memory(self.story_id, character_name, test_character)

        # Benchmark original (non-cached) operations
        original_times = []
        for _i in range(num_operations):
            start_time = time.time()
            character = self.original_orchestrator.character_manager.get_character_memory(self.story_id, character_name)
            end_time = time.time()
            original_times.append((end_time - start_time) * 1000)  # Convert to ms

        # Benchmark cached operations (with warm-up)
        cached_times = []

        # Warm-up cache
        await self.cached_orchestrator.cached_character_manager.get_character_memory(self.story_id, character_name)

        for _i in range(num_operations):
            start_time = time.time()
            character = await self.cached_orchestrator.cached_character_manager.get_character_memory(
                self.story_id, character_name
            )
            end_time = time.time()
            cached_times.append((end_time - start_time) * 1000)  # Convert to ms

        # Calculate statistics
        results = {
            "operation_type": "character_read",
            "num_operations": num_operations,
            "original_performance": {
                "avg_ms": statistics.mean(original_times),
                "median_ms": statistics.median(original_times),
                "min_ms": min(original_times),
                "max_ms": max(original_times),
                "std_dev_ms": (statistics.stdev(original_times) if len(original_times) > 1 else 0),
            },
            "cached_performance": {
                "avg_ms": statistics.mean(cached_times),
                "median_ms": statistics.median(cached_times),
                "min_ms": min(cached_times),
                "max_ms": max(cached_times),
                "std_dev_ms": (statistics.stdev(cached_times) if len(cached_times) > 1 else 0),
            },
        }

        # Calculate improvement
        original_avg = results["original_performance"]["avg_ms"]
        cached_avg = results["cached_performance"]["avg_ms"]
        improvement = (original_avg - cached_avg) / original_avg * 100 if original_avg > 0 else 0
        speedup = original_avg / cached_avg if cached_avg > 0 else 0

        results["performance_improvement"] = {
            "improvement_percent": improvement,
            "speedup_factor": speedup,
            "time_saved_ms": original_avg - cached_avg,
        }

        return results

    async def benchmark_memory_snapshots(self, num_operations: int = 50) -> dict[str, Any]:
        """Benchmark memory snapshot operations."""
        self.logger.info(f"Benchmarking {num_operations} memory snapshot operations...")

        # Prepare test memory data
        for i in range(10):
            self.original_orchestrator.save_current_memory(
                self.story_id,
                {"content": f"Test memory content {i}", "importance": i % 5},
            )  # Benchmark original operations
        original_times = []
        for _i in range(num_operations):
            start_time = time.time()
            snapshot = self.original_orchestrator.load_current_memory(self.story_id)
            end_time = time.time()
            original_times.append((end_time - start_time) * 1000)

        # Benchmark cached operations
        cached_times = []

        # Warm-up cache
        await self.cached_orchestrator.get_memory_snapshot(self.story_id)

        for _i in range(num_operations):
            start_time = time.time()
            snapshot = await self.cached_orchestrator.get_memory_snapshot(self.story_id)
            end_time = time.time()
            cached_times.append((end_time - start_time) * 1000)

        # Calculate statistics
        results = {
            "operation_type": "memory_snapshot",
            "num_operations": num_operations,
            "original_performance": {
                "avg_ms": statistics.mean(original_times),
                "median_ms": statistics.median(original_times),
                "min_ms": min(original_times),
                "max_ms": max(original_times),
                "std_dev_ms": (statistics.stdev(original_times) if len(original_times) > 1 else 0),
            },
            "cached_performance": {
                "avg_ms": statistics.mean(cached_times),
                "median_ms": statistics.median(cached_times),
                "min_ms": min(cached_times),
                "max_ms": max(cached_times),
                "std_dev_ms": (statistics.stdev(cached_times) if len(cached_times) > 1 else 0),
            },
        }

        # Calculate improvement
        original_avg = results["original_performance"]["avg_ms"]
        cached_avg = results["cached_performance"]["avg_ms"]
        improvement = (original_avg - cached_avg) / original_avg * 100 if original_avg > 0 else 0
        speedup = original_avg / cached_avg if cached_avg > 0 else 0

        results["performance_improvement"] = {
            "improvement_percent": improvement,
            "speedup_factor": speedup,
            "time_saved_ms": original_avg - cached_avg,
        }

        return results

    async def benchmark_concurrent_operations(self, concurrent_tasks: int = 20) -> dict[str, Any]:
        """Benchmark concurrent cache operations."""
        self.logger.info(f"Benchmarking {concurrent_tasks} concurrent operations...")

        character_name = "ConcurrentBenchmark"

        # Store test character
        self.original_orchestrator.update_character_memory(self.story_id, character_name, {"concurrent_test": True})

        async def cached_read_task(task_id: int):
            start_time = time.time()
            character = await self.cached_orchestrator.cached_character_manager.get_character_memory(
                self.story_id, character_name
            )
            end_time = time.time()
            return (end_time - start_time) * 1000, task_id

        def original_read_task(task_id: int):
            start_time = time.time()
            character = self.original_orchestrator.character_manager.get_character_memory(self.story_id, character_name)
            end_time = time.time()
            return (end_time - start_time) * 1000, task_id

        # Warm up cache
        await self.cached_orchestrator.cached_character_manager.get_character_memory(self.story_id, character_name)

        # Run concurrent cached operations
        cached_start = time.time()
        cached_tasks = [cached_read_task(i) for i in range(concurrent_tasks)]
        cached_results = await asyncio.gather(*cached_tasks)
        cached_total = time.time() - cached_start

        # Run concurrent original operations (simulated with thread pool)
        import concurrent.futures

        original_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_tasks) as executor:
            original_futures = [executor.submit(original_read_task, i) for i in range(concurrent_tasks)]
            original_results = [future.result() for future in concurrent.futures.as_completed(original_futures)]
        original_total = time.time() - original_start

        # Analyze results
        cached_times = [result[0] for result in cached_results]
        original_times = [result[0] for result in original_results]

        return {
            "operation_type": "concurrent_reads",
            "concurrent_tasks": concurrent_tasks,
            "cached_total_time_ms": cached_total * 1000,
            "original_total_time_ms": original_total * 1000,
            "cached_avg_task_time_ms": statistics.mean(cached_times),
            "original_avg_task_time_ms": statistics.mean(original_times),
            "throughput_improvement": (original_total / cached_total if cached_total > 0 else 0),
            "cache_metrics": await self.cached_orchestrator.get_cache_metrics(),
        }

    async def run_comprehensive_benchmark(self) -> dict[str, Any]:
        """Run all benchmarks and return comprehensive results."""
        self.logger.info("Starting comprehensive cache performance benchmark...")

        start_time = datetime.now(UTC)

        results = {
            "benchmark_timestamp": start_time.isoformat(),
            "story_id": self.story_id,
            "benchmarks": {},
        }

        try:
            # Character operations benchmark
            results["benchmarks"]["character_operations"] = await self.benchmark_character_operations(100)

            # Memory snapshots benchmark
            results["benchmarks"]["memory_snapshots"] = await self.benchmark_memory_snapshots(50)

            # Concurrent operations benchmark
            results["benchmarks"]["concurrent_operations"] = await self.benchmark_concurrent_operations(20)

            # Cache metrics
            results["cache_metrics"] = await self.cached_orchestrator.get_cache_metrics()

            # Calculate overall performance summary
            char_speedup = results["benchmarks"]["character_operations"]["performance_improvement"]["speedup_factor"]
            memory_speedup = results["benchmarks"]["memory_snapshots"]["performance_improvement"]["speedup_factor"]
            concurrent_speedup = results["benchmarks"]["concurrent_operations"]["throughput_improvement"]

            results["summary"] = {
                "character_speedup": f"{char_speedup:.2f}x",
                "memory_speedup": f"{memory_speedup:.2f}x",
                "concurrent_speedup": f"{concurrent_speedup:.2f}x",
                "average_speedup": f"{(char_speedup + memory_speedup + concurrent_speedup) / 3:.2f}x",
                "cache_hit_rate": f"{results['cache_metrics']['overall_hit_rate'] * 100:.1f}%",
            }

        except (KeyError, ValueError, TypeError) as e:
            self.logger.exception("Data processing error in benchmark")
            results["error"] = str(e)
        except Exception as e:
            self.logger.exception("Unexpected benchmark error")
            results["error"] = str(e)

        finally:
            await self.cleanup()

        end_time = datetime.now(UTC)
        results["benchmark_duration_seconds"] = (end_time - start_time).total_seconds()

        return results

    async def cleanup(self):
        """Clean up benchmark resources."""
        try:
            await self.cached_orchestrator.close()
        except Exception as e:
            self.logger.exception("Cleanup error")


class CacheMonitor:
    """Real-time cache performance monitoring."""

    def __init__(self, cached_orchestrator: CachedMemoryOrchestrator):
        self.cached_orchestrator = cached_orchestrator
        self.logger = logging.getLogger("openchronicle.monitor")
        self.monitoring = False

    async def start_monitoring(self, interval_seconds: int = 30):
        """Start real-time cache monitoring."""
        self.monitoring = True
        self.logger.info(f"Starting cache monitoring (interval: {interval_seconds}s)")

        while self.monitoring:
            try:
                metrics = await self.cached_orchestrator.get_cache_metrics()
                self.logger.info(
                    f"Cache Performance: Hit Rate: {metrics['overall_hit_rate']:.1%}, "
                    f"Operations/sec: {metrics['operations_per_second']:.1f}, "
                    f"Avg Redis Time: {metrics['avg_redis_response_ms']:.1f}ms"
                )

                # Alert on poor performance
                if metrics["overall_hit_rate"] < 0.7:
                    self.logger.warning(f"Low cache hit rate: {metrics['overall_hit_rate']:.1%}")

                if metrics["avg_redis_response_ms"] > 100:
                    self.logger.warning(f"High Redis latency: {metrics['avg_redis_response_ms']:.1f}ms")

                await asyncio.sleep(interval_seconds)

            except (asyncio.CancelledError, asyncio.TimeoutError) as e:
                self.logger.warning(f"Async operation interrupted during monitoring: {e}")
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                self.logger.exception("Unexpected monitoring error")
                await asyncio.sleep(interval_seconds)

    def stop_monitoring(self):
        """Stop cache monitoring."""
        self.monitoring = False
        self.logger.info("Cache monitoring stopped")


# Convenience function for quick benchmarking
async def quick_benchmark(story_id: str = "quick_benchmark") -> dict[str, Any]:
    """Run a quick performance benchmark."""
    benchmark = CachePerformanceBenchmark(story_id)
    return await benchmark.run_comprehensive_benchmark()
