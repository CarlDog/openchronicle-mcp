"""
OpenChronicle Core - Response Intelligence System

Modular response intelligence system providing context analysis,
response planning, and quality evaluation.

Replaces IntelligentResponseEngine (995 lines) with specialized components.

Author: OpenChronicle Development Team
"""

from .response_models import (
    ResponseStrategy,
    ContextQuality,
    ResponseComplexity,
    ContextAnalysis,
    ResponsePlan,
    ResponseEvaluation,
    ResponseMetrics,
    ResponseContext,
    ResponseRequest,
    ResponseResult,
)

from .context_analyzer import ContextAnalyzer
from .response_planner import ResponsePlanner
from .response_orchestrator import ResponseOrchestrator

__all__ = [
    # Core orchestrator
    "ResponseOrchestrator",
    # Component classes
    "ContextAnalyzer",
    "ResponsePlanner",
    # Data models
    "ResponseStrategy",
    "ContextQuality",
    "ResponseComplexity",
    "ContextAnalysis",
    "ResponsePlan",
    "ResponseEvaluation",
    "ResponseMetrics",
    "ResponseContext",
    "ResponseRequest",
    "ResponseResult",
]
