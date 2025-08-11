"""
Distributed Caching Infrastructure - Week 17
Redis Cluster Support and Cache Partitioning

Implements distributed caching strategies for production-ready scaling:
- Redis Cluster support for high availability
- Cache partitioning across multiple Redis instances
- Advanced performance analytics dashboard
- Production monitoring integration
- Cache warming strategies
"""

import hashlib
import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, UTC, timedelta
from dataclasses import dataclass, asdict
import logging

try:
    import redis.asyncio as redis
    from redis.asyncio import RedisCluster

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    RedisCluster = None

from .redis_cache import CacheConfig, CacheMetrics, MultiTierCache


@dataclass
class ClusterNode:
    """Redis cluster node configuration."""

    host: str
    port: int
    password: Optional[str] = None
    db: int = 0


@dataclass
class PartitionConfig:
    """Cache partitioning configuration."""

    partition_key_patterns: List[str]  # Patterns like "char:*", "scene:*"
    hash_algorithm: str = "sha256"
    replication_factor: int = 1
    consistency_level: str = "eventual"  # "eventual", "strong"


class DistributedCacheConfig(CacheConfig):
    """Enhanced configuration for distributed caching."""

    def __init__(
        self,
        # Base config
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        default_ttl: int = 3600,
        character_ttl: int = 7200,
        memory_ttl: int = 1800,
        scene_ttl: int = 3600,
        enable_local_cache: bool = True,
        local_cache_size: int = 1000,
        # Distributed config
        cluster_nodes: Optional[List[ClusterNode]] = None,
        enable_clustering: bool = False,
        partition_config: Optional[PartitionConfig] = None,
        enable_monitoring: bool = True,
        metrics_collection_interval: int = 60,
        enable_cache_warming: bool = True,
        warming_batch_size: int = 100,
    ):

        super().__init__(
            redis_host,
            redis_port,
            redis_db,
            redis_password,
            default_ttl,
            character_ttl,
            memory_ttl,
            scene_ttl,
            enable_local_cache,
            local_cache_size,
        )

        self.cluster_nodes = cluster_nodes or []
        self.enable_clustering = enable_clustering
        self.partition_config = partition_config
        self.enable_monitoring = enable_monitoring
        self.metrics_collection_interval = metrics_collection_interval
        self.enable_cache_warming = enable_cache_warming
        self.warming_batch_size = warming_batch_size


class DistributedCacheMetrics(CacheMetrics):
    """Enhanced metrics for distributed caching."""

    def __init__(self):
        super().__init__()
        self.cluster_metrics = {}
        self.partition_metrics = {}
        self.warming_metrics = {
            "operations": 0,
            "success_rate": 0.0,
            "avg_time_ms": 0.0,
        }

    def record_cluster_operation(
        self, node_id: str, operation: str, success: bool, response_time: float
    ):
        """Record cluster-specific operation."""
        if node_id not in self.cluster_metrics:
            self.cluster_metrics[node_id] = {
                "operations": 0,
                "successes": 0,
                "failures": 0,
                "response_times": [],
                "last_operation": None,
            }

        metrics = self.cluster_metrics[node_id]
        metrics["operations"] += 1
        metrics["last_operation"] = datetime.now(UTC).isoformat()

        if success:
            metrics["successes"] += 1
        else:
            metrics["failures"] += 1

        metrics["response_times"].append(response_time)
        # Keep only last 100 measurements per node
        if len(metrics["response_times"]) > 100:
            metrics["response_times"] = metrics["response_times"][-100:]

    def record_partition_operation(
        self, partition_id: str, operation: str, key_hash: str
    ):
        """Record partition-specific operation."""
        if partition_id not in self.partition_metrics:
            self.partition_metrics[partition_id] = {
                "operations": 0,
                "unique_keys": set(),
                "last_access": None,
            }

        metrics = self.partition_metrics[partition_id]
        metrics["operations"] += 1
        metrics["unique_keys"].add(key_hash)
        metrics["last_access"] = datetime.now(UTC).isoformat()

        # Limit set size to prevent memory issues
        if len(metrics["unique_keys"]) > 10000:
            # Keep random subset
            unique_list = list(metrics["unique_keys"])
            metrics["unique_keys"] = set(unique_list[-5000:])

    def get_distributed_summary(self) -> Dict[str, Any]:
        """Get comprehensive distributed cache metrics."""
        base_summary = self.get_summary()

        # Cluster metrics summary
        cluster_summary = {}
        for node_id, metrics in self.cluster_metrics.items():
            total_ops = metrics["operations"]
            success_rate = metrics["successes"] / total_ops if total_ops > 0 else 0
            avg_response = (
                sum(metrics["response_times"]) / len(metrics["response_times"])
                if metrics["response_times"]
                else 0
            )

            cluster_summary[node_id] = {
                "operations": total_ops,
                "success_rate": success_rate,
                "avg_response_ms": avg_response * 1000,
                "last_operation": metrics["last_operation"],
            }

        # Partition metrics summary
        partition_summary = {}
        for partition_id, metrics in self.partition_metrics.items():
            partition_summary[partition_id] = {
                "operations": metrics["operations"],
                "unique_keys": len(metrics["unique_keys"]),
                "last_access": metrics["last_access"],
            }

        return {
            **base_summary,
            "cluster_nodes": cluster_summary,
            "partitions": partition_summary,
            "cache_warming": self.warming_metrics,
        }


class CachePartitioner:
    """Handles cache key partitioning across multiple Redis instances."""

    def __init__(self, config: PartitionConfig, cluster_nodes: List[ClusterNode]):
        self.config = config
        self.cluster_nodes = cluster_nodes
        self.logger = logging.getLogger("openchronicle.cache.partitioner")

    def _hash_key(self, key: str) -> str:
        """Generate hash for partitioning key."""
        if self.config.hash_algorithm == "sha256":
            return hashlib.sha256(key.encode()).hexdigest()
        elif self.config.hash_algorithm == "md5":
            return hashlib.md5(key.encode()).hexdigest()
        else:
            # Simple string hash fallback
            return str(hash(key))

    def get_partition_for_key(self, key: str) -> Tuple[int, str]:
        """
        Determine which partition (Redis node) should handle this key.

        Returns:
            Tuple of (node_index, key_hash)
        """
        key_hash = self._hash_key(key)

        # Use consistent hashing
        partition_index = int(key_hash, 16) % len(self.cluster_nodes)

        return partition_index, key_hash

    def get_replica_nodes(self, primary_index: int) -> List[int]:
        """Get replica node indices for replication."""
        if self.config.replication_factor <= 1:
            return []

        replicas = []
        total_nodes = len(self.cluster_nodes)

        for i in range(1, self.config.replication_factor):
            replica_index = (primary_index + i) % total_nodes
            replicas.append(replica_index)

        return replicas


class RedisClusterManager:
    """Manages Redis cluster connections and operations."""

    def __init__(self, config: DistributedCacheConfig):
        self.config = config
        self.logger = logging.getLogger("openchronicle.cache.cluster")
        self.clients: Dict[int, Any] = {}
        self.cluster_client: Optional[Any] = None
        self.partitioner = None

        if config.cluster_nodes:
            self.partitioner = CachePartitioner(
                config.partition_config or PartitionConfig([]), config.cluster_nodes
            )

    async def initialize_cluster(self):
        """Initialize Redis cluster connections."""
        if not REDIS_AVAILABLE:
            self.logger.warning("Redis not available, clustering disabled")
            return

        if self.config.enable_clustering and self.config.cluster_nodes:
            try:
                # Initialize individual node clients
                for i, node in enumerate(self.config.cluster_nodes):
                    if redis is not None:
                        client = redis.Redis(
                            host=node.host,
                            port=node.port,
                            db=node.db,
                            password=node.password,
                            decode_responses=True,
                        )
                        await client.ping()
                        self.clients[i] = client
                        self.logger.info(
                            f"Connected to Redis node {i}: {node.host}:{node.port}"
                        )

                # Initialize cluster client if enough nodes
                if len(self.config.cluster_nodes) >= 3 and RedisCluster is not None:
                    cluster_startup_nodes = [
                        {"host": node.host, "port": node.port}
                        for node in self.config.cluster_nodes
                    ]

                    self.cluster_client = RedisCluster(
                        startup_nodes=cluster_startup_nodes,
                        decode_responses=True,
                        skip_full_coverage_check=True,
                    )
                    await self.cluster_client.ping()
                    self.logger.info("Redis cluster client initialized")

            except Exception as e:
                self.logger.error(f"Failed to initialize Redis cluster: {e}")
                # Fallback to single node
                await self._initialize_single_node()
        else:
            await self._initialize_single_node()

    async def _initialize_single_node(self):
        """Initialize single Redis node as fallback."""
        try:
            if redis is not None:
                client = redis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    decode_responses=True,
                )
                await client.ping()
                self.clients[0] = client
                self.logger.info(
                    f"Connected to single Redis node: {self.config.redis_host}:{self.config.redis_port}"
                )
        except Exception as e:
            self.logger.error(f"Failed to initialize single Redis node: {e}")

    async def get_client_for_key(self, key: str) -> Tuple[Optional[Any], int]:
        """Get the appropriate Redis client for a key."""
        if not self.clients:
            return None, -1

        if self.partitioner and len(self.clients) > 1:
            node_index, _ = self.partitioner.get_partition_for_key(key)
            return self.clients.get(node_index), node_index
        else:
            # Use first available client
            client = list(self.clients.values())[0]
            return client, 0

    async def get_all_clients(self) -> List[Tuple[Any, int]]:
        """Get all active Redis clients."""
        return [(client, index) for index, client in self.clients.items()]

    async def close_all(self):
        """Close all Redis connections."""
        for client in self.clients.values():
            await client.close()

        if self.cluster_client:
            await self.cluster_client.close()

        self.logger.info("All Redis connections closed")


class CacheWarmingManager:
    """Manages cache warming strategies for optimal performance."""

    def __init__(self, cache_manager: "DistributedMultiTierCache"):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger("openchronicle.cache.warming")
        self.warming_tasks = {}

    async def warm_character_cache(
        self, story_id: str, character_names: List[str]
    ) -> Dict[str, bool]:
        """Warm cache with character data."""
        self.logger.info(
            f"Warming character cache for story {story_id}: {len(character_names)} characters"
        )

        results = {}
        batch_size = self.cache_manager.config.warming_batch_size

        for i in range(0, len(character_names), batch_size):
            batch = character_names[i : i + batch_size]
            batch_tasks = []

            for character_name in batch:
                task = self._warm_single_character(story_id, character_name)
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for character_name, result in zip(batch, batch_results):
                results[character_name] = not isinstance(result, Exception)
                if isinstance(result, Exception):
                    self.logger.error(
                        f"Failed to warm cache for {character_name}: {result}"
                    )

        success_count = sum(1 for success in results.values() if success)
        success_rate = success_count / len(results) if results else 0

        self.cache_manager.metrics.warming_metrics.update(
            {"operations": len(results), "success_rate": success_rate}
        )

        self.logger.info(
            f"Cache warming completed: {success_count}/{len(results)} successful"
        )
        return results

    async def _warm_single_character(self, story_id: str, character_name: str) -> bool:
        """Warm cache for a single character."""
        try:
            start_time = time.time()

            # Use the cache system to load character data
            # This will populate both local and Redis caches
            cache_key = self.cache_manager._make_key("char", story_id, character_name)

            # Simulate loading from database (would be actual database call in production)
            character_data = {
                "name": character_name,
                "traits": {"warmed": True},
                "last_warmed": datetime.now(UTC).isoformat(),
            }

            await self.cache_manager.set(cache_key, character_data)

            warming_time = (time.time() - start_time) * 1000
            current_avg = self.cache_manager.metrics.warming_metrics.get(
                "avg_time_ms", 0
            )
            # Simple moving average
            new_avg = (current_avg + warming_time) / 2
            self.cache_manager.metrics.warming_metrics["avg_time_ms"] = new_avg

            return True

        except Exception as e:
            self.logger.error(f"Cache warming failed for {character_name}: {e}")
            return False

    async def warm_memory_snapshots(self, story_ids: List[str]) -> Dict[str, bool]:
        """Warm cache with memory snapshots."""
        self.logger.info(f"Warming memory snapshot cache for {len(story_ids)} stories")

        results = {}
        for story_id in story_ids:
            try:
                cache_key = self.cache_manager._make_key(
                    "snapshot", story_id, "current"
                )

                # Simulate memory snapshot data
                snapshot_data = {
                    "story_id": story_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "characters": [],
                    "warmed": True,
                }

                await self.cache_manager.set(cache_key, snapshot_data)
                results[story_id] = True

            except Exception as e:
                self.logger.error(f"Failed to warm memory snapshot for {story_id}: {e}")
                results[story_id] = False

        return results


class DistributedMultiTierCache(MultiTierCache):
    """
    Enhanced multi-tier cache with distributed capabilities.

    Features:
    - Redis Cluster support
    - Cache partitioning
    - Advanced monitoring
    - Cache warming
    """

    def __init__(self, config: Optional[DistributedCacheConfig] = None):
        self.config = config or DistributedCacheConfig()
        self.logger = logging.getLogger("openchronicle.cache.distributed")
        self.metrics = DistributedCacheMetrics()

        # Local memory cache
        if self.config.enable_local_cache:
            from cachetools import TTLCache

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
            while True:
                try:
                    await asyncio.sleep(self.config.metrics_collection_interval)
                    await self._collect_metrics()
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

    async def get(
        self,
        key: str,
        fallback_func: Optional[callable] = None,
        ttl: Optional[int] = None,
    ) -> Optional[Any]:
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
                    _, key_hash = (
                        self.cluster_manager.partitioner.get_partition_for_key(key)
                    )
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
                    _, key_hash = (
                        self.cluster_manager.partitioner.get_partition_for_key(key)
                    )
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
        self, story_ids: List[str], character_names: Dict[str, List[str]]
    ) -> Dict[str, Any]:
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

    async def get_distributed_metrics(self) -> Dict[str, Any]:
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
    cluster_nodes: List[Dict[str, Any]],
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
