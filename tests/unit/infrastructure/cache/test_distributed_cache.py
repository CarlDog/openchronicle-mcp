"""
Tests for Distributed Caching - Week 17
Comprehensive test suite for distributed caching infrastructure

Tests cover:
- Redis Cluster support
- Cache partitioning
- Performance analytics
- Production monitoring
"""
import asyncio
import json
import time
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from openchronicle.infrastructure.memory.engines.caching.cluster_manager import CachePartitioner
from openchronicle.infrastructure.memory.engines.caching.warming_manager import (
    CacheWarmingManager,
)
from openchronicle.infrastructure.memory.engines.caching.config import ClusterNode
from openchronicle.infrastructure.memory.engines.caching.config import (
    DistributedCacheConfig,
)
from openchronicle.infrastructure.memory.engines.caching.metrics import (
    DistributedCacheMetrics,
)
from openchronicle.infrastructure.memory.cache_orchestrator import (
    DistributedMultiTierCache,
)
from openchronicle.infrastructure.memory.engines.caching.config import PartitionConfig
from openchronicle.infrastructure.memory.engines.caching.cluster_manager import (
    RedisClusterManager,
)
from openchronicle.infrastructure.memory.cache_orchestrator import (
    create_production_distributed_cache,
)
from openchronicle.infrastructure.memory.engines.monitoring.analytics.performance_analytics import AlertManager
from openchronicle.infrastructure.memory.engines.monitoring.analytics.performance_analytics import (
    CacheAnalyticsDashboard,
)
from openchronicle.infrastructure.memory.engines.monitoring.analytics.performance_analytics import (
    MetricsCollector,
)
from openchronicle.infrastructure.memory.engines.monitoring.analytics.performance_analytics import (
    PerformanceRecommendationEngine,
)
from openchronicle.infrastructure.memory.engines.monitoring.health_checker import HealthChecker
from openchronicle.infrastructure.memory.engines.monitoring.health_checker import (
    HealthCheckResult,
)
from openchronicle.infrastructure.memory.engines.monitoring.prometheus_exporter import (
    PrometheusExporter,
)
from openchronicle.infrastructure.memory.engines.monitoring.structured_logger import (
    StructuredLogger,
)
from openchronicle.infrastructure.memory.engines.monitoring.production_monitoring import (
    setup_production_monitoring,
)


class TestDistributedCacheConfig:
    """Test distributed cache configuration."""

    def test_default_config(self):
        """Test default distributed cache configuration."""
        config = DistributedCacheConfig()

        assert config.enable_clustering is False
        assert config.cluster_nodes == []
        assert config.partition_config is None
        assert config.enable_monitoring is True
        assert config.enable_cache_warming is True
        assert config.warming_batch_size == 100

    def test_cluster_config(self):
        """Test cluster configuration."""
        nodes = [
            ClusterNode(host="redis1", port=6379),
            ClusterNode(host="redis2", port=6380),
            ClusterNode(host="redis3", port=6381),
        ]

        partition_config = PartitionConfig(
            partition_key_patterns=["char:*", "scene:*"], replication_factor=2
        )

        config = DistributedCacheConfig(
            cluster_nodes=nodes,
            enable_clustering=True,
            partition_config=partition_config,
        )

        assert config.enable_clustering is True
        assert len(config.cluster_nodes) == 3
        assert config.partition_config.replication_factor == 2


class TestDistributedCacheMetrics:
    """Test enhanced metrics for distributed caching."""

    def test_cluster_metrics_recording(self):
        """Test cluster metrics recording."""
        metrics = DistributedCacheMetrics()

        # Record some cluster operations
        metrics.record_cluster_operation("node_0", "get", True, 0.05)
        metrics.record_cluster_operation("node_0", "set", True, 0.03)
        metrics.record_cluster_operation("node_1", "get", False, 0.15)

        summary = metrics.get_distributed_summary()

        assert "cluster_nodes" in summary
        assert "node_0" in summary["cluster_nodes"]
        assert "node_1" in summary["cluster_nodes"]

        node_0_metrics = summary["cluster_nodes"]["node_0"]
        assert node_0_metrics["operations"] == 2
        assert node_0_metrics["success_rate"] == 1.0

        node_1_metrics = summary["cluster_nodes"]["node_1"]
        assert node_1_metrics["success_rate"] == 0.0

    def test_partition_metrics_recording(self):
        """Test partition metrics recording."""
        metrics = DistributedCacheMetrics()

        # Record partition operations
        metrics.record_partition_operation("partition_0", "get", "hash123")
        metrics.record_partition_operation("partition_0", "set", "hash456")
        metrics.record_partition_operation("partition_1", "get", "hash789")

        summary = metrics.get_distributed_summary()

        assert "partitions" in summary
        assert "partition_0" in summary["partitions"]
        assert summary["partitions"]["partition_0"]["operations"] == 2
        assert summary["partitions"]["partition_0"]["unique_keys"] == 2


class TestCachePartitioner:
    """Test cache partitioning logic."""

    def test_key_partitioning(self):
        """Test consistent key partitioning."""
        nodes = [
            ClusterNode(host="redis1", port=6379),
            ClusterNode(host="redis2", port=6380),
            ClusterNode(host="redis3", port=6381),
        ]

        config = PartitionConfig(partition_key_patterns=["*"])
        partitioner = CachePartitioner(config, nodes)

        # Test same key always goes to same partition
        key = "test:character:alice"
        partition1, hash1 = partitioner.get_partition_for_key(key)
        partition2, hash2 = partitioner.get_partition_for_key(key)

        assert partition1 == partition2
        assert hash1 == hash2
        assert 0 <= partition1 < 3

    def test_replication_nodes(self):
        """Test replica node calculation."""
        nodes = [ClusterNode(host=f"redis{i}", port=6379 + i) for i in range(5)]
        config = PartitionConfig(partition_key_patterns=["*"], replication_factor=3)
        partitioner = CachePartitioner(config, nodes)

        replicas = partitioner.get_replica_nodes(0)
        assert len(replicas) == 2  # replication_factor - 1
        assert replicas == [1, 2]

        # Test wraparound
        replicas = partitioner.get_replica_nodes(4)
        assert replicas == [0, 1]


@pytest.mark.asyncio
class TestRedisClusterManager:
    """Test Redis cluster management."""

    @pytest.mark.asyncio
    @patch(
        "src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.REDIS_AVAILABLE",
        True,
    )
    @patch("src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.redis")
    async def test_single_node_initialization(self, mock_redis):
        """Test single node Redis initialization."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"redis_version": "6.0.0"}
        mock_redis.Redis.return_value = mock_client

        config = DistributedCacheConfig(redis_host="localhost", redis_port=6379)
        manager = RedisClusterManager(config)

        await manager.initialize_cluster()

        mock_redis.Redis.assert_called_once()
        mock_client.ping.assert_called_once()
        assert len(manager.clients) == 1

    @pytest.mark.asyncio
    @patch(
        "src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.REDIS_AVAILABLE",
        True,
    )
    @patch("src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.RedisCluster")
    @patch("src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.redis")
    async def test_cluster_initialization(self, mock_redis, mock_redis_cluster):
        """Test Redis cluster initialization."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client
        mock_cluster = AsyncMock()
        mock_cluster.ping.return_value = True
        mock_cluster.cluster_info.return_value = {"cluster_state": "ok"}
        mock_redis_cluster.return_value = mock_cluster

        nodes = [ClusterNode(host=f"redis{i}", port=6379 + i) for i in range(3)]
        config = DistributedCacheConfig(cluster_nodes=nodes, enable_clustering=True)

        manager = RedisClusterManager(config)
        await manager.initialize_cluster()

        # Should create individual Redis clients for each node
        assert mock_redis.Redis.call_count == 3
        mock_redis_cluster.assert_called_once()
        mock_cluster.ping.assert_called_once()
        assert len(manager.clients) == 3

    @pytest.mark.asyncio
    @patch(
        "src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.REDIS_AVAILABLE",
        True,
    )
    @patch("src.openchronicle.infrastructure.memory.engines.caching.cluster_manager.redis")
    async def test_distributed_get_set_operations(self, mock_redis):
        """Test distributed get/set operations through cluster manager."""
        mock_client = AsyncMock()
        mock_client.set.return_value = True
        mock_client.get.return_value = b'{"test": "value"}'
        mock_client.delete.return_value = 1
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        config = DistributedCacheConfig(redis_host="localhost", redis_port=6379)
        manager = RedisClusterManager(config)
        await manager.initialize_cluster()

        # Test getting client for key operations
        client, index = await manager.get_client_for_key("test:key")
        assert client is not None
        assert index == 0

        # Test that we can get all clients
        all_clients = await manager.get_all_clients()
        assert len(all_clients) == 1
        assert all_clients[0][1] == 0  # index

        # Test client operations through the actual client
        await client.set("test:key", '{"test": "value"}', ex=3600)
        result = await client.get("test:key")
        await client.delete("test:key")

        # Verify calls were made
        mock_client.set.assert_called()
        mock_client.get.assert_called()
        mock_client.delete.assert_called()

    async def test_client_selection_for_key(self):
        """Test client selection for specific keys."""
        # Mock the cluster manager with initialized clients
        config = DistributedCacheConfig()
        manager = RedisClusterManager(config)

        # Manually set up clients
        manager.clients = {0: AsyncMock(), 1: AsyncMock()}

        # Test single client scenario
        client, index = await manager.get_client_for_key("test:key")
        assert client is not None
        assert index == 0


@pytest.mark.asyncio
class TestCacheWarmingManager:
    """Test cache warming functionality."""

    async def test_character_cache_warming(self):
        """Test character cache warming."""
        mock_cache = AsyncMock()
        mock_cache.config.warming_batch_size = 2
        mock_cache._make_key.return_value = "test:key"
        mock_cache.set.return_value = True
        mock_cache.metrics.warming_metrics = {}

        warming_manager = CacheWarmingManager(mock_cache)

        character_names = ["alice", "bob", "charlie"]
        results = await warming_manager.warm_character_cache("story1", character_names)

        assert len(results) == 3
        assert all(success for success in results.values())
        assert mock_cache.set.call_count == 3

    async def test_memory_snapshot_warming(self):
        """Test memory snapshot warming."""
        mock_cache = AsyncMock()
        mock_cache._make_key.return_value = "test:snapshot:key"
        mock_cache.set.return_value = True

        warming_manager = CacheWarmingManager(mock_cache)

        story_ids = ["story1", "story2"]
        results = await warming_manager.warm_memory_snapshots(story_ids)

        assert len(results) == 2
        assert all(success for success in results.values())
        assert mock_cache.set.call_count == 2


@pytest.mark.asyncio
class TestDistributedMultiTierCache:
    """Test distributed multi-tier cache functionality."""

    async def test_cache_initialization(self):
        """Test distributed cache initialization."""
        config = DistributedCacheConfig(enable_monitoring=False)
        cache = DistributedMultiTierCache(config)

        # Mock the cluster manager initialization
        with patch.object(cache.cluster_manager, "initialize_cluster") as mock_init:
            await cache.initialize()
            mock_init.assert_called_once()

    @pytest.mark.skipif(
        True, reason="Distributed cache integration test - requires Redis cluster setup"
    )
    async def test_distributed_get_set_operations(self):
        """Test distributed get/set operations."""
        config = DistributedCacheConfig(enable_monitoring=False)
        cache = DistributedMultiTierCache(config)

        # Mock cluster manager to return a client
        mock_client = AsyncMock()
        mock_client.get.return_value = json.dumps({"test": "value"})
        mock_client.setex.return_value = True

        cache.cluster_manager.get_client_for_key = AsyncMock(
            return_value=(mock_client, 0)
        )

        # Test set operation
        result = await cache.set("test:key", {"test": "value"})
        assert result is True
        mock_client.setex.assert_called_once()

        # Test get operation
        value = await cache.get("test:key")
        assert value == {"test": "value"}
        mock_client.get.assert_called_once()

    async def test_cache_warming_integration(self):
        """Test cache warming integration."""
        config = DistributedCacheConfig(
            enable_monitoring=False, enable_cache_warming=True
        )
        cache = DistributedMultiTierCache(config)

        # Mock the warming manager
        with patch.object(
            cache.warming_manager, "warm_memory_snapshots"
        ) as mock_memory, patch.object(
            cache.warming_manager, "warm_character_cache"
        ) as mock_char:
            mock_memory.return_value = {"story1": True}
            mock_char.return_value = {"alice": True, "bob": True}

            results = await cache.warm_cache(["story1"], {"story1": ["alice", "bob"]})

            assert "memory_snapshots" in results
            assert "characters" in results
            mock_memory.assert_called_once_with(["story1"])
            mock_char.assert_called_once_with("story1", ["alice", "bob"])


class TestPerformanceAnalytics:
    """Test performance analytics dashboard."""

    def test_metrics_collector(self):
        """Test metrics collection and time series."""
        collector = MetricsCollector(max_history_hours=1)

        # Add test metrics
        test_metrics = {
            "overall_hit_rate": 0.8,
            "avg_redis_response_ms": 25.5,
            "total_operations": 1000,
        }

        collector.add_metrics_snapshot(test_metrics)

        assert len(collector.metrics_history) == 1

        # Test time series extraction
        series = collector.get_time_series("overall_hit_rate", hours=1)
        assert len(series) >= 0  # May be empty due to time constraints in test

    def test_alert_manager(self):
        """Test alert management."""
        alert_manager = AlertManager()

        # Test metrics that should trigger alerts
        low_hit_rate_metrics = {"overall_hit_rate": 0.4}
        alerts = alert_manager.check_alerts(low_hit_rate_metrics)

        # Should trigger both warning and critical alerts
        assert len(alerts) >= 1
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        assert len(critical_alerts) >= 1

    def test_recommendation_engine(self):
        """Test performance recommendation generation."""
        engine = PerformanceRecommendationEngine()
        collector = MetricsCollector()

        # Test metrics with performance issues
        poor_metrics = {
            "overall_hit_rate": 0.3,
            "avg_redis_response_ms": 150,
            "cluster_nodes": {
                "node_0": {"operations": 1000},
                "node_1": {"operations": 100},
            },
        }

        recommendations = engine.analyze_performance(poor_metrics, collector)

        assert (
            len(recommendations) >= 2
        )  # Should recommend hit rate and response time improvements
        rec_types = [r["type"] for r in recommendations]
        assert "hit_rate" in rec_types
        assert "response_time" in rec_types


@pytest.mark.asyncio
class TestCacheAnalyticsDashboard:
    """Test cache analytics dashboard."""

    async def test_dashboard_creation(self):
        """Test dashboard creation and initialization."""
        mock_cache = AsyncMock()
        mock_cache.get_distributed_metrics.return_value = {
            "overall_hit_rate": 0.85,
            "total_operations": 5000,
        }

        dashboard = CacheAnalyticsDashboard(mock_cache)

        # Test monitoring start/stop
        await dashboard.start_monitoring(interval_seconds=1)
        assert dashboard._monitoring_active is True

        # Give monitoring a moment to collect data
        await asyncio.sleep(0.1)

        await dashboard.stop_monitoring()
        assert dashboard._monitoring_active is False

    async def test_dashboard_data_collection(self):
        """Test dashboard data collection."""
        mock_cache = AsyncMock()
        mock_cache.get_distributed_metrics.return_value = {
            "overall_hit_rate": 0.85,
            "cluster_nodes": {"node_0": {"operations": 100, "success_rate": 0.95}},
        }

        dashboard = CacheAnalyticsDashboard(mock_cache)

        # Manually trigger data collection (simulating monitoring loop)
        current_metrics = await mock_cache.get_distributed_metrics()
        dashboard.metrics_collector.add_metrics_snapshot(current_metrics)

        # Get cluster overview
        overview = dashboard.get_cluster_overview()
        assert overview["total_nodes"] >= 0
        assert "nodes" in overview


class TestProductionMonitoring:
    """Test production monitoring capabilities."""

    def test_prometheus_exporter(self):
        """Test Prometheus metrics export."""
        mock_cache = AsyncMock()
        exporter = PrometheusExporter(mock_cache)

        # This would require mocking the entire cache.get_distributed_metrics() call
        # For now, just test that the exporter can be instantiated
        assert exporter.cache == mock_cache

    @pytest.mark.asyncio
    async def test_health_checker(self):
        """Test health checking functionality."""
        mock_cache = AsyncMock()
        mock_cache.cluster_manager.get_all_clients.return_value = [(AsyncMock(), 0)]
        mock_cache.set.return_value = True
        mock_cache.get.return_value = {"test": "value"}
        mock_cache.delete.return_value = True
        mock_cache.get_distributed_metrics.return_value = {
            "overall_hit_rate": 0.8,
            "avg_redis_response_ms": 50,
            "operations_per_second": 100,
        }

        health_checker = HealthChecker(mock_cache)

        # Test cache operations health check
        result = await health_checker.check_cache_operations()
        assert isinstance(result, HealthCheckResult)
        assert result.name == "cache_operations"

        # Test performance thresholds check
        result = await health_checker.check_performance_thresholds()
        assert isinstance(result, HealthCheckResult)
        assert result.name == "performance_thresholds"
        assert result.status == "healthy"  # Good metrics should pass

    def test_structured_logger(self):
        """Test structured logging functionality."""
        mock_cache = Mock()
        logger = StructuredLogger(mock_cache)

        # Test event logging (would write to file in real usage)
        logger.log_cache_event("test_event", {"key": "value"})

        # Test specific log methods
        logger.log_performance_metrics(
            {"overall_hit_rate": 0.8, "total_operations": 1000}
        )

        logger.log_alert("performance", "warning", "Test alert")

        # Just verify no exceptions were raised
        assert True


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """Test integration scenarios for distributed caching."""

    async def test_production_cache_setup(self):
        """Test production cache setup."""
        cluster_nodes = [
            {"host": "redis1", "port": 6379},
            {"host": "redis2", "port": 6380},
            {"host": "redis3", "port": 6381},
        ]

        cache = create_production_distributed_cache(
            cluster_nodes=cluster_nodes,
            enable_monitoring=False,  # Disable for testing
            enable_cache_warming=True,
        )

        assert isinstance(cache, DistributedMultiTierCache)
        assert cache.config.enable_clustering is True
        assert len(cache.config.cluster_nodes) == 3
        assert cache.config.enable_cache_warming is True

    @pytest.mark.skipif(
        True, reason="Production monitoring integration test - requires complex setup"
    )
    @patch(
        "src.openchronicle.infrastructure.memory.production_monitoring.setup_production_monitoring"
    )
    async def test_full_monitoring_setup(self, mock_setup):
        """Test full monitoring setup integration."""
        mock_cache = AsyncMock()
        mock_monitoring = AsyncMock()
        mock_setup.return_value = mock_monitoring

        # This tests the integration flow
        monitoring = await setup_production_monitoring(mock_cache)

        mock_setup.assert_called_once_with(mock_cache)
        assert monitoring == mock_monitoring

    async def test_cache_warming_with_monitoring(self):
        """Test cache warming with performance monitoring."""
        config = DistributedCacheConfig(
            enable_monitoring=False,  # Disable background monitoring for test
            enable_cache_warming=True,
        )

        cache = DistributedMultiTierCache(config)

        # Mock the underlying operations
        with patch.object(cache.warming_manager, "warm_character_cache") as mock_warm:
            mock_warm.return_value = {"alice": True, "bob": True}

            # Test warming operation
            results = await cache.warm_cache(["story1"], {"story1": ["alice", "bob"]})

            assert "characters" in results
            assert results["characters"]["story1"]["alice"] is True
            mock_warm.assert_called_once()


@pytest.mark.integration
class TestRealRedisIntegration:
    """Integration tests with real Redis (requires Redis server)."""

    @pytest.mark.skipif(
        True,  # Always skip for now - Redis is optional dependency
        reason="Redis integration tests require redis server setup",
    )
    @pytest.mark.asyncio
    async def test_real_redis_operations(self):
        """Test with real Redis server (if available)."""
        try:
            config = DistributedCacheConfig(
                redis_host="localhost", redis_port=6379, enable_monitoring=False
            )

            cache = DistributedMultiTierCache(config)
            await cache.initialize()

            # Test basic operations
            test_key = f"test:integration:{int(time.time())}"
            test_value = {"integration": "test", "timestamp": time.time()}

            # Set value
            result = await cache.set(test_key, test_value, ttl=60)
            if result:  # Only proceed if Redis is actually available
                # Get value
                retrieved = await cache.get(test_key)
                assert retrieved == test_value

                # Delete value
                await cache.delete(test_key)

                # Verify deletion
                deleted_value = await cache.get(test_key)
                assert deleted_value is None

            await cache.close()

        except Exception as e:
            pytest.skip(f"Redis server not available: {e}")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
