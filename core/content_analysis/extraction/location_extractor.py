"""
Location extraction component for analyzing and extracting location data from content.

Date: August 4, 2025
Purpose: Extract location information from story content using LLM analysis
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 1269-1335)
"""

import json
import re
from typing import Dict, List, Any

from ..shared.interfaces import ExtractionComponent

# Import logging utilities
from utilities.logging_system import log_info, log_warning, log_error, log_model_interaction

class LocationExtractor(ExtractionComponent):
    """Extract location information from raw text content using LLM analysis."""
    
    def __init__(self, model_manager):
        super().__init__(model_manager)
    
    async def extract_data(self, content: str) -> Dict[str, Any]:
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
            model = self._get_best_analysis_model("analysis")
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
    
    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process content and extract location data."""
        return await self.extract_data(content)
    
    def _get_best_analysis_model(self, content_type: str = "general") -> str:
        """Get the best model for analysis tasks."""
        # This would normally delegate to the model manager
        # For now, return a default model identifier
        return "default_analysis_model"
