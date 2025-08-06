#!/usr/bin/env python3
"""
Simple Integration Test - Model-Memory Interface Check
"""

import asyncio
import time
from typing import Dict, Any

class SimpleIntegrationTest:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
    
    def log_test(self, test_name: str, success: bool, details: str, duration: float):
        """Log test result."""
        self.total += 1
        if success:
            self.passed += 1
            print(f"PASS: {test_name} ({duration:.3f}s)")
            print(f"    -> {details}")
        else:
            self.failed += 1
            print(f"FAIL: {test_name} ({duration:.3f}s)")
            print(f"    -> {details}")
    
    async def test_model_memory_integration(self):
        """Test Model-Memory integration with shared interface points."""
        print("\nTesting MODEL <-> MEMORY Integration")
        print("-" * 50)
        
        start = time.time()
        try:
            from core.model_management import ModelOrchestrator
            from core.memory_management import MemoryOrchestrator
            
            # Initialize components
            model_orch = ModelOrchestrator()
            memory_orch = MemoryOrchestrator()
            
            self.log_test("Model-Memory component instantiation", True, 
                         "Both orchestrators created successfully", time.time() - start)
            
            # Test integration points
            model_methods = [m for m in dir(model_orch) if not m.startswith('_')]
            memory_methods = [m for m in dir(memory_orch) if not m.startswith('_')]
            
            integration_points = set(model_methods) & set(memory_methods)
            
            self.log_test("Model-Memory interface compatibility", len(integration_points) > 0,
                         f"Found {len(integration_points)} shared interface points: {integration_points}", 
                         time.time() - start)
            
            # Test specific shared methods exist
            has_get_status = hasattr(model_orch, 'get_status') and hasattr(memory_orch, 'get_status')
            has_initialize = hasattr(model_orch, 'initialize') and hasattr(memory_orch, 'initialize')
            
            self.log_test("Shared interface methods", has_get_status and has_initialize,
                         f"get_status: {has_get_status}, initialize: {has_initialize}", 
                         time.time() - start)
            
            return True
            
        except Exception as e:
            self.log_test("Model-Memory integration", False, str(e), time.time() - start)
            return False
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 60)
        print(f"Tests completed: {self.total}")
        print(f"Tests passed: {self.passed}")
        print(f"Tests failed: {self.failed}")
        success_rate = (self.passed / self.total * 100) if self.total > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        
        if self.failed == 0:
            print("RESULT: ALL TESTS PASSED - Integration Successful!")
        else:
            print(f"RESULT: {self.failed} TEST(S) FAILED - Integration Issues Remain")

async def main():
    """Run simple integration test."""
    test = SimpleIntegrationTest()
    
    print("Phase 2: Integration Excellence Testing")
    print("Simple Model-Memory Interface Validation")
    print("=" * 60)
    
    await test.test_model_memory_integration()
    test.print_summary()
    
    return test.failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
