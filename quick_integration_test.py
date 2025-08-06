#!/usr/bin/env python3
"""
Quick Integration Test - Check Shared Interface Points
"""

import os
import sys

def check_shared_methods():
    """Check for shared method names between orchestrators without imports."""
    
    # Read ModelOrchestrator methods
    model_file = 'core/model_management/model_orchestrator.py'
    memory_file = 'core/memory_management/memory_orchestrator.py'
    
    model_methods = set()
    memory_methods = set()
    
    try:
        with open(model_file, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                line = line.strip()
                if (line.startswith('def ') or line.startswith('async def ')) and not line.startswith('def _') and not line.startswith('async def _'):
                    method_name = line.split('(')[0].replace('def ', '').replace('async def ', '')
                    model_methods.add(method_name)
        
        with open(memory_file, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                line = line.strip()
                if (line.startswith('def ') or line.startswith('async def ')) and not line.startswith('def _') and not line.startswith('async def _'):
                    method_name = line.split('(')[0].replace('def ', '').replace('async def ', '')
                    memory_methods.add(method_name)
        
        shared_methods = model_methods & memory_methods
        
        print("🔗 SHARED INTERFACE ANALYSIS")
        print("=" * 50)
        print(f"Model methods found: {len(model_methods)}")
        print(f"Memory methods found: {len(memory_methods)}")
        print(f"Shared methods: {len(shared_methods)}")
        print(f"Shared method names: {shared_methods}")
        
        if len(shared_methods) > 0:
            print("\n✅ INTEGRATION COMPATIBLE - Found shared interface points!")
            return True
        else:
            print("\n❌ INTEGRATION ISSUE - No shared interface points found")
            return False
            
    except Exception as e:
        print(f"Error checking methods: {e}")
        return False

if __name__ == "__main__":
    success = check_shared_methods()
    sys.exit(0 if success else 1)
