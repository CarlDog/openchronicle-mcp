"""
Shared interfaces and base classes for content analysis components.

Date: August 4, 2025
Purpose: Define common interfaces for modular content analysis system
Part of: Phase 5A - Content Analysis Enhancement
"""

from abc import ABC
from abc import abstractmethod
from typing import Any


class ContentAnalysisComponent(ABC):
    """Base interface for all content analysis components."""

    def __init__(self, model_manager):
        self.model_manager = model_manager

    @abstractmethod
    async def process(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Process content and return analysis results."""


class DetectionComponent(ContentAnalysisComponent):
    """Base for content detection components."""

    @abstractmethod
    def detect_content_type(self, content: str) -> dict[str, Any]:
        """Detect content type and classification."""


class ExtractionComponent(ContentAnalysisComponent):
    """Base for data extraction components."""

    @abstractmethod
    async def extract_data(self, content: str) -> dict[str, Any]:
        """Extract structured data from content."""


class RoutingComponent(ContentAnalysisComponent):
    """Base for routing and recommendation components."""

    @abstractmethod
    def get_recommendation(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Get routing recommendation based on analysis."""
