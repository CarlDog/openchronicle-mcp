"""
Cache Orchestrator

Main orchestrator for distributed multi-tier caching infrastructure.
Coordinates modular caching engines for enhanced functionality.

Features:
- Redis Cluster support
- Cache partitioning  
- Advanced monitoring
- Cache warming
- Modular component architecture
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable

from .engines.caching.redis_cache import MultiTierCache
from .engines.caching.config import DistributedCacheConfig, ClusterNode, PartitionConfig
from .engines.caching.metrics import DistributedCacheMetrics
from .engines.caching.cluster_manager import RedisClusterManager
from .engines.caching.warming_manager import CacheWarmingManager

try:
    from cachetools import TTLCache
    CACHETOOLS_AVAILABLE = True
except ImportError:
    TTLCache = None
    CACHETOOLS_AVAILABLE = False


class RetryPolicy:
    """Simple retry policy for monitoring operations."""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 0.5, retry_exceptions: tuple = (Exception,)):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.retry_exceptions = retry_exceptions
    
    async def run(self, func):
        """Run function with retry policy."""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                else:
                    return func()
            except self.retry_exceptions as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    await asyncio.sleep(self.base_delay * (2 ** attempt))
                continue
        
        raise last_exception


class DistributedMultiTierCache(MultiTierCache):
    """
    Enhanced multi-tier cache with distributed capabilities.

    Features:
    - Redis Cluster support
    - Cache partitioning
    - Advanced monitoring
    - Cache warming
    """

    def __init__(self, config: DistributedCacheConfig | None = None):
        self.config = config or DistributedCacheConfig()
        self.logger = logging.getLogger("openchronicle.cache.distributed")
        self.metrics = DistributedCacheMetrics()

        # Local memory cache
        if self.config.enable_local_cache and CACHETOOLS_AVAILABLE:
            self.local_cache = TTLCache(
                maxsize=self.config.local_cache_size, ttl=300  # 5 minutes local TTL
            )
        else:
            self.local_cache = None

        # Distributed Redis management
        self.cluster_manager = RedisClusterManager(self.config)
        self.warming_manager = CacheWarmingManager(self)

        # Monitoring
        self._monitoring_task = None
        if self.config.enable_monitoring:
            self._start_monitoring()

    async def initialize(self):
        """Initialize distributed cache infrastructure."""
        await self.cluster_manager.initialize_cluster()
        self.logger.info("Distributed cache initialized")

    def _start_monitoring(self):
        """Start background monitoring task."""

        async def monitor():
            policy = RetryPolicy(max_attempts=3, base_delay=0.5, retry_exceptions=(Exception,))
            while True:
                try:
                    await asyncio.sleep(self.config.metrics_collection_interval)
                    try:
                        await policy.run(lambda: self._collect_metrics())
                    except Exception as e:
                        # Final failure after retries; logged inside _collect_metrics as well
                        self.logger.error(f"Monitoring collection failed after retries: {e}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Monitoring error: {e}")

        self._monitoring_task = asyncio.create_task(monitor())

    async def _collect_metrics(self):
        """Collect periodic metrics from all Redis nodes."""
        try:
            clients = await self.cluster_manager.get_all_clients()

            for client, node_index in clients:
                start_time = time.time()
                try:
                    info = await client.info()
                    response_time = time.time() - start_time

                    self.metrics.record_cluster_operation(
                        f"node_{node_index}", "info", True, response_time
                    )

                    # Log important Redis metrics
                    memory_used = info.get("used_memory_human", "unknown")
                    connected_clients = info.get("connected_clients", 0)
                    keyspace_hits = info.get("keyspace_hits", 0)
                    keyspace_misses = info.get("keyspace_misses", 0)

                    self.logger.debug(
                        f"Node {node_index} - Memory: {memory_used}, "
                        f"Clients: {connected_clients}, "
                        f"Hit ratio: {keyspace_hits}/{keyspace_hits + keyspace_misses}"
                    )

                except Exception as e:
                    self.metrics.record_cluster_operation(
                        f"node_{node_index}", "info", False, time.time() - start_time
                    )
                    self.logger.warning(
                        f"Failed to collect metrics from node {node_index}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Metrics collection error: {e}")

    def _make_key(self, *args: str) -> str:
        """Create a cache key from arguments."""
        return ":".join(str(arg) for arg in args)

    async def get(
        self,
        key: str,
        fallback_func: Callable[..., Any] | None = None,
        ttl: int | None = None,
    ) -> Any | None:
        """Enhanced get with distributed support."""
        start_time = time.time()

        # Tier 1: Local memory cache
        if self.local_cache is not None and key in self.local_cache:
            self.metrics.record_hit("local")
            self.logger.debug(f"Local cache hit: {key}")
            return self.local_cache[key]

        if self.local_cache is not None:
            self.metrics.record_miss("local")

        # Tier 2: Distributed Redis cache
        redis_client, node_index = await self.cluster_manager.get_client_for_key(key)
        if redis_client:
            try:
                redis_start = time.time()
                redis_value = await redis_client.get(key)
                redis_time = time.time() - redis_start

                # Record partition metrics
                if self.cluster_manager.partitioner:
                    (
                        _,
                        key_hash,
                    ) = self.cluster_manager.partitioner.get_partition_for_key(key)
                    self.metrics.record_partition_operation(
                        f"partition_{node_index}", "get", key_hash
                    )

                # Record cluster metrics
                self.metrics.record_cluster_operation(
                    f"node_{node_index}", "get", True, redis_time
                )

                if redis_value is not None:
                    self.metrics.record_hit("redis")
                    self.logger.debug(f"Redis cache hit: {key} (node {node_index})")

                    # Deserialize and store in local cache
                    try:
                        value = json.loads(redis_value)
                        if self.local_cache is not None:
                            self.local_cache[key] = value
                        return value
                    except json.JSONDecodeError:
                        self.logger.error(
                            f"Failed to deserialize Redis value for key: {key}"
                        )
                else:
                    self.metrics.record_miss("redis")

            except Exception as e:
                self.logger.error(
                    f"Redis error for key {key} on node {node_index}: {e}"
                )
                self.metrics.record_cluster_operation(
                    f"node_{node_index}", "get", False, time.time() - redis_start
                )

        # Tier 3: Fallback function (usually database)
        if fallback_func:
            self.logger.debug(f"Cache miss, calling fallback for: {key}")
            value = (
                await fallback_func()
                if asyncio.iscoroutinefunction(fallback_func)
                else fallback_func()
            )

            if value is not None:
                # Store in cache with appropriate TTL
                await self.set(key, value, ttl or self.config.default_ttl)

            return value

        return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Enhanced set with distributed support."""
        ttl = ttl or self.config.default_ttl
        success = True

        # Store in local cache
        if self.local_cache is not None:
            try:
                self.local_cache[key] = value
            except Exception as e:
                self.logger.error(f"Local cache error for key {key}: {e}")
                success = False

        # Store in distributed Redis
        redis_client, node_index = await self.cluster_manager.get_client_for_key(key)
        if redis_client:
            try:
                start_time = time.time()
                serialized = json.dumps(value, default=str)
                await redis_client.setex(key, ttl, serialized)
                response_time = time.time() - start_time

                # Record metrics
                self.metrics.record_cluster_operation(
                    f"node_{node_index}", "set", True, response_time
                )

                if self.cluster_manager.partitioner:
                    (
                        _,
                        key_hash,
                    ) = self.cluster_manager.partitioner.get_partition_for_key(key)
                    self.metrics.record_partition_operation(
                        f"partition_{node_index}", "set", key_hash
                    )

                self.logger.debug(
                    f"Cached in Redis: {key} (node {node_index}, TTL: {ttl}s)"
                )

                # Handle replication if configured
                await self._replicate_to_replicas(key, value, ttl, node_index)

            except Exception as e:
                self.logger.error(
                    f"Redis cache error for key {key} on node {node_index}: {e}"
                )
                self.metrics.record_cluster_operation(
                    f"node_{node_index}", "set", False, time.time() - start_time
                )
                success = False

        return success

    async def _replicate_to_replicas(
        self, key: str, value: Any, ttl: int, primary_index: int
    ):
        """Replicate data to replica nodes if configured."""
        if not self.cluster_manager.partitioner:
            return

        replica_indices = self.cluster_manager.partitioner.get_replica_nodes(
            primary_index
        )
        if not replica_indices:
            return

        serialized = json.dumps(value, default=str)

        for replica_index in replica_indices:
            replica_client = self.cluster_manager.clients.get(replica_index)
            if replica_client:
                try:
                    await replica_client.setex(f"replica:{key}", ttl, serialized)
                    self.logger.debug(f"Replicated {key} to node {replica_index}")
                except Exception as e:
                    self.logger.warning(
                        f"Replication failed for {key} to node {replica_index}: {e}"
                    )

    async def warm_cache(
        self, story_ids: list[str], character_names: dict[str, list[str]]
    ) -> dict[str, Any]:
        """Warm cache with commonly accessed data."""
        if not self.config.enable_cache_warming:
            return {"warming_disabled": True}

        results = {}

        # Warm memory snapshots
        memory_results = await self.warming_manager.warm_memory_snapshots(story_ids)
        results["memory_snapshots"] = memory_results

        # Warm character data
        character_results = {}
        for story_id, names in character_names.items():
            story_results = await self.warming_manager.warm_character_cache(
                story_id, names
            )
            character_results[story_id] = story_results

        results["characters"] = character_results

        return results

    async def get_distributed_metrics(self) -> dict[str, Any]:
        """Get comprehensive distributed cache metrics."""
        return self.metrics.get_distributed_summary()

    async def close(self):
        """Close all connections and cleanup."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        await self.cluster_manager.close_all()
        self.logger.info("Distributed cache closed")


# Convenience function for production setup
def create_production_distributed_cache(
    cluster_nodes: list[dict[str, Any]],
    enable_monitoring: bool = True,
    enable_cache_warming: bool = True,
) -> DistributedMultiTierCache:
    """Create production-ready distributed cache."""

    nodes = [
        ClusterNode(
            host=node["host"],
            port=node["port"],
            password=node.get("password"),
            db=node.get("db", 0),
        )
        for node in cluster_nodes
    ]

    partition_config = PartitionConfig(
        partition_key_patterns=["char:*", "scene:*", "snapshot:*"],
        hash_algorithm="sha256",
        replication_factor=min(2, len(nodes)),  # Max 2 replicas
        consistency_level="eventual",
    )

    config = DistributedCacheConfig(
        cluster_nodes=nodes,
        enable_clustering=len(nodes) > 1,
        partition_config=partition_config,
        enable_monitoring=enable_monitoring,
        enable_cache_warming=enable_cache_warming,
        character_ttl=3600,  # 1 hour for production
        memory_ttl=1800,  # 30 minutes for production
        default_ttl=2400,  # 40 minutes for production
    )

    return DistributedMultiTierCache(config)
