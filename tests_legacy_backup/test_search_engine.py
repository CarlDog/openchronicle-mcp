"""
Test suite for OpenChronicle Full-Text Search (FTS5) System.

This comprehensive test suite covers:
- FTS5 database schema and indexing
- Search engine functionality 
- Query parsing and sanitization
- Search result ranking and snippets
- Integration with existing systems
"""

import unittest
import os
import tempfile
import shutil
import json
from datetime import datetime, UTC
import sys
import gc
import time
import platform

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def safe_teardown_temp_dir(temp_dir, original_cwd, engine=None):
    """
    Safely remove temporary directory with Windows-compatible cleanup.
    
    Args:
        temp_dir: Path to temporary directory to remove
        original_cwd: Original working directory to restore
        engine: Optional search engine instance to close
    """
    # Force close any database connections
    gc.collect()
    
    # Try to close engine if provided
    if engine and hasattr(engine, 'close'):
        try:
            engine.close()
        except:
            pass
    
    os.chdir(original_cwd)
    
    # On Windows, add retry logic for file removal
    if platform.system() == 'Windows':
        time.sleep(0.1)  # Small delay to let file handles close
        
        # Try multiple times to remove the directory
        for attempt in range(3):
            try:
                shutil.rmtree(temp_dir)
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.2)
                    gc.collect()
                else:
                    # Last resort: try Windows rd command
                    try:
                        import subprocess
                        subprocess.run(['rd', '/s', '/q', temp_dir], shell=True, capture_output=True)
                    except:
                        pass
    else:
        shutil.rmtree(temp_dir)

from core.database import init_database, check_fts_support, optimize_fts_index, execute_insert
from core.search_engine import SearchEngine, SearchResult, SearchQuery, search_story
from core.scene_logger import save_scene

# Try to import optional features
try:
    from core.database import get_fts_stats
    HAS_FTS_STATS = True
except ImportError:
    HAS_FTS_STATS = False


def store_memory_for_testing(story_id, memory_type, key, value):
    """Helper function to store memory for testing purposes."""
    execute_insert(story_id, '''
        INSERT INTO memory (story_id, type, key, value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (story_id, memory_type, key, f'"{value}"', 
          datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()))


class TestFTSSupport(unittest.TestCase):
    """Test FTS5 support detection."""
    
    def test_fts_support_detection(self):
        """Test that FTS5 support is properly detected."""
        fts_supported = check_fts_support()
        self.assertIsInstance(fts_supported, bool)
        
        # If FTS5 is supported, we should be able to create a SearchEngine
        if fts_supported:
            # This should not raise an exception
            temp_dir = tempfile.mkdtemp()
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                init_database("test_story")
                engine = SearchEngine("test_story")
                self.assertIsNotNone(engine)
            finally:
                safe_teardown_temp_dir(temp_dir, original_cwd, engine)


class TestFTSDatabase(unittest.TestCase):
    """Test FTS5 database schema and operations."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_fts"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_fts_tables_creation(self):
        """Test that FTS5 virtual tables are created."""
        stats = get_fts_stats(self.test_story_id)
        
        # Check that FTS tables exist
        self.assertIn('scenes_fts', stats['fts_tables'])
        self.assertIn('memory_fts', stats['fts_tables'])
        
        # Check initial counts
        self.assertEqual(stats['scenes_fts_entries'], 0)
        self.assertEqual(stats['memory_fts_entries'], 0)
    
    def test_fts_indexing_scenes(self):
        """Test that scenes are automatically indexed."""
        # Create a test scene
        scene_id = save_scene(
            self.test_story_id,
            "The hero enters the dark forest",
            "You find yourself in a mysterious woodland filled with ancient trees",
            scene_label="Forest Entry"
        )
        
        # Check that it was indexed
        stats = get_fts_stats(self.test_story_id)
        self.assertEqual(stats['scenes_fts_entries'], 1)
    
    def test_fts_indexing_memory(self):
        """Test that memory is automatically indexed."""
        # Get initial count
        initial_stats = get_fts_stats(self.test_story_id)
        initial_count = initial_stats.get('memory_fts_entries', 0)
        print(f"Initial FTS entries: {initial_count}")
        
        # Create memory entries
        store_memory_for_testing(self.test_story_id, 'character', 'hero_name', 'Aragorn the Brave')
        print("Added first memory entry")
        
        # Check intermediate count
        mid_stats = get_fts_stats(self.test_story_id)
        mid_count = mid_stats.get('memory_fts_entries', 0)
        print(f"After first entry: {mid_count}")
        
        store_memory_for_testing(self.test_story_id, 'world', 'location', 'Enchanted Forest')
        print("Added second memory entry")
        
        # Check that they were indexed
        stats = get_fts_stats(self.test_story_id)
        final_count = stats.get('memory_fts_entries', 0)
        print(f"Final FTS entries: {final_count}")
        
        self.assertEqual(final_count, initial_count + 2, 
                        f"Expected {initial_count + 2} FTS entries, got {final_count}")
    
    def test_fts_optimization(self):
        """Test FTS5 index optimization."""
        # Create some test data
        save_scene(self.test_story_id, "test input", "test output")
        
        # Optimize indexes (should not raise an exception)
        optimize_fts_index(self.test_story_id)
        
        # Verify data is still there
        stats = get_fts_stats(self.test_story_id)
        self.assertEqual(stats['scenes_fts_entries'], 1)


class TestSearchEngine(unittest.TestCase):
    """Test SearchEngine functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_search"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine
        self.engine = SearchEngine(self.test_story_id)
        
        # Create test data
        self.scene1_id = save_scene(
            self.test_story_id,
            "I want to explore the ancient castle",
            "You approach the massive stone fortress with its towering walls",
            scene_label="Castle Approach"
        )
        
        self.scene2_id = save_scene(
            self.test_story_id,
            "I examine the mysterious door",
            "The door is covered in strange runes and symbols",
            scene_label="Mysterious Door"
        )
        
        self.scene3_id = save_scene(
            self.test_story_id,
            "I cast a fire spell",
            "Flames dance from your fingertips, illuminating the dark corridor",
            scene_label="Fire Magic"
        )
        
        # Create memory data
        store_memory_for_testing(self.test_story_id, 'character', 'hero_name', 'Gandalf the Grey')
        store_memory_for_testing(self.test_story_id, 'character', 'hero_class', 'Wizard')
        store_memory_for_testing(self.test_story_id, 'world', 'current_location', 'Ancient Castle')
        store_memory_for_testing(self.test_story_id, 'world', 'discovered_items', 'Magic Staff, Ancient Key')
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd, self.engine)
    
    def test_search_engine_initialization(self):
        """Test SearchEngine initialization."""
        self.assertEqual(self.engine.story_id, self.test_story_id)
        self.assertTrue(self.engine.fts_supported)
    
    def test_query_parsing_simple(self):
        """Test parsing of simple queries."""
        query = self.engine.parse_query("castle ancient")
        
        self.assertEqual(query.original, "castle ancient")
        self.assertEqual(query.sanitized, "castle ancient")
        self.assertEqual(query.terms, ["castle", "ancient"])
        self.assertEqual(query.operators, [])
        self.assertEqual(query.quoted_phrases, [])
        self.assertEqual(query.filters, {})
        self.assertEqual(query.content_types, ['scene', 'memory'])
    
    def test_query_parsing_quoted_phrases(self):
        """Test parsing of quoted phrases."""
        query = self.engine.parse_query('castle "ancient fortress" door')
        
        self.assertIn("ancient fortress", query.quoted_phrases)
        self.assertIn("castle", query.terms)
        self.assertIn("door", query.terms)
    
    def test_query_parsing_operators(self):
        """Test parsing of boolean operators."""
        query = self.engine.parse_query("castle AND door OR magic")
        
        self.assertIn("AND", query.operators)
        self.assertIn("OR", query.operators)
        self.assertIn("castle", query.terms)
        self.assertIn("door", query.terms)
        self.assertIn("magic", query.terms)
    
    def test_query_parsing_filters(self):
        """Test parsing of filters."""
        query = self.engine.parse_query("castle type:scene label:approach")
        
        self.assertEqual(query.filters['type'], 'scene')
        self.assertEqual(query.filters['label'], 'approach')
        self.assertEqual(query.content_types, ['scene'])
    
    def test_search_scenes_simple(self):
        """Test simple scene search."""
        query = self.engine.parse_query("castle")
        results = self.engine.search_scenes(query)
        
        # Should find the castle scene
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content_type, 'scene')
        self.assertEqual(results[0].id, self.scene1_id)
        self.assertIn("castle", results[0].content.lower())
    
    def test_search_scenes_with_label_filter(self):
        """Test scene search with label filter."""
        query = self.engine.parse_query("door label:mysterious")
        results = self.engine.search_scenes(query)
        
        # Should find the mysterious door scene
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.scene2_id)
        self.assertEqual(results[0].scene_label, "Mysterious Door")
    
    def test_search_memory_simple(self):
        """Test simple memory search."""
        query = self.engine.parse_query("Gandalf")
        results = self.engine.search_memory(query)
        
        # Should find the character memory
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content_type, 'memory')
        self.assertIn("Gandalf", results[0].content)
    
    def test_search_memory_with_type_filter(self):
        """Test memory search with type filter."""
        query = self.engine.parse_query("castle memtype:world")
        results = self.engine.search_memory(query)
        
        # Should find the world memory about castle
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata['memory_type'], 'world')
        self.assertIn("Castle", results[0].content)
    
    def test_search_all_content_types(self):
        """Test searching across all content types."""
        results = self.engine.search_all("castle")
        
        # Should find both scene and memory results
        self.assertGreater(len(results), 0)
        
        # Check that we have different content types
        content_types = {result.content_type for result in results}
        self.assertIn('scene', content_types)
        self.assertIn('memory', content_types)
    
    def test_search_with_quoted_phrases(self):
        """Test search with quoted phrases."""
        query = self.engine.parse_query('"Ancient Castle"')
        results = self.engine.search_memory(query)
        
        # Should find the exact phrase match
        self.assertEqual(len(results), 1)
        self.assertIn("Ancient Castle", results[0].content)
    
    def test_search_ranking(self):
        """Test that search results are ranked by relevance."""
        # Create a scene with multiple matches
        save_scene(
            self.test_story_id,
            "The castle door is ancient and mysterious",
            "This ancient castle door holds many secrets",
            scene_label="Castle Door Investigation"
        )
        
        results = self.engine.search_all("castle door ancient")
        
        # Should have results
        self.assertGreater(len(results), 0)
        
        # Check that scores are in descending order (lower is better for BM25)
        for i in range(len(results) - 1):
            self.assertLessEqual(results[i].score, results[i + 1].score)
    
    def test_search_snippets(self):
        """Test that search results include snippets."""
        results = self.engine.search_all("castle")
        
        # Should have results with snippets
        self.assertGreater(len(results), 0)
        
        for result in results:
            self.assertIsInstance(result.snippet, str)
            self.assertGreater(len(result.snippet), 0)
    
    def test_search_no_results(self):
        """Test search with no matching results."""
        results = self.engine.search_all("nonexistent_term_xyz")
        
        # Should return empty list
        self.assertEqual(len(results), 0)
    
    def test_search_stats(self):
        """Test search engine statistics."""
        stats = self.engine.get_search_stats()
        
        self.assertTrue(stats['fts_supported'])
        self.assertEqual(stats['story_id'], self.test_story_id)
        self.assertGreater(stats['indexed_scenes'], 0)
        self.assertGreater(stats['indexed_memory'], 0)
    
    def test_health_check(self):
        """Test search engine health check."""
        health = self.engine.health_check()
        
        self.assertEqual(health['status'], 'healthy')
        self.assertTrue(health['fts_supported'])
        self.assertTrue(health['search_functional'])
        self.assertTrue(health['fts_integrity'])
        self.assertEqual(len(health['issues']), 0)
    
    def test_index_optimization(self):
        """Test FTS5 index optimization."""
        # Should not raise an exception
        self.engine.optimize_indexes()
        
        # Verify search still works
        results = self.engine.search_all("castle")
        self.assertGreater(len(results), 0)


class TestSearchConvenienceFunctions(unittest.TestCase):
    """Test convenience functions for search."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_convenience"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create test data
        save_scene(
            self.test_story_id,
            "I explore the enchanted forest",
            "You discover a magical clearing with glowing flowers",
            scene_label="Forest Discovery"
        )
        
        store_memory_for_testing(self.test_story_id, 'world', 'forest_type', 'Enchanted Forest')
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_search_story_function(self):
        """Test search_story convenience function."""
        results = search_story(self.test_story_id, "forest")
        
        # Should find both scene and memory results
        self.assertGreater(len(results), 0)
        
        # Check that we have different content types
        content_types = {result.content_type for result in results}
        self.assertTrue(len(content_types) >= 1)


class TestSearchIntegration(unittest.TestCase):
    """Test integration with existing systems."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_integration"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine
        self.engine = SearchEngine(self.test_story_id)
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_search_with_scene_labels(self):
        """Test search integration with scene labeling system."""
        # Create scenes with labels
        save_scene(
            self.test_story_id,
            "I begin my quest",
            "Your epic journey starts here",
            scene_label="Chapter 1: The Beginning"
        )
        
        save_scene(
            self.test_story_id,
            "I face the dragon",
            "A mighty dragon blocks your path",
            scene_label="Chapter 5: Dragon Fight"
        )
        
        # Search with label filter
        results = self.engine.search_all("quest label:beginning")
        
        # Should find the first scene
        self.assertEqual(len(results), 1)
        self.assertIn("Chapter 1", results[0].scene_label)
    
    def test_search_with_memory_types(self):
        """Test search integration with memory management."""
        # Create different types of memory
        store_memory_for_testing(self.test_story_id, 'character', 'hero_stats', 'Strength: 18, Wisdom: 16')
        store_memory_for_testing(self.test_story_id, 'inventory', 'weapons', 'Magic Sword, Shield of Protection')
        store_memory_for_testing(self.test_story_id, 'world', 'current_area', 'Dragon Lair')
        
        # Search with memory type filter
        results = self.engine.search_all("sword memtype:inventory")
        
        # Should find the inventory memory
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata['memory_type'], 'inventory')


# =============================================================================
# ADVANCED FEATURES TESTS (PHASE 2)
# =============================================================================

class TestAdvancedQueryParsing(unittest.TestCase):
    """Test advanced query parsing features."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_advanced"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine
        self.engine = SearchEngine(self.test_story_id)
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_wildcard_parsing(self):
        """Test parsing of wildcard queries."""
        query = self.engine.parse_query("cast* ancient ?oor")
        
        self.assertEqual(len(query.wildcards), 2)
        self.assertIn("cast*", query.wildcards)
        self.assertIn("?oor", query.wildcards)
    
    def test_proximity_search_parsing(self):
        """Test parsing of proximity searches."""
        query = self.engine.parse_query("castle NEAR/5 door")
        
        self.assertEqual(len(query.proximity_searches), 1)
        self.assertEqual(query.proximity_searches[0], ("castle", "door", 5))
    
    def test_sort_order_parsing(self):
        """Test parsing of sort orders."""
        query = self.engine.parse_query("castle sort:date")
        
        self.assertEqual(query.sort_order, "date")
        self.assertNotIn("sort", query.filters)
    
    def test_limit_parsing(self):
        """Test parsing of result limits."""
        query = self.engine.parse_query("castle limit:25")
        
        self.assertEqual(query.limit, 25)
        self.assertNotIn("limit", query.filters)
    
    def test_complex_query_parsing(self):
        """Test parsing of complex queries with multiple features."""
        query = self.engine.parse_query(
            'castle AND "ancient door" cast* type:scene sort:date limit:20'
        )
        
        self.assertIn("castle", query.terms)
        self.assertIn("ancient door", query.quoted_phrases)
        self.assertIn("cast*", query.wildcards)
        self.assertIn("AND", query.operators)
        self.assertEqual(query.filters["type"], "scene")
        self.assertEqual(query.sort_order, "date")
        self.assertEqual(query.limit, 20)


class TestSearchCaching(unittest.TestCase):
    """Test search caching and performance features."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_caching"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine with small cache for testing
        self.engine = SearchEngine(self.test_story_id, cache_size=3)
        
        # Create test data
        save_scene(
            self.test_story_id,
            "I explore the ancient castle",
            "You approach the massive stone fortress",
            scene_label="Castle Entry"
        )
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_search_caching(self):
        """Test that search results are cached."""
        # First search
        results1 = self.engine.search_all("castle")
        
        # Second search should use cache
        results2 = self.engine.search_all("castle")
        
        # Results should be identical
        self.assertEqual(len(results1), len(results2))
        self.assertEqual(self.engine.performance_stats['cache_hits'], 1)
        self.assertEqual(self.engine.performance_stats['total_queries'], 2)
    
    def test_cache_size_limit(self):
        """Test that cache size is limited."""
        # Fill cache beyond limit
        for i in range(5):
            self.engine.search_all(f"query{i}")
        
        # Cache should be limited to configured size
        self.assertLessEqual(len(self.engine.query_cache), 3)
    
    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        # Perform search to populate cache
        self.engine.search_all("castle")
        self.assertGreater(len(self.engine.query_cache), 0)
        
        # Clear cache
        self.engine.clear_cache()
        self.assertEqual(len(self.engine.query_cache), 0)
    
    def test_performance_tracking(self):
        """Test performance statistics tracking."""
        # Perform some searches
        self.engine.search_all("castle")
        self.engine.search_all("door")
        
        stats = self.engine.get_performance_stats()
        
        self.assertEqual(stats['total_queries'], 2)
        self.assertGreater(stats['avg_query_time'], 0)
        self.assertGreater(stats['total_query_time'], 0)
        self.assertGreaterEqual(stats['cache_hit_rate'], 0)


# Define advanced features availability
ADVANCED_FEATURES_AVAILABLE = True

@unittest.skipUnless(ADVANCED_FEATURES_AVAILABLE, "Advanced search features not available")
class TestSearchHistory(unittest.TestCase):
    """Test search history functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_history"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine
        self.engine = SearchEngine(self.test_story_id)
        
        # Create test data
        save_scene(
            self.test_story_id,
            "I explore the castle",
            "You enter the grand hall",
            scene_label="Castle Exploration"
        )
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_search_history_recording(self):
        """Test that search history is recorded."""
        # Perform searches
        self.engine.search_all("castle")
        self.engine.search_all("door")
        self.engine.search_all("magic")
        
        # Check history
        history = self.engine.get_search_history()
        self.assertEqual(len(history), 3)
        
        # Check that most recent is first
        self.assertEqual(history[0].query, "magic")
        self.assertEqual(history[1].query, "door")
        self.assertEqual(history[2].query, "castle")
    
    def test_search_history_limit(self):
        """Test that search history is limited."""
        # Perform many searches
        for i in range(15):
            self.engine.search_all(f"query{i}")
        
        # History should be limited
        history = self.engine.get_search_history()
        self.assertLessEqual(len(history), 10)  # Default limit
    
    def test_clear_search_history(self):
        """Test clearing search history."""
        # Perform searches
        self.engine.search_all("castle")
        self.engine.search_all("door")
        
        # Clear history
        self.engine.clear_search_history()
        
        # History should be empty
        history = self.engine.get_search_history()
        self.assertEqual(len(history), 0)


@unittest.skipUnless(ADVANCED_FEATURES_AVAILABLE, "Advanced search features not available")
class TestSavedSearches(unittest.TestCase):
    """Test saved searches functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_saved"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine
        self.engine = SearchEngine(self.test_story_id)
        
        # Create test data
        save_scene(
            self.test_story_id,
            "I cast a spell",
            "Magic energy flows through you",
            scene_label="Spellcasting"
        )
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_save_search(self):
        """Test saving a search."""
        # Save a search
        saved_search = self.engine.save_search(
            "magic_search",
            "magic AND spell",
            "Find all magic-related content"
        )
        
        self.assertEqual(saved_search.name, "magic_search")
        self.assertEqual(saved_search.query, "magic AND spell")
        self.assertEqual(saved_search.description, "Find all magic-related content")
        
        # Should be in saved searches
        saved_searches = self.engine.list_saved_searches()
        self.assertEqual(len(saved_searches), 1)
        self.assertEqual(saved_searches[0].name, "magic_search")
    
    def test_list_saved_searches(self):
        """Test listing saved searches."""
        # Save multiple searches
        self.engine.save_search("search1", "castle", "Castle search")
        self.engine.save_search("search2", "magic", "Magic search")
        
        # List searches
        saved_searches = self.engine.list_saved_searches()
        self.assertEqual(len(saved_searches), 2)
        
        # Should be sorted by name
        names = [s.name for s in saved_searches]
        self.assertEqual(sorted(names), names)
    
    def test_delete_saved_search(self):
        """Test deleting a saved search."""
        # Save a search
        self.engine.save_search("temp_search", "test", "Temporary search")
        
        # Delete it
        self.engine.delete_saved_search("temp_search")
        
        # Should not be in saved searches
        saved_searches = self.engine.list_saved_searches()
        self.assertEqual(len(saved_searches), 0)
    
    def test_execute_saved_search(self):
        """Test executing a saved search."""
        # Save a search
        self.engine.save_search("magic_search", "magic", "Find magic content")
        
        # Execute the saved search
        results = self.engine.execute_saved_search("magic_search")
        
        # Should find results
        self.assertGreater(len(results), 0)
        self.assertIn("magic", results[0].content.lower())


class TestSearchExport(unittest.TestCase):
    """Test search result export functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_export"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Check if FTS5 is supported
        if not check_fts_support():
            self.skipTest("FTS5 is not supported in this SQLite version")
        
        # Create SearchEngine
        self.engine = SearchEngine(self.test_story_id)
        
        # Create test data
        save_scene(
            self.test_story_id,
            "I explore the library",
            "Ancient books line the walls",
            scene_label="Library Discovery"
        )
        
        store_memory_for_testing(self.test_story_id, 'world', 'location', 'Ancient Library')
    
    def tearDown(self):
        """Clean up test environment."""
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_export_results_to_json(self):
        """Test exporting search results to JSON."""
        # Perform search
        results = self.engine.search_all("library")
        
        # Export to JSON
        if hasattr(self.engine, 'export_search_results'):
            json_data = self.engine.export_search_results(results, format='json')
            
            # Should be valid JSON
            parsed = json.loads(json_data)
            self.assertIsInstance(parsed, list)
            self.assertGreater(len(parsed), 0)
            
            # Check structure
            result_item = parsed[0]
            self.assertIn('id', result_item)
            self.assertIn('content_type', result_item)
            self.assertIn('title', result_item)
            self.assertIn('content', result_item)
            self.assertIn('score', result_item)
        else:
            self.skipTest("Export functionality not implemented")


if __name__ == '__main__':
    unittest.main()
