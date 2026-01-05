"""
Cache Warming Management

Manages cache warming strategies for optimal performance.
Extracted from distributed_cache.py for better modularity.
"""

import asyncio
import logging
import time
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ...cache_orchestrator import DistributedMultiTierCache


class CacheWarmingManager:
    """Manages cache warming strategies for optimal performance."""

    def __init__(self, cache_manager: "DistributedMultiTierCache"):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger("openchronicle.cache.warming")
        self.warming_tasks = {}

    async def warm_character_cache(self, story_id: str, character_names: list[str]) -> dict[str, bool]:
        """Warm cache with participant data."""
        self.logger.info(f"Warming participant cache for unit {story_id}: {len(character_names)} participants")

        results = {}
        batch_size = self.cache_manager.config.warming_batch_size

        for i in range(0, len(character_names), batch_size):
            batch = character_names[i : i + batch_size]
            batch_tasks = []

            for character_name in batch:
                task = self._warm_single_character(story_id, character_name)
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for character_name, result in zip(batch, batch_results, strict=False):
                results[character_name] = not isinstance(result, Exception)
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to warm cache for {character_name}: {result}")

        success_count = sum(1 for success in results.values() if success)
        success_rate = success_count / len(results) if results else 0

        self.cache_manager.metrics.warming_metrics.update({"operations": len(results), "success_rate": success_rate})

        self.logger.info(f"Cache warming completed: {success_count}/{len(results)} successful")
        return results

    async def _warm_single_character(self, story_id: str, character_name: str) -> bool:
        """Warm cache for a single participant."""
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
            current_avg = self.cache_manager.metrics.warming_metrics.get("avg_time_ms", 0)
            # Simple moving average
            new_avg = (current_avg + warming_time) / 2
            self.cache_manager.metrics.warming_metrics["avg_time_ms"] = new_avg
        except (AttributeError, KeyError) as e:
            self.logger.exception("Data structure error during cache warming for participant")
            return False
        except (ConnectionError, TimeoutError) as e:
            self.logger.exception("Network error during cache warming for participant")
            return False
        except Exception as e:
            self.logger.exception("Cache warming failed for participant")
            return False
        else:
            return True

    async def warm_memory_snapshots(self, story_ids: list[str]) -> dict[str, bool]:
        """Warm cache with memory snapshots."""
        self.logger.info(f"Warming memory snapshot cache for {len(story_ids)} units")

        results = {}
        for story_id in story_ids:
            try:
                cache_key = self.cache_manager._make_key("snapshot", story_id, "current")

                # Simulate memory snapshot data
                snapshot_data = {
                    "story_id": story_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "characters": [],
                    "warmed": True,
                }

                await self.cache_manager.set(cache_key, snapshot_data)
                results[story_id] = True

            except (AttributeError, KeyError) as e:
                self.logger.exception("Data structure error warming memory snapshot for unit")
                results[story_id] = False
            except (ConnectionError, TimeoutError) as e:
                self.logger.exception("Network error warming memory snapshot for unit")
                results[story_id] = False
            except Exception as e:
                self.logger.exception("Failed to warm memory snapshot for unit")
                results[story_id] = False

        return results
