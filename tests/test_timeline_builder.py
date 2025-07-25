"""
Test suite for Timeline Builder

Tests timeline creation, scene organization, and navigation utilities.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from core.timeline_builder import TimelineBuilder


@pytest.fixture
def mock_database():
    """Mock database operations for testing."""
    with patch('core.timeline_builder.init_database') as mock_init, \
         patch('core.timeline_builder.execute_query') as mock_query:
        mock_init.return_value = None
        yield mock_query


@pytest.fixture
def mock_bookmark_manager():
    """Mock BookmarkManager for testing."""
    with patch('core.timeline_builder.BookmarkManager') as mock_bm:
        mock_instance = Mock()
        mock_bm.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_scene_logger():
    """Mock scene logger functions."""
    with patch('core.timeline_builder.get_labeled_scenes') as mock_labeled:
        mock_labeled.return_value = []
        yield mock_labeled


@pytest.fixture
def sample_scenes():
    """Sample scene data for testing."""
    return [
        ('scene_001', '2024-01-01 08:00:00', 'User input 1', 'Model output 1', '{}', '[]', '[]', 'Scene 1'),
        ('scene_002', '2024-01-01 10:00:00', 'User input 2', 'Model output 2', '{}', '[]', '[]', 'Scene 2'),
        ('scene_003', '2024-01-01 12:00:00', 'User input 3', 'Model output 3', '{}', '[]', '[]', 'Scene 3')
    ]


class TestTimelineBuilder:
    """Test cases for TimelineBuilder class."""

    def test_init(self, mock_database, mock_bookmark_manager):
        """Test TimelineBuilder initialization."""
        builder = TimelineBuilder('test_story')
        assert builder.story_id == 'test_story'
        assert builder.bookmark_manager is not None

    def test_get_full_timeline(self, mock_database, mock_bookmark_manager, sample_scenes):
        """Test getting full timeline with scenes and bookmarks."""
        mock_database.return_value = sample_scenes
        mock_bookmark_manager.get_timeline_bookmarks.return_value = []
        
        builder = TimelineBuilder('test_story')
        timeline = builder.get_full_timeline()
        
        assert 'timeline' in timeline
        assert 'story_id' in timeline
        assert timeline['story_id'] == 'test_story'
        assert 'total_scenes' in timeline
        mock_database.assert_called()

    def test_get_chapter_timeline(self, mock_database, mock_bookmark_manager):
        """Test getting chapter-based timeline."""
        mock_bookmark_manager.get_chapter_structure.return_value = {
            1: [{'bookmark_id': 'ch1', 'scene_id': 'scene_001', 'title': 'Chapter 1', 'created_at': '2024-01-01'}]
        }
        mock_database.return_value = []
        
        builder = TimelineBuilder('test_story')
        timeline = builder.get_chapter_timeline()
        
        assert 'chapters' in timeline
        assert 'story_id' in timeline

    def test_get_labeled_timeline(self, mock_database, mock_bookmark_manager, mock_scene_logger):
        """Test getting labeled timeline."""
        mock_scene_logger.return_value = [
            {'scene_id': 'scene_001', 'scene_label': 'Important Scene'}
        ]
        
        builder = TimelineBuilder('test_story')
        timeline = builder.get_labeled_timeline()
        
        assert 'labeled_scenes' in timeline
        assert 'story_id' in timeline

    def test_get_navigation_menu(self, mock_database, mock_bookmark_manager, mock_scene_logger):
        """Test getting navigation menu structure."""
        mock_bookmark_manager.list_bookmarks.side_effect = [
            [{'bookmark_id': 'ch1', 'title': 'Chapter 1'}],  # chapters
            [{'bookmark_id': 'user1', 'title': 'Important Scene'}]  # user bookmarks
        ]
        mock_database.return_value = [
            ('scene_001', '2024-01-01 08:00:00', 'Scene 1', 'User input 1')
        ]
        
        builder = TimelineBuilder('test_story')
        menu = builder.get_navigation_menu()
        
        assert 'chapters' in menu
        assert 'user_bookmarks' in menu
        assert 'labeled_scenes' in menu
        assert 'recent_scenes' in menu

    def test_export_timeline_json(self, mock_database, mock_bookmark_manager):
        """Test JSON timeline export."""
        mock_database.return_value = []
        mock_bookmark_manager.get_timeline_bookmarks.return_value = []
        
        builder = TimelineBuilder('test_story')
        json_output = builder.export_timeline_json()
        
        assert isinstance(json_output, str)
        # Should be valid JSON
        parsed = json.loads(json_output)
        assert 'story_id' in parsed

    def test_export_timeline_markdown(self, mock_database, mock_bookmark_manager):
        """Test Markdown timeline export."""
        mock_database.return_value = []
        mock_bookmark_manager.get_timeline_bookmarks.return_value = []
        
        builder = TimelineBuilder('test_story')
        markdown_output = builder.export_timeline_markdown()
        
        assert isinstance(markdown_output, str)
        assert '# Timeline' in markdown_output or 'Timeline' in markdown_output

    def test_get_scene_context(self, mock_database, mock_bookmark_manager, sample_scenes):
        """Test getting scene context with window."""
        mock_database.return_value = sample_scenes
        
        builder = TimelineBuilder('test_story')
        context = builder.get_scene_context('scene_002', context_window=1)
        
        assert 'target_scene_id' in context
        assert 'scenes' in context
        assert 'story_id' in context

    def test_get_stats(self, mock_database, mock_bookmark_manager):
        """Test getting timeline statistics."""
        # Mock the complex query result that get_stats expects
        mock_database.return_value = [(5, 3, '2024-01-01 08:00:00', '2024-01-01 12:00:00')]
        mock_bookmark_manager.get_stats.return_value = {
            'total': 2,
            'by_type': {'chapter': 1, 'user': 1}
        }
        
        builder = TimelineBuilder('test_story')
        stats = builder.get_stats()
        
        assert 'scenes' in stats
        assert 'bookmarks' in stats
        assert 'story_id' in stats

    def test_track_tone_consistency_audit(self, mock_database, mock_bookmark_manager):
        """Test tone consistency tracking."""
        mock_database.return_value = []
        
        builder = TimelineBuilder('test_story')
        audit = builder.track_tone_consistency_audit()
        
        assert 'story_id' in audit
        assert 'inconsistencies' in audit

    def test_generate_auto_summary(self, mock_database, mock_bookmark_manager):
        """Test automatic summary generation."""
        # Mock with proper 6-value scene structure (scene_id, timestamp, input, output, flags, scene_label)
        mock_database.return_value = [
            ('scene_001', '2024-01-01 08:00:00', 'User input 1', 'Model output 1', '[]', 'Scene 1'),
            ('scene_002', '2024-01-01 10:00:00', 'User input 2', 'Model output 2', '[]', 'Scene 2')
        ]
        
        builder = TimelineBuilder('test_story')
        summary = builder.generate_auto_summary()
        
        assert 'story_id' in summary
        assert 'generated_at' in summary
        # Function should always return a dict with these keys, even on error
