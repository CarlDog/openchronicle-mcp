#!/usr/bin/env python3
"""
OpenChronicle Storypack Import Interfaces

This module defines the interfaces for the modular storypack import system,
following SOLID principles with focused, segregated interfaces.
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ContentFile:
    """Represents a discovered content file."""
    path: Path
    category: str
    size: int
    encoding: str = 'utf-8'
    metadata: dict[str, Any] | None = None


@dataclass
class ImportContext:
    """Context information for import operations."""
    source_path: Path
    storypack_name: str
    import_mode: str  # 'basic' or 'ai'
    target_path: Path
    templates_available: list[str]
    ai_available: bool = False


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    storypack_name: str
    storypack_path: Path | None
    files_processed: int
    generated_files: list[Path]
    processing_time: float
    created_at: str
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]


class IContentParser(ABC):
    """Interface for content parsing operations."""

    @abstractmethod
    def discover_files(self, source_path: Path) -> dict[str, list[ContentFile]]:
        """Discover and categorize files in the source directory."""

    @abstractmethod
    def categorize_file(self, file_path: Path) -> str:
        """Categorize a single file based on its path and name."""

    @abstractmethod
    def read_file_content(self, file_path: Path) -> tuple[str, str]:
        """Read file content and detect encoding."""

    @abstractmethod
    def validate_file_format(self, file_path: Path) -> bool:
        """Validate that a file format is supported."""


class IMetadataExtractor(ABC):
    """Interface for metadata extraction from content."""

    @abstractmethod
    def extract_basic_metadata(self, content: str, file_path: Path) -> dict[str, Any]:
        """Extract basic metadata from content."""

    @abstractmethod
    def detect_content_structure(self, content: str) -> dict[str, Any]:
        """Analyze content structure and organization."""

    @abstractmethod
    def extract_file_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract filesystem metadata."""


class IStructureAnalyzer(ABC):
    """Interface for analyzing directory structures."""

    @abstractmethod
    def analyze_directory_structure(self, source_path: Path) -> dict[str, Any]:
        """Analyze the overall directory structure."""

    @abstractmethod
    def suggest_organization(self, discovered_files: dict[str, list[ContentFile]]) -> dict[str, str]:
        """Suggest how to organize content in the storypack."""

    @abstractmethod
    def validate_source_structure(self, source_path: Path) -> tuple[bool, list[str]]:
        """Validate source directory structure."""


class IAIProcessor(ABC):
    """Interface for AI-powered content processing."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize AI capabilities."""

    @abstractmethod
    async def analyze_content(self, content: str, file_path: Path, context: ImportContext) -> dict[str, Any]:
        """Analyze content using AI capabilities."""

    @abstractmethod
    async def extract_entities(self, content: str, entity_type: str) -> list[dict[str, Any]]:
        """Extract specific entities (characters, locations, etc.) from content."""

    @abstractmethod
    async def classify_content_type(self, content: str) -> dict[str, Any]:
        """Classify content type and determine processing approach."""

    @abstractmethod
    async def test_capabilities(self) -> tuple[bool, list[str]]:
        """Test AI capabilities and return status."""


class IContentClassifier(ABC):
    """Interface for content classification."""

    @abstractmethod
    def classify_by_content(self, content: str) -> str:
        """Classify content based on its actual content."""

    @abstractmethod
    def classify_by_structure(self, content: str) -> dict[str, Any]:
        """Analyze content structure patterns."""

    @abstractmethod
    def get_confidence_score(self, content: str, category: str) -> float:
        """Get confidence score for content categorization."""


class IValidationEngine(ABC):
    """Interface for content validation."""

    @abstractmethod
    def validate_content_format(self, content: str, expected_type: str) -> tuple[bool, list[str]]:
        """Validate content format against expected type."""

    @abstractmethod
    def validate_import_readiness(self, context: ImportContext) -> tuple[bool, list[str]]:
        """Validate that system is ready for import."""

    @abstractmethod
    def validate_storypack_structure(self, storypack_path: Path) -> tuple[bool, list[str]]:
        """Validate generated storypack structure."""


class IStorypackBuilder(ABC):
    """Interface for storypack structure building."""

    @abstractmethod
    def create_storypack_structure(self, context: ImportContext) -> Path:
        """Create the directory structure for a new storypack."""

    @abstractmethod
    def generate_metadata_file(self, context: ImportContext, content_summary: dict[str, Any]) -> dict[str, Any]:
        """Generate the meta.json file for the storypack."""

    @abstractmethod
    def organize_content_files(self, discovered_files: dict[str, list[ContentFile]],
                              target_path: Path) -> dict[str, list[Path]]:
        """Organize and copy content files to storypack structure."""


class ITemplateEngine(ABC):
    """Interface for template processing."""

    @abstractmethod
    def load_templates(self, templates_dir: Path) -> dict[str, dict[str, Any]]:
        """Load all available templates."""

    @abstractmethod
    def select_template(self, content_analysis: dict[str, Any]) -> str | None:
        """Select appropriate template based on content analysis."""

    @abstractmethod
    def process_template(self, template_name: str, context: ImportContext) -> dict[str, Any]:
        """Process template with given context."""


class IOutputFormatter(ABC):
    """Interface for output formatting."""

    @abstractmethod
    def format_import_result(self, result: ImportResult, format_type: str = 'summary') -> str:
        """Format import result for display."""

    @abstractmethod
    def generate_report(self, result: ImportResult, report_type: str = 'standard') -> dict[str, Any]:
        """Generate comprehensive import report."""

    @abstractmethod
    def save_report(self, report: dict[str, Any], output_path: Path, format_type: str = 'json') -> bool:
        """Save report to file."""

    @abstractmethod
    def format_import_summary(self, result: ImportResult) -> str:
        """Format import results for display."""

    @abstractmethod
    def generate_readme(self, context: ImportContext, content_summary: dict[str, Any]) -> str:
        """Generate README content for the storypack."""

    @abstractmethod
    def format_error_report(self, errors: list[str], warnings: list[str]) -> str:
        """Format error and warning messages."""
