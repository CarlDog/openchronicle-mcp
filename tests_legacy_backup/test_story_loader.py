"""
Tests for the story loader module.
Tests storypack listing, loading, and file operations functionality.
"""

import pytest
import os
import json
from unittest.mock import patch, mock_open

from core.story_loader import (
    list_storypacks,
    load_meta,
    load_storypack
)


class TestStorypackListing:
    """Test storypack listing functionality."""
    
    @patch('core.story_loader.os.listdir')
    @patch('core.story_loader.os.path.isdir')
    @patch('core.story_loader.os.path.exists')
    def test_list_storypacks_with_meta_json(self, mock_exists, mock_isdir, mock_listdir):
        """Test listing storypacks with meta.json files."""
        mock_listdir.return_value = ["story1", "story2", "not_a_dir"]
        mock_isdir.side_effect = lambda path: path.endswith("story1") or path.endswith("story2")
        mock_exists.side_effect = lambda path: path.endswith("meta.json")
        
        result = list_storypacks()
        
        assert result == ["story1", "story2"]
        mock_listdir.assert_called_once()
        
    @patch('core.story_loader.os.listdir')
    @patch('core.story_loader.os.path.isdir')
    @patch('core.story_loader.os.path.exists')
    def test_list_storypacks_empty_directory(self, mock_exists, mock_isdir, mock_listdir):
        """Test listing when storypacks directory is empty."""
        mock_listdir.return_value = []
        
        result = list_storypacks()
        
        assert result == []


class TestMetaFileLoading:
    """Test meta file loading functionality."""
    
    def test_load_meta_json(self):
        """Test loading meta.json file."""
        mock_meta_data = {"title": "Test Story", "version": "1.0"}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_meta_data))):
            result = load_meta("test/meta.json")
            
        assert result == mock_meta_data
        
    @patch('yaml.safe_load')
    def test_load_meta_yaml(self, mock_yaml_load):
        """Test loading meta.yaml file."""
        mock_meta_data = {"title": "Legacy Story", "version": "0.9"}
        mock_yaml_load.return_value = mock_meta_data
        
        with patch("builtins.open", mock_open()):
            result = load_meta("test/meta.yaml")
            
        assert result == mock_meta_data
        mock_yaml_load.assert_called_once()


class TestStorypackLoading:
    """Test storypack loading functionality."""
    
    @patch('core.story_loader.os.path.exists')
    @patch('core.story_loader.load_meta')
    def test_load_storypack_with_meta_json(self, mock_load_meta, mock_exists):
        """Test loading storypack with meta.json."""
        mock_meta_data = {"title": "Test Adventure", "version": "1.0"}
        mock_load_meta.return_value = mock_meta_data
        
        def mock_exists_side_effect(path):
            if path.endswith("test_story"):
                return True
            elif path.endswith("meta.json"):
                return True
            elif path.endswith("meta.yaml"):
                return False
            elif path.endswith("style_guide.json"):
                return True
            return False
        
        mock_exists.side_effect = mock_exists_side_effect
        
        result = load_storypack("test_story")
        
        assert result["id"] == "test_story"
        assert result["meta"] == mock_meta_data
        assert "path" in result
        assert "canon_dir" in result
        assert "characters_dir" in result
        assert "memory_dir" in result
        assert "style_guide" in result
        assert result["style_guide"].endswith("style_guide.json")
        
    @patch('core.story_loader.os.path.exists')
    def test_load_storypack_not_found(self, mock_exists):
        """Test loading non-existent storypack."""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError, match="Storypack 'nonexistent' not found"):
            load_storypack("nonexistent")
