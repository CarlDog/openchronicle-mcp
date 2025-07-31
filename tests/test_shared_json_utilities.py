"""Tests for shared JSON utilities."""

import pytest
import tempfile
import os
import json
from pathlib import Path

from core.shared.json_utilities import (
    JSONUtilities, 
    DatabaseJSONMixin, 
    ConfigJSONMixin,
    safe_loads, 
    safe_dumps, 
    load_json_file, 
    save_json_file
)

@pytest.fixture
def temp_json_file():
    """Create temporary JSON file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        test_data = {"test": "data", "number": 42}
        json.dump(test_data, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_path:
        yield Path(temp_path)

class TestJSONUtilities:
    """Test core JSONUtilities class."""
    
    def test_safe_loads_success(self):
        """Test successful JSON loading."""
        data = JSONUtilities.safe_loads('{"key": "value"}')
        assert data == {"key": "value"}
    
    def test_safe_loads_invalid_json(self):
        """Test JSON loading with invalid JSON."""
        data = JSONUtilities.safe_loads('{"invalid": json}')
        assert data == {}  # Default fallback
    
    def test_safe_loads_empty_string(self):
        """Test JSON loading with empty string."""
        data = JSONUtilities.safe_loads("")
        assert data == {}
    
    def test_safe_loads_with_fallback(self):
        """Test JSON loading with custom fallback."""
        data = JSONUtilities.safe_loads("invalid", fallback={"default": True})
        assert data == {"default": True}
    
    def test_safe_loads_with_fallback_type(self):
        """Test JSON loading with fallback type."""
        data = JSONUtilities.safe_loads("invalid", fallback_type=list)
        assert data == []
    
    def test_safe_dumps_success(self):
        """Test successful JSON serialization."""
        result = JSONUtilities.safe_dumps({"key": "value"})
        assert json.loads(result) == {"key": "value"}
    
    def test_safe_dumps_pretty(self):
        """Test pretty JSON serialization."""
        result = JSONUtilities.safe_dumps({"key": "value"}, pretty=True)
        assert "  " in result  # Should have indentation
        assert json.loads(result) == {"key": "value"}
    
    def test_safe_dumps_ensure_ascii(self):
        """Test ASCII encoding control."""
        data = {"unicode": "café"}
        result_ascii = JSONUtilities.safe_dumps(data, ensure_ascii=True)
        result_unicode = JSONUtilities.safe_dumps(data, ensure_ascii=False)
        
        assert "\\u" in result_ascii  # Should escape unicode
        assert "café" in result_unicode  # Should preserve unicode
    
    def test_load_file_success(self, temp_json_file):
        """Test successful file loading."""
        data = JSONUtilities.load_file(temp_json_file)
        assert data == {"test": "data", "number": 42}
    
    def test_load_file_not_found(self):
        """Test loading non-existent file."""
        data = JSONUtilities.load_file("nonexistent.json")
        assert data == {}
    
    def test_load_file_with_fallback(self):
        """Test loading non-existent file with fallback."""
        data = JSONUtilities.load_file("nonexistent.json", fallback={"default": True})
        assert data == {"default": True}
    
    def test_save_file_success(self, temp_dir):
        """Test successful file saving."""
        test_data = {"save": "test", "number": 123}
        file_path = temp_dir / "test.json"
        
        result = JSONUtilities.save_file(test_data, file_path)
        assert result is True
        assert file_path.exists()
        
        # Verify content
        loaded_data = JSONUtilities.load_file(file_path)
        assert loaded_data == test_data
    
    def test_save_file_create_dirs(self, temp_dir):
        """Test file saving with directory creation."""
        test_data = {"nested": "save"}
        file_path = temp_dir / "nested" / "dir" / "test.json"
        
        result = JSONUtilities.save_file(test_data, file_path, create_dirs=True)
        assert result is True
        assert file_path.exists()
        
        loaded_data = JSONUtilities.load_file(file_path)
        assert loaded_data == test_data
    
    def test_merge_objects_shallow(self):
        """Test shallow object merging."""
        base = {"a": 1, "b": {"nested": "base"}}
        update = {"b": {"nested": "update"}, "c": 3}
        
        result = JSONUtilities.merge_objects(base, update, deep=False)
        expected = {"a": 1, "b": {"nested": "update"}, "c": 3}
        assert result == expected
    
    def test_merge_objects_deep(self):
        """Test deep object merging."""
        base = {"a": 1, "b": {"x": 1, "y": 2}}
        update = {"b": {"y": 20, "z": 3}, "c": 3}
        
        result = JSONUtilities.merge_objects(base, update, deep=True)
        expected = {"a": 1, "b": {"x": 1, "y": 20, "z": 3}, "c": 3}
        assert result == expected
    
    def test_validate_schema_success(self):
        """Test successful schema validation."""
        data = {"required1": "value", "required2": "value", "optional1": "value"}
        required = ["required1", "required2"]
        optional = ["optional1", "optional2"]
        
        is_valid, errors = JSONUtilities.validate_schema(data, required, optional)
        assert is_valid is True
        assert errors == []
    
    def test_validate_schema_missing_required(self):
        """Test schema validation with missing required keys."""
        data = {"required1": "value"}
        required = ["required1", "required2"]
        
        is_valid, errors = JSONUtilities.validate_schema(data, required)
        assert is_valid is False
        assert "Missing required key: required2" in errors
    
    def test_validate_schema_unknown_keys(self):
        """Test schema validation with unknown keys."""
        data = {"required1": "value", "unknown": "value"}
        required = ["required1"]
        optional = []
        
        is_valid, errors = JSONUtilities.validate_schema(data, required, optional)
        assert is_valid is False
        assert "Unknown key: unknown" in errors

class TestDatabaseJSONMixin:
    """Test database-specific JSON operations."""
    
    def test_safe_db_loads_success(self):
        """Test successful database JSON loading."""
        data = DatabaseJSONMixin.safe_db_loads('{"key": "value"}')
        assert data == {"key": "value"}
    
    def test_safe_db_loads_empty(self):
        """Test database JSON loading with empty/null values."""
        assert DatabaseJSONMixin.safe_db_loads(None) == {}
        assert DatabaseJSONMixin.safe_db_loads("") == {}
        assert DatabaseJSONMixin.safe_db_loads("   ") == {}
    
    def test_safe_db_loads_list_fallback(self):
        """Test database JSON loading with list fallback."""
        data = DatabaseJSONMixin.safe_db_loads(None, fallback_type=list)
        assert data == []
    
    def test_safe_db_dumps(self):
        """Test database JSON serialization."""
        result = DatabaseJSONMixin.safe_db_dumps({"key": "value"})
        assert '"key": "value"' in result
        assert "  " not in result  # Should not be pretty-printed

class TestConfigJSONMixin:
    """Test configuration-specific JSON operations."""
    
    def test_load_config_success(self, temp_json_file):
        """Test successful config loading."""
        config = ConfigJSONMixin.load_config(temp_json_file)
        assert config == {"test": "data", "number": 42}
    
    def test_load_config_with_validation(self, temp_json_file):
        """Test config loading with validation."""
        config = ConfigJSONMixin.load_config(temp_json_file, required_keys=["test"])
        assert config == {"test": "data", "number": 42}
    
    def test_load_config_validation_failure(self, temp_json_file):
        """Test config loading with validation failure."""
        config = ConfigJSONMixin.load_config(temp_json_file, required_keys=["missing"])
        assert config == {}  # Should return empty dict on validation failure
    
    def test_save_config(self, temp_dir):
        """Test config saving."""
        config_data = {"setting1": "value1", "setting2": {"nested": "value"}}
        config_path = temp_dir / "config.json"
        
        result = ConfigJSONMixin.save_config(config_data, config_path)
        assert result is True
        
        # Verify it's pretty-printed and unicode-friendly
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "  " in content  # Should be indented
            
        loaded = ConfigJSONMixin.load_config(config_path)
        assert loaded == config_data

class TestBackwardCompatibility:
    """Test backward compatibility functions."""
    
    def test_safe_loads_compat(self):
        """Test backward compatibility safe_loads."""
        assert safe_loads('{"key": "value"}') == {"key": "value"}
        assert safe_loads("invalid") == {}
    
    def test_safe_dumps_compat(self):
        """Test backward compatibility safe_dumps."""
        result = safe_dumps({"key": "value"})
        assert json.loads(result) == {"key": "value"}
    
    def test_load_json_file_compat(self, temp_json_file):
        """Test backward compatibility load_json_file."""
        data = load_json_file(temp_json_file)
        assert data == {"test": "data", "number": 42}
    
    def test_save_json_file_compat(self, temp_dir):
        """Test backward compatibility save_json_file."""
        test_data = {"compat": "test"}
        file_path = temp_dir / "compat.json"
        
        result = save_json_file(test_data, file_path)
        assert result is True
        assert file_path.exists()

class TestRealWorldPatterns:
    """Test patterns found in the actual codebase."""
    
    def test_scene_logger_pattern(self):
        """Test pattern from scene_logger.py: json.loads(row["field"] or "{}")"""
        # Simulating database row data
        row_data = {
            "memory_snapshot": '{"character": "data"}',
            "flags": '["flag1", "flag2"]',
            "empty_field": None,
            "structured_tags": ""
        }
        
        # Using our new utilities
        memory = DatabaseJSONMixin.safe_db_loads(row_data["memory_snapshot"])
        flags = DatabaseJSONMixin.safe_db_loads(row_data["flags"], fallback_type=list)
        empty = DatabaseJSONMixin.safe_db_loads(row_data["empty_field"])
        tags = DatabaseJSONMixin.safe_db_loads(row_data["structured_tags"])
        
        assert memory == {"character": "data"}
        assert flags == ["flag1", "flag2"]
        assert empty == {}
        assert tags == {}
    
    def test_model_adapter_pattern(self, temp_dir):
        """Test pattern from model_adapter.py: registry loading/saving."""
        registry_data = {
            "models": {
                "openai": {"enabled": True},
                "ollama": {"enabled": False}
            },
            "global_config": {"default_model": "openai"}
        }
        
        registry_path = temp_dir / "model_registry.json"
        
        # Save registry
        success = ConfigJSONMixin.save_config(registry_data, registry_path)
        assert success is True
        
        # Load registry
        loaded_registry = ConfigJSONMixin.load_config(
            registry_path, 
            required_keys=["models", "global_config"]
        )
        assert loaded_registry == registry_data
