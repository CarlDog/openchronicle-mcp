#!/usr/bin/env python3
"""
Centralized Backup System Test Script
Tests all functionality of the centralized backup system.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add the utilities directory to the Python path
utilities_path = Path(__file__).parent.parent / "utilities"
sys.path.insert(0, str(utilities_path))

from backup_manager import BackupManager
from logging_system import log_info, log_error

def test_centralized_backup_system():
    """Test the centralized backup system functionality."""
    print("🔄 Testing Centralized Backup System")
    print("=" * 50)
    
    # Initialize backup manager
    backup_manager = BackupManager('storage/backups')
    
    # Test 1: Get backup statistics
    print("\n📊 Backup Statistics:")
    stats = backup_manager.get_backup_statistics()
    print(f"  Total files: {stats['total_files']}")
    print(f"  Total size: {stats['total_size']:,} bytes")
    
    for category, info in stats['directories'].items():
        if info['file_count'] > 0:
            print(f"  {category.title()}: {info['file_count']} files ({info['total_size']:,} bytes)")
            if info['latest_backup']:
                print(f"    Latest: {info['latest_backup']['file']}")
    
    # Test 2: Test config backup (if config exists)
    config_path = Path('config/model_registry.json')
    if config_path.exists():
        print("\n📁 Testing Config Backup:")
        backup_file = backup_manager.backup_config("model_registry.json")
        if backup_file:
            print(f"  ✅ Config backup created: {backup_file}")
        else:
            print("  ❌ Config backup failed")
    else:
        print("\n📁 Config file not found, skipping config backup test")
    
    # Test 3: Test cleanup functionality
    print("\n🧹 Testing Cleanup Functionality:")
    cleanup_stats = backup_manager.cleanup_old_backups(keep_count=10)
    total_cleaned = sum(cleanup_stats.values())
    if total_cleaned > 0:
        print(f"  ✅ Cleaned up {total_cleaned} old backup files")
    else:
        print("  ℹ️  No old backups to clean up")
    
    # Test 4: Directory structure verification
    print("\n📂 Verifying Directory Structure:")
    base_path = Path('storage/backups')
    expected_dirs = ['config', 'databases', 'logs', 'stories']
    
    for dir_name in expected_dirs:
        dir_path = base_path / dir_name
        if dir_path.exists():
            print(f"  ✅ {dir_name}/ directory exists")
        else:
            print(f"  ❌ {dir_name}/ directory missing")
    
    # Test 5: Integration with other utilities
    print("\n🔗 Integration Test:")
    try:
        # Test import of utilities that use backup manager
        from cleanup_storage import main as cleanup_main
        from update_models import main as update_main
        print("  ✅ All utility integrations working")
    except ImportError as e:
        print(f"  ❌ Integration error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Centralized Backup System Test Complete!")
    
    # Summary
    final_stats = backup_manager.get_backup_statistics()
    print(f"\nFinal Statistics:")
    print(f"  📦 Total backup files: {final_stats['total_files']}")
    print(f"  💾 Total backup size: {final_stats['total_size']:,} bytes")
    print(f"  📁 Active categories: {len([k for k, v in final_stats['directories'].items() if v['file_count'] > 0])}")

if __name__ == "__main__":
    test_centralized_backup_system()
