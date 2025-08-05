"""
Test suite for Scene Labeling and Bookmarking System.
"""

import unittest
import os
import tempfile
import shutil
from datetime import datetime
import sys
import gc
import time
import platform

# Add the parent directory to the path so we can import our modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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

from core.scene_systems import SceneOrchestrator
from core.scene_systems.scene_orchestrator import save_scene, load_scene, update_scene_label, get_scenes_by_label, get_labeled_scenes
from core.management_systems import BookmarkManager
from core.timeline_systems import TimelineOrchestrator
from core.database import init_database

class TestSceneLabeling(unittest.TestCase):
    """Test scene labeling functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_labeling"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Create test scenes
        self.scene1_id = save_scene(
            self.test_story_id,
            "Hello, I'm starting a new adventure",
            "Welcome to the mystical realm of Eldoria!",
            scene_label="Chapter 1: The Beginning"
        )
        
        self.scene2_id = save_scene(
            self.test_story_id,
            "I look around the forest",
            "You see tall ancient trees and hear mysterious sounds",
            scene_label="Forest Exploration"
        )
        
        self.scene3_id = save_scene(
            self.test_story_id,
            "I continue on the path",
            "The path winds deeper into the forest",
            scene_label=None  # No label
        )
    
    def tearDown(self):
        """Clean up test environment."""
        # Close any open database connections
        import sqlite3
        import gc
        gc.collect()
        
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_save_scene_with_label(self):
        """Test saving scene with label."""
        scene_id = save_scene(
            self.test_story_id,
            "Test input",
            "Test output",
            scene_label="Test Label"
        )
        
        scene = load_scene(self.test_story_id, scene_id)
        self.assertEqual(scene['scene_label'], "Test Label")
    
    def test_save_scene_without_label(self):
        """Test saving scene without label."""
        scene_id = save_scene(
            self.test_story_id,
            "Test input",
            "Test output"
        )
        
        scene = load_scene(self.test_story_id, scene_id)
        self.assertIsNone(scene['scene_label'])
    
    def test_update_scene_label(self):
        """Test updating scene label."""
        # Update label
        success = update_scene_label(self.test_story_id, self.scene3_id, "Updated Label")
        self.assertTrue(success)
        
        # Verify update
        scene = load_scene(self.test_story_id, self.scene3_id)
        self.assertEqual(scene['scene_label'], "Updated Label")
    
    def test_get_scenes_by_label(self):
        """Test getting scenes by label."""
        scenes = get_scenes_by_label(self.test_story_id, "Forest Exploration")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]['scene_id'], self.scene2_id)
    
    def test_get_labeled_scenes(self):
        """Test getting all labeled scenes."""
        labeled_scenes = get_labeled_scenes(self.test_story_id)
        self.assertEqual(len(labeled_scenes), 2)  # scene1 and scene2 have labels
        
        labels = [scene['scene_label'] for scene in labeled_scenes]
        self.assertIn("Chapter 1: The Beginning", labels)
        self.assertIn("Forest Exploration", labels)
    
    def test_structured_tags_functionality(self):
        """Test enhanced structured tags functionality."""
        # Test saving scene with structured tags
        scene_id = save_scene(
            self.test_story_id,
            "I investigate the mysterious sound",
            "You discover it's coming from an old music box",
            scene_label="Investigation",
            structured_tags={
                'location': 'old_house',
                'mood': 'mysterious',
                'action_type': 'investigation',
                'significance': 'medium',
                'long_turn': True,
                'token_usage': {'input_tokens': 30, 'output_tokens': 45, 'total_tokens': 75}
            }
        )
        
        scene = load_scene(self.test_story_id, scene_id)
        tags = scene.get('structured_tags', {})
        self.assertEqual(tags['location'], 'old_house')
        self.assertEqual(tags['mood'], 'mysterious')
        self.assertTrue(tags['long_turn'])
        self.assertEqual(tags['token_usage']['total_tokens'], 75)
    
    def test_token_usage_stats(self):
        """Test token usage statistics."""
        from core.scene_systems.scene_orchestrator import get_token_usage_stats
        
        # Create scene with token data
        save_scene(
            self.test_story_id,
            "Short input",
            "Short output",
            structured_tags={
                'token_usage': {'input_tokens': 20, 'output_tokens': 30, 'total_tokens': 50}
            }
        )
        
        stats = get_token_usage_stats(self.test_story_id)
        self.assertIsInstance(stats, dict)
        self.assertIn('total_tokens', stats)
        self.assertIn('scene_count', stats)
        self.assertGreater(stats['total_tokens'], 0)
    
    def test_long_turn_detection(self):
        """Test long turn detection functionality."""
        from core.scene_systems.scene_orchestrator import get_scenes_with_long_turns
        
        # Create a long turn scene
        save_scene(
            self.test_story_id,
            "This is a very long input that should be detected as a long turn",
            "This is a detailed response that provides comprehensive information",
            structured_tags={'long_turn': True}
        )
        
        long_turns = get_scenes_with_long_turns(self.test_story_id)
        self.assertIsInstance(long_turns, list)
        # Should have at least one long turn (may have more from setup)
        self.assertGreater(len(long_turns), 0)
    
    def test_character_mood_timeline(self):
        """Test character mood timeline functionality."""
        from core.scene_systems.scene_orchestrator import get_character_mood_timeline
        
        # Create scenes with character mood data
        save_scene(
            self.test_story_id,
            "Character feels happy",
            "The character smiles brightly",
            structured_tags={
                'characters': ['protagonist'],
                'mood': 'happy'
            }
        )
        
        save_scene(
            self.test_story_id,
            "Character becomes worried",
            "The character's expression turns serious",
            structured_tags={
                'characters': ['protagonist'],
                'mood': 'worried'
            }
        )
        
        timeline = get_character_mood_timeline(self.test_story_id, 'protagonist')
        self.assertIsInstance(timeline, list)
        # Should capture mood changes
        if len(timeline) > 0:
            self.assertIn('mood', timeline[0])
            self.assertIn('timestamp', timeline[0])
    
    def test_scene_summary_stats(self):
        """Test scene summary statistics."""
        from core.scene_systems.scene_orchestrator import get_scene_summary_stats
        
        # Create scene with comprehensive tags
        save_scene(
            self.test_story_id,
            "Test scene",
            "Test response",
            structured_tags={
                'location': 'test_location',
                'mood': 'test_mood',
                'action_type': 'test_action',
                'significance': 'high'
            }
        )
        
        stats = get_scene_summary_stats(self.test_story_id)
        self.assertIsInstance(stats, dict)
        self.assertIn('total_scenes', stats)
        self.assertIn('scenes_by_location', stats)
        self.assertIn('scenes_by_mood', stats)
        self.assertIn('scenes_by_action_type', stats)
        self.assertIn('scenes_by_significance', stats)


class TestBookmarkManager(unittest.TestCase):
    """Test bookmark management functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_bookmarks"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database and create test scenes
        init_database(self.test_story_id)
        
        self.scene1_id = save_scene(
            self.test_story_id,
            "Test scene 1",
            "Test output 1"
        )
        
        self.scene2_id = save_scene(
            self.test_story_id,
            "Test scene 2",
            "Test output 2"
        )
        
        self.bookmark_manager = BookmarkManager(self.test_story_id)
    
    def tearDown(self):
        """Clean up test environment."""
        # Close any open database connections
        import sqlite3
        import gc
        gc.collect()
        
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_create_bookmark(self):
        """Test creating a bookmark."""
        bookmark_id = self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Important Scene",
            description="This is an important scene",
            bookmark_type="user"
        )
        
        self.assertIsInstance(bookmark_id, int)
        self.assertGreater(bookmark_id, 0)
    
    def test_get_bookmark(self):
        """Test getting a bookmark."""
        bookmark_id = self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Test Bookmark",
            description="Test description"
        )
        
        bookmark = self.bookmark_manager.get_bookmark(bookmark_id)
        self.assertIsNotNone(bookmark)
        self.assertEqual(bookmark['label'], "Test Bookmark")
        self.assertEqual(bookmark['scene_id'], self.scene1_id)
    
    def test_create_duplicate_bookmark(self):
        """Test creating duplicate bookmark fails."""
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Duplicate",
            description="First bookmark"
        )
        
        with self.assertRaises(ValueError):
            self.bookmark_manager.create_bookmark(
                scene_id=self.scene1_id,
                label="Duplicate",
                description="Second bookmark"
            )
    
    def test_list_bookmarks(self):
        """Test listing bookmarks."""
        # Create test bookmarks
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="User Bookmark",
            bookmark_type="user"
        )
        
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene2_id,
            label="Chapter Bookmark",
            bookmark_type="chapter"
        )
        
        # Test listing all bookmarks
        all_bookmarks = self.bookmark_manager.list_bookmarks()
        self.assertEqual(len(all_bookmarks), 2)
        
        # Test filtering by type
        user_bookmarks = self.bookmark_manager.list_bookmarks(bookmark_type="user")
        self.assertEqual(len(user_bookmarks), 1)
        self.assertEqual(user_bookmarks[0]['label'], "User Bookmark")
    
    def test_update_bookmark(self):
        """Test updating a bookmark."""
        bookmark_id = self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Original Label",
            description="Original description"
        )
        
        # Update bookmark
        success = self.bookmark_manager.update_bookmark(
            bookmark_id=bookmark_id,
            label="Updated Label",
            description="Updated description"
        )
        
        self.assertTrue(success)
        
        # Verify update
        bookmark = self.bookmark_manager.get_bookmark(bookmark_id)
        self.assertEqual(bookmark['label'], "Updated Label")
        self.assertEqual(bookmark['description'], "Updated description")
    
    def test_delete_bookmark(self):
        """Test deleting a bookmark."""
        bookmark_id = self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="To Delete",
            description="This will be deleted"
        )
        
        # Delete bookmark
        success = self.bookmark_manager.delete_bookmark(bookmark_id)
        self.assertTrue(success)
        
        # Verify deletion
        bookmark = self.bookmark_manager.get_bookmark(bookmark_id)
        self.assertIsNone(bookmark)
    
    def test_search_bookmarks(self):
        """Test searching bookmarks."""
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Important Scene",
            description="This is very important"
        )
        
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene2_id,
            label="Battle Scene",
            description="Epic battle sequence"
        )
        
        # Search by label
        results = self.bookmark_manager.search_bookmarks("Important")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['label'], "Important Scene")
        
        # Search by description
        results = self.bookmark_manager.search_bookmarks("battle")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['label'], "Battle Scene")
    
    def test_auto_create_chapter_bookmark(self):
        """Test auto-creating chapter bookmark."""
        bookmark_id = self.bookmark_manager.auto_create_chapter_bookmark(
            scene_id=self.scene1_id,
            chapter_title="Chapter 1",
            chapter_level=1
        )
        
        bookmark = self.bookmark_manager.get_bookmark(bookmark_id)
        self.assertEqual(bookmark['label'], "Chapter 1")
        self.assertEqual(bookmark['bookmark_type'], "chapter")
        self.assertEqual(bookmark['metadata']['chapter_level'], 1)
        self.assertTrue(bookmark['metadata']['auto_generated'])
    
    def test_bookmark_stats(self):
        """Test bookmark statistics."""
        # Create bookmarks of different types
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="User 1",
            bookmark_type="user"
        )
        
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene2_id,
            label="User 2",
            bookmark_type="user"
        )
        
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Chapter 1",
            bookmark_type="chapter"
        )
        
        stats = self.bookmark_manager.get_stats()
        self.assertEqual(stats['total_bookmarks'], 3)
        self.assertEqual(stats['by_type']['user'], 2)
        self.assertEqual(stats['by_type']['chapter'], 1)


class TestTimelineBuilder(unittest.TestCase):
    """Test timeline building functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_story_id = "test_story_timeline"
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Initialize database
        init_database(self.test_story_id)
        
        # Create test scenes
        self.scene1_id = save_scene(
            self.test_story_id,
            "Chapter 1 starts",
            "Beginning of the story",
            scene_label="Chapter 1"
        )
        
        self.scene2_id = save_scene(
            self.test_story_id,
            "Action sequence",
            "Exciting action happens",
            scene_label="Action Scene"
        )
        
        self.scene3_id = save_scene(
            self.test_story_id,
            "Chapter 2 begins",
            "New chapter starts",
            scene_label="Chapter 2"
        )
        
        # Create bookmarks
        self.bookmark_manager = BookmarkManager(self.test_story_id)
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene1_id,
            label="Chapter 1",
            bookmark_type="chapter"
        )
        
        self.bookmark_manager.create_bookmark(
            scene_id=self.scene3_id,
            label="Chapter 2",
            bookmark_type="chapter"
        )
        
        self.timeline_orchestrator = TimelineOrchestrator(self.test_story_id)
    
    def tearDown(self):
        """Clean up test environment."""
        # Close any open database connections
        import sqlite3
        import gc
        gc.collect()
        
        safe_teardown_temp_dir(self.temp_dir, self.original_cwd)
    
    def test_get_full_timeline(self):
        """Test getting full timeline."""
        timeline = self.timeline_builder.get_full_timeline()
        
        self.assertEqual(timeline['story_id'], self.test_story_id)
        self.assertEqual(timeline['total_scenes'], 3)
        self.assertEqual(timeline['total_bookmarks'], 2)
        self.assertEqual(len(timeline['timeline']), 3)
        
        # Check that bookmarks are associated with scenes
        scene1_entry = timeline['timeline'][0]
        self.assertEqual(len(scene1_entry['bookmarks']), 1)
        self.assertEqual(scene1_entry['bookmarks'][0]['label'], "Chapter 1")
    
    def test_get_chapter_timeline(self):
        """Test getting chapter timeline."""
        timeline = self.timeline_builder.get_chapter_timeline()
        
        self.assertEqual(timeline['story_id'], self.test_story_id)
        self.assertEqual(timeline['total_chapters'], 2)
        
        # Check chapter structure
        chapters = timeline['chapters']
        self.assertEqual(len(chapters), 2)
        
        # First chapter should have scenes 1 and 2
        first_chapter = chapters[0]
        self.assertEqual(first_chapter['chapter']['label'], "Chapter 1")
        self.assertEqual(first_chapter['scene_count'], 2)
    
    def test_get_labeled_timeline(self):
        """Test getting labeled timeline."""
        timeline = self.timeline_builder.get_labeled_timeline()
        
        self.assertEqual(timeline['story_id'], self.test_story_id)
        self.assertEqual(timeline['total_labels'], 3)
        self.assertEqual(timeline['total_labeled_scenes'], 3)
        
        # Check labeled scenes grouping
        labeled_scenes = timeline['labeled_scenes']
        self.assertIn("Chapter 1", labeled_scenes)
        self.assertIn("Action Scene", labeled_scenes)
        self.assertIn("Chapter 2", labeled_scenes)
    
    def test_get_navigation_menu(self):
        """Test getting navigation menu."""
        menu = self.timeline_builder.get_navigation_menu()
        
        self.assertEqual(menu['story_id'], self.test_story_id)
        self.assertEqual(len(menu['chapters']), 2)
        self.assertEqual(len(menu['labeled_scenes']), 3)
        self.assertEqual(len(menu['recent_scenes']), 3)
    
    def test_export_timeline_json(self):
        """Test exporting timeline as JSON."""
        json_timeline = self.timeline_builder.export_timeline_json()
        self.assertIsInstance(json_timeline, str)
        self.assertIn(self.test_story_id, json_timeline)
        
        # Test minimal export
        minimal_json = self.timeline_builder.export_timeline_json(include_content=False)
        self.assertIsInstance(minimal_json, str)
    
    def test_export_timeline_markdown(self):
        """Test exporting timeline as Markdown."""
        markdown = self.timeline_builder.export_timeline_markdown()
        self.assertIsInstance(markdown, str)
        self.assertIn(f"# Story Timeline: {self.test_story_id}", markdown)
        self.assertIn("## Chapter 1", markdown)
        self.assertIn("## Action Scene", markdown)
    
    def test_get_scene_context(self):
        """Test getting scene context."""
        context = self.timeline_builder.get_scene_context(self.scene2_id, context_window=1)
        
        self.assertEqual(context['target_scene_id'], self.scene2_id)
        self.assertEqual(context['context_window'], 1)
        self.assertEqual(len(context['scenes']), 3)  # scene1, scene2, scene3
        
        # Check that target scene is marked
        target_scene = next(s for s in context['scenes'] if s['is_target'])
        self.assertEqual(target_scene['scene_id'], self.scene2_id)
    
    def test_get_stats(self):
        """Test getting timeline statistics."""
        stats = self.timeline_builder.get_stats()
        
        self.assertEqual(stats['story_id'], self.test_story_id)
        self.assertEqual(stats['scenes']['total'], 3)
        self.assertEqual(stats['scenes']['labeled'], 3)
        self.assertEqual(stats['scenes']['unlabeled'], 0)
        self.assertEqual(stats['bookmarks']['total_bookmarks'], 2)
        self.assertTrue(stats['timeline_coverage']['has_chapters'])
        self.assertEqual(stats['timeline_coverage']['labeling_percentage'], 100.0)
    
    def test_tone_consistency_audit(self):
        """Test tone consistency auditing functionality."""
        # Create scenes with tone indicators
        save_scene(
            self.test_story_id,
            "Happy scene",
            "Everyone is cheerful",
            structured_tags={
                'mood': 'happy',
                'tone_indicators': {'emotional_tone': 'positive'}
            }
        )
        
        save_scene(
            self.test_story_id,
            "Sad scene",
            "Things become dark",
            structured_tags={
                'mood': 'sad',
                'tone_indicators': {'emotional_tone': 'negative'}
            }
        )
        
        audit_result = self.timeline_builder.track_tone_consistency_audit()
        
        self.assertIsInstance(audit_result, dict)
        self.assertIn('story_id', audit_result)
        self.assertIn('tone_timeline', audit_result)
        self.assertIn('inconsistencies', audit_result)
        self.assertIn('tone_transitions', audit_result)
        self.assertIn('summary', audit_result)
        
        # Should have processed the scenes
        self.assertEqual(audit_result['story_id'], self.test_story_id)
        self.assertIsInstance(audit_result['tone_timeline'], list)
        self.assertIsInstance(audit_result['inconsistencies'], list)
    
    def test_generate_auto_summary(self):
        """Test auto-summary generation functionality."""
        # Create scenes with more detailed content
        save_scene(
            self.test_story_id,
            "The hero begins their journey",
            "In a small village, our hero sets out on an epic quest",
            scene_label="Journey Begins",
            structured_tags={
                'significance': 'high',
                'action_type': 'journey_start',
                'characters': ['hero']
            }
        )
        
        save_scene(
            self.test_story_id,
            "A challenge appears",
            "The hero faces their first obstacle",
            scene_label="First Challenge",
            structured_tags={
                'significance': 'medium',
                'action_type': 'conflict',
                'characters': ['hero']
            }
        )
        
        summary = self.timeline_builder.generate_auto_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn('story_id', summary)
        self.assertIn('summary', summary)
        self.assertIn('metadata', summary)
        
        # Should have generated a summary
        self.assertEqual(summary['story_id'], self.test_story_id)
        self.assertIsInstance(summary['summary'], str)
        self.assertGreater(len(summary['summary']), 0)
        
        # Metadata should contain scene count
        self.assertIn('scene_count', summary['metadata'])
        self.assertGreater(summary['metadata']['scene_count'], 0)
    
    def test_enhanced_timeline_with_structured_data(self):
        """Test timeline building with enhanced structured data."""
        # Create scene with comprehensive structured tags
        save_scene(
            self.test_story_id,
            "Complex scene with metadata",
            "This scene has extensive metadata for testing",
            scene_label="Metadata Test",
            structured_tags={
                'location': 'castle',
                'mood': 'tense',
                'action_type': 'negotiation',
                'significance': 'high',
                'characters': ['protagonist', 'antagonist'],
                'themes': ['conflict', 'diplomacy'],
                'tone_indicators': {
                    'emotional_tone': 'neutral',
                    'energy_level': 'medium'
                }
            }
        )
        
        # Test that timeline can handle enhanced data
        timeline_data = self.timeline_builder.get_full_timeline()
        
        self.assertIsInstance(timeline_data, dict)
        self.assertIn('timeline', timeline_data)
        timeline = timeline_data['timeline']
        self.assertGreater(len(timeline), 0)
        
        # Find our test scene
        test_scene = None
        for scene in timeline:
            if scene.get('scene_label') == 'Metadata Test':
                test_scene = scene
                break
        
        self.assertIsNotNone(test_scene)
        if 'structured_tags' in test_scene:
            tags = test_scene['structured_tags']
            self.assertEqual(tags['location'], 'castle')
            self.assertEqual(tags['mood'], 'tense')
            self.assertEqual(tags['action_type'], 'negotiation')


if __name__ == '__main__':
    unittest.main()
