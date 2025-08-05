"""
Debug CharacterStorage initialization issue
"""

import sys
import traceback
import tempfile
from pathlib import Path

def debug_storage_issue():
    """Debug the CharacterStorage initialization problem."""
    try:
        print("🔍 Debugging CharacterStorage initialization...")
        
        from core.character_management.character_storage import CharacterStorage
        
        # Test with minimal config
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            storage_path.mkdir(parents=True, exist_ok=True)
            
            print(f"   📁 Test storage path: {storage_path}")
            print(f"   📁 Path exists: {storage_path.exists()}")
            print(f"   📁 Is directory: {storage_path.is_dir()}")
            
            config = {
                'storage_path': str(storage_path),
                'cache_enabled': True,
                'auto_save': True,
                'backup_enabled': False,
                'max_cache_size': 100
            }
            
            print(f"   ⚙️  Config: {config}")
            
            # Try to create storage
            print("   🧪 Creating CharacterStorage...")
            storage = CharacterStorage(config)
            
            print(f"   ✅ Storage created successfully!")
            print(f"   📁 Storage path: {storage.storage_path}")
            print(f"   ⚙️  Cache enabled: {storage.cache_enabled}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   📋 Full traceback:")
        traceback.print_exc()
        return False

def debug_orchestrator_issue():
    """Debug the CharacterOrchestrator initialization."""
    try:
        print("\n🔍 Debugging CharacterOrchestrator initialization...")
        
        from core.character_management import CharacterOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            storage_path.mkdir(parents=True, exist_ok=True)
            
            # First test: storage config only
            config = {
                'storage': {
                    'storage_path': str(storage_path),
                    'cache_enabled': True,
                    'auto_save': True,
                    'backup_enabled': False
                }
            }
            
            print(f"   ⚙️  Orchestrator config: {config}")
            print("   🧪 Creating CharacterOrchestrator...")
            
            orchestrator = CharacterOrchestrator(config)
            
            print(f"   ✅ Orchestrator created successfully!")
            print(f"   📁 Storage type: {type(orchestrator.storage).__name__}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   📋 Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Character Management Debug Session")
    print("=" * 50)
    
    storage_ok = debug_storage_issue()
    orchestrator_ok = debug_orchestrator_issue()
    
    print("\n" + "=" * 50)
    print("📊 DEBUG RESULTS:")
    print(f"   CharacterStorage: {'✅ OK' if storage_ok else '❌ FAILED'}")
    print(f"   CharacterOrchestrator: {'✅ OK' if orchestrator_ok else '❌ FAILED'}")
    
    if storage_ok and orchestrator_ok:
        print("🎉 All components working correctly!")
    else:
        print("⚠️  Issues found - check error details above")
