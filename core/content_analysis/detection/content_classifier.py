"""
Content classification component that combines keyword and transformer analysis.

Date: August 4, 2025
Purpose: Main content classification and type detection
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 579-759)
"""

from typing import Dict, List, Any

from ..shared.interfaces import DetectionComponent
from .keyword_detector import KeywordDetector
from .transformer_analyzer import TransformerAnalyzer

# Import logging utilities
from core.shared.logging_system import log_system_event, log_error

class ContentClassifier(DetectionComponent):
    """Main content classification combining keyword and transformer approaches."""
    
    def __init__(self, model_manager, use_transformers: bool = True):
        super().__init__(model_manager)
        
        # Initialize sub-components
        self.keyword_detector = KeywordDetector(model_manager)
        self.transformer_analyzer = TransformerAnalyzer(model_manager, use_transformers)
    
    def detect_content_type(self, content: str) -> Dict[str, Any]:
        """Detect content type using hybrid keyword + transformer approach."""
        # Start with keyword-based analysis
        keyword_analysis = self.keyword_detector.detect_content_type(content)
        
        # Add transformer-based analysis if available
        try:
            transformer_analysis = self.transformer_analyzer.detect_content_type(content)
        except Exception as e:
            log_error(f"Transformer analysis failed in detect_content_type: {e}")
            transformer_analysis = {}
        
        # Combine both approaches for enhanced accuracy
        combined_analysis = self._combine_analysis_results(keyword_analysis, transformer_analysis, content)
        
        return combined_analysis
    
    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process content and return classification results."""
        return self.detect_content_type(content)
    
    def _combine_analysis_results(self, keyword_analysis: Dict[str, Any], transformer_analysis: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Combine keyword and transformer analysis for enhanced accuracy."""
        combined = keyword_analysis.copy()
        
        # If no transformer analysis available, return keyword-only results
        if not transformer_analysis:
            combined["analysis_method"] = "keyword_only"
            return combined
        
        # Extract transformer results
        sentiment = transformer_analysis.get("sentiment", "neutral")
        emotions = transformer_analysis.get("emotions", {})
        
        # NSFW detection enhancement using transformer scores
        nsfw_score = transformer_analysis.get("nsfw_score", 0.0)
        
        # High confidence toxic content detection override
        if nsfw_score > 0.8:
            # Strong transformer signal for toxic content
            if combined["content_type"] != "nsfw":
                combined["content_type"] = "nsfw"
                combined["content_flags"].append("toxic_detected")
            combined["confidence"] = max(combined["confidence"], nsfw_score)
        elif nsfw_score > 0.6 and combined["content_type"] == "nsfw":
            # Reinforce existing NSFW classification
            combined["confidence"] = (combined["confidence"] + nsfw_score) / 2
        
        # Add transformer-derived metadata
        combined["sentiment"] = sentiment
        combined["emotions"] = emotions
        
        combined["sentiment"] = sentiment
        combined["emotions"] = emotions
        
        # Sentiment-based content flags
        if sentiment in ["negative", "NEGATIVE"]:
            combined["content_flags"].append("negative_sentiment")
        elif sentiment in ["positive", "POSITIVE"]:
            combined["content_flags"].append("positive_sentiment")
        
        # Emotion-based content flags
        primary_emotion = emotions.get("primary_emotion", "").lower()
        if primary_emotion in ["anger", "fear", "sadness"]:
            combined["content_flags"].append("negative_emotion")
        elif primary_emotion in ["joy", "surprise"]:
            combined["content_flags"].append("positive_emotion")
        elif primary_emotion in ["sadness"]:
            combined["content_flags"].append("melancholy")
        
        # Weighted confidence combining
        transformer_confidence = transformer_analysis.get("transformer_confidence", 0.0)
        if transformer_confidence > 0.5:
            # Weight transformer confidence higher if it's reliable
            combined["confidence"] = (transformer_confidence * 0.6) + (combined["confidence"] * 0.4)
        
        # Store full transformer analysis for debugging/advanced features
        combined["transformer_analysis"] = transformer_analysis
        combined["analysis_method"] = "hybrid"
        
        log_system_event("content_classification_complete",
                        f"Final: {combined['content_type']} (confidence: {combined['confidence']:.3f}), "
                        f"Flags: {combined['content_flags']}, Method: {combined['analysis_method']}")
        
        return combined
    
    def check_transformer_connectivity(self) -> Dict[str, Any]:
        """Check transformer connectivity status."""
        return self.transformer_analyzer.check_transformer_connectivity()
    
    def get_analysis_capabilities(self) -> Dict[str, Any]:
        """Get information about available analysis capabilities."""
        keyword_caps = {
            "available": True,
            "features": [
                "NSFW detection (explicit/suggestive/mature)",
                "Creative content detection",
                "Analysis content detection", 
                "Action content detection",
                "Dialogue detection",
                "Simple response detection"
            ]
        }
        
        transformer_caps = {
            "available": self.transformer_analyzer.use_transformers,
            "features": []
        }
        
        if self.transformer_analyzer.use_transformers:
            if self.transformer_analyzer.nsfw_classifier:
                transformer_caps["features"].append("Advanced toxic content detection")
            if self.transformer_analyzer.sentiment_classifier:
                transformer_caps["features"].append("Sentiment analysis")
            if self.transformer_analyzer.emotion_classifier:
                transformer_caps["features"].append("Emotion detection")
        
        return {
            "keyword_analysis": keyword_caps,
            "transformer_analysis": transformer_caps,
            "hybrid_mode": transformer_caps["available"],
            "total_features": len(keyword_caps["features"]) + len(transformer_caps["features"])
        }
