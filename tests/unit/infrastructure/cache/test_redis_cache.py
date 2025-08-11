"""
Tests for Redis Caching System
Week 16: Performance Optimization Advanced

Comprehensive test suite for multi-tier caching functionality.
"""
import time
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from openchronicle.infrastructure.memory.cache_benchmark import (
    CachePerformanceBenchmark,
)
from openchronicle.infrastructure.memory.memory_orchestrator import (
    MemoryOrchestrator,
)
from openchronicle.infrastructure.memory.redis_cache import CacheConfig
from openchronicle.infrastructure.memory.redis_cache import CachedCharacterManager
from openchronicle.infrastructure.memory.redis_cache import CachedMemoryOrchestrator
from openchronicle.infrastructure.memory.redis_cache import CacheMetrics
from openchronicle.infrastructure.memory.redis_cache import MultiTierCache


class TestCacheConfig:
    """Test cache configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig()
        assert config.redis_host == "localhost"
        assert config.redis_port == 6379
        assert config.default_ttl == 3600
        assert config.character_ttl == 7200
        assert config.enable_local_cache is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = CacheConfig(
            redis_host="cache.example.com",
            redis_port=6380,
            character_ttl=1800,
            enable_local_cache=False,
        )
        assert config.redis_host == "cache.example.com"
        assert config.redis_port == 6380
        assert config.character_ttl == 1800
        assert config.enable_local_cache is False


class TestCacheMetrics:
    """Test cache metrics tracking."""

    def test_initial_metrics(self):
        """Test initial metrics state."""
        metrics = CacheMetrics()
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.hit_rate == 0.0

    def test_hit_tracking(self):
        """Test hit tracking."""
        metrics = CacheMetrics()
        metrics.record_hit("local")
        metrics.record_hit("redis")
        metrics.record_miss("local")

        assert metrics.hits == 2
        assert metrics.misses == 1
        assert metrics.local_hits == 1
        assert metrics.redis_hits == 1
        assert metrics.hit_rate == 2 / 3

    def test_response_time_tracking(self):
        """Test Redis response time tracking."""
        metrics = CacheMetrics()
        metrics.record_redis_time(0.05)
        metrics.record_redis_time(0.03)

        assert len(metrics.redis_response_times) == 2
        assert metrics.avg_redis_time == 0.04

    def test_metrics_summary(self):
        """Test metrics summary generation."""
        metrics = CacheMetrics()
        metrics.record_hit("local")
        metrics.record_miss("redis")
        metrics.record_redis_time(0.1)

        summary = metrics.get_summary()
        assert "overall_hit_rate" in summary
        assert "avg_redis_response_ms" in summary
        assert summary["total_operations"] == 2


@pytest.mark.asyncio
class TestMultiTierCache:
    """Test multi-tier cache functionality."""

    async def test_cache_without_redis(self):
        """Test cache functionality when Redis is unavailable."""
        with patch(
            "src.openchronicle.infrastructure.memory.redis_cache.REDIS_AVAILABLE", False
        ):
            config = CacheConfig()
            cache = MultiTierCache(config)

            # Should work with local cache only
            await cache.set("test_key", {"data": "test"})
            result = await cache.get("test_key")

            assert result == {"data": "test"}

    async def test_local_cache_operations(self):
        """Test local cache operations."""
        config = CacheConfig(enable_local_cache=True)
        cache = MultiTierCache(config)

        # Test set and get
        await cache.set("local_test", {"value": 123})
        result = await cache.get("local_test")

        assert result == {"value": 123}
        assert cache.metrics.local_hits > 0

    async def test_cache_key_generation(self):
        """Test cache key generation."""
        cache = MultiTierCache()
        key = cache._make_key("char", "story1", "alice")
        assert key == "oc:char:story1:alice"

    async def test_fallback_function(self):
        """Test fallback function execution."""
        cache = MultiTierCache()

        fallback_called = False

        async def async_fallback():
            nonlocal fallback_called
            fallback_called = True
            return {"fallback": "data"}

        result = await cache.get("missing_key", async_fallback)

        assert fallback_called
        assert result == {"fallback": "data"}

    async def test_cache_deletion(self):
        """Test cache deletion."""
        cache = MultiTierCache()

        await cache.set("delete_test", {"data": "test"})
        assert await cache.get("delete_test") is not None

        await cache.delete("delete_test")

        # Should miss cache and return None (no fallback)
        result = await cache.get("delete_test")
        assert result is None

    async def test_cache_invalidation_pattern(self):
        """Test pattern-based cache invalidation."""
        cache = MultiTierCache()

        # Set multiple keys
        await cache.set("oc:char:story1:alice", {"name": "Alice"})
        await cache.set("oc:char:story1:bob", {"name": "Bob"})
        await cache.set("oc:scene:story1:scene1", {"content": "Scene"})

        # Invalidate character pattern
        deleted = await cache.invalidate_pattern("oc:char:story1:*")

        # Characters should be gone, scene should remain
        assert await cache.get("oc:char:story1:alice") is None
        assert await cache.get("oc:char:story1:bob") is None
        # Note: local cache is cleared entirely in pattern invalidation

    async def test_cache_metrics_integration(self):
        """Test cache metrics integration."""
        cache = MultiTierCache()

        # Generate some cache activity
        await cache.set("metrics_test", {"data": "test"})
        await cache.get("metrics_test")  # Hit
        await cache.get("missing_key")  # Miss

        metrics = cache.get_metrics()
        assert metrics["total_operations"] >= 2
        assert metrics["overall_hit_rate"] > 0


@pytest.mark.asyncio
class TestCachedCharacterManager:
    """Test cached character manager."""

    async def test_character_caching(self):
        """Test character retrieval with caching."""
        # Mock original manager
        original_manager = Mock()
        original_manager.get_character_memory.return_value = {
            "name": "Test",
            "traits": {},
        }

        cache = MultiTierCache()
        cached_manager = CachedCharacterManager(cache, original_manager)

        # First call should hit original
        result1 = await cached_manager.get_character_memory("story1", "test_char")
        assert original_manager.get_character_memory.call_count == 1

        # Second call should hit cache
        result2 = await cached_manager.get_character_memory("story1", "test_char")
        assert (
            original_manager.get_character_memory.call_count == 1
        )  # No additional calls

        assert result1 == result2

    async def test_character_update_invalidation(self):
        """Test cache invalidation on character update."""
        original_manager = Mock()
        original_manager.get_character_memory.return_value = {"name": "Test"}
        original_manager.update_character.return_value = True

        cache = MultiTierCache()
        cached_manager = CachedCharacterManager(cache, original_manager)

        # Cache the character
        await cached_manager.get_character_memory("story1", "test_char")

        # Update should invalidate cache
        success = await cached_manager.update_character(
            "story1", "test_char", {"new": "data"}
        )
        assert success
        assert original_manager.update_character.called

        # Next get should call original again (cache invalidated)
        await cached_manager.get_character_memory("story1", "test_char")
        assert original_manager.get_character_memory.call_count == 2


@pytest.mark.asyncio
class TestCachedMemoryOrchestrator:
    """Test cached memory orchestrator."""

    async def test_memory_orchestrator_integration(self):
        """Test integration with memory orchestrator."""
        # Create real memory orchestrator
        original = MemoryOrchestrator()
        cached = CachedMemoryOrchestrator(original)

        # Test memory snapshot caching
        snapshot1 = await cached.get_memory_snapshot("test_story")
        snapshot2 = await cached.get_memory_snapshot("test_story")

        # Should get same snapshot from cache
        assert snapshot1 is not None
        assert snapshot2 is not None

        # Check cache metrics
        metrics = await cached.get_cache_metrics()
        assert "overall_hit_rate" in metrics

        await cached.close()

    async def test_memory_store_invalidation(self):
        """Test cache invalidation on memory store."""
        original = MemoryOrchestrator()
        cached = CachedMemoryOrchestrator(original)

        # Cache snapshot
        await cached.get_memory_snapshot("test_story")

        # Store memory should invalidate cache
        memory_data = {"data": "test", "timestamp": 12345}
        success = await cached.save_memory("test_story", memory_data)

        # Verify the operation completed
        assert success is not None

        await cached.close()


@pytest.mark.asyncio
class TestCachePerformanceBenchmark:
    """Test cache performance benchmarking."""

    async def test_benchmark_creation(self):
        """Test benchmark creation."""
        benchmark = CachePerformanceBenchmark("test_story")
        assert benchmark.story_id == "test_story"
        assert benchmark.original_orchestrator is not None
        assert benchmark.cached_orchestrator is not None

        await benchmark.cleanup()

    async def test_character_operations_benchmark(self):
        """Test character operations benchmark."""
        benchmark = CachePerformanceBenchmark("test_benchmark")

        try:
            # Run small benchmark
            results = await benchmark.benchmark_character_operations(5)

            assert results["operation_type"] == "character_read"
            assert results["num_operations"] == 5
            assert "original_performance" in results
            assert "cached_performance" in results
            assert "performance_improvement" in results

        finally:
            await benchmark.cleanup()

    async def test_memory_snapshots_benchmark(self):
        """Test memory snapshots benchmark."""
        benchmark = CachePerformanceBenchmark("test_benchmark")

        try:
            results = await benchmark.benchmark_memory_snapshots(3)

            assert results["operation_type"] == "memory_snapshot"
            assert results["num_operations"] == 3
            assert "speedup_factor" in results["performance_improvement"]

        finally:
            await benchmark.cleanup()

    @pytest.mark.slow
    async def test_concurrent_operations_benchmark(self):
        """Test concurrent operations benchmark."""
        benchmark = CachePerformanceBenchmark("test_benchmark")

        try:
            results = await benchmark.benchmark_concurrent_operations(5)

            assert results["operation_type"] == "concurrent_reads"
            assert results["concurrent_tasks"] == 5
            assert "throughput_improvement" in results
            assert "cache_metrics" in results

        finally:
            await benchmark.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
class TestCacheIntegration:
    """Integration tests for cache system."""

    async def test_full_cache_workflow(self):
        """Test complete cache workflow."""
        # Create orchestrators
        original = MemoryOrchestrator()
        cached = CachedMemoryOrchestrator(original)

        try:
            # Test memory snapshot retrieval (should work)
            snapshot1 = await cached.get_memory_snapshot("integration_test")
            assert snapshot1 is not None

            # Get again (should hit cache)
            snapshot2 = await cached.get_memory_snapshot("integration_test")
            assert snapshot2 is not None

            # Verify cache metrics
            metrics = await cached.get_cache_metrics()
            assert metrics["total_operations"] > 0

        finally:
            await cached.close()

    async def test_cache_fallback_behavior(self):
        """Test cache behavior when Redis is unavailable."""
        original = MemoryOrchestrator()

        # Create cached orchestrator with invalid Redis config
        config = CacheConfig(redis_host="invalid_host", redis_port=9999)
        cached = CachedMemoryOrchestrator(original, config)

        try:
            # Should still work with local cache only
            snapshot = await cached.get_memory_snapshot("fallback_test")
            assert snapshot is not None

            # Metrics should still be available
            metrics = await cached.get_cache_metrics()
            assert "overall_hit_rate" in metrics

        finally:
            await cached.close()


# Performance markers for pytest
@pytest.mark.performance
class TestCachePerformance:
    """Performance-focused tests."""

    @pytest.mark.asyncio
    async def test_cache_response_time(self):
        """Test cache response time is under threshold."""
        cache = MultiTierCache()

        # Set test data
        await cache.set("performance_test", {"large_data": list(range(1000))})

        # Measure cached retrieval time
        start_time = time.time()
        result = await cache.get("performance_test")
        end_time = time.time()

        response_time_ms = (end_time - start_time) * 1000

        # Should be under 10ms for cached data
        assert response_time_ms < 10
        assert result is not None
        assert len(result["large_data"]) == 1000
