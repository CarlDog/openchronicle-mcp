"""
OpenChronicle System Health Check
Fast validation of core systems
"""
import sys
import os
sys.path.insert(0, '.')

def check_core_imports():
    """Test core system imports"""
    print("Core System Import Check:")
    print("-" * 30)
    
    modules = [
        'core.model_management',
        'core.memory_management', 
        'core.character_management'
    ]
    
    working = 0
    for module in modules:
        try:
            exec(f"import {module}")
            print(f"✅ {module}")
            working += 1
        except Exception as e:
            print(f"❌ {module}: {e}")
    
    print(f"\nResult: {working}/{len(modules)} core modules working")
    return working == len(modules)

def check_file_structure():
    """Check critical files exist"""
    print("\nFile Structure Check:")
    print("-" * 30)
    
    critical_paths = [
        'config/system_config.json',
        'storage/',
        'tests/',
        'main.py'
    ]
    
    existing = 0
    for path in critical_paths:
        if os.path.exists(path):
            print(f"✅ {path}")
            existing += 1
        else:
            print(f"❌ {path}")
    
    print(f"\nResult: {existing}/{len(critical_paths)} critical paths exist")
    return existing == len(critical_paths)

if __name__ == "__main__":
    print("🔍 OpenChronicle Health Check")
    print("=" * 40)
    
    imports_ok = check_core_imports()
    structure_ok = check_file_structure()
    
    print(f"\n🎯 Overall System Health:")
    if imports_ok and structure_ok:
        print("✅ HEALTHY - Ready for quality consolidation")
    else:
        print("⚠️  NEEDS ATTENTION - Fix issues before proceeding")
