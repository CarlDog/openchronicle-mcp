"""
Character extraction component for analyzing and extracting character data from content.

Date: August 4, 2025
Purpose: Extract character information from story content using LLM analysis
Part of: Phase 5A - Content Analysis Enhancement
Extracted from: core/content_analyzer.py (lines 1203-1268)
"""

import json
import re
from typing import Any

from openchronicle.shared.exceptions import ModelInitializationError
from openchronicle.shared.exceptions import ModelNotFoundError

# Import logging utilities
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_model_interaction
from openchronicle.shared.logging_system import log_warning

from ..shared.interfaces import ExtractionComponent


class CharacterExtractor(ExtractionComponent):
    """Extract character information from raw text content using LLM analysis."""

    def __init__(self, model_manager):
        super().__init__(model_manager)

    async def extract_data(self, content: str) -> dict[str, Any]:
        """Extract character information from raw text content."""

        def _raise_model_initialization_error(model):
            raise ModelInitializationError(f"Failed to initialize adapter for model: {model}")

        def _raise_model_not_found_error(model):
            raise ModelNotFoundError(f"No adapter available for model: {model}")

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
            model = self._get_best_analysis_model("analysis")
            log_model_interaction("character_extraction", model, len(prompt), 0)

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
            log_model_interaction("character_extraction", model, len(prompt), len(response))

            # Try to parse JSON response
            try:
                result = json.loads(response)
                log_info(f"Successfully extracted character data: {result.get('name', 'multiple/unknown')}")
            except json.JSONDecodeError:
                log_warning("Failed to parse character extraction JSON, attempting cleanup")
                # Try to extract JSON from response
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                log_error("No valid JSON found in character extraction response")
                return {}
            else:
                return result

        except ValueError as e:
            log_error(f"Invalid data format in character extraction: {e}")
            return {}
        except (ConnectionError, TimeoutError) as e:
            log_error(f"Network error during character extraction: {e}")
            return {}
        except Exception as e:
            log_error(f"Character extraction failed: {e}")
            return {}

    async def process(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Process content and extract character data."""
        return await self.extract_data(content)

    async def extract_characters(self, content: str, content_name: str) -> list[dict[str, Any]]:
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
            character_data = await self.extract_data(content)

            # Convert to list format if it's a single character
            if isinstance(character_data, dict) and character_data:
                # Check if it's a single character object or empty
                if "name" in character_data:
                    return [character_data]
                return []
            if isinstance(character_data, list):
                return character_data
        except ValueError as e:
            log_error(f"Invalid data format in character extraction from {content_name}: {e}")
            return []
        except (ConnectionError, TimeoutError) as e:
            log_error(f"Network error during character extraction from {content_name}: {e}")
            return []
        except Exception as e:
            log_error(f"Error extracting characters from {content_name}: {e}")
            return []
        else:
            return []

    def _get_best_analysis_model(self, content_type: str = "general") -> str:
        """Get the best model for analysis tasks."""
        # This would normally delegate to the model manager
        # For now, return a default model identifier
        return "default_analysis_model"
