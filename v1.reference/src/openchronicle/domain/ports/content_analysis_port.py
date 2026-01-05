"""
Content Analysis Port - Interface for content analysis operations

Defines the contract for content analysis operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any


class IContentAnalysisPort(ABC):
    """Interface for content analysis operations."""

    @abstractmethod
    async def generate_content_flags(self, analysis: dict[str, Any], content: str) -> list[dict[str, Any]]:
        """
        Generate content flags based on analysis and content.

        Args:
            analysis: Analysis data dictionary
            content: Content text to analyze

        Returns:
            List of content flags with name, value, and metadata
        """

    @abstractmethod
    async def analyze_content_sentiment(self, content: str) -> dict[str, Any]:
        """
        Analyze sentiment of content.

        Args:
            content: Content text to analyze

        Returns:
            Sentiment analysis results
        """

    @abstractmethod
    async def detect_content_themes(self, content: str) -> list[str]:
        """
        Detect themes in content.

        Args:
            content: Content text to analyze

        Returns:
            List of detected themes
        """
