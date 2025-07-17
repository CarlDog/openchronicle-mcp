"""
Content Analysis Engine for OpenChronicle.
Uses local LLM to analyze, classify, and optimize story content before main LLM processing.
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from core.model_adapter import model_manager

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_model_interaction, log_system_event, log_info, log_error

class ContentAnalyzer:
    """Analyzes user input and story content to optimize context and routing."""
    
    def __init__(self):
        self.analysis_cache = {}
        
    def get_analyzer_adapter(self):
        """Get the configured analyzer adapter."""
        # Import here to avoid circular imports
        from .model_adapter import model_manager
        return model_manager.config.get("analyzer_adapter", "mock")
        
    async def analyze_user_input(self, user_input: str, story_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user input to extract intent, content type, and required context.
        """
        analysis_prompt = self._build_analysis_prompt(user_input, story_context)
        
        try:
            # Use local LLM for fast analysis
            analyzer_adapter = self.get_analyzer_adapter()
            analysis_response = await model_manager.generate_response(
                analysis_prompt,
                adapter_name=analyzer_adapter,
                max_tokens=512,
                temperature=0.1  # Low temperature for consistent analysis
            )
            
            # Parse the structured analysis
            analysis = self._parse_analysis_response(analysis_response)
            
            # Cache the analysis
            cache_key = hash(user_input + str(story_context.get("story_id", "")))
            self.analysis_cache[cache_key] = analysis
            
            return analysis
            
        except Exception as e:
            log_error(f"⚠️ Content analysis failed: {e}")
            # Fallback to basic analysis
            return self._fallback_analysis(user_input)
    
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
        
        # Get all available canon files
        canon_files = [f[:-4] for f in os.listdir(canon_dir) if f.endswith(".txt")]
        
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
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Add entity flags
        entities = analysis.get("entities", {})
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                if entity:  # Skip empty entities
                    flags.append({
                        "name": f"{entity_type}_{entity.lower().replace(' ', '_')}",
                        "value": True,
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        # Add content flags
        content_flags = analysis.get("content_flags", {})
        for flag_name, flag_value in content_flags.items():
            if flag_value and flag_name != "emotional_intensity":
                flags.append({
                    "name": f"content_{flag_name}",
                    "value": flag_value,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # Add emotional intensity flag
        emotional_intensity = content_flags.get("emotional_intensity", "medium")
        flags.append({
            "name": "emotional_intensity",
            "value": emotional_intensity,
            "timestamp": datetime.utcnow().isoformat()
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

# Global content analyzer instance
content_analyzer = ContentAnalyzer()
