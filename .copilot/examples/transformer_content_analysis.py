#!/usr/bin/env python3
"""
Transformer Content Analysis Examples for OpenChronicle

This file demonstrates how to use the hybrid transformer + keyword content analysis 
system implemented in OpenChronicle. Shows practical examples of content classification, 
routing decisions, and confidence weighting.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.content_analysis import ContentAnalysisOrchestrator as ContentAnalyzer
from core.model_manager_compat import ModelManager


class TransformerAnalysisExamples:
    """Examples of transformer-based content analysis and routing."""
    
    def __init__(self):
        self.model_manager = None
        self.content_analyzer = None
    
    async def setup(self):
        """Initialize the model manager and content analyzer."""
        self.model_manager = ModelManager()
        await self.model_manager.initialize_adapter("mock")
        
        # Initialize with transformers enabled (will gracefully fall back if not available)
        self.content_analyzer = ContentAnalyzer(self.model_manager, use_transformers=True)
        
        print("🤖 Transformer Content Analysis Examples")
        print("=" * 60)
        print(f"Transformers Available: {self.content_analyzer.use_transformers}")
        print(f"Analysis Method: {'Hybrid (Transformer + Keyword)' if self.content_analyzer.use_transformers else 'Keyword Only'}")
        print()
    
    def analyze_content_examples(self):
        """Demonstrate content type detection with various inputs."""
        print("📝 Content Type Detection Examples")
        print("-" * 40)
        
        # Test cases covering different content types
        test_cases = [
            # Safe content
            ("Hello, what's your name?", "general/analysis"),
            ("I walk through the peaceful village.", "creative"),
            
            # Creative/Fantasy content  
            ("I cast a fireball spell at the dragon!", "creative"),
            ("The wizard's tower gleams in the moonlight.", "creative"),
            
            # Action content
            ("I draw my sword and attack the bandits!", "creative/action"),
            ("She leaps across the chasm with acrobatic grace.", "creative/action"),
            
            # Analysis/Question content
            ("What is the meaning of this ancient rune?", "analysis"),
            ("Can you explain the magic system here?", "analysis"),
            
            # Potentially sensitive content (should be handled carefully)
            ("The character seduces the tavern keeper.", "nsfw"),
            ("There's blood on the battlefield.", "nsfw/mature"),
        ]
        
        for user_input, expected_category in test_cases:
            print(f"\n📝 Input: \"{user_input}\"")
            print(f"   Expected Category: {expected_category}")
            
            # Analyze the content
            result = self.content_analyzer.detect_content_type(user_input)
            
            print(f"   Detected Type: {result['content_type']}")
            print(f"   Confidence: {result['confidence']:.3f}")
            print(f"   Flags: {', '.join(result['content_flags'])}")
            print(f"   Method: {result['analysis_method']}")
            
            # Show transformer data if available
            if 'transformer_analysis' in result:
                transformer = result['transformer_analysis']
                print(f"   NSFW Score: {transformer.get('nsfw_score', 0):.3f}")
                print(f"   Sentiment: {transformer.get('sentiment', 'unknown')}")
                emotions = transformer.get('emotions', {})
                if emotions:
                    print(f"   Emotion: {emotions.get('primary_emotion', 'unknown')} ({emotions.get('confidence', 0):.3f})")
    
    def routing_examples(self):
        """Demonstrate model routing based on content analysis."""
        print("\n🚦 Model Routing Examples")
        print("-" * 40)
        
        # Different content types that should route to different models
        routing_cases = [
            {
                "input": "Tell me about this magical forest.",
                "expected_route": "creative_models",
                "description": "Safe creative content"
            },
            {
                "input": "I need to analyze this ancient text.",
                "expected_route": "analysis_models", 
                "description": "Analysis request"
            },
            {
                "input": "Quick question - what time is it?",
                "expected_route": "fast_models",
                "description": "Simple/quick response"
            },
            {
                "input": "The scene becomes very intimate.",
                "expected_route": "nsfw_models",
                "description": "Potentially NSFW content"
            }
        ]
        
        for case in routing_cases:
            print(f"\n🎯 Scenario: {case['description']}")
            print(f"   Input: \"{case['input']}\"")
            
            # Analyze content
            analysis = self.content_analyzer.detect_content_type(case['input'])
            
            # Get routing recommendation
            recommended_model = self.content_analyzer.recommend_generation_model(analysis)
            
            print(f"   Content Type: {analysis['content_type']}")
            print(f"   Confidence: {analysis['confidence']:.3f}")
            print(f"   Recommended Model: {recommended_model}")
            print(f"   Expected Route Type: {case['expected_route']}")
    
    def confidence_weighting_examples(self):
        """Demonstrate how confidence weighting works in hybrid mode."""
        print("\n⚖️  Confidence Weighting Examples")
        print("-" * 40)
        
        if not self.content_analyzer.use_transformers:
            print("   (Transformers not available - showing keyword-only mode)")
            return
        
        print("   Hybrid mode combines:")
        print("   • 60% Transformer confidence")
        print("   • 40% Keyword-based confidence")
        print("   • False positive reduction for fantasy content")
        print()
        
        # Examples showing how transformer and keyword analysis combine
        weighting_cases = [
            "I cast a magic spell to heal the wounded knight.",
            "The battle was fierce and bloody.",
            "What does this mysterious symbol mean?",
            "She whispers sweet words of love.",
        ]
        
        for user_input in weighting_cases:
            print(f"📊 Input: \"{user_input}\"")
            
            # Get keyword-only analysis
            keyword_result = self.content_analyzer._keyword_based_detection(user_input)
            
            # Get full hybrid analysis
            hybrid_result = self.content_analyzer.detect_content_type(user_input)
            
            print(f"   Keyword Confidence: {keyword_result['confidence']:.3f}")
            if 'transformer_analysis' in hybrid_result:
                transformer_conf = hybrid_result['transformer_analysis'].get('transformer_confidence', 0)
                print(f"   Transformer Confidence: {transformer_conf:.3f}")
            print(f"   Final Hybrid Confidence: {hybrid_result['confidence']:.3f}")
            print(f"   Final Classification: {hybrid_result['content_type']}")
            print()
    
    def error_handling_examples(self):
        """Demonstrate graceful error handling and fallbacks."""
        print("\n🛡️  Error Handling & Fallback Examples")
        print("-" * 40)
        
        print("   The system gracefully handles:")
        print("   • Missing transformer dependencies")
        print("   • Model loading failures") 
        print("   • Network connectivity issues")
        print("   • Malformed input text")
        print()
        
        # Test edge cases
        edge_cases = [
            "",  # Empty input
            "   ",  # Whitespace only
            "🔥🐉⚔️",  # Emoji only
            "A" * 1000,  # Very long input
            "Special chars: @#$%^&*()",  # Special characters
        ]
        
        for test_input in edge_cases:
            display_input = test_input if len(test_input) < 50 else test_input[:47] + "..."
            print(f"🧪 Edge case: \"{display_input}\"")
            
            try:
                result = self.content_analyzer.detect_content_type(test_input)
                print(f"   ✅ Handled gracefully: {result['content_type']}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            print()
    
    async def cleanup(self):
        """Clean up resources."""
        if self.model_manager:
            await self.model_manager.shutdown()


async def main():
    """Run all transformer analysis examples."""
    examples = TransformerAnalysisExamples()
    
    try:
        await examples.setup()
        
        # Run all example categories
        examples.analyze_content_examples()
        examples.routing_examples()
        examples.confidence_weighting_examples()
        examples.error_handling_examples()
        
        print("✅ All transformer content analysis examples completed!")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
    finally:
        await examples.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
