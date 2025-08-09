"""
Keyword-based content detection and analysis component.

Date: August 4, 2025
Purpose: Keyword-based content analysis for content classification
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 596-676, 1606-1624)
"""

from typing import Dict, List, Any
from ..shared.interfaces import DetectionComponent

class KeywordDetector(DetectionComponent):
    """Keyword-based content detection and classification."""
    
    def __init__(self, model_manager):
        super().__init__(model_manager)
        self._initialize_keywords()
    
    def _initialize_keywords(self):
        """Initialize keyword patterns and categories."""
        
        # Enhanced NSFW content detection with severity levels
        self.nsfw_explicit = ["explicit", "sexual", "adult", "erotic", "nude", "naked", "sex"]
        self.nsfw_suggestive = ["intimate", "romantic", "kiss", "embrace", "seductive", "passionate", "desire", "love"]
        self.nsfw_mature = ["violence", "blood", "death", "kill", "murder", "torture", "gore"]
        
        # Creative content detection
        self.creative_keywords = [
            "imagine", "create", "describe", "story", "scene", "character",
            "dialogue", "narrative", "plot", "setting", "atmosphere", "cast", "spell",
            "explore", "magical", "magic", "fantasy", "wizard", "dragon", "forest", "adventure"
        ]
        
        # Analysis content detection
        self.analysis_keywords = [
            "analyze", "classify", "determine", "evaluate", "assess",
            "summarize", "explain", "interpret", "understand", "what", "why", "how"
        ]
        
        # Action content detection
        self.action_keywords = [
            "attack", "fight", "battle", "sword", "weapon", "combat", "hit", "strike",
            "run", "jump", "climb", "move", "go", "walk", "enter", "exit"
        ]
    
    def detect_content_type(self, user_input: str) -> Dict[str, Any]:
        """Main public API for content detection using keywords."""
        return self._keyword_based_detection(user_input)
    
    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process content and return keyword-based analysis results."""
        return self.detect_content_type(content)
    
    def _keyword_based_detection(self, user_input: str) -> Dict[str, Any]:
        """Core keyword-based content detection logic."""
        text_lower = user_input.lower()
        content_flags = []
        content_type = "general"
        confidence = 0.0
        
        # Enhanced NSFW content detection with severity levels
        explicit_matches = sum(1 for keyword in self.nsfw_explicit if keyword in text_lower)
        suggestive_matches = sum(1 for keyword in self.nsfw_suggestive if keyword in text_lower)
        mature_matches = sum(1 for keyword in self.nsfw_mature if keyword in text_lower)
        
        if explicit_matches > 0:
            content_type = "nsfw"
            content_flags.append("explicit")
            confidence = min(0.9, 0.7 + (explicit_matches * 0.1))
        elif suggestive_matches > 1:
            content_type = "nsfw"
            content_flags.append("suggestive")
            confidence = min(0.8, 0.5 + (suggestive_matches * 0.1))
        elif mature_matches > 0:
            content_type = "nsfw"
            content_flags.append("mature")
            confidence = min(0.7, 0.4 + (mature_matches * 0.1))
            
        # Creative content detection
        creative_matches = sum(1 for keyword in self.creative_keywords if keyword in text_lower)
        if creative_matches > 0 and content_type == "general":
            content_type = "creative"
            content_flags.append("creative")
            confidence = min(0.8, 0.4 + (creative_matches * 0.1))
            
        # Analysis content detection
        analysis_matches = sum(1 for keyword in self.analysis_keywords if keyword in text_lower)
        if analysis_matches > 0 and content_type == "general":
            content_type = "analysis"
            content_flags.append("analysis")
            confidence = min(0.7, 0.3 + (analysis_matches * 0.1))
        
        # Action content detection
        action_matches = sum(1 for keyword in self.action_keywords if keyword in text_lower)
        if action_matches > 0:
            content_flags.append("action")
            
        # Dialogue content detection
        if any(marker in user_input for marker in ['"', "'", "say", "tell", "ask", "whisper", "shout"]):
            content_flags.append("dialogue")
            
        # Simple/quick response detection
        if len(user_input.split()) < 5:
            content_flags.append("simple")
            
        return {
            "content_type": content_type,
            "content_flags": content_flags,
            "confidence": confidence,
            "raw_text": user_input,
            "word_count": len(user_input.split()),
            "analysis_method": "keyword"
        }
    
    def _basic_content_analysis(self, content: str) -> Dict[str, Any]:
        """Basic content analysis using patterns and heuristics."""
        words = content.split()
        lines = content.split('\n')
        
        # Look for simple patterns
        has_dialogue = any(line.strip().startswith('"') or line.strip().startswith("'") for line in lines)
        has_headers = any(line.strip().startswith('#') for line in lines)
        has_markdown = '**' in content or '*' in content or '[' in content
        
        return {
            "word_count": len(words),
            "line_count": len(lines),
            "has_dialogue": has_dialogue,
            "has_headers": has_headers,
            "has_markdown": has_markdown,
            "estimated_category": "narrative" if has_dialogue else "description"
        }
