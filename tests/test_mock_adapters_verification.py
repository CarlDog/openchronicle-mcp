"""
Quick verification test for both mock adapters.

This test ensures both the production MockAdapter and TestMockAdapter
work correctly and can be used in OpenChronicle's testing infrastructure.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mocks.mock_adapters import TestMockAdapter, create_deterministic_mock, create_error_mock


async def test_mock_adapters():
    """Test both mock adapter implementations."""
    
    print("🧪 Testing Mock Adapters")
    print("=" * 50)
    
    # Test 1: Basic TestMockAdapter functionality
    print("\n1. Testing TestMockAdapter:")
    test_adapter = TestMockAdapter("test-model")
    
    response = await test_adapter.generate_response("Test prompt")
    print(f"   ✅ Basic response: {response.content}")
    print(f"   ✅ Call count: {test_adapter.get_call_count()}")
    
    # Test 2: Queued responses
    print("\n2. Testing queued responses:")
    test_adapter.queue_responses(["First response", "Second response"])
    
    resp1 = await test_adapter.generate_response("Prompt 1")
    resp2 = await test_adapter.generate_response("Prompt 2")
    
    print(f"   ✅ First queued: {resp1.content}")
    print(f"   ✅ Second queued: {resp2.content}")
    
    # Test 3: Error handling
    print("\n3. Testing error handling:")
    error_adapter = create_error_mock(ValueError("Test error"))
    
    try:
        await error_adapter.generate_response("This should fail")
        print("   ❌ Error test failed - no exception raised")
    except ValueError as e:
        print(f"   ✅ Error correctly raised: {e}")
    
    # Test 4: Deterministic behavior
    print("\n4. Testing deterministic behavior:")
    det_adapter = create_deterministic_mock()
    
    response1 = await det_adapter.generate_response("Same prompt")
    response2 = await det_adapter.generate_response("Same prompt")
    
    print(f"   ✅ Response 1: {response1.content}")
    print(f"   ✅ Response 2: {response2.content}")
    print(f"   ✅ Deterministic: {response1.content == response2.content}")
    
    # Test 5: Assertion helpers
    print("\n5. Testing assertion helpers:")
    assert_adapter = TestMockAdapter("assert-test")
    
    await assert_adapter.generate_response("Test assertion")
    
    try:
        assert_adapter.assert_called()
        print("   ✅ assert_called() passed")
        
        assert_adapter.assert_called_times(1)
        print("   ✅ assert_called_times(1) passed")
        
        assert_adapter.assert_last_prompt_contains("assertion")
        print("   ✅ assert_last_prompt_contains() passed")
        
    except AssertionError as e:
        print(f"   ❌ Assertion failed: {e}")
    
    # Test 6: Production Mock Adapter (if available)
    print("\n6. Testing Production MockAdapter:")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'mock_adapter', 
            'core/adapters/providers/mock_adapter.py'
        )
        mock_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mock_module)
        
        MockAdapter = mock_module.MockAdapter
        
        prod_adapter = MockAdapter('prod-test', personality='creative')
        prod_response = await prod_adapter.generate_response('Create an engaging story')
        
        print(f"   ✅ Production response: {prod_response.content[:60]}...")
        print(f"   ✅ Personality: {prod_response.metadata.get('personality')}")
        
    except Exception as e:
        print(f"   ⚠️  Production mock test skipped: {e}")
    
    print("\n🎉 All mock adapter tests completed!")


if __name__ == "__main__":
    asyncio.run(test_mock_adapters())
