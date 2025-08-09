"""
OpenChronicle Core - Response Context Analyzer

Analyzes context data to understand quality, complexity needs, and content type.
Extracted from IntelligentResponseEngine for modular architecture.

Author: OpenChronicle Development Team
"""

import json
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from ..shared import NarrativeComponent, ValidationResult
from .response_models import ContextAnalysis, ContextQuality, ResponseComplexity


class ContextAnalyzer(NarrativeComponent):
    """
    Analyzes context data to determine quality and complexity needs.
    
    Responsible for:
    - Assessing context data quality
    - Identifying key narrative elements  
    - Determining appropriate response complexity
    - Providing context-based recommendations
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("ContextAnalyzer", config)
        
        # Analysis thresholds
        self.quality_thresholds = config.get("quality_thresholds", {
            "excellent": 0.9,
            "good": 0.7,
            "fair": 0.5,
            "poor": 0.3
        }) if config else {
            "excellent": 0.9,
            "good": 0.7, 
            "fair": 0.5,
            "poor": 0.3
        }
        
        # Content type patterns
        self.content_patterns = config.get("content_patterns", {
            "dialogue": ["said", "asked", "replied", "whispered", "shouted"],
            "action": ["moved", "ran", "jumped", "attacked", "defended"],
            "description": ["looked", "appeared", "seemed", "was", "were"],
            "emotion": ["felt", "angry", "happy", "sad", "excited", "worried"],
            "narrative": ["meanwhile", "later", "suddenly", "then", "however"]
        }) if config else {
            "dialogue": ["said", "asked", "replied", "whispered", "shouted"],
            "action": ["moved", "ran", "jumped", "attacked", "defended"],
            "description": ["looked", "appeared", "seemed", "was", "were"],
            "emotion": ["felt", "angry", "happy", "sad", "excited", "worried"],
            "narrative": ["meanwhile", "later", "suddenly", "then", "however"]
        }
    
    def process(self, data: Dict[str, Any]) -> ContextAnalysis:
        """Analyze context data and return analysis results."""
        try:
            context_data = data.get("context", {})
            
            # Assess context quality
            quality = self._assess_context_quality(context_data)
            
            # Determine complexity needs
            complexity = self._determine_complexity_needs(context_data)
            
            # Identify content type
            content_type = self._identify_content_type(context_data)
            
            # Extract context components
            character_context = self._extract_character_context(context_data)
            narrative_context = self._extract_narrative_context(context_data)
            emotional_context = self._extract_emotional_context(context_data)
            
            # Analyze key elements
            key_elements = self._identify_key_elements(context_data)
            missing_elements = self._identify_missing_elements(context_data)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                quality, complexity, key_elements, missing_elements
            )
            
            # Calculate confidence
            confidence = self._calculate_analysis_confidence(context_data, quality)
            
            return ContextAnalysis(
                quality=quality,
                complexity_needs=complexity,
                content_type=content_type,
                character_context=character_context,
                narrative_context=narrative_context,
                emotional_context=emotional_context,
                confidence=confidence,
                key_elements=key_elements,
                missing_elements=missing_elements,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ContextAnalysis(
                quality=ContextQuality.POOR,
                complexity_needs=ResponseComplexity.SIMPLE,
                content_type="unknown",
                confidence=0.0,
                recommendations=[f"Analysis error: {str(e)}"]
            )
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate context data for analysis."""
        required_fields = ["context"]
        return self._validate_required_fields(data, required_fields)
    
    def _assess_context_quality(self, context_data: Dict[str, Any]) -> ContextQuality:
        """Assess the quality of context data."""
        score = 0.0
        max_score = 0.0
        
        # Check for various context elements
        quality_indicators = [
            ("user_input", 0.3),           # User input present
            ("story_state", 0.2),          # Story state available
            ("character_states", 0.2),     # Character information
            ("narrative_history", 0.15),   # Previous narrative
            ("scene_context", 0.15)        # Scene information
        ]
        
        for field, weight in quality_indicators:
            max_score += weight
            if field in context_data and context_data[field]:
                if isinstance(context_data[field], (dict, list)):
                    if len(context_data[field]) > 0:
                        score += weight
                elif isinstance(context_data[field], str):
                    if len(context_data[field].strip()) > 0:
                        score += weight
                else:
                    score += weight
        
        # Calculate percentage
        quality_percentage = score / max_score if max_score > 0 else 0.0
        
        # Map to quality enum
        if quality_percentage >= self.quality_thresholds["excellent"]:
            return ContextQuality.EXCELLENT
        elif quality_percentage >= self.quality_thresholds["good"]:
            return ContextQuality.GOOD
        elif quality_percentage >= self.quality_thresholds["fair"]:
            return ContextQuality.FAIR
        elif quality_percentage >= self.quality_thresholds["poor"]:
            return ContextQuality.POOR
        else:
            return ContextQuality.MINIMAL
    
    def _determine_complexity_needs(self, context_data: Dict[str, Any]) -> ResponseComplexity:
        """Determine appropriate response complexity based on context."""
        complexity_score = 0
        
        # Check complexity indicators
        user_input = context_data.get("user_input", "")
        
        # Input length indicator
        if len(user_input) > 200:
            complexity_score += 2
        elif len(user_input) > 100:
            complexity_score += 1
        
        # Multiple characters
        character_states = context_data.get("character_states", {})
        if len(character_states) > 3:
            complexity_score += 2
        elif len(character_states) > 1:
            complexity_score += 1
        
        # Rich narrative history
        narrative_history = context_data.get("narrative_history", [])
        if len(narrative_history) > 10:
            complexity_score += 2
        elif len(narrative_history) > 5:
            complexity_score += 1
        
        # Complex scene context
        scene_context = context_data.get("scene_context", {})
        if len(scene_context) > 5:
            complexity_score += 1
        
        # Map score to complexity
        if complexity_score >= 6:
            return ResponseComplexity.ELABORATE
        elif complexity_score >= 4:
            return ResponseComplexity.COMPLEX
        elif complexity_score >= 2:
            return ResponseComplexity.MODERATE
        else:
            return ResponseComplexity.SIMPLE
    
    def _identify_content_type(self, context_data: Dict[str, Any]) -> str:
        """Identify the primary content type from context."""
        user_input = context_data.get("user_input", "").lower()
        
        # Count pattern matches for each content type
        type_scores = {}
        for content_type, patterns in self.content_patterns.items():
            score = sum(1 for pattern in patterns if pattern in user_input)
            if score > 0:
                type_scores[content_type] = score
        
        # Return type with highest score, or "general" if none found
        if type_scores:
            return max(type_scores.items(), key=lambda x: x[1])[0]
        else:
            return "general"
    
    def _extract_character_context(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract character-related context."""
        character_context = {}
        
        # Get character states
        character_states = context_data.get("character_states", {})
        if character_states:
            character_context["active_characters"] = list(character_states.keys())
            character_context["character_count"] = len(character_states)
            character_context["character_details"] = character_states
        
        # Extract character mentions from user input
        user_input = context_data.get("user_input", "")
        character_mentions = []
        for char_name in character_states.keys():
            if char_name.lower() in user_input.lower():
                character_mentions.append(char_name)
        character_context["mentioned_characters"] = character_mentions
        
        return character_context
    
    def _extract_narrative_context(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract narrative-related context."""
        narrative_context = {}
        
        # Story state information
        story_state = context_data.get("story_state", {})
        if story_state:
            narrative_context["story_state"] = story_state
        
        # Narrative history
        narrative_history = context_data.get("narrative_history", [])
        if narrative_history:
            narrative_context["history_length"] = len(narrative_history)
            narrative_context["recent_events"] = narrative_history[-3:] if len(narrative_history) >= 3 else narrative_history
        
        # Scene context
        scene_context = context_data.get("scene_context", {})
        if scene_context:
            narrative_context["scene_info"] = scene_context
        
        return narrative_context
    
    def _extract_emotional_context(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract emotional context from data."""
        emotional_context = {}
        
        user_input = context_data.get("user_input", "")
        
        # Simple emotional indicators
        emotional_indicators = {
            "positive": ["happy", "joy", "excited", "love", "wonderful", "great"],
            "negative": ["sad", "angry", "hate", "terrible", "awful", "horrible"],
            "neutral": ["okay", "fine", "normal", "usual", "regular"]
        }
        
        emotion_scores = {}
        for emotion_type, indicators in emotional_indicators.items():
            score = sum(1 for indicator in indicators if indicator in user_input.lower())
            if score > 0:
                emotion_scores[emotion_type] = score
        
        if emotion_scores:
            emotional_context["detected_emotions"] = emotion_scores
            emotional_context["primary_emotion"] = max(emotion_scores.items(), key=lambda x: x[1])[0]
        
        return emotional_context
    
    def _identify_key_elements(self, context_data: Dict[str, Any]) -> List[str]:
        """Identify key elements in the context."""
        key_elements = []
        
        # Check for important context components
        if context_data.get("user_input"):
            key_elements.append("user_input_provided")
        
        if context_data.get("character_states"):
            key_elements.append("character_information_available")
        
        if context_data.get("narrative_history"):
            key_elements.append("narrative_history_present")
        
        if context_data.get("scene_context"):
            key_elements.append("scene_context_available")
        
        if context_data.get("story_state"):
            key_elements.append("story_state_tracked")
        
        return key_elements
    
    def _identify_missing_elements(self, context_data: Dict[str, Any]) -> List[str]:
        """Identify missing important elements."""
        missing_elements = []
        
        # Check for missing important context
        if not context_data.get("user_input"):
            missing_elements.append("user_input_missing")
        
        if not context_data.get("character_states"):
            missing_elements.append("character_information_missing")
        
        if not context_data.get("story_state"):
            missing_elements.append("story_state_missing")
        
        return missing_elements
    
    def _generate_recommendations(self, quality: ContextQuality, complexity: ResponseComplexity,
                                key_elements: List[str], missing_elements: List[str]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Quality-based recommendations
        if quality == ContextQuality.POOR or quality == ContextQuality.MINIMAL:
            recommendations.append("Consider gathering more context before response generation")
        
        if quality == ContextQuality.EXCELLENT:
            recommendations.append("Rich context available - can generate detailed response")
        
        # Missing element recommendations
        if "character_information_missing" in missing_elements:
            recommendations.append("Character context would improve response relevance")
        
        if "story_state_missing" in missing_elements:
            recommendations.append("Story state information would enhance narrative coherence")
        
        # Complexity recommendations
        if complexity == ResponseComplexity.ELABORATE:
            recommendations.append("Context supports complex, multi-faceted response")
        elif complexity == ResponseComplexity.SIMPLE:
            recommendations.append("Simple, focused response recommended")
        
        return recommendations
    
    def _calculate_analysis_confidence(self, context_data: Dict[str, Any], 
                                     quality: ContextQuality) -> float:
        """Calculate confidence in the analysis."""
        base_confidence = {
            ContextQuality.EXCELLENT: 0.95,
            ContextQuality.GOOD: 0.85,
            ContextQuality.FAIR: 0.70,
            ContextQuality.POOR: 0.45,
            ContextQuality.MINIMAL: 0.25
        }
        
        confidence = base_confidence.get(quality, 0.5)
        
        # Adjust based on data completeness
        data_fields = len([k for k, v in context_data.items() if v])
        if data_fields >= 5:
            confidence += 0.05
        elif data_fields <= 2:
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _validate_required_fields(self, data: Dict[str, Any], 
                                required_fields: List[str]) -> ValidationResult:
        """Validate required fields are present."""
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                validation_type="required_fields",
                issues=[f"Missing required field: {field}" for field in missing_fields]
            )
        
        return ValidationResult(
            is_valid=True,
            confidence=1.0,
            validation_type="required_fields"
        )
