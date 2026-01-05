"""
Lore extraction component for analyzing and extracting world-building data from content.

Date: August 4, 2025
Purpose: Extract lore and world-building information from story content using LLM analysis
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 1336-1398)
"""

import json
import re
from typing import Any

from openchronicle.shared.exceptions import ModelInitializationError
from openchronicle.shared.exceptions import ModelNotFoundError
from openchronicle.shared.logging_system import log_error

# Import logging utilities
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_model_interaction
from openchronicle.shared.logging_system import log_warning

from ..shared.interfaces import ExtractionComponent


class LoreExtractor(ExtractionComponent):
    """Extract world-building and lore information from raw text content using LLM analysis."""

    def __init__(self, model_manager):
        super().__init__(model_manager)

    async def extract_data(self, content: str) -> dict[str, Any]:
        """Extract world-building and lore information from raw text content."""

        def _raise_model_initialization_error(model):
            raise ModelInitializationError(f"Failed to initialize adapter for model: {model}")

        def _raise_model_not_found_error(model):
            raise ModelNotFoundError(f"No adapter available for model: {model}")

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
            model = self._get_best_analysis_model("analysis")
            log_model_interaction("lore_extraction", model, len(prompt), 0)

            # Initialize adapter if needed
            if model not in self.model_manager.adapters:
                success = await self.model_manager.initialize_adapter(model)
                if not success:
                    _raise_model_initialization_error(model)

            adapter = self.model_manager.adapters.get(model)
            if not adapter:
                _raise_model_not_found_error(model)

            response = await adapter.generate_response(prompt)

            # Log actual response length
            log_model_interaction("lore_extraction", model, len(prompt), len(response))

            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully extracted lore data: {result.get('title', 'multiple/unknown')}")
            except json.JSONDecodeError:
                log_warning("Failed to parse lore extraction JSON, attempting cleanup")
                # Try to extract JSON from response
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                log_error("No valid JSON found in lore extraction response")
                return {}
            else:
                return result

        except Exception as e:
            log_error(f"Lore extraction failed: {e}")
            return {}

    async def process(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Process content and extract lore data."""
        return await self.extract_data(content)

    def _get_best_analysis_model(self, content_type: str = "general") -> str:
        """Get the best model for analysis tasks."""
        # This would normally delegate to the model manager
        # For now, return a default model identifier
        return "default_analysis_model"
