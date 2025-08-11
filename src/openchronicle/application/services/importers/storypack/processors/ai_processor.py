from openchronicle.domain.ports.storypack_port import IStorypackProcessorPort\n\n#!/usr/bin/env python3
"""
OpenChronicle AI Processor

Focused component for AI-powered content analysis and processing.
Handles model integration and content intelligence.
"""

from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_system_event
from openchronicle.shared.logging_system import log_warning





class AIProcessor(IAIProcessor):
    """Handles AI-powered content analysis using OpenChronicle's model management."""

    def __init__(self):
        """Initialize the AI processor."""
        self.logger = get_logger()
        self.content_analyzer = None
        self.available_models = []
        self.is_initialized = False

    async def initialize(self) -> bool:
        """Initialize AI capabilities."""
        try:
            # Import here to avoid circular dependencies
            from openchronicle.infrastructure.content import (
                ContentAnalysisOrchestrator,
            )

            self.content_analyzer = ContentAnalysisOrchestrator()

            # Test capabilities
            success, messages = await self.test_capabilities()
            self.is_initialized = success

            if success:
                log_system_event(
                    "ai_processor",
                    "AI capabilities initialized",
                    {
                        "analyzer_available": True,
                        "models_tested": len(self.available_models),
                    },
                )
            else:
                log_warning("AI processor initialization completed with limitations")

            return success

        except Exception as e:
            log_error(f"Failed to initialize AI processor: {e}")
            self.is_initialized = False
            return False

    async def analyze_content(
        self, content: str, file_path: Path, context: ImportContext
    ) -> dict[str, Any]:
        """
        Analyze content using AI capabilities.

        Args:
            content: Text content to analyze
            file_path: Path to the source file
            context: Import context information

        Returns:
            Dictionary containing AI analysis results
        """
        if not self.is_initialized or not self.content_analyzer:
            return {
                "status": "ai_unavailable",
                "error": "AI processor not initialized or unavailable",
            }

        try:
            # Determine content category for targeted analysis
            category = self._determine_content_category(file_path, content)

            # Run AI analysis
            analysis_result = await self.content_analyzer.analyze_imported_content(
                content=content,
                source_name=file_path.name,
                context_id=f"import_{context.storypack_name}_{file_path.stem}",
            )

            if not analysis_result:
                return {
                    "status": "analysis_failed",
                    "error": "AI analysis returned no results",
                }

            # Enhance with category-specific analysis
            enhanced_result = await self._enhance_category_analysis(
                analysis_result, category, content
            )

            log_system_event(
                "ai_processor",
                "Content analysis completed",
                {
                    "file_path": str(file_path),
                    "content_length": len(content),
                    "category": category,
                    "entities_found": len(enhanced_result.get("entities", {})),
                },
            )

            return enhanced_result

        except Exception as e:
            log_error(f"AI content analysis failed for {file_path}: {e}")
            return {
                "status": "analysis_error",
                "error": str(e),
                "file_path": str(file_path),
            }

    async def extract_entities(
        self, content: str, entity_type: str
    ) -> list[dict[str, Any]]:
        """
        Extract specific entities from content.

        Args:
            content: Text content to analyze
            entity_type: Type of entities to extract ('characters', 'locations', etc.)

        Returns:
            List of extracted entities with metadata
        """
        if not self.is_initialized or not self.content_analyzer:
            return []

        try:
            # Use content analyzer's entity extraction capabilities
            analysis = await self.content_analyzer.analyze_imported_content(
                content=content,
                source_name=f"entity_extraction_{entity_type}",
                context_id=f"extract_{entity_type}",
            )

            if not analysis:
                return []

            # Extract entities of the requested type
            entities = analysis.get(entity_type, [])

            # Ensure entities are in the expected format
            formatted_entities = []
            for entity in entities:
                if isinstance(entity, str):
                    formatted_entities.append(
                        {
                            "name": entity,
                            "type": entity_type,
                            "confidence": 0.8,  # Default confidence for string entities
                            "source": "ai_extraction",
                        }
                    )
                elif isinstance(entity, dict):
                    formatted_entities.append(
                        {
                            "name": entity.get("name", "Unknown"),
                            "type": entity_type,
                            "confidence": entity.get("confidence", 0.8),
                            "description": entity.get("description", ""),
                            "attributes": entity.get("attributes", {}),
                            "source": "ai_extraction",
                        }
                    )

            return formatted_entities

        except Exception as e:
            log_error(f"Entity extraction failed for type {entity_type}: {e}")
            return []

    async def classify_content_type(self, content: str) -> dict[str, Any]:
        """
        Classify content type using AI analysis.

        Args:
            content: Text content to classify

        Returns:
            Dictionary containing classification results
        """
        if not self.is_initialized or not self.content_analyzer:
            return {"type": "unknown", "confidence": 0.0, "reason": "AI unavailable"}

        try:
            # Run classification analysis
            analysis = await self.content_analyzer.analyze_imported_content(
                content=content,
                source_name="content_classification",
                context_id="classify_content",
            )

            if not analysis:
                return {
                    "type": "unknown",
                    "confidence": 0.0,
                    "reason": "Analysis failed",
                }

            # Extract classification from analysis
            content_type = analysis.get("content_type", "unknown")
            confidence = analysis.get("confidence", 0.5)

            # Additional classification logic based on analysis results
            if analysis.get("characters"):
                if content_type == "unknown":
                    content_type = "character_focused"
                    confidence = 0.7

            if analysis.get("locations"):
                if content_type == "unknown":
                    content_type = "location_focused"
                    confidence = 0.7

            if analysis.get("narrative_elements"):
                if content_type == "unknown":
                    content_type = "narrative"
                    confidence = 0.6

            return {
                "type": content_type,
                "confidence": confidence,
                "entities_detected": {
                    "characters": len(analysis.get("characters", [])),
                    "locations": len(analysis.get("locations", [])),
                    "themes": len(analysis.get("themes", [])),
                },
                "complexity": analysis.get("complexity", "medium"),
            }

        except Exception as e:
            log_error(f"Content classification failed: {e}")
            return {"type": "unknown", "confidence": 0.0, "reason": f"Error: {e!s}"}

    async def test_capabilities(self) -> tuple[bool, list[str]]:
        """
        Test AI capabilities and return status.

        Returns:
            Tuple of (success, list_of_messages)
        """
        messages = []

        try:
            if not self.content_analyzer:
                from openchronicle.infrastructure.content import (
                    ContentAnalysisOrchestrator,
                )

                self.content_analyzer = ContentAnalysisOrchestrator()

            # Test with a simple content sample
            test_content = """
            # The Brave Knight

            Sir Marcus was a noble knight who lived in the castle of Eldridge.
            He was known for his courage and his magical sword, Lightbringer.

            **Personality:** Brave, honorable, sometimes reckless
            **Appearance:** Tall, brown hair, wearing silver armor
            """

            # Test basic analysis
            analysis = await self.content_analyzer.analyze_imported_content(
                content=test_content,
                source_name="ai_capability_test",
                context_id="test_capabilities",
            )

            if analysis:
                messages.append("✓ Basic content analysis working")

                # Check for character detection
                if analysis.get("characters"):
                    messages.append(
                        f"✓ Character detection working ({len(analysis['characters'])} found)"
                    )
                else:
                    messages.append("⚠ Character detection limited")

                # Check for other features
                if analysis.get("locations"):
                    messages.append(
                        f"✓ Location detection working ({len(analysis['locations'])} found)"
                    )

                if analysis.get("themes"):
                    messages.append(
                        f"✓ Theme detection working ({len(analysis['themes'])} found)"
                    )

                self.available_models = [
                    "content_analyzer"
                ]  # Simplified model tracking
                return True, messages
            messages.append("✗ AI analysis returned no results")
            return False, messages

        except Exception as e:
            messages.append(f"✗ AI capability test failed: {e!s}")
            return False, messages

    def _determine_content_category(self, file_path: Path, content: str) -> str:
        """Determine content category for targeted analysis."""
        # Check file path for category hints
        path_lower = str(file_path).lower()

        if any(keyword in path_lower for keyword in ["character", "people", "npc"]):
            return "characters"
        if any(keyword in path_lower for keyword in ["location", "place", "setting"]):
            return "locations"
        if any(keyword in path_lower for keyword in ["lore", "history", "background"]):
            return "lore"
        if any(keyword in path_lower for keyword in ["story", "narrative", "scene"]):
            return "narrative"

        # Check content for category indicators
        content_lower = content.lower()

        # Character indicators
        if any(
            indicator in content_lower
            for indicator in ["age:", "personality:", "appearance:", "background:"]
        ):
            return "characters"

        # Location indicators
        if any(
            indicator in content_lower
            for indicator in ["geography:", "climate:", "population:", "description:"]
        ):
            return "locations"

        # Narrative indicators
        if any(
            indicator in content_lower
            for indicator in ['"', "said", "walked", "looked"]
        ):
            return "narrative"

        return "general"

    async def _enhance_category_analysis(
        self, base_analysis: dict[str, Any], category: str, content: str
    ) -> dict[str, Any]:
        """Enhance analysis results based on content category."""
        enhanced = base_analysis.copy()
        enhanced["category"] = category
        enhanced["enhancement_applied"] = True

        try:
            if category == "characters" and enhanced.get("characters"):
                # Enhanced character analysis
                for character in enhanced["characters"]:
                    if isinstance(character, dict):
                        # Add character-specific attributes if missing
                        if "attributes" not in character:
                            character[
                                "attributes"
                            ] = self._extract_character_attributes(content)

            elif category == "locations" and enhanced.get("locations"):
                # Enhanced location analysis
                for location in enhanced["locations"]:
                    if isinstance(location, dict):
                        # Add location-specific attributes if missing
                        if "attributes" not in location:
                            location["attributes"] = self._extract_location_attributes(
                                content
                            )

            # Add category-specific confidence scoring
            enhanced["category_confidence"] = self._calculate_category_confidence(
                category, enhanced
            )

        except Exception as e:
            log_warning(f"Enhancement failed for category {category}: {e}")
            enhanced["enhancement_error"] = str(e)

        return enhanced

    def _extract_character_attributes(self, content: str) -> dict[str, Any]:
        """Extract character-specific attributes from content."""
        attributes = {}
        content_lower = content.lower()

        # Look for common character attributes
        if "age:" in content_lower:
            attributes["has_age_info"] = True
        if "personality:" in content_lower:
            attributes["has_personality_info"] = True
        if "appearance:" in content_lower:
            attributes["has_appearance_info"] = True
        if "background:" in content_lower:
            attributes["has_background_info"] = True

        return attributes

    def _extract_location_attributes(self, content: str) -> dict[str, Any]:
        """Extract location-specific attributes from content."""
        attributes = {}
        content_lower = content.lower()

        # Look for common location attributes
        if any(word in content_lower for word in ["geography", "terrain", "landscape"]):
            attributes["has_geography_info"] = True
        if any(word in content_lower for word in ["climate", "weather", "season"]):
            attributes["has_climate_info"] = True
        if any(
            word in content_lower for word in ["population", "inhabitants", "people"]
        ):
            attributes["has_population_info"] = True

        return attributes

    def _calculate_category_confidence(
        self, category: str, analysis: dict[str, Any]
    ) -> float:
        """Calculate confidence score for category classification."""
        base_confidence = 0.5

        # Boost confidence based on relevant entities found
        if category == "characters" and analysis.get("characters"):
            base_confidence += min(0.4, len(analysis["characters"]) * 0.1)
        elif category == "locations" and analysis.get("locations"):
            base_confidence += min(0.4, len(analysis["locations"]) * 0.1)
        elif category == "narrative" and analysis.get("themes"):
            base_confidence += min(0.3, len(analysis["themes"]) * 0.1)

        return min(1.0, base_confidence)
