"""
OpenChronicle Test Suite

This package contains comprehensive tests for the OpenChronicle storytelling engine.

Test modules:
- test_backup_system.py: Tests for backup and restore functionality
- test_character_style_manager.py: Tests for character tone and style continuity
- test_codebase.py: Main codebase integration tests
- test_content_analysis.py: Tests for content analysis and routing
- test_dynamic_integration.py: Tests for dynamic model integration
- test_dynamic_models.py: Tests for dynamic model management

To run all tests:
    python -m unittest discover -s tests -p "test_*.py" -v

To run a specific test module:
    python -m unittest tests.test_codebase -v
"""

# Test configuration
import sys
import os

# Add the project root to the Python path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
