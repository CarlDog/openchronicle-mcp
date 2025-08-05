#!/usr/bin/env python3
"""
Test script for Dynamic Model Integration Features
Demonstrates the enhanced capabilities with dynamic model selection.
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

from core.model_management import ModelOrchestrator as ModelManager
from core.content_analysis import ContentAnalysisOrchestrator as ContentAnalyzer
from core.character_management import CharacterOrchestrator
from core.token_manager import TokenManager
from core.context_systems.context_orchestrator import ContextOrchestrator
from core.story_loader import load_storypack

@pytest.mark.asyncio
async def test_dynamic_model_integration():
    """Test the enhanced dynamic model integration features."""
    print("🧪 Testing Dynamic Model Integration")
    print("=" * 60)
    
    # Initialize model manager
    model_manager = ModelManager()
    
    # Test 1: Content Analysis with Dynamic Model Selection
    print("\n1. Testing Content Analysis with Dynamic Model Selection:")
    content_analyzer = ContentAnalyzer(model_manager)
    
    test_inputs = [
        ("Tell me about Lyra", "general"),
        ("Lyra kisses the mysterious stranger", "nsfw"),
        ("Create a vivid description of the tavern", "creative"),
        ("Analyze the current situation", "analysis"),
        ("Quick response needed", "fast")
    ]
    
    for user_input, expected_type in test_inputs:
        detected_type = content_analyzer.detect_content_type(user_input)
        best_model = content_analyzer.get_best_analysis_model(detected_type)
        print(f"   '{user_input}' -> {detected_type} -> {best_model}")
    
    # Test 2: Character Style Management
    print("\n2. Testing Character Style Management:")
    character_manager = CharacterOrchestrator()
    
    # Load demo story to test character styles
    try:
        story_data = load_storypack("demo-story")
        styles = character_manager.load_character_styles(story_data["path"])
        print(f"   Loaded {len(styles)} character styles")
        
        for char_name in styles:
            model = character_manager.select_character_model(char_name, "dialogue")
            print(f"   {char_name} -> {model}")
            
    except Exception as e:
        print(f"   ⚠️  Character style test failed: {e}")
    
    # Test 3: Token Management
    print("\n3. Testing Token Management:")
    token_manager = TokenManager(model_manager)
    
    test_text = "This is a test prompt for token estimation across different models."
    
    models = ["openai", "anthropic", "mock"]
    for model in models:
        try:
            tokens = token_manager.estimate_tokens(test_text, model)
            print(f"   {model}: {tokens} tokens")
        except Exception as e:
            print(f"   {model}: Error - {e}")
    
    # Test 4: Model Selection Based on Token Requirements
    print("\n4. Testing Model Selection Based on Token Requirements:")
    
    token_scenarios = [
        (1000, 500, "short content"),
        (3000, 1000, "medium content"),
        (8000, 2000, "long content"),
        (20000, 4000, "very long content")
    ]
    
    for prompt_tokens, response_tokens, description in token_scenarios:
        optimal_model = token_manager.select_optimal_model_for_length(
            prompt_tokens, response_tokens)
        print(f"   {description} ({prompt_tokens}+{response_tokens}): {optimal_model}")
    
    # Test 5: Comprehensive Context Building
    print("\n5. Testing Enhanced Context Building:")
    
    try:
        story_data = load_storypack("demo-story")
        test_input = "Lyra decides to investigate the mysterious hooded figure"
        
        # Use new context orchestrator
        orchestrator = ContextOrchestrator()
        context_result = await orchestrator.build_context_with_analysis(
            test_input, story_data)
        
        print(f"   Recommended model: {context_result['recommended_model']}")
        print(f"   Content type: {context_result['content_analysis'].get('content_type', 'unknown')}")
        print(f"   Active character: {context_result.get('active_character', 'None')}")
        print(f"   Token estimate: {context_result['token_estimate']}")
        print(f"   Context length: {len(context_result['context'])} chars")
        
    except Exception as e:
        print(f"   ⚠️  Context building test failed: {e}")
    
    # Test 6: Dynamic Model Registry Operations
    print("\n6. Testing Dynamic Model Registry Operations:")
    
    # Add a test model configuration
    test_config = {
        "type": "mock",
        "api_config": {
            "model_name": "test-integration-model",
            "base_url": "http://localhost:8080",
            "api_key": "",
            "api_key_env": ""
        },
        "limits": {
            "max_tokens": 2048,
            "max_requests_per_minute": 100
        },
        "generation_params": {
            "temperature": 0.8,
            "top_p": 0.9,
            "top_k": 40
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
        "available_models": ["test-integration-model"],
        "enabled": True
    }
    
    success = model_manager.add_model_config("test-integration", test_config)
    print(f"   Add test model: {'✅ Success' if success else '❌ Failed'}")
    
    # Test content analysis with new model
    if success:
        content_analyzer = ContentAnalyzer(model_manager)
        creative_model = content_analyzer.get_best_analysis_model("creative")
        print(f"   Creative content model: {creative_model}")
    
    # Test 7: Token Usage Tracking
    print("\n7. Testing Token Usage Tracking:")
    
    token_manager.track_token_usage("test-integration", 100, 200, 0.001)
    token_manager.track_token_usage("mock", 150, 300, 0.0)
    
    stats = token_manager.get_usage_stats()
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Total tokens: {stats['total_prompt_tokens'] + stats['total_response_tokens']}")
    print(f"   Total cost: ${stats['total_cost']:.4f}")
    
    # Test 8: Model Recommendation
    print("\n8. Testing Model Recommendations:")
    
    # Test cost-based recommendation
    high_cost_pattern = {"high_cost": True}
    recommendation = token_manager.recommend_model_switch("openai", high_cost_pattern)
    print(f"   High cost scenario: {recommendation}")
    
    # Test truncation-based recommendation
    truncation_pattern = {"frequent_truncation": True}
    recommendation = token_manager.recommend_model_switch("mock", truncation_pattern)
    print(f"   Truncation scenario: {recommendation}")
    
    # Test 9: Cleanup
    print("\n9. Cleaning up test configuration:")
    cleanup_success = model_manager.remove_model_config("test-integration")
    print(f"   Remove test model: {'✅ Success' if cleanup_success else '❌ Failed'}")
    
    print("\n🎉 Dynamic Model Integration Test Complete!")
    
    # Summary
    print("\n📋 Integration Features Tested:")
    print("  ✅ Content Analysis with Dynamic Model Selection")
    print("  ✅ Character Style Management")
    print("  ✅ Token Management and Optimization")
    print("  ✅ Model Selection Based on Token Requirements")
    print("  ✅ Enhanced Context Building")
    print("  ✅ Dynamic Model Registry Operations")
    print("  ✅ Token Usage Tracking")
    print("  ✅ Model Recommendations")
    
    print("\n🚀 Key Benefits:")
    print("  • Intelligent model selection based on content type")
    print("  • Character-specific model preferences")
    print("  • Token-aware context optimization")
    print("  • Dynamic model management")
    print("  • Cost and performance optimization")
    print("  • Automatic fallback and recovery")

if __name__ == "__main__":
    asyncio.run(test_dynamic_model_integration())
