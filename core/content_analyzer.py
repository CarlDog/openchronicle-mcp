"""
Content Analysis Engine for OpenChronicle with Dynamic Model Routing.
Uses dynamic model selection to optimize content analysis and routing.
"""

import json
import os
import sys
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, UTC
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_model_interaction, log_system_event, log_info, log_error, log_warning

# Optional transformer imports with graceful fallback
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
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
        self.nsfw_classifier = None
        self.sentiment_classifier = None
        self.emotion_classifier = None
        
        if self.use_transformers:
            self._initialize_transformers()
    
    def _initialize_transformers(self):
        """Initialize transformer-based classifiers."""
        try:
            log_info("Initializing transformer-based content classifiers...")
            
            # NSFW Content Detection
            # Using a general text classification model fine-tuned for content safety
            self.nsfw_classifier = pipeline(
                "text-classification",
                model="unitary/toxic-bert",
                device=0 if torch.cuda.is_available() else -1,
                truncation=True,
                max_length=512
            )
            
            # Sentiment Analysis
            self.sentiment_classifier = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=0 if torch.cuda.is_available() else -1,
                truncation=True,
                max_length=512
            )
            
            # Emotion Detection
            self.emotion_classifier = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                device=0 if torch.cuda.is_available() else -1,
                truncation=True,
                max_length=512
            )
            
            log_info("Transformer classifiers initialized successfully")
            
        except Exception as e:
            log_error(f"Failed to initialize transformer classifiers: {e}")
            self.use_transformers = False
            self.nsfw_classifier = None
            self.sentiment_classifier = None
            self.emotion_classifier = None
        
    def get_best_analysis_model(self, content_type: str = "general") -> str:
        """Get the best model for content analysis based on dynamic configuration."""
        # Get content routing from registry
        config = self.model_manager.config
        content_routing = config.get("content_routing", {})
        
        # Select model based on content type
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
            
        # Select the first available model (they're ordered by preference)
        selected = enabled_models[0]
        log_info(f"Selected {selected} for {content_type} content analysis")
        return selected
        
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
                if isinstance(nsfw_result, list):
                    nsfw_result = nsfw_result[0]
                
                # toxic-bert returns TOXIC or NOT_TOXIC
                analysis["transformer_results"]["nsfw"] = nsfw_result
                if nsfw_result["label"] == "TOXIC":
                    analysis["nsfw_score"] = nsfw_result["score"]
                else:
                    analysis["nsfw_score"] = 1.0 - nsfw_result["score"]
            
            # Sentiment Analysis
            if self.sentiment_classifier:
                sentiment_result = self.sentiment_classifier(user_input)
                if isinstance(sentiment_result, list):
                    sentiment_result = sentiment_result[0]
                
                analysis["transformer_results"]["sentiment"] = sentiment_result
                analysis["sentiment"] = sentiment_result["label"].lower()
                analysis["sentiment_score"] = sentiment_result["score"]
            
            # Emotion Detection
            if self.emotion_classifier:
                emotion_result = self.emotion_classifier(user_input)
                if isinstance(emotion_result, list):
                    emotion_result = emotion_result[0]
                
                analysis["transformer_results"]["emotion"] = emotion_result
                analysis["emotions"] = {
                    "primary_emotion": emotion_result["label"],
                    "confidence": emotion_result["score"]
                }
            
            # Calculate overall transformer confidence
            confidences = []
            for result in analysis["transformer_results"].values():
                if isinstance(result, dict) and "score" in result:
                    confidences.append(result["score"])
            
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
        
        # Add content flags
        content_flags = analysis.get("content_flags", {})
        for flag_name, flag_value in content_flags.items():
            if flag_value and flag_name != "emotional_intensity":
                flags.append({
                    "name": f"content_{flag_name}",
                    "value": flag_value,
                    "timestamp": datetime.now(UTC).isoformat()
                })
        
        # Add emotional intensity flag
        emotional_intensity = content_flags.get("emotional_intensity", "medium")
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
        content_flags = analysis.get("content_flags", {})
        token_priority = analysis.get("token_priority", "medium")
        
        # Default routing
        recommendation = {
            "adapter": "mock",  # Default to mock for safety
            "max_tokens": 1024,
            "temperature": 0.7,
            "content_filter": False
        }
        
        # Adjust based on content flags
        if content_flags.get("nsfw") or content_flags.get("mature_themes"):
            recommendation["content_filter"] = True
            recommendation["adapter"] = "ollama"  # Use local model for sensitive content
        
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

# For testing purposes
if __name__ == "__main__":
    # Initialize test
    logging.basicConfig(level=logging.INFO)
    from model_adapter import ModelManager
    
    model_manager = ModelManager()
    content_analyzer = ContentAnalyzer(model_manager)
    
    # Test the system
    test_content = "Lyra draws her sword and attacks the dragon"
    print(f"Analyzing: {test_content}")
    
    # Analyze content
    result = content_analyzer.analyze_content(test_content)
    print(f"Content analysis result: {result}")
    
    # Test content type detection
    content_type = content_analyzer.detect_content_type(test_content)
    print(f"Content type: {content_type}")
    
    # Test model recommendation
    model = content_analyzer.get_best_analysis_model(content_type)
    print(f"Recommended model: {model}")
    
    print("Content analysis system test complete!")
