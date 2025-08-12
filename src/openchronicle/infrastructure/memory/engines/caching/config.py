"""
Distributed Cache Configuration

Configuration classes and data structures for distributed caching.
Extracted from distributed_cache.py for better modularity.
"""

from dataclasses import dataclass
from ..redis_cache import CacheConfig


@dataclass
class ClusterNode:
    """Redis cluster node configuration."""

    host: str
    port: int
    password: str | None = None
    db: int = 0


@dataclass
class PartitionConfig:
    """Cache partitioning configuration."""

    partition_key_patterns: list[str]  # Patterns like "char:*", "scene:*"
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
        redis_password: str | None = None,
        default_ttl: int = 3600,
        character_ttl: int = 7200,
        memory_ttl: int = 1800,
        scene_ttl: int = 3600,
        enable_local_cache: bool = True,
        local_cache_size: int = 1000,
        # Distributed config
        cluster_nodes: list[ClusterNode] | None = None,
        enable_clustering: bool = False,
        partition_config: PartitionConfig | None = None,
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
        self.partition_config = partition_config or PartitionConfig([])
        self.enable_monitoring = enable_monitoring
        self.metrics_collection_interval = metrics_collection_interval
        self.enable_cache_warming = enable_cache_warming
        self.warming_batch_size = warming_batch_size
