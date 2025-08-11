"""
Test async memory management system.
Validates async memory operations, caching, and performance optimization.
"""

import asyncio
import time
import uuid

import pytest
from src.openchronicle.infrastructure.memory.async_memory_orchestrator import (
    AsyncMemoryOrchestrator,
)


@pytest.mark.asyncio
class TestAsyncMemoryOperations:
    """Test async memory operations."""

    @pytest.fixture
    def async_memory_orchestrator(self):
        """Create async memory orchestrator for testing."""
        return AsyncMemoryOrchestrator(cache_size=64, cache_ttl=60)

    @pytest.fixture
    def test_story_id(self):
        """Generate unique test story ID for each test."""
        return f"test_async_memory_{uuid.uuid4().hex[:8]}"

    async def test_async_memory_initialization(self, async_memory_orchestrator, test_story_id):
        """Test async memory orchestrator initialization."""
        # Test that we can initialize the orchestrator
        assert async_memory_orchestrator is not None
        assert async_memory_orchestrator.repository is not None

        # Test that we can load default memory
        memory = await async_memory_orchestrator.load_current_memory(test_story_id)
        assert memory is not None
        assert 'characters' in memory
        assert 'world_state' in memory
        assert 'flags' in memory
        assert 'recent_events' in memory

    async def test_async_memory_save_load(self, async_memory_orchestrator, test_story_id):
        """Test async memory save and load operations."""
        # Create test memory data
        test_memory = {
            'characters': {
                'Alice': {
                    'traits': {'brave': True, 'kind': True},
                    'mood': 'confident',
                    'history': ['Entered the forest']
                }
            },
            'world_state': {
                'location': 'Dark Forest',
                'time_of_day': 'night'
            },
            'flags': {'forest_entered': True},
            'recent_events': [
                {'description': 'Alice entered the forest', 'timestamp': '2025-08-05T10:00:00Z'}
            ]
        }

        # Save memory
        save_result = await async_memory_orchestrator.save_current_memory(test_story_id, test_memory)
        assert save_result is True

        # Load memory
        loaded_memory = await async_memory_orchestrator.load_current_memory(test_story_id)
        assert loaded_memory['characters']['Alice']['traits']['brave'] is True
        assert loaded_memory['world_state']['location'] == 'Dark Forest'
        assert loaded_memory['flags']['forest_entered'] is True

    async def test_async_character_memory_operations(self, async_memory_orchestrator, test_story_id):
        """Test async character-specific memory operations."""
        character_name = f"TestChar_{uuid.uuid4().hex[:6]}"

        # Update character memory
        character_updates = {
            'traits': {'intelligent': True, 'curious': True},
            'mood': 'excited',
            'current_state': {'location': 'Library', 'action': 'reading'}
        }

        update_result = await async_memory_orchestrator.update_character_memory(
            test_story_id, character_name, character_updates
        )
        assert update_result is True

        # Get character snapshot
        snapshot = await async_memory_orchestrator.get_character_memory_snapshot(
            test_story_id, character_name, format_for_prompt=True
        )
        assert snapshot is not None
        assert 'traits' in snapshot
        assert snapshot['traits']['intelligent'] is True

    async def test_async_world_state_operations(self, async_memory_orchestrator, test_story_id):
        """Test async world state operations."""
        # Update world state
        world_updates = {
            'weather': 'stormy',
            'political_situation': 'tense',
            'active_quests': ['Find the artifact', 'Rescue the villagers']
        }

        update_result = await async_memory_orchestrator.update_world_state(test_story_id, world_updates)
        assert update_result is True

        # Verify world state was updated
        memory = await async_memory_orchestrator.load_current_memory(test_story_id)
        assert memory['world_state']['weather'] == 'stormy'
        assert 'Find the artifact' in memory['world_state']['active_quests']

    async def test_async_memory_flags(self, async_memory_orchestrator, test_story_id):
        """Test async memory flag operations."""
        flag_name = f"test_flag_{uuid.uuid4().hex[:6]}"
        flag_data = {'value': 42, 'description': 'Test flag'}

        # Add flag
        add_result = await async_memory_orchestrator.add_memory_flag(test_story_id, flag_name, flag_data)
        assert add_result is True

        # Check flag exists
        has_flag = await async_memory_orchestrator.has_memory_flag(test_story_id, flag_name)
        assert has_flag is True

        # Remove flag
        remove_result = await async_memory_orchestrator.remove_memory_flag(test_story_id, flag_name)
        assert remove_result is True

        # Verify flag removed
        has_flag_after = await async_memory_orchestrator.has_memory_flag(test_story_id, flag_name)
        assert has_flag_after is False

    async def test_async_recent_events(self, async_memory_orchestrator, test_story_id):
        """Test async recent events operations."""
        event_description = f"Test event {uuid.uuid4().hex[:6]}"
        event_data = {'importance': 'high', 'characters_involved': ['Alice', 'Bob']}

        # Add recent event
        add_result = await async_memory_orchestrator.add_recent_event(
            test_story_id, event_description, event_data
        )
        assert add_result is True

        # Verify event was added
        memory = await async_memory_orchestrator.load_current_memory(test_story_id)
        events = memory['recent_events']
        assert len(events) > 0
        assert any(event['description'] == event_description for event in events)

    async def test_async_memory_snapshots(self, async_memory_orchestrator, test_story_id):
        """Test async memory snapshot and rollback operations."""
        scene_id = f"scene_{uuid.uuid4().hex[:6]}"

        # Create initial memory state
        initial_memory = {
            'characters': {'Hero': {'level': 1, 'hp': 100}},
            'world_state': {'chapter': 1},
            'flags': {'started': True}
        }

        save_result = await async_memory_orchestrator.save_current_memory(test_story_id, initial_memory)
        assert save_result is True

        # Create snapshot
        snapshot_result = await async_memory_orchestrator.archive_memory_snapshot(test_story_id, scene_id)
        assert snapshot_result is True

        # Modify memory
        modified_memory = {
            'characters': {'Hero': {'level': 5, 'hp': 80}},
            'world_state': {'chapter': 2},
            'flags': {'started': True, 'boss_defeated': True}
        }

        save_modified = await async_memory_orchestrator.save_current_memory(test_story_id, modified_memory)
        assert save_modified is True

        # Restore from snapshot
        restore_result = await async_memory_orchestrator.refresh_memory_after_rollback(test_story_id, scene_id)
        assert restore_result is True

        # Verify restoration
        restored_memory = await async_memory_orchestrator.load_current_memory(test_story_id)
        assert restored_memory['characters']['Hero']['level'] == 1
        assert restored_memory['world_state']['chapter'] == 1
        assert 'boss_defeated' not in restored_memory['flags']


@pytest.mark.asyncio
class TestAsyncMemoryPerformance:
    """Test async memory performance and caching."""

    @pytest.fixture
    def performance_orchestrator(self):
        """Create orchestrator for performance testing."""
        return AsyncMemoryOrchestrator(cache_size=128, cache_ttl=300)

    @pytest.fixture
    def performance_story_id(self):
        """Generate unique performance test story ID."""
        return f"perf_test_async_memory_{uuid.uuid4().hex[:8]}"

    async def test_async_memory_caching_performance(self, performance_orchestrator, performance_story_id):
        """Test memory caching effectiveness."""
        # Create test data
        test_memory = {
            'characters': {f'Character_{i}': {'level': i, 'hp': 100 + i} for i in range(10)},
            'world_state': {'populated': True, 'character_count': 10}
        }

        # Save initial data
        await performance_orchestrator.save_current_memory(performance_story_id, test_memory)

        # First load (cache miss)
        start_time = time.time()
        memory1 = await performance_orchestrator.load_current_memory(performance_story_id)
        first_load_time = time.time() - start_time

        # Second load (cache hit)
        start_time = time.time()
        memory2 = await performance_orchestrator.load_current_memory(performance_story_id)
        second_load_time = time.time() - start_time

        # Verify cache effectiveness
        assert memory1 == memory2  # Same data
        assert second_load_time < first_load_time  # Faster due to cache

        # Check cache stats
        stats = performance_orchestrator.get_performance_stats()
        assert stats['cache_stats']['total_hits'] > 0
        assert stats['cache_stats']['hit_rate_percent'] > 0

    async def test_async_concurrent_memory_operations(self, performance_orchestrator, performance_story_id):
        """Test concurrent memory operations."""
        # Create multiple concurrent character updates
        async def update_character(char_num):
            character_name = f"ConcurrentChar_{char_num}"
            updates = {
                'traits': {'concurrent': True, 'number': char_num},
                'mood': f'mood_{char_num}',
                'level': char_num * 10
            }
            return await performance_orchestrator.update_character_memory(
                performance_story_id, character_name, updates
            )

        # Run 10 concurrent character updates
        tasks = [update_character(i) for i in range(1, 11)]
        results = await asyncio.gather(*tasks)

        # Verify all updates succeeded
        assert all(result is True for result in results)

        # Verify all characters were created
        final_memory = await performance_orchestrator.load_current_memory(performance_story_id)
        characters = final_memory['characters']
        assert len(characters) == 10

        for i in range(1, 11):
            char_name = f"ConcurrentChar_{i}"
            assert char_name in characters
            assert characters[char_name]['level'] == i * 10

    async def test_async_memory_large_dataset_performance(self, performance_orchestrator, performance_story_id):
        """Test performance with large datasets."""
        # Create large memory structure
        large_memory = {
            'characters': {
                f'Character_{i}': {
                    'traits': {f'trait_{j}': j % 2 == 0 for j in range(10)},
                    'history': [f'Event {j} for character {i}' for j in range(20)],
                    'relationships': {f'Character_{(i+k)%100}': f'relationship_{k}' for k in range(5)},
                    'level': i,
                    'experience': i * 100
                }
                for i in range(100)  # 100 characters with detailed data
            },
            'world_state': {
                f'location_{i}': {
                    'name': f'Location {i}',
                    'description': f'A detailed description of location {i}' * 10,
                    'inhabitants': list(range(i, i+10))
                }
                for i in range(50)  # 50 detailed locations
            },
            'flags': {f'flag_{i}': {'value': i, 'active': i % 2 == 0} for i in range(200)},
            'recent_events': [
                {
                    'description': f'Large event {i}',
                    'data': {'importance': i % 5, 'characters': list(range(i, i+5))},
                    'timestamp': f'2025-08-05T{i%24:02d}:00:00Z'
                }
                for i in range(100)  # 100 detailed events
            ]
        }

        # Test save performance
        start_time = time.time()
        save_result = await performance_orchestrator.save_current_memory(performance_story_id, large_memory)
        save_time = time.time() - start_time

        assert save_result is True
        assert save_time < 5.0  # Should save large dataset in under 5 seconds

        # Test load performance
        start_time = time.time()
        loaded_memory = await performance_orchestrator.load_current_memory(performance_story_id)
        load_time = time.time() - start_time

        assert loaded_memory is not None
        assert len(loaded_memory['characters']) == 100
        assert len(loaded_memory['world_state']) == 50
        assert load_time < 3.0  # Should load large dataset in under 3 seconds

        # Test character-specific loading (lazy loading benefit)
        start_time = time.time()
        character_snapshot = await performance_orchestrator.get_character_memory_snapshot(
            performance_story_id, 'Character_50', format_for_prompt=True
        )
        character_load_time = time.time() - start_time

        assert character_snapshot is not None
        assert character_load_time < 0.5  # Character loading should be very fast

    async def test_async_memory_cache_management(self, performance_orchestrator, performance_story_id):
        """Test cache management and statistics."""
        # Generate multiple stories to test cache management
        story_ids = [f"{performance_story_id}_{i}" for i in range(5)]

        # Load memory for each story (populate cache)
        for story_id in story_ids:
            await performance_orchestrator.load_current_memory(story_id)

        # Get initial cache stats
        initial_stats = performance_orchestrator.get_performance_stats()
        assert initial_stats['cache_stats']['memory_cache_size'] > 0

        # Clear cache for specific story
        performance_orchestrator.clear_cache(story_ids[0])

        # Clear all caches
        performance_orchestrator.clear_cache()

        # Verify cache cleared
        final_stats = performance_orchestrator.get_performance_stats()
        assert final_stats['cache_stats']['memory_cache_size'] == 0
        assert final_stats['cache_stats']['character_cache_size'] == 0
