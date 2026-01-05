"""
Storypack interfaces port for domain layer operations.
Abstract interfaces for storypack import operations without dependency violations.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


class IStorypackProcessorPort(ABC):
    """Port for storypack processing operations."""

    @abstractmethod
    async def process_content(self, content: Any) -> Dict[str, Any]:
        """Process storypack content."""
        pass

    @abstractmethod
    async def validate_structure(self, data: Dict) -> bool:
        """Validate storypack structure."""
        pass

    @abstractmethod
    async def extract_metadata(self, content: Any) -> Dict[str, Any]:
        """Extract metadata from content."""
        pass

    @abstractmethod
    async def classify_content(self, content: str) -> str:
        """Classify content type."""
        pass

    @abstractmethod
    async def format_output(self, data: Dict) -> str:
        """Format output data."""
        pass

    @abstractmethod
    async def build_storypack(self, components: Dict) -> Dict[str, Any]:
        """Build storypack from components."""
        pass

    @abstractmethod
    async def generate_template(self, template_type: str) -> str:
        """Generate template content."""
        pass

    @abstractmethod
    async def parse_content(self, content: str) -> Dict[str, Any]:
        """Parse content structure."""
        pass

    @abstractmethod
    async def analyze_structure(self, data: Dict) -> Dict[str, Any]:
        """Analyze content structure."""
        pass

    @abstractmethod
    async def validate_content(self, content: Any) -> bool:
        """Validate content."""
        pass
