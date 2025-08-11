"""
Content Analysis Orchestrator - Main coordination component for modular content analysis system.

Date: August 4, 2025
Purpose: Coordinate all content analysis components and provide unified interface
Part of: Phase 5A - Content Analysis Enhancement
Replaces: core/content_analyzer.py monolithic implementation
"""

from typing import Dict, List, Any, Optional
import asyncio

from .shared.interfaces import ContentAnalysisComponent
from .detection import ContentClassifier, KeywordDetector, TransformerAnalyzer
from .extraction import CharacterExtractor, LocationExtractor, LoreExtractor
from .routing import ModelSelector, ContentRouter, RecommendationEngine

# Import logging utilities
from src.openchronicle.shared.logging_system import (
    log_info,
    log_error,
    log_system_event,
)


class ContentAnalysisOrchestrator(ContentAnalysisComponent):
    """
    Main orchestrator for the modular content analysis system.

    Coordinates detection, extraction, and routing components to provide
    unified content analysis functionality that replaces the original
    monolithic ContentAnalyzer.
    """

    def __init__(self, model_manager, use_transformers: bool = True):
        super().__init__(model_manager)

        # Initialize all component modules
        self._initialize_components(use_transformers)

        log_info("Content Analysis Orchestrator initialized with modular components")

    def _initialize_components(self, use_transformers: bool):
        """Initialize all content analysis components."""
        # Detection components
        self.keyword_detector = KeywordDetector(self.model_manager)
        self.transformer_analyzer = TransformerAnalyzer(
            self.model_manager, use_transformers
        )
        self.content_classifier = ContentClassifier(
            self.model_manager, use_transformers
        )

        # Extraction components
        self.character_extractor = CharacterExtractor(self.model_manager)
        self.location_extractor = LocationExtractor(self.model_manager)
        self.lore_extractor = LoreExtractor(self.model_manager)

        # Routing components
        self.model_selector = ModelSelector(self.model_manager)
        self.content_router = ContentRouter(self.model_manager)
        self.recommendation_engine = RecommendationEngine(self.model_manager)

    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method - analyze content using all components.

        Args:
            content: Content to analyze
            context: Additional context for analysis

        Returns:
            Comprehensive analysis results
        """
        try:
            log_info(f"Starting comprehensive content analysis ({len(content)} chars)")

            # Step 1: Content Detection and Classification
            classification_result = await self._run_detection_analysis(content, context)

            # Step 2: Content Extraction (if requested)
            extraction_result = await self._run_extraction_analysis(content, context)

            # Step 3: Routing Recommendations
            routing_result = await self._run_routing_analysis(
                classification_result, context
            )

            # Step 4: Combine all results
            comprehensive_result = self._combine_analysis_results(
                classification_result, extraction_result, routing_result, content
            )

            log_system_event(
                "comprehensive_analysis_complete",
                f"Content type: {comprehensive_result.get('content_type')}, "
                f"Components used: {comprehensive_result.get('components_used')}",
            )

            return comprehensive_result

        except Exception as e:
            log_error(f"Content analysis orchestration failed: {e}")
            return self._create_error_result(str(e), content)

    async def _run_detection_analysis(
        self, content: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run all detection and classification components."""
        try:
            # Get detailed content classification
            classification = await self.content_classifier.process(content, context)

            # Add component metadata
            classification["detection_methods"] = []
            if self.content_classifier.keyword_detector:
                classification["detection_methods"].append("keyword")
            if self.content_classifier.transformer_analyzer.use_transformers:
                classification["detection_methods"].append("transformer")

            return classification

        except Exception as e:
            log_error(f"Detection analysis failed: {e}")
            # Fallback to keyword-only detection
            return await self.keyword_detector.process(content, context)

    async def _run_extraction_analysis(
        self, content: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run content extraction components if requested."""
        extraction_result = {}

        # Check if extraction is requested
        if context.get("extract_characters", False):
            try:
                extraction_result["characters"] = (
                    await self.character_extractor.extract_data(content)
                )
            except Exception as e:
                log_error(f"Character extraction failed: {e}")
                extraction_result["characters"] = {}

        if context.get("extract_locations", False):
            try:
                extraction_result["locations"] = (
                    await self.location_extractor.extract_data(content)
                )
            except Exception as e:
                log_error(f"Location extraction failed: {e}")
                extraction_result["locations"] = {}

        if context.get("extract_lore", False):
            try:
                extraction_result["lore"] = await self.lore_extractor.extract_data(
                    content
                )
            except Exception as e:
                log_error(f"Lore extraction failed: {e}")
                extraction_result["lore"] = {}

        return extraction_result

    async def _run_routing_analysis(
        self, classification_result: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run routing analysis components."""
        routing_result = {}

        try:
            # Get model selection recommendation
            model_selection = await self.model_selector.process(
                "", {"analysis": classification_result}
            )
            routing_result["model_selection"] = model_selection

            # Get detailed routing configuration
            routing_config = await self.content_router.process(
                "", {"analysis": classification_result}
            )
            routing_result["routing_config"] = routing_config

            # Get system recommendations if requested
            if context.get("include_recommendations", False):
                recommendations = await self.recommendation_engine.process(
                    "",
                    {
                        "analysis": classification_result,
                        "system_resources": context.get("system_resources"),
                    },
                )
                routing_result["recommendations"] = recommendations

        except Exception as e:
            log_error(f"Routing analysis failed: {e}")
            routing_result["error"] = str(e)

        return routing_result

    def _combine_analysis_results(
        self,
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        routing: Dict[str, Any],
        content: str,
    ) -> Dict[str, Any]:
        """Combine all analysis results into comprehensive response."""
        combined = {
            # Core classification results (maintain backward compatibility)
            "content_type": classification.get("content_type", "general"),
            "content_flags": classification.get("content_flags", []),
            "confidence": classification.get("confidence", 0.0),
            "analysis_method": classification.get("analysis_method", "keyword"),
            # Metadata
            "word_count": len(content.split()),
            "char_count": len(content),
            "components_used": self._get_components_used(
                classification, extraction, routing
            ),
            # Detailed component results
            "classification_details": classification,
            "extraction_results": extraction,
            "routing_results": routing,
            # System information
            "transformer_available": self.transformer_analyzer.use_transformers,
            "capabilities": self._get_system_capabilities(),
        }

        # Add transformer analysis if available
        if "transformer_analysis" in classification:
            combined["transformer_analysis"] = classification["transformer_analysis"]
            combined["sentiment"] = classification.get("sentiment", "neutral")
            combined["emotions"] = classification.get("emotions", {})

        return combined

    def _get_components_used(
        self,
        classification: Dict[str, Any],
        extraction: Dict[str, Any],
        routing: Dict[str, Any],
    ) -> List[str]:
        """Get list of components that were used in analysis."""
        components = []

        # Detection components
        if classification.get("detection_methods"):
            components.extend(
                [
                    f"detection_{method}"
                    for method in classification["detection_methods"]
                ]
            )

        # Extraction components
        if extraction.get("characters"):
            components.append("character_extraction")
        if extraction.get("locations"):
            components.append("location_extraction")
        if extraction.get("lore"):
            components.append("lore_extraction")

        # Routing components
        if routing.get("model_selection"):
            components.append("model_selection")
        if routing.get("routing_config"):
            components.append("routing_config")
        if routing.get("recommendations"):
            components.append("recommendations")

        return components

    def _get_system_capabilities(self) -> Dict[str, Any]:
        """Get current system capabilities."""
        return {
            "detection": {
                "keyword_analysis": True,
                "transformer_analysis": self.transformer_analyzer.use_transformers,
                "hybrid_classification": True,
            },
            "extraction": {
                "character_extraction": True,
                "location_extraction": True,
                "lore_extraction": True,
            },
            "routing": {
                "model_selection": True,
                "parameter_optimization": True,
                "safety_configuration": True,
                "system_recommendations": True,
            },
        }

    def _create_error_result(self, error_message: str, content: str) -> Dict[str, Any]:
        """Create error result with basic fallback analysis."""
        return {
            "content_type": "general",
            "content_flags": [],
            "confidence": 0.0,
            "analysis_method": "error_fallback",
            "word_count": len(content.split()),
            "char_count": len(content),
            "error": error_message,
            "components_used": ["error_fallback"],
        }

    # Backward compatibility methods
    def detect_content_type(self, content: str) -> Dict[str, Any]:
        """Backward compatibility method for content type detection."""
        try:
            # Run synchronous detection using the classification component
            result = asyncio.create_task(self.content_classifier.process(content, {}))
            return asyncio.get_event_loop().run_until_complete(result)
        except Exception as e:
            log_error(f"Backward compatibility detect_content_type failed: {e}")
            return self.keyword_detector.detect_content_type(content)

    def recommend_generation_model(self, analysis: Dict[str, Any]) -> str:
        """Backward compatibility method for model recommendation."""
        return self.model_selector.recommend_generation_model(analysis)

    def get_routing_recommendation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Backward compatibility method for routing recommendations."""
        return self.content_router.get_routing_recommendation(analysis)

    async def extract_character_data(self, content: str) -> Dict[str, Any]:
        """Backward compatibility method for character extraction."""
        return await self.character_extractor.extract_data(content)

    async def extract_location_data(self, content: str) -> Dict[str, Any]:
        """Backward compatibility method for location extraction."""
        return await self.location_extractor.extract_data(content)

    async def extract_lore_data(self, content: str) -> Dict[str, Any]:
        """Backward compatibility method for lore extraction."""
        return await self.lore_extractor.extract_data(content)

    def check_transformer_connectivity(self) -> Dict[str, Any]:
        """Check transformer connectivity and capabilities."""
        return self.transformer_analyzer.check_transformer_connectivity()

    def get_analysis_capabilities(self) -> Dict[str, Any]:
        """Get comprehensive analysis capabilities."""
        return {
            "content_classifier": self.content_classifier.get_analysis_capabilities(),
            "extraction_capabilities": {
                "character_extraction": True,
                "location_extraction": True,
                "lore_extraction": True,
            },
            "routing_capabilities": {
                "model_selection": True,
                "parameter_optimization": True,
                "safety_configuration": True,
            },
            "transformer_status": self.check_transformer_connectivity(),
            "system_capabilities": self._get_system_capabilities(),
        }
