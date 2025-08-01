"""
Content Router - Intelligent routing system for content-aware model selection.

This component implements sophisticated content analysis and routing logic
that was embedded in the original ModelManager. Now extracted as a clean,
testable component with registry-driven configuration.

Key Features:
- Content type analysis and classification
- Provider preference based on content characteristics
- Dynamic routing rules from registry configuration
- Performance-aware routing (latency, cost, quality)
- Content complexity analysis for model selection
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from datetime import datetime

from utilities.logging_system import log_info, log_error

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Content type classifications for routing."""
    NARRATIVE = "narrative"
    DIALOGUE = "dialogue"
    DESCRIPTION = "description"
    ACTION = "action"
    IMAGE_PROMPT = "image_prompt"
    SYSTEM = "system"
    ANALYSIS = "analysis"
    CREATIVE = "creative"


class ComplexityLevel(Enum):
    """Content complexity levels for model selection."""
    SIMPLE = "simple"      # Basic responses, simple prompts
    MODERATE = "moderate"  # Standard narrative, dialogue
    COMPLEX = "complex"    # Deep analysis, complex reasoning
    CREATIVE = "creative"  # High creativity, novel generation


class ContentRouter:
    """
    Intelligent content routing system with registry-driven configuration.
    
    Analyzes content characteristics and routes to optimal providers
    based on performance, quality, and cost considerations.
    """
    
    def __init__(self, registry_manager):
        self.registry_manager = registry_manager
        
        # Load routing rules from registry
        self.routing_rules = self._load_routing_rules()
        self.provider_capabilities = self._load_provider_capabilities()
        self.performance_profiles = self._load_performance_profiles()
        
        log_info("ContentRouter initialized with registry-driven configuration")
    
    def _load_routing_rules(self) -> Dict[str, Any]:
        """Load content routing rules from registry."""
        try:
            rules = self.registry_manager.get_content_routing_rules()
            return rules if rules else self._get_default_routing_rules()
        except Exception as e:
            log_error(f"Failed to load routing rules from registry: {e}")
            return self._get_default_routing_rules()
    
    def _load_provider_capabilities(self) -> Dict[str, Any]:
        """Load provider capability profiles from registry."""
        try:
            capabilities = {}
            for provider in self.registry_manager.get_available_providers():
                provider_config = self.registry_manager.get_provider_config(provider)
                if provider_config:
                    capabilities[provider] = provider_config.get('capabilities', {})
            return capabilities
        except Exception as e:
            log_error(f"Failed to load provider capabilities: {e}")
            return {}
    
    def _load_performance_profiles(self) -> Dict[str, Any]:
        """Load performance profiles from registry."""
        try:
            profiles = {}
            for provider in self.registry_manager.get_available_providers():
                performance_limits = self.registry_manager.get_performance_limits(provider)
                if performance_limits:
                    profiles[provider] = performance_limits
            return profiles
        except Exception as e:
            log_error(f"Failed to load performance profiles: {e}")
            return {}
    
    def _get_default_routing_rules(self) -> Dict[str, Any]:
        """Default routing rules as fallback."""
        return {
            ContentType.NARRATIVE.value: ["openai", "anthropic", "ollama"],
            ContentType.DIALOGUE.value: ["anthropic", "openai", "ollama"],
            ContentType.DESCRIPTION.value: ["openai", "ollama", "anthropic"],
            ContentType.ACTION.value: ["openai", "ollama", "anthropic"],
            ContentType.IMAGE_PROMPT.value: ["dalle", "stabilityai", "midjourney"],
            ContentType.SYSTEM.value: ["openai", "anthropic"],
            ContentType.ANALYSIS.value: ["anthropic", "openai"],
            ContentType.CREATIVE.value: ["anthropic", "openai", "ollama"]
        }
    
    def analyze_content_type(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ContentType:
        """
        Analyze prompt to determine content type.
        
        Args:
            prompt: Input prompt to analyze
            context: Additional context for classification
            
        Returns:
            ContentType: Classified content type
        """
        prompt_lower = prompt.lower()
        
        # Image generation indicators
        image_keywords = ["generate image", "create picture", "draw", "visualize", "image of", "picture of"]
        if any(keyword in prompt_lower for keyword in image_keywords):
            return ContentType.IMAGE_PROMPT
        
        # Dialogue indicators
        dialogue_keywords = ["dialogue", "conversation", "says", "replies", "speaks", '"']
        if any(keyword in prompt_lower for keyword in dialogue_keywords) or '"' in prompt:
            return ContentType.DIALOGUE
        
        # Action scene indicators
        action_keywords = ["action", "fight", "battle", "chase", "runs", "attacks", "combat"]
        if any(keyword in prompt_lower for keyword in action_keywords):
            return ContentType.ACTION
        
        # Analysis indicators
        analysis_keywords = ["analyze", "evaluate", "assess", "examine", "review", "explain why"]
        if any(keyword in prompt_lower for keyword in analysis_keywords):
            return ContentType.ANALYSIS
        
        # System/meta indicators
        system_keywords = ["system", "configuration", "settings", "initialize", "setup"]
        if any(keyword in prompt_lower for keyword in system_keywords):
            return ContentType.SYSTEM
        
        # Creative writing indicators
        creative_keywords = ["creative", "innovative", "unique", "original", "imaginative"]
        if any(keyword in prompt_lower for keyword in creative_keywords):
            return ContentType.CREATIVE
        
        # Description indicators (detailed scene setting)
        description_keywords = ["describe", "setting", "environment", "appearance", "looks like"]
        if any(keyword in prompt_lower for keyword in description_keywords):
            return ContentType.DESCRIPTION
        
        # Default to narrative for story content
        return ContentType.NARRATIVE
    
    def analyze_complexity(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> ComplexityLevel:
        """
        Analyze content complexity to inform model selection.
        
        Args:
            prompt: Input prompt to analyze
            context: Additional context for complexity assessment
            
        Returns:
            ComplexityLevel: Assessed complexity level
        """
        prompt_lower = prompt.lower()
        
        # Simple indicators
        if len(prompt) < 50:
            return ComplexityLevel.SIMPLE
        
        # Complex reasoning indicators
        complex_keywords = [
            "analyze the relationship between", "complex reasoning", "multi-step",
            "intricate", "sophisticated", "nuanced", "philosophical", 
            "psychological depth", "multiple perspectives"
        ]
        if any(keyword in prompt_lower for keyword in complex_keywords):
            return ComplexityLevel.COMPLEX
        
        # Creative indicators
        creative_keywords = [
            "creative", "innovative", "original", "unique perspective",
            "imaginative", "artistic", "poetic", "metaphorical"
        ]
        if any(keyword in prompt_lower for keyword in creative_keywords):
            return ComplexityLevel.CREATIVE
        
        # Moderate complexity for standard narrative content
        if len(prompt) > 200 or "detailed" in prompt_lower:
            return ComplexityLevel.MODERATE
        
        return ComplexityLevel.SIMPLE
    
    def get_optimal_providers(self, content_type: ContentType, complexity: ComplexityLevel,
                            performance_priority: str = "quality") -> List[str]:
        """
        Get optimal provider list based on content analysis and performance priority.
        
        Args:
            content_type: Classified content type
            complexity: Assessed complexity level
            performance_priority: Priority factor ("quality", "speed", "cost")
            
        Returns:
            List of provider names in preference order
        """
        # Get base providers for content type
        base_providers = self.routing_rules.get(content_type.value, ["openai", "anthropic"])
        
        # Filter based on complexity requirements
        filtered_providers = self._filter_by_complexity(base_providers, complexity)
        
        # Sort based on performance priority
        sorted_providers = self._sort_by_performance_priority(filtered_providers, performance_priority)
        
        log_info(f"Selected providers for {content_type.value}/{complexity.value}: {sorted_providers}")
        return sorted_providers
    
    def _filter_by_complexity(self, providers: List[str], complexity: ComplexityLevel) -> List[str]:
        """Filter providers based on complexity handling capabilities."""
        if complexity == ComplexityLevel.SIMPLE:
            # Any provider can handle simple content
            return providers
        
        elif complexity == ComplexityLevel.COMPLEX:
            # Prefer providers known for reasoning capabilities
            complex_capable = ["anthropic", "openai", "gpt-4"]
            return [p for p in providers if any(cap in p for cap in complex_capable)] or providers
        
        elif complexity == ComplexityLevel.CREATIVE:
            # Prefer providers known for creativity
            creative_capable = ["anthropic", "openai", "claude"]
            return [p for p in providers if any(cap in p for cap in creative_capable)] or providers
        
        return providers
    
    def _sort_by_performance_priority(self, providers: List[str], priority: str) -> List[str]:
        """Sort providers based on performance priority."""
        if priority == "speed":
            # Sort by latency (lower is better)
            return sorted(providers, key=lambda p: self._get_latency_score(p))
        
        elif priority == "cost":
            # Sort by cost (lower is better)
            return sorted(providers, key=lambda p: self._get_cost_score(p))
        
        else:  # quality priority (default)
            # Sort by quality score (higher is better)
            return sorted(providers, key=lambda p: self._get_quality_score(p), reverse=True)
    
    def _get_latency_score(self, provider: str) -> float:
        """Get latency score for provider (lower is better)."""
        performance = self.performance_profiles.get(provider, {})
        # Use timeout as proxy for expected latency
        return performance.get("timeout", 30.0)
    
    def _get_cost_score(self, provider: str) -> float:
        """Get cost score for provider (lower is better)."""
        # Simple cost scoring - could be enhanced with actual pricing data
        cost_rankings = {
            "ollama": 0.0,      # Local, no API costs
            "openai": 2.0,      # Moderate cost
            "anthropic": 2.5,   # Slightly higher cost
            "dalle": 5.0,       # Higher cost for image generation
            "stabilityai": 3.0  # Moderate image cost
        }
        return cost_rankings.get(provider, 1.0)
    
    def _get_quality_score(self, provider: str) -> float:
        """Get quality score for provider (higher is better)."""
        # Quality scoring based on general capabilities
        quality_rankings = {
            "anthropic": 9.5,   # High quality reasoning
            "openai": 9.0,      # High quality general
            "gpt-4": 9.5,       # Highest quality OpenAI
            "ollama": 7.0,      # Good local quality
            "dalle": 8.5,       # High image quality
            "stabilityai": 8.0  # Good image quality
        }
        return quality_rankings.get(provider, 6.0)
    
    def route_content(self, prompt: str, context: Optional[Dict[str, Any]] = None,
                     performance_priority: str = "quality") -> Tuple[List[str], Dict[str, Any]]:
        """
        Main routing method - analyze content and return optimal providers.
        
        Args:
            prompt: Input prompt to route
            context: Additional context for routing decisions
            performance_priority: Performance priority factor
            
        Returns:
            Tuple of (provider_list, routing_metadata)
        """
        # Analyze content characteristics
        content_type = self.analyze_content_type(prompt, context)
        complexity = self.analyze_complexity(prompt, context)
        
        # Get optimal providers
        providers = self.get_optimal_providers(content_type, complexity, performance_priority)
        
        # Build routing metadata
        metadata = {
            "content_type": content_type.value,
            "complexity": complexity.value,
            "performance_priority": performance_priority,
            "prompt_length": len(prompt),
            "routing_timestamp": datetime.now().isoformat()
        }
        
        log_info(f"Routed content to providers: {providers} (type: {content_type.value}, complexity: {complexity.value})")
        
        return providers, metadata
