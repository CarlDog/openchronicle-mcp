"""
Redis Cluster Management

Handles Redis cluster connections and operations for distributed caching.
Extracted from distributed_cache.py for better modularity.
"""

import logging
from typing import Any


try:
    import redis
    from redis.cluster import RedisCluster
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    RedisCluster = None
    REDIS_AVAILABLE = False

from .config import ClusterNode
from .config import DistributedCacheConfig
from .config import PartitionConfig


class CachePartitioner:
    """Handles cache key partitioning across multiple Redis instances."""

    def __init__(self, config: PartitionConfig, cluster_nodes: list[ClusterNode]):
        self.config = config
        self.cluster_nodes = cluster_nodes
        self.logger = logging.getLogger("openchronicle.cache.partitioner")

    def _hash_key(self, key: str) -> str:
        """Generate hash for partitioning key."""
        import hashlib

        if self.config.hash_algorithm == "sha256":
            return hashlib.sha256(key.encode()).hexdigest()
        if self.config.hash_algorithm == "md5":
            return hashlib.md5(key.encode()).hexdigest()
        # Simple string hash fallback
        return str(hash(key))

    def get_partition_for_key(self, key: str) -> tuple[int, str]:
        """
        Determine which partition (Redis node) should handle this key.

        Returns:
            Tuple of (node_index, key_hash)
        """
        key_hash = self._hash_key(key)

        # Use consistent hashing
        partition_index = int(key_hash, 16) % len(self.cluster_nodes)

        return partition_index, key_hash

    def get_replica_nodes(self, primary_index: int) -> list[int]:
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
        self.clients: dict[int, Any] = {}
        self.cluster_client: Any | None = None
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
                self.logger.exception("Failed to initialize Redis cluster")
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
            self.logger.exception("Failed to initialize single Redis node")

    async def get_client_for_key(self, key: str) -> tuple[Any | None, int]:
        """Get the appropriate Redis client for a key."""
        if not self.clients:
            return None, -1

        if self.partitioner and len(self.clients) > 1:
            node_index, _ = self.partitioner.get_partition_for_key(key)
            return self.clients.get(node_index), node_index
        # Use first available client
        client = list(self.clients.values())[0]
        return client, 0

    async def get_all_clients(self) -> list[tuple[Any, int]]:
        """Get all active Redis clients."""
        return [(client, index) for index, client in self.clients.items()]

    async def close_all(self):
        """Close all Redis connections."""
        """Initialize Redis connections (cluster if configured, always attempt single-node fallback)."""
        if not REDIS_AVAILABLE or redis is None:
            self.logger.warning("Redis not available - skipping Redis initialization")
            return

        try:
            # Cluster path
            if self.config.enable_clustering and self.config.cluster_nodes:
                for i, node in enumerate(self.config.cluster_nodes):
                    client = redis.Redis(
                        host=node.host,
                        port=node.port,
                        db=node.db,
                        password=node.password,
                        decode_responses=True,
                    )
                    try:
                        ping_result = client.ping()
                        if hasattr(ping_result, "__await__"):
                            await ping_result
                    except TypeError:
                        client.ping()
                    self.clients[i] = client
                    self.logger.info(
                        f"Connected to Redis node {i}: {node.host}:{node.port}"
                    )

                # Optional cluster logical client
                if (
                    len(self.config.cluster_nodes) >= 3
                    and RedisCluster is not None
                    and not self.cluster_client
                ):
                    cluster_startup_nodes = [
                        {"host": node.host, "port": node.port}
                        for node in self.config.cluster_nodes
                    ]
                    try:
                        self.cluster_client = RedisCluster(
                            startup_nodes=cluster_startup_nodes,
                            decode_responses=True,
                            skip_full_coverage_check=True,
                        )
                        ping_result = self.cluster_client.ping()
                        if hasattr(ping_result, "__await__"):
                            await ping_result
                        self.logger.info("Redis cluster client initialized")
                    except Exception:
                        self.logger.warning(
                            "Cluster client initialization failed; continuing with node clients only"
                        )

            # Always attempt single-node fallback if no clients were created
            if not self.clients:
                await self._initialize_single_node()
        except Exception:
            self.logger.exception(
                "Redis initialization error; attempting single-node fallback"
            )
            if not self.clients:
                await self._initialize_single_node()
