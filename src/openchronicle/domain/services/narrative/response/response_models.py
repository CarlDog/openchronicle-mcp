"""
OpenChronicle Core - Response System Data Models

Data classes and enums for the response intelligence system.
Extracted from IntelligentResponseEngine for modular architecture.

Author: OpenChronicle Development Team
"""

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any


class ResponseStrategy(Enum):
    """Enumeration of response generation strategies."""

    CONSERVATIVE = "conservative"  # Safe, predictable responses
    BALANCED = "balanced"  # Mix of safety and creativity
    CREATIVE = "creative"  # More experimental responses
    ADAPTIVE = "adaptive"  # Strategy based on context
    CONTEXTUAL = "contextual"  # Heavily context-dependent
    EXPLORATORY = "exploratory"  # Push boundaries of narrative
    SUPPORTIVE = "supportive"  # Focus on user support
    CHALLENGING = "challenging"  # Present narrative challenges
    EMOTIONAL = "emotional"  # Emphasize emotional content
    ANALYTICAL = "analytical"  # Focus on logical analysis


class ContextQuality(Enum):
    """Quality assessment of context data."""

    EXCELLENT = "excellent"  # Rich, comprehensive context
    GOOD = "good"  # Adequate context for good response
    FAIR = "fair"  # Limited but usable context
    POOR = "poor"  # Insufficient context quality
    MINIMAL = "minimal"  # Very limited context available


class ResponseComplexity(Enum):
    """Complexity levels for response generation."""

    SIMPLE = "simple"  # Basic, straightforward response
    MODERATE = "moderate"  # Standard complexity response
    COMPLEX = "complex"  # Detailed, nuanced response
    ELABORATE = "elaborate"  # Comprehensive, multi-faceted response


@dataclass
class ContextAnalysis:
    """Analysis of context data for response planning."""

    quality: ContextQuality
    complexity_needs: ResponseComplexity
    content_type: str
    character_context: dict[str, Any] = field(default_factory=dict)
    narrative_context: dict[str, Any] = field(default_factory=dict)
    emotional_context: dict[str, Any] = field(default_factory=dict)

    # Analysis results
    confidence: float = 0.0  # Confidence in analysis (0-1)
    key_elements: list[str] = field(
        default_factory=list
    )  # Important context elements identified
    missing_elements: list[str] = field(
        default_factory=list
    )  # Important elements that are missing
    recommendations: list[str] = field(default_factory=list)  # Analysis recommendations


@dataclass
class ResponsePlan:
    """Plan for generating an intelligent response."""

    strategy: ResponseStrategy
    complexity: ResponseComplexity
    content_focus: str
    tone: str = "balanced"
    style_guides: list[str] = field(default_factory=list)

    # Planning details
    estimated_length: int = 0  # Estimated response length
    key_points: list[str] = field(default_factory=list)  # Key points to address
    context_integration: dict[str, Any] = field(
        default_factory=dict
    )  # How to integrate context
    quality_targets: dict[str, float] = field(
        default_factory=dict
    )  # Quality metrics to target


@dataclass
class ResponseEvaluation:
    """Evaluation of response quality and effectiveness."""

    overall_score: float  # Overall quality score (0-1)
    coherence_score: float  # Logical consistency score
    creativity_score: float  # Creative elements score
    context_integration_score: float  # How well context was used

    # Detailed assessment
    strengths: list[str] = field(default_factory=list)  # Response strengths
    weaknesses: list[str] = field(default_factory=list)  # Areas for improvement
    suggestions: list[str] = field(default_factory=list)  # Improvement suggestions
    meets_plan: bool = True  # Whether response met the plan


@dataclass
class ResponseMetrics:
    """Performance metrics for response generation."""

    generation_time: float  # Time to generate response
    analysis_time: float  # Time for context analysis
    planning_time: float  # Time for response planning
    evaluation_time: float  # Time for response evaluation

    # Quality metrics
    average_quality: float = 0.0  # Average quality score
    consistency_rating: float = 0.0  # Consistency across responses
    improvement_trend: float = 0.0  # Quality improvement over time

    # Usage statistics
    responses_generated: int = 0  # Total responses generated
    strategies_used: dict[str, int] = field(
        default_factory=dict
    )  # Strategy usage counts
    context_types_handled: dict[str, int] = field(
        default_factory=dict
    )  # Context type counts


@dataclass
class ResponseContext:
    """Comprehensive context for response generation."""

    user_input: str
    story_state: dict[str, Any] = field(default_factory=dict)
    character_states: dict[str, Any] = field(default_factory=dict)
    narrative_history: list[str] = field(default_factory=list)
    scene_context: dict[str, Any] = field(default_factory=dict)

    # Meta context
    session_info: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)


@dataclass
class ResponseRequest:
    """Request for intelligent response generation."""

    context: ResponseContext
    preferred_strategy: ResponseStrategy | None = None
    preferred_complexity: ResponseComplexity | None = None
    quality_requirements: dict[str, float] = field(default_factory=dict)
    custom_instructions: list[str] = field(default_factory=list)

    # Request metadata
    request_id: str = ""
    timestamp: str = ""
    priority: str = "normal"


@dataclass
class ResponseResult:
    """Complete result of response generation process."""

    request: ResponseRequest
    analysis: ContextAnalysis
    plan: ResponsePlan
    generated_response: str
    evaluation: ResponseEvaluation
    metrics: ResponseMetrics

    # Result metadata
    success: bool = True
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)
    processing_notes: list[str] = field(default_factory=list)
