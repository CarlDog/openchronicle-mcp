#!/usr/bin/env python3
"""
Comprehensive test suite for OpenChronicle Storypack Importer.

This module contains all tests for the storypack import functionality,
including basic import, AI-powered analysis, file discovery, and CLI operations.
"""

import pytest
import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Import OpenChronicle utilities
from utilities.logging_system import log_info, log_warning, log_error, log_system_event

# Import the system under test
from utilities.storypack_importer import StorypackImporter, quick_import_test


# Global list to track created storypacks for cleanup
_created_storypacks = []


def track_storypack(storypack_path):
    """Track a storypack for cleanup."""
    global _created_storypacks
    path = Path(storypack_path)
    if path not in _created_storypacks:
        _created_storypacks.append(path)
        log_system_event("test_storypack_tracking", "Tracked storypack for cleanup", {
            "storypack_path": str(path),
            "total_tracked": len(_created_storypacks)
        })


def cleanup_tracked_storypacks():
    """Clean up only the storypacks we explicitly created."""
    global _created_storypacks
    
    log_system_event("test_cleanup", "Starting tracked storypack cleanup", {
        "storypacks_to_clean": len(_created_storypacks)
    })
    
    cleaned_count = 0
    failed_count = 0
    
    for storypack_path in _created_storypacks:
        if storypack_path.exists():
            try:
                shutil.rmtree(storypack_path)
                log_info(f"Cleaned up tracked storypack: {storypack_path.name}")
                cleaned_count += 1
            except Exception as e:
                log_warning(f"Could not clean up storypack {storypack_path.name}: {e}")
                failed_count += 1
        else:
            log_info(f"Storypack already removed: {storypack_path.name}")
    
    _created_storypacks.clear()
    
    log_system_event("test_cleanup", "Completed tracked storypack cleanup", {
        "cleaned_count": cleaned_count,
        "failed_count": failed_count,
        "total_processed": cleaned_count + failed_count
    })


@pytest.fixture(scope="session", autouse=True)
def test_session_cleanup():
    """Clean up tracked storypacks at the end of test session."""
    yield
    cleanup_tracked_storypacks()


class TestStorypackImporter:
    """Test cases for the StorypackImporter class."""
    
    @pytest.fixture
    def temp_source_dir(self):
        """Create a temporary directory with test source files."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create test directory structure
        (temp_dir / "characters").mkdir()
        (temp_dir / "locations").mkdir()
        (temp_dir / "lore").mkdir()
        
        # Create test files
        (temp_dir / "characters" / "hero.txt").write_text(
            "Sir Galahad the Pure\n\nA noble knight with unwavering honor..."
        )
        (temp_dir / "characters" / "villain.txt").write_text(
            "Lord Vex the Dark\n\nA corrupted sorcerer seeking power..."
        )
        (temp_dir / "locations" / "castle.txt").write_text(
            "Castle Brightkeep\n\nA shining fortress on the hill..."
        )
        (temp_dir / "lore" / "legend.txt").write_text(
            "The Legend of the Crystal Sword\n\nLong ago, when magic flowed..."
        )
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def importer(self, temp_source_dir):
        """Create a StorypackImporter instance with test source directory."""
        return StorypackImporter(temp_source_dir)
    
    def test_initialization(self, temp_source_dir):
        """Test StorypackImporter initialization."""
        importer = StorypackImporter(temp_source_dir)
        
        assert importer.source_dir == temp_source_dir
        assert importer.logger is not None
        assert isinstance(importer.content_categories, dict)
        assert isinstance(importer.supported_extensions, set)  # It's a set, not a list
    
    def test_file_discovery(self, importer):
        """Test source file discovery and categorization."""
        discovered_files = importer.discover_source_files()
        
        # Check that files were discovered
        assert "characters" in discovered_files
        assert "locations" in discovered_files
        assert "lore" in discovered_files
        
        # Check specific files
        character_files = [f.name for f in discovered_files["characters"]]
        assert "hero.txt" in character_files
        assert "villain.txt" in character_files
        
        location_files = [f.name for f in discovered_files["locations"]]
        assert "castle.txt" in location_files
        
        lore_files = [f.name for f in discovered_files["lore"]]
        assert "legend.txt" in lore_files
    
    def test_validate_import_readiness(self, importer):
        """Test import readiness validation."""
        ready, issues = importer.validate_import_readiness()
        
        # Should be ready with test files
        assert ready is True
        assert len(issues) == 0
    
    def test_basic_import(self, importer, temp_source_dir):
        """Test basic storypack import functionality."""
        storypack_name = "test_basic_import"
        
        log_system_event("test_start", "Starting basic import test", {
            "test_name": "test_basic_import",
            "storypack_name": storypack_name,
            "source_dir": str(temp_source_dir)
        })
        
        result = importer.run_basic_import(storypack_name)
        
        # Track the created storypack for cleanup
        storypack_path = Path(result["storypack_path"])
        track_storypack(storypack_path)
        
        # Check result structure
        assert result["success"] is True
        assert result["storypack_name"] == storypack_name
        assert "storypack_path" in result
        assert "discovered_files" in result
        assert "templates_used" in result
        
        # Check that storypack was created
        assert storypack_path.exists()
        assert (storypack_path / "meta.json").exists()
        
        # Verify discovered files structure
        discovered = result["discovered_files"]
        assert len(discovered["characters"]) == 2
        assert len(discovered["locations"]) == 1
        assert len(discovered["lore"]) == 1
        
        log_system_event("test_end", "Completed basic import test", {
            "test_name": "test_basic_import",
            "result_success": result["success"],
            "storypack_created": str(storypack_path)
        })
    
    @pytest.mark.asyncio
    async def test_ai_import(self, importer):
        """Test AI-powered storypack import."""
        storypack_name = "test_ai_import"
        
        log_system_event("test_start", "Starting AI import test", {
            "test_name": "test_ai_import",
            "storypack_name": storypack_name
        })
        
        # Mock AI capabilities to avoid external dependencies
        with patch.object(importer, 'test_ai_capabilities', return_value=True), \
             patch.object(importer, 'content_analyzer') as mock_analyzer:
            
            # Mock AI analysis methods
            mock_analyzer.analyze_content_category = AsyncMock(return_value={
                "content_type": "character",
                "confidence": 0.8
            })
            mock_analyzer.extract_character_data = AsyncMock(return_value=[])
            mock_analyzer.extract_location_data = AsyncMock(return_value=[])
            mock_analyzer.extract_lore_data = AsyncMock(return_value=[])
            mock_analyzer.generate_import_metadata = AsyncMock(return_value={
                "title": storypack_name,
                "confidence": 0.75
            })
            
            result = await importer.run_ai_import(storypack_name)
            
            # Track the created storypack for cleanup
            storypack_path = Path(result["storypack_path"])
            track_storypack(storypack_path)
            
            # Check result structure
            assert result["success"] is True
            assert result["storypack_name"] == storypack_name
            assert "files_processed" in result
            assert "analysis_results" in result
            assert "metadata" in result
            
            log_system_event("test_end", "Completed AI import test", {
                "test_name": "test_ai_import",
                "result_success": result["success"],
                "storypack_created": str(storypack_path)
            })
    
    def test_get_import_summary(self, importer):
        """Test import summary generation."""
        summary = importer.get_import_summary()
        
        assert "source_directory" in summary
        assert "discovered_files" in summary
        assert "available_templates" in summary  # This is what's actually returned
        assert "import_ready" in summary
    
    def test_categorize_file(self, importer, temp_source_dir):
        """Test file categorization logic."""
        # Test character file categorization
        char_file = temp_source_dir / "characters" / "hero.txt"
        category = importer._categorize_file(char_file)
        assert category == "characters"
        
        # Test location file categorization
        loc_file = temp_source_dir / "locations" / "castle.txt"
        category = importer._categorize_file(loc_file)
        assert category == "locations"
        
        # Test uncategorized file
        misc_file = temp_source_dir / "misc.txt"
        misc_file.write_text("Random content")
        category = importer._categorize_file(misc_file)
        assert category == "uncategorized"


class TestStorypackImporterAI:
    """Test cases for AI-powered features."""
    
    @pytest.fixture
    def temp_source_dir(self):
        """Create a temporary directory with test source files."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create test directory structure
        (temp_dir / "characters").mkdir()
        (temp_dir / "test.txt").write_text("Test content")
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_importer(self, temp_source_dir):
        """Create a mock importer for AI testing."""
        importer = StorypackImporter(temp_source_dir)
        
        # Mock the AI components
        importer.model_manager = Mock()
        importer.content_analyzer = Mock()
        
        return importer
    
    def test_ai_initialization(self, mock_importer):
        """Test AI capabilities initialization."""
        # Mock successful AI initialization
        mock_importer.model_manager.get_model_for_content_type.return_value = "mock"
        mock_importer.content_analyzer.model_manager = mock_importer.model_manager
        
        result = mock_importer.initialize_ai()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_ai_capabilities_test(self, mock_importer):
        """Test AI capabilities testing."""
        # Mock AI test responses
        mock_importer.content_analyzer.find_working_analysis_models = AsyncMock(
            return_value=[
                {"name": "mock", "suitability_score": 0.9},
                {"name": "test-sync", "suitability_score": 0.8}
            ]
        )
        mock_importer.content_analyzer.analyze_imported_content = AsyncMock(
            return_value={"characters": [{"name": "Sarah"}], "content_type": "narrative"}
        )
        mock_importer.content_analyzer.analyze_content_category = AsyncMock(
            return_value={"content_type": "test", "confidence": 0.8}
        )
        mock_importer.content_analyzer.extract_character_data = AsyncMock(
            return_value=[{"name": "Test Character"}]
        )
        
        result = await mock_importer.test_ai_capabilities()
        
        # Should return True for successful test
        assert result is True


class TestQuickImportFunction:
    """Test cases for the quick_import_test function."""
    
    def test_quick_import_test(self):
        """Test the quick import test function."""
        with patch('utilities.storypack_importer.StorypackImporter') as MockImporter:
            # Mock the importer behavior to avoid creating real files
            mock_instance = MockImporter.return_value
            mock_instance.validate_import_readiness.return_value = (True, [])
            mock_instance.run_basic_import.return_value = {
                "success": True,
                "storypack_name": "test_import",
                "storypack_path": "/fake/path/that/does/not/exist",  # Use fake path
                "discovered_files": {"characters": [], "locations": [], "lore": []}
            }
            
            result = quick_import_test("test_import")
            
            assert result["success"] is True
            assert result["storypack_name"] == "test_import"
            # No need to track this since it's a fake path


class TestStorageAndCleanup:
    """Test cases for storage management and cleanup."""
    
    @pytest.fixture
    def temp_source_dir(self):
        """Create a temporary directory with test source files."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create test directory structure
        (temp_dir / "characters").mkdir()
        (temp_dir / "test.txt").write_text("Test content")
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def importer(self, temp_source_dir):
        """Create a StorypackImporter instance with test source directory."""
        return StorypackImporter(temp_source_dir)
    
    def test_storypack_creation_structure(self, importer):
        """Test that created storypacks have correct structure."""
        storypack_name = "test_structure_validation"
        
        result = importer.run_basic_import(storypack_name)
        storypack_path = Path(result["storypack_path"])
        track_storypack(storypack_path)
        
        # Verify directory structure (based on create_storypack_structure method)
        assert storypack_path.exists()
        assert (storypack_path / "meta.json").exists()
        assert (storypack_path / "characters").exists()
        assert (storypack_path / "canon").exists()
        assert (storypack_path / "memory").exists()
    
    def test_cleanup_tracking(self):
        """Test that our tracking system works correctly."""
        # Create a temporary test directory to simulate a storypack
        temp_dir = Path(tempfile.mkdtemp(prefix="test_cleanup_"))
        temp_dir.mkdir(exist_ok=True)
        (temp_dir / "test_file.txt").write_text("test content")
        
        # Track it
        track_storypack(temp_dir)
        
        # Verify it's tracked
        assert temp_dir in _created_storypacks
        
        # Clean up manually for this test
        cleanup_tracked_storypacks()
        
        # Verify it was cleaned up
        assert not temp_dir.exists()
        assert len(_created_storypacks) == 0


class TestCLIIntegration:
    """Test cases for CLI functionality."""
    
    @pytest.mark.asyncio
    async def test_cli_preview_mode(self):
        """Test CLI preview mode functionality."""
        from utilities.storypack_importer import _run_cli_import
        
        # Mock CLI arguments
        mock_args = Mock()
        mock_args.source_directory = "test_dir"
        mock_args.storypack_name = "test"
        mock_args.preview = True
        mock_args.basic = False
        mock_args.ai = False
        mock_args.dry_run = False
        
        # Mock the importer
        with patch('utilities.storypack_importer.StorypackImporter') as MockImporter:
            mock_instance = MockImporter.return_value
            mock_instance.discover_source_files.return_value = {
                "characters": ["hero.txt"],
                "locations": ["castle.txt"]
            }
            
            # Should run without errors
            try:
                await _run_cli_import(mock_args)
            except SystemExit:
                pass  # CLI may exit normally


if __name__ == "__main__":
    # Run pytest when script is executed directly
    pytest.main([__file__, "-v"])
