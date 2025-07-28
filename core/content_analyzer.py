"""
Content Analysis Engine for OpenChronicle with Dynamic Model Routing.
Uses dynamic model selection to optimize content analysis and routing.
"""

import json
import os
import sys
import logging
from typing import Dict, List, Any, Optional, Tuple, Union, cast
from datetime import datetime, UTC
from pathlib import Path

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

class ContentAnalyzer:
    """Analyzes user input and story content with dynamic model routing."""
    
    def __init__(self, model_manager, use_transformers: bool = True):
        self.model_manager = model_manager
        self.analysis_cache = {}
        self.routing_rules = {}
        self.content_patterns = {}
        self.use_transformers = use_transformers and TRANSFORMERS_AVAILABLE
        
        # Initialize transformer models if available
        self.nsfw_classifier: Optional[Any] = None
        self.sentiment_classifier: Optional[Any] = None
        self.emotion_classifier: Optional[Any] = None
        
        if self.use_transformers:
            self._initialize_transformers()
    
    def _initialize_transformers(self):
        """Initialize transformer-based classifiers."""
        try:
            log_info("Initializing transformer-based content classifiers...")
            
            # Suppress all warnings and output during model loading
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # Temporarily redirect stdout and stderr to suppress console output
                import sys
                from io import StringIO
                
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = StringIO()
                sys.stderr = StringIO()
                
                try:
                    device = 0 if torch.cuda.is_available() else -1
                    
                    # NSFW Content Detection  
                    # Using a general text classification model fine-tuned for content safety
                    self.nsfw_classifier = pipeline(  # type: ignore
                        "text-classification",
                        model="unitary/toxic-bert",
                        device=device,
                        truncation=True,
                        max_length=512,
                        top_k=1  # Only return top prediction
                    )
                    
                    # Sentiment Analysis
                    # Use explicit Any casting to avoid type checker issues
                    pipeline_func = cast(Any, pipeline)
                    self.sentiment_classifier = pipeline_func(
                        "sentiment-analysis",
                        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                        device=device,
                        truncation=True,
                        max_length=512,
                        top_k=1  # Only return top prediction
                    )
                    
                    # Emotion Detection
                    self.emotion_classifier = pipeline(  # type: ignore
                        "text-classification",
                        model="j-hartmann/emotion-english-distilroberta-base",
                        device=device,
                        truncation=True,
                        max_length=512,
                        top_k=1  # Only return top prediction
                    )
                    
                finally:
                    # Restore stdout and stderr
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
            
            log_info("Transformer classifiers initialized successfully")
            
        except Exception as e:
            log_error(f"Failed to initialize transformer classifiers: {e}")
            self.use_transformers = False
            self.nsfw_classifier = None
            self.sentiment_classifier = None
            self.emotion_classifier = None
        
    def get_best_analysis_model(self, content_type: str = "general", allow_fallbacks: bool = True) -> str:
        """
        Get the best available model for content analysis with intelligent selection and fallback strategies.
        
        Args:
            content_type: Type of content to analyze (general, creative, analysis, etc.)
            allow_fallbacks: Whether to allow fallback to less suitable models
            
        Returns:
            Model name string, or "mock" as ultimate fallback
        """
        # Get content routing from registry
        config = self.model_manager.config
        content_routing = config.get("content_routing", {})
        
        # Select model candidates based on content type
        if content_type == "nsfw":
            candidates = content_routing.get("nsfw_models", [])
        elif content_type == "creative":
            candidates = content_routing.get("creative_models", [])
        elif content_type == "analysis":
            candidates = content_routing.get("analysis_models", [])
        else:
            candidates = content_routing.get("safe_models", [])
            
        # Filter for enabled models
        enabled_models = [
            name for name in candidates 
            if self.model_manager.list_model_configs().get(name, {}).get("enabled", True)
        ]
        
        if not enabled_models:
            log_warning("No enabled models for content analysis, using fallback")
            return "mock"
        
        # First pass: Test preferred models for suitability
        suitable_models = []
        unsuitable_models = []
        
        for model_name in enabled_models:
            suitability = self._check_model_suitability(model_name, content_type)
            if suitability["suitable"]:
                suitable_models.append((model_name, suitability["score"], suitability["reason"]))
                log_info(f"✓ Model {model_name} suitable for {content_type}: {suitability['reason']}")
            else:
                unsuitable_models.append((model_name, suitability["score"], suitability["reason"]))
                log_warning(f"✗ Model {model_name} not suitable for {content_type}: {suitability['reason']}")
        
        # If we have suitable models, use the best one
        if suitable_models:
            suitable_models.sort(key=lambda x: x[1], reverse=True)
            selected = suitable_models[0][0]
            
            # Warn if mock adapter is selected for real AI work
            if selected == "mock":
                log_warning("WARNING: Mock adapter selected for AI processing - this provides simulated responses only!")
                log_warning("For real AI functionality, please configure Ollama, OpenAI, Anthropic, or another AI provider.")
            
            log_info(f"Selected {selected} for {content_type} content analysis (score: {suitable_models[0][1]:.2f})")
            return selected
        
        # Second pass: Try fallback strategies if no suitable models found
        if allow_fallbacks and unsuitable_models:
            log_warning(f"No ideal models for {content_type}, evaluating fallback options...")
            
            # Check if any models are "good enough" (score > 0.1)
            acceptable_fallbacks = [(name, score, reason) for name, score, reason in unsuitable_models if score > 0.1]
            
            if acceptable_fallbacks:
                acceptable_fallbacks.sort(key=lambda x: x[1], reverse=True)
                fallback_model = acceptable_fallbacks[0][0]
                log_warning(f"Using fallback model {fallback_model} for {content_type} (score: {acceptable_fallbacks[0][1]:.2f})")
                log_warning(f"Fallback reason: {acceptable_fallbacks[0][2]}")
                
                # Check if we should suggest user actions
                self._suggest_model_improvements(content_type, unsuitable_models, acceptable_fallbacks)
                
                return fallback_model
        
        # Third pass: Check if there are any other enabled models not in preferred list
        if allow_fallbacks:
            all_models = self.model_manager.list_model_configs()
            other_models = [name for name in all_models.keys() 
                          if all_models[name].get("enabled", True) and name not in enabled_models]
            
            if other_models:
                log_warning(f"Testing non-preferred models for {content_type}...")
                
                for model_name in other_models:
                    suitability = self._check_model_suitability(model_name, content_type)
                    if suitability["suitable"]:
                        log_warning(f"Found alternative model {model_name} suitable for {content_type}: {suitability['reason']}")
                        return model_name
        
        # Ultimate fallback with user guidance
        log_error(f"No suitable models found for {content_type} content analysis")
        self._provide_model_guidance(content_type, unsuitable_models)
        
        log_warning("WARNING: Falling back to mock adapter - this provides simulated responses only!")
        log_warning("For real AI functionality, please configure Ollama, OpenAI, Anthropic, or another AI provider.")
        
        return "mock"

    def _check_model_suitability(self, model_name: str, content_type: str) -> Dict[str, Any]:
        """Check if a model is suitable for the given content type."""
        try:
            # Get model configuration
            model_configs = self.model_manager.list_model_configs()
            if model_name not in model_configs:
                return {"suitable": False, "reason": "Model not in configuration", "score": 0.0}
            
            model_config = model_configs[model_name]
            
            # Check if model is enabled
            if not model_config.get("enabled", True):
                return {"suitable": False, "reason": "Model disabled in configuration", "score": 0.0}
            
            # Get model info to check actual model name and type
            model_info = model_config.get("model_name", "").lower()
            provider_type = model_config.get("type", "").lower()
            
            # Score based on model suitability for content analysis
            score = 0.0
            suitability_reasons = []
            
            # Base score for any working model
            score += 0.3
            suitability_reasons.append("basic functionality")
            
            # Bonus for models known to be good at analysis
            if any(analysis_model in model_info for analysis_model in [
                "gpt-4", "gpt-3.5", "claude", "llama", "mistral", "gemini"
            ]):
                score += 0.4
                suitability_reasons.append("analysis-capable model")
            
            # Penalty for code-specific models (as you mentioned codellama)
            if any(code_model in model_info for code_model in [
                "codellama", "code-", "coding", "programmer", "coder"
            ]):
                score -= 0.3
                suitability_reasons.append("code-focused model (less suitable for general analysis)")
            
            # Bonus for instruction-following models
            if any(instruct_model in model_info for instruct_model in [
                "instruct", "chat", "turbo", "assistant"
            ]):
                score += 0.2
                suitability_reasons.append("instruction-following variant")
            
            # Penalty for very small models (likely not good for complex analysis)
            if any(small_indicator in model_info for small_indicator in [
                "7b", "3b", "1b", "mini", "nano", "tiny"
            ]):
                score -= 0.1
                suitability_reasons.append("small model size")
            
            # Bonus for larger models
            if any(large_indicator in model_info for large_indicator in [
                "70b", "34b", "30b", "13b", "large", "xl"
            ]):
                score += 0.2
                suitability_reasons.append("larger model size")
            
            # Special handling for mock adapter (always suitable as fallback)
            if model_name == "mock":
                score = 0.1  # Low but non-zero score
                suitability_reasons = ["fallback mock adapter - NOT FOR PRODUCTION USE"]
            
            # Determine suitability threshold
            threshold = 0.2
            suitable = score >= threshold
            
            reason = f"Score: {score:.2f} ({', '.join(suitability_reasons)})"
            
            return {
                "suitable": suitable,
                "score": score,
                "reason": reason,
                "model_info": model_info,
                "provider_type": provider_type
            }
            
        except Exception as e:
            log_error(f"Error checking model suitability for {model_name}: {e}")
            return {"suitable": False, "reason": f"Error during check: {e}", "score": 0.0}

    async def test_model_availability(self, model_name: str) -> Dict[str, Any]:
        """Test if a model is actually available and responsive."""
        try:
            log_info(f"Testing availability of model: {model_name}")
            
            # Try to initialize the adapter if not already done
            if model_name not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model_name)
                if not success:
                    return {"available": False, "reason": "Failed to initialize adapter", "response_time": None}
            
            # Get the initialized adapter
            adapter = self.model_manager.adapters.get(model_name)
            if not adapter:
                return {"available": False, "reason": "No adapter found", "response_time": None}
            
            # Try a simple test prompt
            import time
            start_time = time.time()
            
            test_prompt = "Hello, please respond with 'OK' to confirm you are working."
            
            try:
                response = await adapter.generate_response(test_prompt)
                response_time = time.time() - start_time
                
                # Check if we got a reasonable response
                if response and len(response.strip()) > 0:
                    return {
                        "available": True,
                        "reason": "Model responded successfully",
                        "response_time": response_time,
                        "test_response": response[:100] + "..." if len(response) > 100 else response
                    }
                else:
                    return {
                        "available": False,
                        "reason": "Empty or invalid response",
                        "response_time": response_time
                    }
                    
            except Exception as e:
                response_time = time.time() - start_time
                return {
                    "available": False,
                    "reason": f"Model error: {str(e)[:200]}",
                    "response_time": response_time
                }
                
        except Exception as e:
            log_error(f"Error testing model availability for {model_name}: {e}")
            return {"available": False, "reason": f"Test failed: {e}", "response_time": None}

    async def find_working_analysis_models(self, content_type: str = "analysis") -> List[Dict[str, Any]]:
        """Find all working models suitable for analysis, sorted by suitability."""
        log_info(f"Searching for working analysis models for content type: {content_type}")
        
        # Get all configured models
        all_models = self.model_manager.list_model_configs()
        working_models = []
        
        for model_name, model_config in all_models.items():
            # Skip disabled models
            if not model_config.get("enabled", True):
                continue
                
            # Check suitability first (faster than availability test)
            suitability = self._check_model_suitability(model_name, content_type)
            if not suitability["suitable"]:
                continue
            
            # Test actual availability
            availability = await self.test_model_availability(model_name)
            
            if availability["available"]:
                working_models.append({
                    "name": model_name,
                    "suitability_score": suitability["score"],
                    "suitability_reason": suitability["reason"],
                    "response_time": availability["response_time"],
                    "test_response": availability.get("test_response", ""),
                    "provider_type": suitability.get("provider_type", "unknown")
                })
                log_info(f">> {model_name} is working (score: {suitability['score']:.2f}, "
                        f"response time: {availability['response_time']:.2f}s)")
            else:
                log_warning(f">> {model_name} is not available: {availability['reason']}")
        
        # Sort by suitability score, then by response time
        working_models.sort(key=lambda x: (x["suitability_score"], -x["response_time"]), reverse=True)
        
        log_system_event("model_discovery", f"Found {len(working_models)} working analysis models", {
            "content_type": content_type,
            "working_models": [m["name"] for m in working_models],
            "total_tested": len(all_models)
        })
        
        return working_models
        
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
        
    def detect_content_type(self, user_input: str) -> Dict[str, Any]:
        """Detect content type and flags using hybrid keyword + transformer approach."""
        # Start with keyword-based analysis
        keyword_analysis = self._keyword_based_detection(user_input)
        
        # Add transformer-based analysis if available
        try:
            transformer_analysis = self._analyze_with_transformers(user_input)
        except Exception as e:
            log_error(f"Transformer analysis failed in detect_content_type: {e}")
            transformer_analysis = {}
        
        # Combine both approaches for enhanced accuracy
        combined_analysis = self._combine_analysis_results(keyword_analysis, transformer_analysis, user_input)
        
        return combined_analysis
    
    def _keyword_based_detection(self, user_input: str) -> Dict[str, Any]:
        """Original keyword-based content detection."""
        text_lower = user_input.lower()
        content_flags = []
        content_type = "general"
        confidence = 0.0
        
        # Enhanced NSFW content detection with severity levels
        nsfw_explicit = ["explicit", "sexual", "adult", "erotic", "nude", "naked", "sex"]
        nsfw_suggestive = ["intimate", "romantic", "kiss", "embrace", "seductive", "passionate", "desire", "love"]
        nsfw_mature = ["violence", "blood", "death", "kill", "murder", "torture", "gore"]
        
        explicit_matches = sum(1 for keyword in nsfw_explicit if keyword in text_lower)
        suggestive_matches = sum(1 for keyword in nsfw_suggestive if keyword in text_lower)
        mature_matches = sum(1 for keyword in nsfw_mature if keyword in text_lower)
        
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
        creative_keywords = [
            "imagine", "create", "describe", "story", "scene", "character",
            "dialogue", "narrative", "plot", "setting", "atmosphere", "cast", "spell",
            "explore", "magical", "magic", "fantasy", "wizard", "dragon", "forest", "adventure"
        ]
        
        creative_matches = sum(1 for keyword in creative_keywords if keyword in text_lower)
        if creative_matches > 0 and content_type == "general":
            content_type = "creative"
            content_flags.append("creative")
            confidence = min(0.8, 0.4 + (creative_matches * 0.1))
            
        # Analysis content detection
        analysis_keywords = [
            "analyze", "classify", "determine", "evaluate", "assess",
            "summarize", "explain", "interpret", "understand", "what", "why", "how"
        ]
        
        analysis_matches = sum(1 for keyword in analysis_keywords if keyword in text_lower)
        if analysis_matches > 0 and content_type == "general":
            content_type = "analysis"
            content_flags.append("analysis")
            confidence = min(0.7, 0.3 + (analysis_matches * 0.1))
        
        # Action content detection
        action_keywords = [
            "attack", "fight", "battle", "sword", "weapon", "combat", "hit", "strike",
            "run", "jump", "climb", "move", "go", "walk", "enter", "exit"
        ]
        
        action_matches = sum(1 for keyword in action_keywords if keyword in text_lower)
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
    
    def _combine_analysis_results(self, keyword_analysis: Dict[str, Any], transformer_analysis: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Combine keyword and transformer analysis for enhanced accuracy."""
        combined = keyword_analysis.copy()
        
        if not transformer_analysis:
            # No transformer analysis available, return keyword-based only
            return combined
        
        # Get sentiment and emotion information first
        sentiment = transformer_analysis.get("sentiment", "neutral")
        emotions = transformer_analysis.get("emotions", {})
        primary_emotion = emotions.get("primary_emotion", "").lower()
        
        # Enhance NSFW detection with transformer results
        nsfw_score = transformer_analysis.get("nsfw_score", 0.0)
        
        # Only override keyword-based detection if transformer is very confident AND
        # there are other indicators (negative sentiment, negative emotions)
        # Increased threshold to reduce false positives on fantasy/gaming content
        
        # Common false positive patterns to exclude
        is_question = user_input.strip().endswith('?') or user_input.lower().startswith(('what', 'why', 'how', 'where', 'when', 'who'))
        is_fantasy_content = any(fantasy_word in user_input.lower() for fantasy_word in 
                               ["spell", "magic", "wizard", "dragon", "adventure", "fantasy", "cast", "battle"])
        is_analysis_request = any(analysis_word in user_input.lower() for analysis_word in
                                ["meaning", "analyze", "explain", "understand", "interpret"])
        
        high_confidence_toxic = (
            nsfw_score > 0.99 and 
            (sentiment in ["negative", "NEGATIVE"] or 
             primary_emotion in ["anger", "disgust"]) and
             # Exclude common false positive patterns
             not is_question and
             not is_fantasy_content and
             not is_analysis_request
        )
        
        if high_confidence_toxic:
            if combined["content_type"] != "nsfw":
                combined["content_type"] = "nsfw"
                combined["content_flags"].append("toxic_detected")
            combined["confidence"] = max(combined["confidence"], nsfw_score)
        elif nsfw_score > 0.6 and combined["content_type"] == "nsfw":
            # Transformer moderates keyword-based NSFW detection
            combined["confidence"] = (combined["confidence"] + nsfw_score) / 2
        
        # Add sentiment and emotion information
        combined["sentiment"] = sentiment
        combined["emotions"] = emotions
        
        combined["sentiment"] = sentiment
        combined["emotions"] = emotions
        
        # Add sentiment-based flags
        if sentiment in ["negative", "NEGATIVE"]:
            combined["content_flags"].append("negative_sentiment")
        elif sentiment in ["positive", "POSITIVE"]:
            combined["content_flags"].append("positive_sentiment")
        
        # Add emotion-based flags
        primary_emotion = emotions.get("primary_emotion", "").lower()
        if primary_emotion in ["anger", "disgust", "fear"]:
            combined["content_flags"].append("negative_emotion")
        elif primary_emotion in ["joy", "surprise"]:
            combined["content_flags"].append("positive_emotion")
        elif primary_emotion == "sadness":
            combined["content_flags"].append("melancholy")
        
        # Update confidence with transformer input
        transformer_confidence = transformer_analysis.get("transformer_confidence", 0.0)
        if transformer_confidence > 0:
            # Weighted average: 60% transformer, 40% keyword for final confidence
            combined["confidence"] = (transformer_confidence * 0.6) + (combined["confidence"] * 0.4)
        
        # Add transformer metadata
        combined["transformer_analysis"] = transformer_analysis
        combined["analysis_method"] = "hybrid"
        
        log_system_event("hybrid_analysis", 
                        f"Final: {combined['content_type']} (confidence: {combined['confidence']:.3f}), "
                        f"Sentiment: {sentiment}, Emotion: {primary_emotion}")
        
        return combined
        
    async def analyze_user_input(self, user_input: str, story_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user input with dynamic model selection for optimal analysis.
        """
        # Detect content type for model routing
        content_detection = self.detect_content_type(user_input)
        content_type = content_detection["content_type"]
        
        # Get the best model for this content type
        analysis_model = self.get_best_analysis_model(content_type)
        
        # Log routing decision
        log_system_event("content_routing", 
                        f"Content type: {content_type}, flags: {content_detection['content_flags']}, "
                        f"confidence: {content_detection['confidence']:.2f}, selected model: {analysis_model}")
        
        analysis_prompt = self._build_analysis_prompt(user_input, story_context)
        
        try:
            # Use dynamically selected model for analysis
            analysis_response = await self.model_manager.generate_response(
                analysis_prompt,
                adapter_name=analysis_model,
                story_id=story_context.get("story_id"),
                max_tokens=512,
                temperature=0.1  # Low temperature for consistent analysis
            )
            
            # Parse the structured analysis
            analysis = self._parse_analysis_response(analysis_response)
            
            # Merge with content detection results
            analysis.update(content_detection)
            analysis["analysis_model"] = analysis_model
            analysis["routing_recommendation"] = self.recommend_generation_model(analysis)
            
            # Cache the analysis
            cache_key = hash(user_input + str(story_context.get("story_id", "")))
            self.analysis_cache[cache_key] = analysis
            
            log_system_event("content_analysis", 
                           f"Analyzed with {analysis_model}: {content_type} content, "
                           f"recommended model: {analysis['routing_recommendation']}")
            
            return analysis
            
        except Exception as e:
            log_error(f"Content analysis failed with {analysis_model}: {e}")
            # Fallback to basic analysis
            return self._basic_analysis_fallback(user_input, story_context, content_detection)
    
    def recommend_generation_model(self, analysis: Dict[str, Any]) -> str:
        """Recommend the best model for content generation based on analysis."""
        content_type = analysis.get("content_type", "general")
        content_flags = analysis.get("content_flags", [])
        confidence = analysis.get("confidence", 0.0)
        
        config = self.model_manager.config
        content_routing = config.get("content_routing", {})
        
        # Priority-based routing with confidence thresholds
        candidates = []
        routing_reason = ""
        
        # High-confidence NSFW content
        if ("explicit" in content_flags) and confidence > 0.7:
            candidates = content_routing.get("nsfw_models", [])
            routing_reason = f"Explicit content detected with {confidence:.2f} confidence"
        
        # Suggestive or mature content with sufficient confidence
        elif ("suggestive" in content_flags or "mature" in content_flags) and confidence > 0.5:
            candidates = content_routing.get("nsfw_models", [])
            routing_reason = f"Mature content detected with {confidence:.2f} confidence"
        
        # NSFW content type but low confidence - route to safe models
        elif content_type == "nsfw" and confidence <= 0.5:
            candidates = content_routing.get("safe_models", [])
            routing_reason = f"Low-confidence NSFW content ({confidence:.2f}) routed to safe models"
        
        # Creative content
        elif content_type == "creative" or "creative" in content_flags:
            candidates = content_routing.get("creative_models", [])
            routing_reason = "Creative content detected"
        
        # Simple/quick responses
        elif "simple" in content_flags or analysis.get("word_count", 0) < 5:
            candidates = content_routing.get("fast_models", [])
            routing_reason = "Simple/quick response needed"
        
        # Analysis requests
        elif content_type == "analysis" or "analysis" in content_flags:
            candidates = content_routing.get("analysis_models", [])
            routing_reason = "Analysis content detected"
        
        # Default to safe models
        else:
            candidates = content_routing.get("safe_models", [])
            routing_reason = "Default safe routing"
        
        # Filter for enabled models
        enabled_models = [
            name for name in candidates 
            if self.model_manager.list_model_configs().get(name, {}).get("enabled", True)
        ]
        
        if not enabled_models:
            log_warning(f"No enabled models for routing decision: {routing_reason}")
            # Fallback to any enabled model
            all_models = self.model_manager.list_model_configs()
            enabled_models = [name for name, config in all_models.items() if config.get("enabled", True)]
            
            if enabled_models:
                recommended = enabled_models[0]
                routing_reason = f"Fallback to {recommended} (no suitable models enabled)"
            else:
                recommended = "mock"
                routing_reason = "Emergency fallback to mock model"
                log_warning("WARNING: Using mock adapter for AI processing - this is for testing only and will not provide real AI functionality!")
                log_warning("Please configure a real AI model (Ollama, OpenAI, Anthropic, etc.) for production use.")
        else:
            recommended = enabled_models[0]  # First in priority order
        
        # Log routing decision
        log_system_event("model_routing", 
                        f"Recommended {recommended} for generation. Reason: {routing_reason}")
        
        return recommended
    
    def _basic_analysis_fallback(self, user_input: str, story_context: Dict[str, Any], content_detection: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fallback analysis when dynamic analysis fails."""
        if content_detection is None:
            content_detection = self.detect_content_type(user_input)
        
        return {
            **content_detection,
            "intent": "story_continuation",
            "routing_recommendation": self.get_best_analysis_model(content_detection["content_type"]),
            "analysis_model": "fallback",
            "context_needed": ["memory", "canon"],
            "fallback_used": True
        }
    
    def _build_analysis_prompt(self, user_input: str, story_context: Dict[str, Any]) -> str:
        """Build the analysis prompt for the local LLM."""
        
        story_title = story_context.get("meta", {}).get("title", "Unknown Story")
        characters = list(story_context.get("characters", {}).keys())
        
        prompt = f"""Analyze this user input for an interactive story system.

STORY CONTEXT:
Title: {story_title}
Known Characters: {', '.join(characters) if characters else 'None'}

USER INPUT: "{user_input}"

Provide analysis in this JSON format:
{{
  "content_type": "action|dialogue|description|question|command",
  "intent": "brief description of user intent",
  "entities": {{
    "characters": ["character names mentioned"],
    "locations": ["locations mentioned"],
    "items": ["items/objects mentioned"],
    "emotions": ["emotional tones detected"]
  }},
  "content_flags": {{
    "nsfw": false,
    "violence": false,
    "mature_themes": false,
    "emotional_intensity": "low|medium|high"
  }},
  "required_canon": ["suggested canon files to reference"],
  "memory_triggers": ["memory flags that should be activated"],
  "response_style": "narrative|descriptive|action|dialogue",
  "token_priority": "high|medium|low"
}}

Response (JSON only):"""
        
        return prompt
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured analysis response from the local LLM."""
        try:
            # Find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end != -1:
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                raise ValueError("No valid JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            log_error(f"⚠️ Failed to parse analysis response: {e}")
            return self._fallback_analysis(response)
    
    def _fallback_analysis(self, user_input: str) -> Dict[str, Any]:
        """Provide basic analysis when LLM analysis fails."""
        return {
            "content_type": "action",
            "intent": "User interaction",
            "entities": {
                "characters": [],
                "locations": [],
                "items": [],
                "emotions": []
            },
            "content_flags": {
                "nsfw": False,
                "violence": False,
                "mature_themes": False,
                "emotional_intensity": "medium"
            },
            "required_canon": [],
            "memory_triggers": [],
            "response_style": "narrative",
            "token_priority": "medium"
        }
    
    async def optimize_canon_selection(self, analysis: Dict[str, Any], story_data: Dict[str, Any]) -> List[str]:
        """
        Select relevant canon snippets based on content analysis.
        """
        canon_dir = os.path.join(story_data["path"], "canon")
        if not os.path.exists(canon_dir):
            return []
        
        # Get all available canon files (JSON and TXT)
        json_files = [f[:-5] for f in os.listdir(canon_dir) if f.endswith(".json")]
        txt_files = [f[:-4] for f in os.listdir(canon_dir) if f.endswith(".txt")]
        canon_files = json_files + txt_files
        
        # If analysis suggests specific canon files, use those
        required_canon = analysis.get("required_canon", [])
        if required_canon:
            # Filter to only existing files
            selected_canon = [c for c in required_canon if c in canon_files]
            if selected_canon:
                return selected_canon
        
        # Otherwise, use entity-based selection
        entities = analysis.get("entities", {})
        relevant_canon = []
        
        # Check for character-specific canon
        for character in entities.get("characters", []):
            char_canon = f"character_{character.lower().replace(' ', '_')}"
            if char_canon in canon_files:
                relevant_canon.append(char_canon)
        
        # Check for location-specific canon
        for location in entities.get("locations", []):
            loc_canon = f"location_{location.lower().replace(' ', '_')}"
            if loc_canon in canon_files:
                relevant_canon.append(loc_canon)
        
        # Add general canon based on content type
        content_type = analysis.get("content_type", "action")
        if content_type == "dialogue":
            if "dialogue_rules" in canon_files:
                relevant_canon.append("dialogue_rules")
        elif content_type == "action":
            if "world_rules" in canon_files:
                relevant_canon.append("world_rules")
        
        # Limit to prevent token overflow
        return relevant_canon[:3]
    
    async def optimize_memory_context(self, analysis: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize memory context based on analysis to reduce tokens.
        """
        optimized_memory = {
            "characters": {},
            "world_state": {},
            "flags": [],
            "recent_events": []
        }
        
        # Only include relevant characters
        mentioned_characters = analysis.get("entities", {}).get("characters", [])
        if mentioned_characters and memory.get("characters"):
            for char_name in mentioned_characters:
                # Find character by name (case-insensitive)
                for mem_char, char_data in memory["characters"].items():
                    if char_name.lower() in mem_char.lower():
                        optimized_memory["characters"][mem_char] = char_data
                        break
        elif memory.get("characters"):
            # Include all characters if none specifically mentioned (but limit)
            char_items = list(memory["characters"].items())
            optimized_memory["characters"] = dict(char_items[:3])
        
        # Include relevant world state
        if memory.get("world_state"):
            # For now, include all world state (could be optimized further)
            optimized_memory["world_state"] = memory["world_state"]
        
        # Include relevant flags
        if memory.get("flags"):
            memory_triggers = analysis.get("memory_triggers", [])
            if memory_triggers:
                optimized_memory["flags"] = [
                    flag for flag in memory["flags"]
                    if flag.get("name") in memory_triggers
                ]
            else:
                # Include recent flags
                optimized_memory["flags"] = memory["flags"][-5:]
        
        # Include recent events (always relevant for continuity)
        if memory.get("recent_events"):
            optimized_memory["recent_events"] = memory["recent_events"][-3:]
        
        return optimized_memory
    
    async def generate_content_flags(self, analysis: Dict[str, Any], response: str) -> List[Dict[str, Any]]:
        """
        Generate memory flags based on content analysis and LLM response.
        """
        flags = []
        
        # Add content type flag
        content_type = analysis.get("content_type", "action")
        flags.append({
            "name": f"content_type_{content_type}",
            "value": True,
            "timestamp": datetime.now(UTC).isoformat()
        })
        
        # Add entity flags
        entities = analysis.get("entities", {})
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                if entity:  # Skip empty entities
                    flags.append({
                        "name": f"{entity_type}_{entity.lower().replace(' ', '_')}",
                        "value": True,
                        "timestamp": datetime.now(UTC).isoformat()
                    })
        
        # Add content flags (handle list format)
        content_flags = analysis.get("content_flags", [])
        if isinstance(content_flags, list):
            # New list format
            for flag in content_flags:
                if flag:  # Skip empty flags
                    flags.append({
                        "name": f"content_{flag}",
                        "value": True,
                        "timestamp": datetime.now(UTC).isoformat()
                    })
            emotional_intensity = "medium"  # Default since no dict structure
        else:
            # Legacy dict format (for backwards compatibility)
            for flag_name, flag_value in content_flags.items():
                if flag_value and flag_name != "emotional_intensity":
                    flags.append({
                        "name": f"content_{flag_name}",
                        "value": flag_value,
                        "timestamp": datetime.now(UTC).isoformat()
                    })
            emotional_intensity = content_flags.get("emotional_intensity", "medium")
        
        # Add emotional intensity flag
        flags.append({
            "name": "emotional_intensity",
            "value": emotional_intensity,
            "timestamp": datetime.now(UTC).isoformat()
        })
        
        return flags
    
    def get_routing_recommendation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend model routing based on content analysis.
        """
        content_flags = analysis.get("content_flags", [])
        token_priority = analysis.get("token_priority", "medium")
        
        # Get default adapter from model manager or fall back to mock
        default_adapter = "mock"  # Safe fallback
        if hasattr(self, 'model_manager') and self.model_manager:
            try:
                # Try to get the configured default, or the first available adapter
                if hasattr(self.model_manager, 'default_adapter') and self.model_manager.default_adapter:
                    default_adapter = self.model_manager.default_adapter
                elif hasattr(self.model_manager, 'get_available_adapters'):
                    available = self.model_manager.get_available_adapters()
                    if available:
                        # Prefer non-mock adapters but use what's available
                        non_mock = [a for a in available if not a.startswith('mock')]
                        default_adapter = non_mock[0] if non_mock else available[0]
            except Exception as e:
                log_warning(f"Could not determine default adapter: {e}, using mock fallback")
                default_adapter = "mock"
        
        # Default routing
        recommendation = {
            "adapter": default_adapter,
            "max_tokens": 1024,
            "temperature": 0.7,
            "content_filter": False
        }
        
        # Adjust based on content flags (list format)
        if ("nsfw" in content_flags or "explicit" in content_flags or 
            "suggestive" in content_flags or "mature" in content_flags or 
            "toxic_detected" in content_flags):
            recommendation["content_filter"] = True
            # For sensitive content, prefer local models
            if hasattr(self, 'model_manager') and self.model_manager:
                try:
                    available = self.model_manager.get_available_adapters()
                    local_adapters = [a for a in available if a in ['ollama', 'mock']]
                    if local_adapters:
                        recommendation["adapter"] = local_adapters[0]
                except Exception:
                    pass
        
        # Adjust token limits based on priority
        if token_priority == "high":
            recommendation["max_tokens"] = 2048
        elif token_priority == "low":
            recommendation["max_tokens"] = 512
        
        # Adjust temperature based on content type
        content_type = analysis.get("content_type", "action")
        if content_type == "dialogue":
            recommendation["temperature"] = 0.8  # More creative for dialogue
        elif content_type == "description":
            recommendation["temperature"] = 0.6  # More focused for descriptions
        
        return recommendation

    # ============================================================================
    # STORYPACK IMPORT ANALYSIS METHODS
    # ============================================================================
    
    async def extract_character_data(self, content: str) -> Dict[str, Any]:
        """Extract character information from raw text content."""
        log_info(f"Extracting character data from content ({len(content)} chars)")
        
        prompt = f"""Analyze this text and extract character information. Return ONLY valid JSON.

Text: {content}

Extract character details in this exact JSON format:
{{
    "name": "Character's full name",
    "description": "Physical appearance and basic description",
    "personality": "Personality traits and characteristics", 
    "background": "Character's history and background",
    "relationships": ["List of mentioned relationships or connections"],
    "traits": ["Key personality traits"],
    "skills": ["Mentioned abilities or skills"],
    "equipment": ["Weapons, items, or possessions mentioned"],
    "role": "Character's role or position",
    "motivation": "What drives this character",
    "confidence": 0.85
}}

If multiple characters are found, return an array of character objects.
Return empty object {{}} if no clear character information found."""

        try:
            model = self.get_best_analysis_model("analysis")
            log_model_interaction("character_extraction", model, len(prompt), 0)
            
            # Initialize adapter if needed
            if model not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model)
                if not success:
                    raise Exception(f"Failed to initialize adapter for model: {model}")
            
            adapter = self.model_manager.adapters.get(model)
            if not adapter:
                raise Exception(f"No adapter available for model: {model}")
            
            response = await adapter.generate_response(prompt)
            
            # Log actual response length
            log_model_interaction("character_extraction", model, len(prompt), len(response))
            
            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully extracted character data: {result.get('name', 'multiple/unknown')}")
                return result
            except json.JSONDecodeError:
                log_warning("Failed to parse character extraction JSON, attempting cleanup")
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    log_error("No valid JSON found in character extraction response")
                    return {}
                    
        except Exception as e:
            log_error(f"Character extraction failed: {e}")
            return {}

    async def extract_location_data(self, content: str) -> Dict[str, Any]:
        """Extract location information from raw text content."""
        log_info(f"Extracting location data from content ({len(content)} chars)")
        
        prompt = f"""Analyze this text and extract location information. Return ONLY valid JSON.

Text: {content}

Extract location details in this exact JSON format:
{{
    "name": "Location name",
    "description": "Detailed description of the location",
    "type": "city|forest|dungeon|castle|etc",
    "climate": "Climate or weather patterns",
    "notable_features": ["List of interesting features or landmarks"],
    "inhabitants": ["Types of creatures or people found here"],
    "dangers": ["Potential threats or hazards"],
    "resources": ["Available resources or materials"],
    "connections": ["Connected locations or travel routes"],
    "significance": "Why this location is important",
    "atmosphere": "Mood or feeling of the place",
    "confidence": 0.85
}}

If multiple locations are found, return an array of location objects.
Return empty object {{}} if no clear location information found."""

        try:
            model = self.get_best_analysis_model("analysis")
            log_model_interaction("location_extraction", model, len(prompt), 0)
            
            # Initialize adapter if needed
            if model not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model)
                if not success:
                    raise Exception(f"Failed to initialize adapter for model: {model}")
            
            adapter = self.model_manager.adapters.get(model)
            if not adapter:
                raise Exception(f"No adapter available for model: {model}")
            
            response = await adapter.generate_response(prompt)
            
            # Log actual response length
            log_model_interaction("location_extraction", model, len(prompt), len(response))
            
            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully extracted location data: {result.get('name', 'multiple/unknown')}")
                return result
            except json.JSONDecodeError:
                log_warning("Failed to parse location extraction JSON, attempting cleanup")
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    log_error("No valid JSON found in location extraction response")
                    return {}
                    
        except Exception as e:
            log_error(f"Location extraction failed: {e}")
            return {}

    async def extract_lore_data(self, content: str) -> Dict[str, Any]:
        """Extract world-building and lore information from raw text content."""
        log_info(f"Extracting lore data from content ({len(content)} chars)")
        
        prompt = f"""Analyze this text and extract world-building/lore information. Return ONLY valid JSON.

Text: {content}

Extract lore details in this exact JSON format:
{{
    "title": "Name or title of this lore element",
    "category": "history|religion|magic|culture|politics|etc",
    "description": "Detailed explanation of this lore element", 
    "time_period": "When this occurred or applies",
    "key_figures": ["Important people involved"],
    "locations": ["Places where this is relevant"],
    "significance": "Why this is important to the world",
    "related_events": ["Connected historical events"],
    "cultural_impact": "How this affects society or culture",
    "mysteries": ["Unexplained aspects or secrets"],
    "source": "Origin or authority of this knowledge",
    "confidence": 0.85
}}

If multiple lore elements are found, return an array of lore objects.
Return empty object {{}} if no clear lore information found."""

        try:
            model = self.get_best_analysis_model("analysis")
            log_model_interaction("lore_extraction", model, len(prompt), 0)
            
            # Initialize adapter if needed
            if model not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model)
                if not success:
                    raise Exception(f"Failed to initialize adapter for model: {model}")
            
            adapter = self.model_manager.adapters.get(model)
            if not adapter:
                raise Exception(f"No adapter available for model: {model}")
            
            response = await adapter.generate_response(prompt)
            
            # Log actual response length
            log_model_interaction("lore_extraction", model, len(prompt), len(response))
            
            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully extracted lore data: {result.get('title', 'multiple/unknown')}")
                return result
            except json.JSONDecodeError:
                log_warning("Failed to parse lore extraction JSON, attempting cleanup")
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    log_error("No valid JSON found in lore extraction response")
                    return {}
                    
        except Exception as e:
            log_error(f"Lore extraction failed: {e}")
            return {}

    async def analyze_content_category(self, content: str) -> Dict[str, Any]:
        """Determine the primary category and metadata for content."""
        log_info(f"Analyzing content category ({len(content)} chars)")
        
        prompt = f"""Analyze this text and categorize it for story import. Return ONLY valid JSON.

Text: {content}

Determine the content category in this exact JSON format:
{{
    "primary_category": "character|location|lore|narrative|dialogue|description",
    "secondary_categories": ["Additional relevant categories"],
    "confidence": 0.85,
    "genre_indicators": ["fantasy|sci-fi|modern|historical|etc"],
    "tone": "dark|light|serious|humorous|epic|intimate|etc",
    "complexity": "simple|moderate|complex",
    "content_type": "worldbuilding|character_development|plot|background|etc",
    "suggested_templates": ["List of template files that would work for this content"],
    "key_themes": ["Major themes present in the content"],
    "target_audience": "general|young_adult|adult|mature",
    "processing_priority": "high|medium|low"
}}"""

        try:
            model = self.get_best_analysis_model("analysis")
            
            # Warn if using mock adapter for real content analysis
            if model == "mock":
                log_warning("Using mock adapter for content category analysis - results will be simulated!")
            
            log_model_interaction("category_analysis", model, len(prompt), 0)
            
            # Initialize adapter if needed
            if model not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model)
                if not success:
                    raise Exception(f"Failed to initialize adapter for model: {model}")
            
            adapter = self.model_manager.adapters.get(model)
            if not adapter:
                raise Exception(f"No adapter available for model: {model}")
            
            response = await adapter.generate_response(prompt)
            
            # Log actual response length
            log_model_interaction("category_analysis", model, len(prompt), len(response))
            
            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully analyzed content category: {result.get('primary_category', 'unknown')}")
                return result
            except json.JSONDecodeError:
                log_warning("Failed to parse category analysis JSON, attempting cleanup")
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    log_error("No valid JSON found in category analysis response")
                    return {"primary_category": "unknown", "confidence": 0.0}
                    
        except Exception as e:
            log_error(f"Category analysis failed: {e}")
            return {"primary_category": "unknown", "confidence": 0.0}

    async def generate_import_metadata(self, all_content: List[str], storypack_name: str) -> Dict[str, Any]:
        """Generate metadata for the entire storypack based on all content."""
        log_info(f"Generating import metadata for storypack: {storypack_name}")
        
        # Combine content samples for analysis
        combined_content = "\n\n---\n\n".join(all_content[:5])  # Use first 5 pieces
        
        prompt = f"""Analyze these story materials and generate comprehensive metadata. Return ONLY valid JSON.

Storypack Name: {storypack_name}

Content Samples:
{combined_content}

Generate metadata in this exact JSON format:
{{
    "title": "Suggested story title",
    "genre": "Primary genre classification",
    "subgenres": ["Additional genre elements"],
    "setting": "Time period and world type",
    "tone": "Overall story tone and mood",
    "themes": ["Major themes present"],
    "target_audience": "Intended audience",
    "content_rating": "G|PG|PG-13|R",
    "estimated_length": "short|medium|long|epic",
    "complexity_level": "beginner|intermediate|advanced",
    "key_elements": ["Most important story elements"],
    "recommended_models": ["LLM models that would work well"],
    "content_warnings": ["Any content that might need warnings"],
    "story_focus": "character_driven|plot_driven|world_building|etc",
    "narrative_style": "first_person|third_person|multiple_pov|etc",
    "confidence": 0.85
}}"""

        try:
            model = self.get_best_analysis_model("analysis")
            log_model_interaction("metadata_generation", model, len(prompt), 0)
            
            # Initialize adapter if needed
            if model not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model)
                if not success:
                    raise Exception(f"Failed to initialize adapter for model: {model}")
            
            adapter = self.model_manager.adapters.get(model)
            if not adapter:
                raise Exception(f"No adapter available for model: {model}")
            if not adapter:
                raise Exception(f"No adapter available for model: {model}")
            
            response = await adapter.generate_response(prompt)
            
            # Log actual response length
            log_model_interaction("metadata_generation", model, len(prompt), len(response))
            
            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully generated metadata for: {storypack_name}")
                return result
            except json.JSONDecodeError:
                log_warning("Failed to parse metadata JSON, attempting cleanup")
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    log_error("No valid JSON found in metadata response")
                    return {"title": storypack_name, "confidence": 0.0}
                    
        except Exception as e:
            log_error(f"Metadata generation failed: {e}")
            return {"title": storypack_name, "confidence": 0.0}
    
    async def analyze_imported_content(self, content: str, content_name: str, analysis_type: str = "general") -> Dict[str, Any]:
        """
        Analyze imported content for storypack processing.
        
        Args:
            content: The content to analyze
            content_name: Human-readable name for the content
            analysis_type: Type of analysis to perform
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            log_info(f"Analyzing imported content: {content_name} ({len(content)} chars)")
            
            # Get the best model for this analysis
            best_model = self.get_best_analysis_model(analysis_type)
            if not best_model:
                log_warning("No suitable model available for content analysis")
                return {
                    "success": False,
                    "error": "No AI model available",
                    "basic_analysis": self._basic_content_analysis(content)
                }
            
            # Analyze content category
            category_analysis = await self.analyze_content_category(content)
            
            # Extract characters (if any)
            characters = await self.extract_characters(content, content_name)
            
            # Basic structure analysis
            structure = self._analyze_content_structure(content)
            
            result = {
                "success": True,
                "content_name": content_name,
                "analysis_type": analysis_type,
                "model_used": best_model,
                "category_analysis": category_analysis,
                "characters": characters,
                "structure": structure,
                "complexity": "advanced" if len(characters) > 0 else "basic",
                "word_count": len(content.split()),
                "char_count": len(content)
            }
            
            log_info(f"Content analysis complete for {content_name}: {len(characters)} characters found")
            return result
            
        except Exception as e:
            log_error(f"Error analyzing imported content {content_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "content_name": content_name,
                "basic_analysis": self._basic_content_analysis(content)
            }
    
    def _basic_content_analysis(self, content: str) -> Dict[str, Any]:
        """Provide basic content analysis without AI."""
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
    
    def _analyze_content_structure(self, content: str) -> Dict[str, Any]:
        """Analyze the structure of content."""
        lines = content.split('\n')
        
        structure = {
            "total_lines": len(lines),
            "non_empty_lines": len([l for l in lines if l.strip()]),
            "paragraphs": len([l for l in lines if l.strip() == ""]) + 1,
            "has_sections": any(line.strip().startswith('#') for line in lines),
            "average_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0
        }
        
        return structure

    async def extract_characters(self, content: str, content_name: str) -> List[Dict[str, Any]]:
        """
        Extract characters from content for import analysis.
        
        Args:
            content: The content to analyze
            content_name: Human-readable name for the content
            
        Returns:
            List of character dictionaries
        """
        try:
            # Use existing character extraction method
            character_data = await self.extract_character_data(content)
            
            # Convert to list format if it's a single character
            if isinstance(character_data, dict) and character_data:
                # Check if it's a single character object or empty
                if "name" in character_data:
                    return [character_data]
                else:
                    return []
            elif isinstance(character_data, list):
                return character_data
            else:
                return []
                
        except Exception as e:
            log_error(f"Error extracting characters from {content_name}: {e}")
            return []

    def _suggest_model_improvements(self, content_type: str, unsuitable_models: List[tuple], fallback_models: List[tuple]):
        """Suggest improvements to the user for better model selection."""
        try:
            suggestions = []
            
            # Analyze why models were unsuitable
            code_models = [name for name, score, reason in unsuitable_models if "code-focused" in reason]
            small_models = [name for name, score, reason in unsuitable_models if "small model" in reason]
            
            if code_models:
                suggestions.append(f"Consider disabling code-focused models for content analysis: {', '.join(code_models)}")
            
            if small_models:
                suggestions.append(f"Small models detected ({', '.join(small_models)}) - consider using larger variants")
            
            # Check for Ollama models that could be pulled
            self._check_ollama_alternatives(content_type, suggestions)
            
            if suggestions:
                log_warning("Model Selection Suggestions:")
                for i, suggestion in enumerate(suggestions, 1):
                    log_warning(f"  {i}. {suggestion}")
                    
        except Exception as e:
            log_error(f"Error generating model suggestions: {e}")

    def _check_ollama_alternatives(self, content_type: str, suggestions: List[str]):
        """Check if better Ollama models could be pulled for this content type."""
        try:
            # Get Ollama configuration
            model_configs = self.model_manager.list_model_configs()
            ollama_config = model_configs.get("ollama", {})
            
            if ollama_config.get("type") == "ollama":
                # Suggest better models for specific content types
                content_recommendations = {
                    "analysis": ["llama3.1:8b-instruct", "mistral:7b-instruct", "qwen2:7b-instruct"],
                    "creative": ["llama3.1:8b", "mistral:7b", "gemma2:9b"],
                    "general": ["llama3.2:3b", "phi3:3.8b", "qwen2:1.5b"]
                }
                
                recommended = content_recommendations.get(content_type, content_recommendations["general"])
                suggestions.append(f"Consider pulling better Ollama models for {content_type}: {', '.join(recommended)}")
                suggestions.append("Use: ollama pull <model_name> to install")
                
        except Exception as e:
            log_error(f"Error checking Ollama alternatives: {e}")

    def _provide_model_guidance(self, content_type: str, unsuitable_models: List[tuple]):
        """Provide guidance when no suitable models are available."""
        try:
            log_warning("=" * 50)
            log_warning("MODEL SELECTION GUIDANCE")
            log_warning("=" * 50)
            log_warning("IMPORTANT: System will fall back to mock adapter which provides")
            log_warning("simulated responses only - NOT real AI functionality!")
            log_warning("")
            
            if unsuitable_models:
                log_warning("Available but unsuitable models:")
                for name, score, reason in unsuitable_models:
                    log_warning(f"  • {name}: {reason} (score: {score:.2f})")
            
            log_warning("\nRecommended actions:")
            
            if content_type == "analysis":
                log_warning("  1. Install analysis-focused models: ollama pull llama3.1:8b-instruct")
                log_warning("  2. Enable OpenAI/Anthropic adapters with API keys")
                log_warning("  3. Consider disabling code-focused models")
            elif content_type == "creative":
                log_warning("  1. Install creative models: ollama pull llama3.1:8b")
                log_warning("  2. Use larger model variants (13b+ recommended)")
            else:
                log_warning("  1. Install general-purpose models: ollama pull llama3.2:3b")
                log_warning("  2. Check model_registry.json configuration")
            
            log_warning("  3. Verify Ollama is running: http://localhost:11434")
            log_warning("  4. Check system resources and consider model optimization")
            log_warning("=" * 50)
            
        except Exception as e:
            log_error(f"Error providing model guidance: {e}")

    async def suggest_model_management_actions(self, content_type: str, system_resources: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Suggest model management actions based on system state and requirements.
        
        Args:
            content_type: The type of content being analyzed
            system_resources: Optional system resource information
            
        Returns:
            Dictionary with suggested actions
        """
        try:
            suggestions = {
                "actions": [],
                "priority": "medium",
                "resource_impact": "low",
                "estimated_improvement": "medium"
            }
            
            # Check current model availability
            working_models = await self.find_working_analysis_models(content_type)
            all_models = self.model_manager.list_model_configs()
            
            # Analyze system state and generate suggestions
            working_analysis_models = [m for m in working_models if m["name"] not in ["mock", "mock_image"]]
            
            if len(working_models) == 0:
                suggestions["priority"] = "high"
                suggestions["actions"].append({
                    "type": "install_model", 
                    "description": f"No working models found - install suitable model for {content_type} content",
                    "commands": self._get_install_commands(content_type)
                })
            
            elif len(working_analysis_models) == 0:
                # Only mock models available
                suggestions["priority"] = "high"
                suggestions["actions"].append({
                    "type": "replace_mock",
                    "description": "Only mock/test models available - install actual AI model",
                    "commands": self._get_install_commands(content_type)
                })
            
            elif len(working_analysis_models) < 2:
                # Very limited options - suggest more models
                suggestions["priority"] = "medium"
                suggestions["actions"].append({
                    "type": "expand_options",
                    "description": f"Limited model options for {content_type} - install additional models for redundancy",
                    "commands": self._get_install_commands(content_type)
                })
            
            # Check quality of available models
            if working_analysis_models:
                best_score = max(m["suitability_score"] for m in working_analysis_models)
                if best_score < 0.7:
                    suggestions["actions"].append({
                        "type": "improve_quality",
                        "description": f"Available models have low suitability scores (best: {best_score:.2f}) - consider better alternatives",
                        "commands": self._get_install_commands(content_type),
                        "current_best_score": best_score
                    })
            
            # Check for API key opportunities
            api_models = ["openai", "anthropic", "groq", "gemini"]
            missing_api_models = [name for name in api_models if name in all_models and not working_analysis_models]
            if missing_api_models and len(working_analysis_models) < 3:
                suggestions["actions"].append({
                    "type": "enable_api_models",
                    "description": "Enable cloud API models for better performance and reliability",
                    "models": missing_api_models,
                    "commands": [f"Add API key for {model}" for model in missing_api_models[:2]]
                })
            
            # Check for resource optimization opportunities
            if system_resources:
                memory_usage = system_resources.get("memory_percent", 0)
                if memory_usage > 80:
                    suggestions["actions"].append({
                        "type": "optimize_resources",
                        "description": "System memory usage high - consider model optimization",
                        "commands": ["Consider smaller model variants", "Enable model offloading"]
                    })
            
            # Check for unsuitable models that could be disabled
            unsuitable_models = []
            for model_name in all_models.keys():
                if all_models[model_name].get("enabled", True):
                    suitability = self._check_model_suitability(model_name, content_type)
                    if not suitability["suitable"] and "code-focused" in suitability.get("reason", ""):
                        unsuitable_models.append(model_name)
            
            if unsuitable_models:
                suggestions["actions"].append({
                    "type": "disable_unsuitable",
                    "description": f"Disable code-focused models for {content_type} tasks",
                    "models": unsuitable_models
                })
            
            return suggestions
            
        except Exception as e:
            log_error(f"Error generating model management suggestions: {e}")
            return {"actions": [], "priority": "low", "error": str(e)}

    def _get_install_commands(self, content_type: str) -> List[str]:
        """Get installation commands for recommended models."""
        commands = {
            "analysis": [
                "ollama pull llama3.1:8b-instruct",
                "ollama pull mistral:7b-instruct"
            ],
            "creative": [
                "ollama pull llama3.1:8b",
                "ollama pull mistral:7b"
            ],
            "general": [
                "ollama pull llama3.2:3b",
                "ollama pull phi3:3.8b"
            ]
        }
        
        return commands.get(content_type, commands["general"])
