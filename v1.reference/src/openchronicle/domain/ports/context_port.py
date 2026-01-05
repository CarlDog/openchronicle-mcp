"""
Context Port - Interface for context building operations

Defines the contract for context building operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any


class IContextPort(ABC):
    """Interface for context building operations."""

    @abstractmethod
    async def build_context_with_analysis(self, user_input: str, story_data: dict[str, Any]) -> dict[str, Any]:
        """
        Build context with intelligent analysis.

        Args:
            user_input: User's input text
            story_data: Story data dictionary

        Returns:
            Context dictionary with analysis
        """

    @abstractmethod
    async def build_basic_context(self, user_input: str, story_data: dict[str, Any]) -> dict[str, Any]:
        """
        Build basic context without analysis.

        Args:
            user_input: User's input text
            story_data: Story data dictionary

        Returns:
            Basic context dictionary
        """

    @abstractmethod
    async def extract_context_metadata(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Extract metadata from context.

        Args:
            context: Context dictionary

        Returns:
            Extracted metadata
        """
