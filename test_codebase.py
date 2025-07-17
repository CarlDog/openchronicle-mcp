#!/usr/bin/env python3
"""
Simple test script to verify the OpenChronicle codebase is working correctly.
"""

import sys
import os
import traceback

def test_imports():
    """Test that all core modules can be imported."""
    try:
        from core.story_loader import load_storypack, list_storypacks
        from core.context_builder import build_context
        from core.scene_logger import save_scene, load_scene
        from core.memory_manager import (
            load_current_memory, 
            update_character_memory, 
            add_memory_flag,
            get_memory_summary
        )
        from core.rollback_engine import (
            rollback_to_scene,
            get_rollback_candidates,
            validate_rollback_integrity
        )
        from core.database import init_database, get_database_stats
        print("✅ All core modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_database_setup():
    """Test SQLite database setup."""
    try:
        from core.database import init_database, get_database_stats
        
        # Initialize database for demo story
        init_database("demo-story")
        print("✅ Database initialized successfully")
        
        # Get database stats
        stats = get_database_stats("demo-story")
        print(f"✅ Database stats: {stats['scenes_count']} scenes, {stats['memory_entries']} memory entries")
        
        return True
    except Exception as e:
        print(f"❌ Database setup error: {e}")
        traceback.print_exc()
        return False

def test_story_loading():
    """Test story loading functionality."""
    try:
        from core.story_loader import load_storypack, list_storypacks
        
        # Test listing storypacks
        storypacks = list_storypacks()
        print(f"✅ Found storypacks: {storypacks}")
        
        # Test loading demo story
        story = load_storypack("demo-story")
        print(f"✅ Loaded story: {story['meta']['title']}")
        
        # Verify story structure
        expected_keys = ['id', 'path', 'meta', 'canon_dir', 'characters_dir', 'memory_dir', 'style_guide']
        for key in expected_keys:
            if key not in story:
                print(f"❌ Missing key in story: {key}")
                return False
        
        print("✅ Story structure is correct")
        return True
    except Exception as e:
        print(f"❌ Story loading error: {e}")
        traceback.print_exc()
        return False

def test_context_building():
    """Test context building functionality."""
    try:
        from core.story_loader import load_storypack
        from core.context_builder import build_context
        
        story = load_storypack("demo-story")
        context = build_context("Hello world", story)
        
        expected_keys = ['prompt', 'memory', 'canon_used']
        for key in expected_keys:
            if key not in context:
                print(f"❌ Missing key in context: {key}")
                return False
        
        print("✅ Context building works correctly")
        return True
    except Exception as e:
        print(f"❌ Context building error: {e}")
        traceback.print_exc()
        return False

def test_memory_system():
    """Test memory management functionality."""
    try:
        from core.memory_manager import (
            load_current_memory,
            update_character_memory,
            add_memory_flag,
            get_memory_summary
        )
        
        # Test basic memory operations
        memory = load_current_memory("demo-story")
        print(f"✅ Loaded memory structure")
        
        # Test character memory update
        update_character_memory("demo-story", "test_character", {
            "traits": {"brave": True},
            "current_state": {"location": "test_location"}
        })
        print("✅ Character memory update works")
        
        # Test memory flags
        add_memory_flag("demo-story", "test_flag", {"value": "test"})
        print("✅ Memory flags work")
        
        # Test memory summary
        summary = get_memory_summary("demo-story")
        print("✅ Memory summary works")
        
        return True
    except Exception as e:
        print(f"❌ Memory system error: {e}")
        traceback.print_exc()
        return False

def test_rollback_system():
    """Test rollback engine functionality."""
    try:
        from core.rollback_engine import (
            get_rollback_candidates,
            validate_rollback_integrity
        )
        from core.scene_logger import save_scene
        
        # Create a test scene first
        scene_id = save_scene("demo-story", "test input", "test output")
        print("✅ Created test scene for rollback testing")
        
        # Test rollback candidates
        candidates = get_rollback_candidates("demo-story", limit=5)
        print("✅ Rollback candidates retrieved")
        
        # Test integrity validation
        issues = validate_rollback_integrity("demo-story")
        print("✅ Rollback integrity validation works")
        
        return True
    except Exception as e:
        print(f"❌ Rollback system error: {e}")
        traceback.print_exc()
        return False

def test_model_adapter_system():
    """Test model adapter system functionality."""
    try:
        from core.model_adapter import ModelManager, MockAdapter
        import asyncio
        
        async def run_adapter_tests():
            # Test model manager initialization
            manager = ModelManager()
            print("✅ Model manager initialized")
            
            # Test available adapters
            adapters = manager.get_available_adapters()
            expected_adapters = ['openai', 'ollama', 'mock']
            for adapter in expected_adapters:
                if adapter not in adapters:
                    print(f"❌ Missing adapter: {adapter}")
                    return False
            print("✅ All expected adapters available")
            
            # Test mock adapter initialization
            success = await manager.initialize_adapter("mock")
            if not success:
                print("❌ Failed to initialize mock adapter")
                return False
            print("✅ Mock adapter initialized")
            
            # Test response generation
            response = await manager.generate_response("Test prompt", story_id="test-story")
            if not response or len(response) == 0:
                print("❌ Empty response from model")
                return False
            print("✅ Response generation works")
            
            # Test adapter info
            info = manager.get_adapter_info("mock")
            if not info.get("initialized"):
                print("❌ Adapter not marked as initialized")
                return False
            print("✅ Adapter info works")
            
            # Test shutdown
            await manager.shutdown()
            print("✅ Model manager shutdown works")
            
            return True
        
        # Run async tests
        result = asyncio.run(run_adapter_tests())
        return result
        
    except Exception as e:
        print(f"❌ Model adapter system error: {e}")
        traceback.print_exc()
        return False

def test_content_analysis_system():
    """Test content analysis system functionality."""
    try:
        from core.content_analyzer import content_analyzer
        from core.context_builder import build_context_with_analysis
        from core.story_loader import load_storypack
        import asyncio
        
        async def run_analysis_tests():
            # Test content analyzer initialization
            print("✅ Content analyzer initialized")
            
            # Test story loading for analysis
            story = load_storypack("demo-story")
            print("✅ Story loaded for analysis")
            
            # Test content analysis
            story_context = {
                "story_id": story["id"],
                "meta": story.get("meta", {}),
                "characters": {}
            }
            
            analysis = await content_analyzer.analyze_user_input(
                "I draw my sword and challenge the dragon!", 
                story_context
            )
            
            if not analysis.get("content_type"):
                print("❌ Analysis missing content_type")
                return False
            print("✅ Content analysis works")
            
            # Test context building with analysis
            context = await build_context_with_analysis("Test input", story)
            if not context.get("analysis"):
                print("❌ Context building missing analysis")
                return False
            print("✅ Context building with analysis works")
            
            # Test flag generation
            flags = await content_analyzer.generate_content_flags(analysis, "Test response")
            if not flags:
                print("❌ Flag generation failed")
                return False
            print("✅ Flag generation works")
            
            # Test routing recommendations
            routing = content_analyzer.get_routing_recommendation(analysis)
            if not routing.get("adapter"):
                print("❌ Routing recommendation missing adapter")
                return False
            print("✅ Routing recommendations work")
            
            return True
        
        # Run async tests
        result = asyncio.run(run_analysis_tests())
        return result
        
    except Exception as e:
        print(f"❌ Content analysis system error: {e}")
        traceback.print_exc()
        return False

def test_directory_structure():
    """Test that all required directories exist."""
    try:
        required_dirs = [
            "core",
            "storypacks",
            "storypacks/demo-story",
            "storypacks/demo-story/canon",
            "storypacks/demo-story/characters", 
            "storypacks/demo-story/memory",
            "storage",
            "storage/demo-story"
        ]
        
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                print(f"❌ Missing directory: {dir_path}")
                return False
        
        print("✅ All required directories exist")
        return True
    except Exception as e:
        print(f"❌ Directory structure error: {e}")
        return False

def test_required_files():
    """Test that all required files exist."""
    try:
        required_files = [
            "main.py",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yaml",
            ".env",
            "core/__init__.py",
            "core/story_loader.py",
            "core/context_builder.py",
            "core/scene_logger.py",
            "core/memory_manager.py",
            "core/database.py",
            "core/model_adapter.py",
            "core/content_analyzer.py",
            "config/models.json",
            "storypacks/demo-story/meta.yaml",
            "storypacks/demo-story/style_guide.md"
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                print(f"❌ Missing file: {file_path}")
                return False
        
        print("✅ All required files exist")
        return True
    except Exception as e:
        print(f"❌ File structure error: {e}")
        return False

def test_backup_system():
    """Test the centralized backup system functionality."""
    try:
        # Add utilities to path
        utilities_path = os.path.join(os.path.dirname(__file__), "utilities")
        sys.path.insert(0, utilities_path)
        
        from backup_manager import BackupManager
        from logging_system import log_info
        
        # Test backup manager initialization
        backup_manager = BackupManager('storage/backups')
        print("✅ Backup manager initialized successfully")
        
        # Test backup statistics
        stats = backup_manager.get_backup_statistics()
        print(f"✅ Backup statistics: {stats['total_files']} files, {stats['total_size']} bytes")
        
        # Test directory structure
        from pathlib import Path
        base_path = Path('storage/backups')
        expected_dirs = ['config', 'databases', 'logs', 'stories']
        
        for dir_name in expected_dirs:
            dir_path = base_path / dir_name
            if not dir_path.exists():
                print(f"❌ Missing backup directory: {dir_name}")
                return False
        
        print("✅ All backup directories exist")
        
        # Test cleanup functionality
        cleanup_stats = backup_manager.cleanup_old_backups(keep_count=10)
        print("✅ Backup cleanup functionality works")
        
        # Test integration with utilities
        try:
            from cleanup_storage import main as cleanup_main
            from update_models import main as update_main
            print("✅ Backup system integration verified")
        except ImportError as e:
            print(f"❌ Integration error: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Backup system error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🔍 Running OpenChronicle codebase verification...")
    print("=" * 50)
    
    tests = [
        test_directory_structure,
        test_required_files,
        test_imports,
        test_database_setup,
        test_story_loading,
        test_context_building,
        test_memory_system,
        test_rollback_system,
        test_model_adapter_system,
        test_content_analysis_system,
        test_backup_system
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print(f"\n🧪 Running {test.__name__}...")
        if test():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The codebase is ready for upload.")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues before upload.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
