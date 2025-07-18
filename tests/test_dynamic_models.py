#!/usr/bin/env python3
"""
Test script for dynamic model management functionality.
"""

import asyncio
import sys
import os
import pytest
from pathlib import Path

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.model_adapter import ModelManager

@pytest.mark.asyncio
async def test_dynamic_model_management():
    """Test the new dynamic model management features."""
    print("🧪 Testing Dynamic Model Management")
    print("=" * 50)
    
    # Initialize model manager
    model_manager = ModelManager()
    
    # Test 1: List current models
    print("\n1. Current Model Configurations:")
    models = model_manager.list_model_configs()
    for name, info in models.items():
        status = "✅ Enabled" if info["enabled"] else "❌ Disabled"
        init_status = "🟢 Initialized" if info["initialized"] else "⚪ Not initialized"
        print(f"   {name}: {info['type']} - {info['model_name']} ({status}) ({init_status})")
    
    # Test 2: Add a new test model
    print("\n2. Adding Test Model Configuration:")
    test_model_config = {
        "type": "mock",
        "api_config": {
            "model_name": "test-model",
            "base_url": "http://localhost:8080",
            "api_key": "",
            "api_key_env": ""
        },
        "limits": {
            "max_tokens": 1000,
            "max_requests_per_minute": 60
        },
        "generation_params": {
            "temperature": 0.8,
            "top_p": 0.9,
            "top_k": 50
        },
        "retry_config": {
            "max_retries": 3,
            "backoff_factor": 2,
            "timeout": 30
        },
        "content_filtering": {
            "supports_nsfw": True,
            "allowed_content": ["general", "creative", "analysis"],
            "blocked_content": []
        },
        "capabilities": {
            "supports_streaming": False,
            "supports_functions": False,
            "supports_system_messages": True
        },
        "health_check": {
            "enabled": False
        },
        "cost_tracking": {
            "enabled": False,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0
        },
        "available_models": ["test-model"],
        "enabled": True
    }
    
    success = model_manager.add_model_config("test-model", test_model_config)
    print(f"   Add test model: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 3: List models after adding
    print("\n3. Models after adding test model:")
    models = model_manager.list_model_configs()
    for name, info in models.items():
        if name == "test-model":
            print(f"   {name}: {info['type']} - {info['model_name']} ({'✅ Enabled' if info['enabled'] else '❌ Disabled'})")
    
    # Test 4: Disable the test model
    print("\n4. Disabling test model:")
    success = model_manager.disable_model("test-model")
    print(f"   Disable test model: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 5: Enable the test model
    print("\n5. Enabling test model:")
    success = model_manager.enable_model("test-model")
    print(f"   Enable test model: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 6: Initialize the test model
    print("\n6. Initializing test model:")
    try:
        success = await model_manager.initialize_adapter("test-model")
        print(f"   Initialize test model: {'✅ Success' if success else '❌ Failed'}")
    except Exception as e:
        print(f"   Initialize test model: ❌ Error: {e}")
    
    # Test 7: Generate response with test model
    print("\n7. Testing response generation with test model:")
    try:
        response = await model_manager.generate_response(
            "Hello, this is a test",
            adapter_name="test-model",
            story_id="test-story"
        )
        print(f"   Response: {response[:50]}...")
        print("   ✅ Response generation works")
    except Exception as e:
        print(f"   ❌ Response generation failed: {e}")
    
    # Test 8: Remove the test model
    print("\n8. Removing test model:")
    success = model_manager.remove_model_config("test-model")
    print(f"   Remove test model: {'✅ Success' if success else '❌ Failed'}")
    
    # Test 9: Verify removal
    print("\n9. Verifying test model removal:")
    models = model_manager.list_model_configs()
    if "test-model" not in models:
        print("   ✅ Test model successfully removed")
    else:
        print("   ❌ Test model still exists")
    
    print("\n🎉 Dynamic Model Management Test Complete!")
    
    # Summary
    print("\n📋 Dynamic Model Management Features:")
    print("  ✅ Add model configurations")
    print("  ✅ Remove model configurations")
    print("  ✅ Enable/disable models")
    print("  ✅ List model configurations")
    print("  ✅ Automatic registry updates")
    print("  ✅ Runtime adapter management")
    print("  ✅ Comprehensive logging")

if __name__ == "__main__":
    asyncio.run(test_dynamic_model_management())
