"""
Transformer-based content analysis component with SSL/network error handling.

Date: August 4, 2025
Purpose: ML-based content analysis using transformers with graceful fallbacks
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 64-207, 494-578)
"""

import warnings
import sys
from io import StringIO
from typing import Dict, List, Any, Optional

from ..shared.interfaces import DetectionComponent

# Import logging utilities
from utilities.logging_system import log_model_interaction, log_system_event, log_info, log_error, log_warning

# Optional transformer imports with graceful fallback
try:
    import warnings
    # Suppress specific transformers warnings about unused weights and deprecations
    warnings.filterwarnings("ignore", message="Some weights of.*were not used when initializing.*")
    warnings.filterwarnings("ignore", message=".*This IS expected if you are initializing.*")
    warnings.filterwarnings("ignore", message=".*This IS NOT expected if you are initializing.*")
    warnings.filterwarnings("ignore", message=".*return_all_scores.*is now deprecated.*")
    
    # Set transformers library logging to ERROR level to suppress console output
    import logging
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
    logging.getLogger("transformers.configuration_utils").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
    
    # Import with fallback for different transformers versions
    try:
        from transformers.pipelines import pipeline
    except ImportError:
        from transformers import pipeline  # type: ignore
    
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
    log_info("Transformers library loaded - advanced classification enabled")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    log_warning("Transformers library not available - using keyword-based classification only")

class TransformerAnalyzer(DetectionComponent):
    """ML-based content analysis using transformers with SSL/network error handling."""
    
    def __init__(self, model_manager, use_transformers: bool = True):
        super().__init__(model_manager)
        self.use_transformers = use_transformers and TRANSFORMERS_AVAILABLE
        
        # Initialize transformer models
        self.nsfw_classifier = None
        self.sentiment_classifier = None
        self.emotion_classifier = None
        
        if self.use_transformers:
            self._initialize_transformers()
    
    def detect_content_type(self, content: str) -> Dict[str, Any]:
        """Detect content type using transformer analysis."""
        return self._analyze_with_transformers(content)
    
    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process content and return transformer-based analysis results."""
        return self.detect_content_type(content)
    
    def _initialize_transformers(self):
        """Initialize transformer-based classifiers with SSL/network error handling."""
        try:
            log_info("Initializing transformer-based content classifiers...")
            
            # Suppress all warnings and output during model loading
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # Temporarily redirect stdout and stderr to suppress console output
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = StringIO()
                sys.stderr = StringIO()
                
                try:
                    device = 0 if torch.cuda.is_available() else -1
                    
                    # Enhanced model loading with SSL/Network error handling
                    def load_model_safely(task: str, model_name: str, description: str) -> Any:
                        """Load transformer model with SSL/network error handling."""
                        try:
                            log_info(f"Loading {description} model: {model_name}")
                            return pipeline(  # type: ignore
                                task,
                                model=model_name,
                                device=device,
                                truncation=True,
                                max_length=512,
                                top_k=1  # Only return top prediction
                            )
                        except Exception as model_error:
                            error_msg = str(model_error).lower()
                            if any(ssl_term in error_msg for ssl_term in ['ssl', 'certificate', 'handshake', 'network']):
                                log_warning(f"SSL/Network error loading {description} model '{model_name}': {model_error}")
                                log_warning(f"Enterprise firewall may be blocking access to huggingface.co")
                            else:
                                log_error(f"Error loading {description} model '{model_name}': {model_error}")
                            return None
                    
                    # NSFW Content Detection  
                    # Using a general text classification model fine-tuned for content safety
                    self.nsfw_classifier = load_model_safely(
                        "text-classification",
                        "unitary/toxic-bert",
                        "NSFW content detection"
                    )
                    
                    # Sentiment Analysis
                    self.sentiment_classifier = load_model_safely(
                        "sentiment-analysis", 
                        "cardiffnlp/twitter-roberta-base-sentiment-latest",
                        "sentiment analysis"
                    )
                    
                    # Emotion Detection
                    self.emotion_classifier = load_model_safely(
                        "text-classification",
                        "j-hartmann/emotion-english-distilroberta-base", 
                        "emotion detection"
                    )
                    
                    # Check if any models loaded successfully
                    models_loaded = sum(1 for model in [self.nsfw_classifier, self.sentiment_classifier, self.emotion_classifier] if model is not None)
                    if models_loaded == 0:
                        log_warning("No transformer models could be loaded - falling back to keyword-based analysis")
                        self.use_transformers = False
                    else:
                        log_info(f"Successfully loaded {models_loaded}/3 transformer models")
                        if models_loaded < 3:
                            log_info("Partial transformer functionality available - some analysis will use keyword fallbacks")
                    
                finally:
                    # Restore stdout and stderr
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
            
            log_info("Transformer classifiers initialized successfully")
            
        except Exception as e:
            # Enhanced error handling for Issue #4: SSL/Network Connectivity
            error_msg = str(e).lower()
            
            if any(ssl_error in error_msg for ssl_error in ['ssl', 'certificate', 'handshake', 'network', 'connection']):
                log_warning(f"Network/SSL issue detected while downloading transformer models: {e}")
                log_warning("This is likely due to enterprise firewall/proxy settings blocking external AI model downloads")
                log_warning("Falling back to keyword-based content analysis (transformers disabled)")
                log_system_event("ssl_fallback_triggered", 
                               f"SSL/Network error triggered transformer fallback: {type(e).__name__}")
            else:
                log_error(f"Failed to initialize transformer classifiers: {e}")
                log_system_event("transformer_init_error", 
                               f"Transformer initialization failed: {type(e).__name__}")
            
            # Graceful degradation: disable transformers and use keyword-based fallbacks
            self.use_transformers = False
            self.nsfw_classifier = None
            self.sentiment_classifier = None
            self.emotion_classifier = None
            
            # Log fallback strategy for user awareness
            log_info("Content analysis will use keyword-based classification methods")
            log_info("For full transformer support, ensure network access to huggingface.co or use local models")
    
    def _analyze_with_transformers(self, user_input: str) -> Dict[str, Any]:
        """Use transformer models for advanced content analysis."""
        if not self.use_transformers:
            return {}
            
        analysis = {
            "transformer_results": {},
            "nsfw_score": 0.0,
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "emotions": {},
            "transformer_confidence": 0.0
        }
        
        try:
            # NSFW/Toxic Content Detection
            if self.nsfw_classifier:
                nsfw_result = self.nsfw_classifier(user_input)
                # Handle nested list format: [[{...}]] -> {...}
                if isinstance(nsfw_result, list) and len(nsfw_result) > 0:
                    nsfw_result = nsfw_result[0]  # type: ignore
                    if isinstance(nsfw_result, list) and len(nsfw_result) > 0:
                        nsfw_result = nsfw_result[0]  # type: ignore
                
                # toxic-bert returns TOXIC or NOT_TOXIC
                analysis["transformer_results"]["nsfw"] = nsfw_result
                if isinstance(nsfw_result, dict) and "label" in nsfw_result and "score" in nsfw_result:
                    if nsfw_result["label"] == "TOXIC":
                        analysis["nsfw_score"] = nsfw_result["score"]
                    else:
                        analysis["nsfw_score"] = 1.0 - nsfw_result["score"]
            
            # Sentiment Analysis
            if self.sentiment_classifier:
                sentiment_result = self.sentiment_classifier(user_input)
                # Handle nested list format: [[{...}]] -> {...}
                if isinstance(sentiment_result, list) and len(sentiment_result) > 0:
                    sentiment_result = sentiment_result[0]  # type: ignore
                    if isinstance(sentiment_result, list) and len(sentiment_result) > 0:
                        sentiment_result = sentiment_result[0]  # type: ignore
                
                analysis["transformer_results"]["sentiment"] = sentiment_result
                if isinstance(sentiment_result, dict) and "label" in sentiment_result and "score" in sentiment_result:
                    analysis["sentiment"] = sentiment_result["label"].lower()
                    analysis["sentiment_score"] = sentiment_result["score"]
            
            # Emotion Detection
            if self.emotion_classifier:
                emotion_result = self.emotion_classifier(user_input)
                # Handle nested list format: [[{...}]] -> {...}
                if isinstance(emotion_result, list) and len(emotion_result) > 0:
                    emotion_result = emotion_result[0]  # type: ignore
                    if isinstance(emotion_result, list) and len(emotion_result) > 0:
                        emotion_result = emotion_result[0]  # type: ignore
                
                analysis["transformer_results"]["emotion"] = emotion_result
                if isinstance(emotion_result, dict) and "label" in emotion_result and "score" in emotion_result:
                    analysis["emotions"] = {
                        "primary_emotion": emotion_result["label"],
                        "confidence": emotion_result["score"]
                    }
            
            # Calculate overall transformer confidence
            confidences = []
            for result in analysis["transformer_results"].values():
                if isinstance(result, dict) and "score" in result:
                    confidences.append(result["score"])
                elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict) and "score" in result[0]:
                    # Handle case where list wasn't properly processed
                    confidences.append(result[0]["score"])
            
            if confidences:
                analysis["transformer_confidence"] = sum(confidences) / len(confidences)
            
            log_system_event("transformer_analysis", 
                           f"NSFW: {analysis['nsfw_score']:.3f}, "
                           f"Sentiment: {analysis['sentiment']} ({analysis['sentiment_score']:.3f}), "
                           f"Emotion: {analysis['emotions'].get('primary_emotion', 'unknown')}")
            
        except Exception as e:
            log_error(f"Transformer analysis failed: {e}")
            analysis["transformer_error"] = str(e)
        
        return analysis
    
    def check_transformer_connectivity(self) -> Dict[str, Any]:
        """
        Diagnose transformer connectivity issues for SSL/Network troubleshooting.
        
        Returns:
            Dictionary with connectivity status and recommendations
        """
        status = {
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "transformers_enabled": self.use_transformers,
            "models_loaded": {
                "nsfw_classifier": self.nsfw_classifier is not None,
                "sentiment_classifier": self.sentiment_classifier is not None,
                "emotion_classifier": self.emotion_classifier is not None
            },
            "recommendations": []
        }
        
        if not TRANSFORMERS_AVAILABLE:
            status["recommendations"].append("Install transformers library: pip install transformers torch")
            
        if TRANSFORMERS_AVAILABLE and not self.use_transformers:
            status["recommendations"].append("Transformers disabled due to initialization errors")
            status["recommendations"].append("Check logs for SSL/network error details")
            
        models_failed = sum(1 for loaded in status["models_loaded"].values() if not loaded)
        if models_failed > 0:
            status["recommendations"].append(f"{models_failed}/3 transformer models failed to load")
            status["recommendations"].append("This is likely due to SSL/network restrictions")
            status["recommendations"].append("Solutions:")
            status["recommendations"].append("  1. Configure corporate proxy settings")
            status["recommendations"].append("  2. Whitelist huggingface.co in firewall")
            status["recommendations"].append("  3. Use offline transformer models")
            status["recommendations"].append("  4. Accept keyword-based fallback analysis")
            
        return status
