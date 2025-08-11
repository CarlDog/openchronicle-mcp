"""
OpenChronicle Core - Response Planner

Plans intelligent responses based on context analysis.
Extracted from IntelligentResponseEngine for modular architecture.

Author: OpenChronicle Development Team
"""

import random
from typing import Any

from ..shared import NarrativeComponent
from ..shared import ValidationResult
from .response_models import ContextAnalysis
from .response_models import ContextQuality
from .response_models import ResponseComplexity
from .response_models import ResponsePlan
from .response_models import ResponseStrategy


class ResponsePlanner(NarrativeComponent):
    """
    Plans intelligent responses based on context analysis.

    Responsible for:
    - Selecting appropriate response strategy
    - Determining response complexity and style
    - Planning key points and content focus
    - Setting quality targets for response generation
    """

    def __init__(self, config: dict[str, Any] = None):
        super().__init__("ResponsePlanner", config)

        # Strategy selection weights
        self.strategy_weights = (
            config.get(
                "strategy_weights",
                {
                    ResponseStrategy.BALANCED: 1.0,
                    ResponseStrategy.CREATIVE: 0.8,
                    ResponseStrategy.ADAPTIVE: 1.2,
                    ResponseStrategy.CONTEXTUAL: 1.1,
                    ResponseStrategy.SUPPORTIVE: 0.9,
                    ResponseStrategy.ANALYTICAL: 0.7,
                },
            )
            if config
            else {
                ResponseStrategy.BALANCED: 1.0,
                ResponseStrategy.CREATIVE: 0.8,
                ResponseStrategy.ADAPTIVE: 1.2,
                ResponseStrategy.CONTEXTUAL: 1.1,
                ResponseStrategy.SUPPORTIVE: 0.9,
                ResponseStrategy.ANALYTICAL: 0.7,
            }
        )

        # Quality targets by complexity
        self.quality_targets = (
            config.get(
                "quality_targets",
                {
                    ResponseComplexity.SIMPLE: {"coherence": 0.8, "creativity": 0.6},
                    ResponseComplexity.MODERATE: {"coherence": 0.85, "creativity": 0.7},
                    ResponseComplexity.COMPLEX: {"coherence": 0.9, "creativity": 0.8},
                    ResponseComplexity.ELABORATE: {
                        "coherence": 0.95,
                        "creativity": 0.85,
                    },
                },
            )
            if config
            else {
                ResponseComplexity.SIMPLE: {"coherence": 0.8, "creativity": 0.6},
                ResponseComplexity.MODERATE: {"coherence": 0.85, "creativity": 0.7},
                ResponseComplexity.COMPLEX: {"coherence": 0.9, "creativity": 0.8},
                ResponseComplexity.ELABORATE: {"coherence": 0.95, "creativity": 0.85},
            }
        )

    def process(self, data: dict[str, Any]) -> ResponsePlan:
        """Plan a response based on context analysis."""
        try:
            context_analysis = data.get("context_analysis")
            preferences = data.get("preferences", {})

            if not context_analysis:
                raise ValueError("Context analysis required for response planning")

            # Select response strategy
            strategy = self._select_response_strategy(context_analysis, preferences)

            # Determine response complexity
            complexity = self._determine_response_complexity(
                context_analysis, preferences
            )

            # Plan content focus
            content_focus = self._plan_content_focus(context_analysis, strategy)

            # Select tone and style
            tone = self._select_tone(context_analysis, strategy)
            style_guides = self._select_style_guides(context_analysis, complexity)

            # Estimate response length
            estimated_length = self._estimate_response_length(complexity, content_focus)

            # Identify key points to address
            key_points = self._identify_key_points(context_analysis, strategy)

            # Plan context integration
            context_integration = self._plan_context_integration(context_analysis)

            # Set quality targets
            quality_targets = self._set_quality_targets(complexity, strategy)

            return ResponsePlan(
                strategy=strategy,
                complexity=complexity,
                content_focus=content_focus,
                tone=tone,
                style_guides=style_guides,
                estimated_length=estimated_length,
                key_points=key_points,
                context_integration=context_integration,
                quality_targets=quality_targets,
            )

        except Exception as e:
            # Return safe default plan
            return ResponsePlan(
                strategy=ResponseStrategy.CONSERVATIVE,
                complexity=ResponseComplexity.SIMPLE,
                content_focus="general",
                tone="neutral",
                estimated_length=100,
                key_points=[f"Planning error: {e!s}"],
                context_integration={},
                quality_targets={"coherence": 0.7, "creativity": 0.5},
            )

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate planning data."""
        required_fields = ["context_analysis"]
        return self._validate_required_fields(data, required_fields)

    def _select_response_strategy(
        self, context_analysis: ContextAnalysis, preferences: dict[str, Any]
    ) -> ResponseStrategy:
        """Select appropriate response strategy."""
        # Check for user preference
        preferred_strategy = preferences.get("strategy")
        if preferred_strategy and isinstance(preferred_strategy, ResponseStrategy):
            return preferred_strategy

        # Strategy selection based on context
        quality = context_analysis.quality
        content_type = context_analysis.content_type

        # Quality-based strategy selection
        if quality == ContextQuality.EXCELLENT:
            candidates = [
                ResponseStrategy.CREATIVE,
                ResponseStrategy.ELABORATE,
                ResponseStrategy.CONTEXTUAL,
            ]
        elif quality == ContextQuality.GOOD:
            candidates = [
                ResponseStrategy.BALANCED,
                ResponseStrategy.ADAPTIVE,
                ResponseStrategy.CONTEXTUAL,
            ]
        elif quality == ContextQuality.FAIR:
            candidates = [ResponseStrategy.SUPPORTIVE, ResponseStrategy.BALANCED]
        else:
            candidates = [ResponseStrategy.CONSERVATIVE, ResponseStrategy.SUPPORTIVE]

        # Content type modifications
        if content_type == "dialogue":
            candidates.append(ResponseStrategy.EMOTIONAL)
        elif content_type == "action":
            candidates.append(ResponseStrategy.CHALLENGING)
        elif content_type == "description":
            candidates.append(ResponseStrategy.CREATIVE)
        elif content_type == "emotion":
            candidates.append(ResponseStrategy.SUPPORTIVE)

        # Weight-based selection
        weighted_candidates = []
        for strategy in candidates:
            weight = self.strategy_weights.get(strategy, 0.5)
            weighted_candidates.extend([strategy] * int(weight * 10))

        if weighted_candidates:
            return random.choice(weighted_candidates)
        return ResponseStrategy.BALANCED

    def _determine_response_complexity(
        self, context_analysis: ContextAnalysis, preferences: dict[str, Any]
    ) -> ResponseComplexity:
        """Determine appropriate response complexity."""
        # Check for user preference
        preferred_complexity = preferences.get("complexity")
        if preferred_complexity and isinstance(
            preferred_complexity, ResponseComplexity
        ):
            return preferred_complexity

        # Use context analysis recommendation, but adjust based on quality
        suggested_complexity = context_analysis.complexity_needs
        quality = context_analysis.quality

        # Quality-based adjustments
        if quality == ContextQuality.POOR or quality == ContextQuality.MINIMAL:
            # Downgrade complexity for poor context
            if suggested_complexity == ResponseComplexity.ELABORATE:
                return ResponseComplexity.COMPLEX
            if suggested_complexity == ResponseComplexity.COMPLEX:
                return ResponseComplexity.MODERATE
            if suggested_complexity == ResponseComplexity.MODERATE:
                return ResponseComplexity.SIMPLE

        elif quality == ContextQuality.EXCELLENT:
            # Can safely use suggested complexity or upgrade slightly
            if suggested_complexity == ResponseComplexity.SIMPLE:
                return ResponseComplexity.MODERATE

        return suggested_complexity

    def _plan_content_focus(
        self, context_analysis: ContextAnalysis, strategy: ResponseStrategy
    ) -> str:
        """Plan the primary content focus."""
        content_type = context_analysis.content_type

        # Strategy-influenced focus
        focus_map = {
            ResponseStrategy.CREATIVE: "creative_expansion",
            ResponseStrategy.ANALYTICAL: "logical_analysis",
            ResponseStrategy.EMOTIONAL: "emotional_depth",
            ResponseStrategy.SUPPORTIVE: "user_support",
            ResponseStrategy.CHALLENGING: "narrative_challenge",
            ResponseStrategy.EXPLORATORY: "boundary_pushing",
        }

        strategy_focus = focus_map.get(strategy)
        if strategy_focus:
            return strategy_focus

        # Content type-based focus
        if content_type in ["dialogue", "emotion"]:
            return "character_interaction"
        if content_type == "action":
            return "scene_progression"
        if content_type == "description":
            return "world_building"
        return "narrative_continuation"

    def _select_tone(
        self, context_analysis: ContextAnalysis, strategy: ResponseStrategy
    ) -> str:
        """Select appropriate tone for response."""
        # Extract emotional context
        emotional_context = context_analysis.emotional_context
        primary_emotion = emotional_context.get("primary_emotion", "neutral")

        # Strategy-based tone mapping
        strategy_tones = {
            ResponseStrategy.SUPPORTIVE: "supportive",
            ResponseStrategy.CHALLENGING: "assertive",
            ResponseStrategy.CREATIVE: "imaginative",
            ResponseStrategy.ANALYTICAL: "thoughtful",
            ResponseStrategy.EMOTIONAL: "empathetic",
        }

        strategy_tone = strategy_tones.get(strategy)
        if strategy_tone:
            return strategy_tone

        # Emotion-based tone
        emotion_tones = {
            "positive": "upbeat",
            "negative": "gentle",
            "neutral": "balanced",
        }

        return emotion_tones.get(primary_emotion, "balanced")

    def _select_style_guides(
        self, context_analysis: ContextAnalysis, complexity: ResponseComplexity
    ) -> list[str]:
        """Select style guides for response generation."""
        style_guides = []

        # Complexity-based style guides
        if complexity == ResponseComplexity.ELABORATE:
            style_guides.extend(
                ["detailed_descriptions", "rich_dialogue", "multiple_perspectives"]
            )
        elif complexity == ResponseComplexity.COMPLEX:
            style_guides.extend(["nuanced_approach", "character_depth"])
        elif complexity == ResponseComplexity.MODERATE:
            style_guides.extend(["clear_progression", "focused_content"])
        else:
            style_guides.extend(["concise_writing", "direct_approach"])

        # Content type style guides
        content_type = context_analysis.content_type
        if content_type == "dialogue":
            style_guides.append("natural_conversation")
        elif content_type == "action":
            style_guides.append("dynamic_pacing")
        elif content_type == "description":
            style_guides.append("vivid_imagery")

        return style_guides

    def _estimate_response_length(
        self, complexity: ResponseComplexity, content_focus: str
    ) -> int:
        """Estimate appropriate response length."""
        base_lengths = {
            ResponseComplexity.SIMPLE: 150,
            ResponseComplexity.MODERATE: 300,
            ResponseComplexity.COMPLEX: 500,
            ResponseComplexity.ELABORATE: 800,
        }

        base_length = base_lengths.get(complexity, 200)

        # Focus-based adjustments
        focus_multipliers = {
            "creative_expansion": 1.3,
            "logical_analysis": 1.2,
            "emotional_depth": 1.1,
            "world_building": 1.4,
            "character_interaction": 1.0,
            "narrative_challenge": 1.2,
        }

        multiplier = focus_multipliers.get(content_focus, 1.0)
        return int(base_length * multiplier)

    def _identify_key_points(
        self, context_analysis: ContextAnalysis, strategy: ResponseStrategy
    ) -> list[str]:
        """Identify key points to address in response."""
        key_points = []

        # Always address user input if available
        if "user_input_provided" in context_analysis.key_elements:
            key_points.append("respond_to_user_input")

        # Character-related points
        if context_analysis.character_context.get("mentioned_characters"):
            key_points.append("address_mentioned_characters")

        # Narrative points based on strategy
        if strategy == ResponseStrategy.CREATIVE:
            key_points.append("introduce_creative_elements")
        elif strategy == ResponseStrategy.CHALLENGING:
            key_points.append("present_narrative_challenge")
        elif strategy == ResponseStrategy.SUPPORTIVE:
            key_points.append("provide_supportive_guidance")
        elif strategy == ResponseStrategy.ANALYTICAL:
            key_points.append("analyze_situation_logically")

        # Content type points
        content_type = context_analysis.content_type
        if content_type == "dialogue":
            key_points.append("facilitate_character_dialogue")
        elif content_type == "action":
            key_points.append("advance_scene_action")
        elif content_type == "description":
            key_points.append("enhance_scene_description")

        return key_points

    def _plan_context_integration(
        self, context_analysis: ContextAnalysis
    ) -> dict[str, Any]:
        """Plan how to integrate available context."""
        integration_plan = {}

        # Character integration
        if context_analysis.character_context:
            integration_plan["characters"] = {
                "use_character_states": True,
                "maintain_character_consistency": True,
                "referenced_characters": context_analysis.character_context.get(
                    "mentioned_characters", []
                ),
            }

        # Narrative integration
        if context_analysis.narrative_context:
            integration_plan["narrative"] = {
                "reference_story_state": True,
                "acknowledge_recent_events": True,
                "maintain_scene_continuity": True,
            }

        # Emotional integration
        if context_analysis.emotional_context:
            integration_plan["emotional"] = {
                "respond_to_emotions": True,
                "maintain_emotional_tone": True,
                "primary_emotion": context_analysis.emotional_context.get(
                    "primary_emotion"
                ),
            }

        return integration_plan

    def _set_quality_targets(
        self, complexity: ResponseComplexity, strategy: ResponseStrategy
    ) -> dict[str, float]:
        """Set quality targets for response generation."""
        # Base targets from complexity
        targets = self.quality_targets.get(
            complexity, {"coherence": 0.8, "creativity": 0.7}
        ).copy()

        # Strategy-based adjustments
        if strategy == ResponseStrategy.CREATIVE:
            targets["creativity"] = min(1.0, targets["creativity"] + 0.1)
        elif strategy == ResponseStrategy.ANALYTICAL:
            targets["coherence"] = min(1.0, targets["coherence"] + 0.05)
        elif strategy == ResponseStrategy.CONSERVATIVE:
            targets["coherence"] = min(1.0, targets["coherence"] + 0.1)
            targets["creativity"] = max(0.5, targets["creativity"] - 0.1)

        # Add context integration target
        targets["context_integration"] = 0.8

        return targets

    def _validate_required_fields(
        self, data: dict[str, Any], required_fields: list[str]
    ) -> ValidationResult:
        """Validate required fields are present."""
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                validation_type="required_fields",
                issues=[f"Missing required field: {field}" for field in missing_fields],
            )

        return ValidationResult(
            is_valid=True, confidence=1.0, validation_type="required_fields"
        )
