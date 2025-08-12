#!/usr/bin/env python3
from openchronicle.application.services.importers.storypack.interfaces import (
    ContentFile,
    IContentParser,
)
"""
OpenChronicle Content Parser

Focused component for discovering, categorizing, and reading content files.
Follows single responsibility principle - only handles file operations.
"""

from pathlib import Path


try:
    import chardet

    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_system_event





class ContentParser(IContentParser):
    """Handles content file discovery, categorization, and reading operations."""

    def __init__(self):
        """Initialize the content parser."""
        self.logger = get_logger()

        # Supported file extensions
        self.supported_extensions = {".txt", ".md", ".json"}

        # Content categorization rules
        self.content_categories = {
            "characters": ["characters", "people", "npcs", "char", "character"],
            "locations": [
                "locations",
                "places",
                "settings",
                "loc",
                "location",
                "world",
            ],
            "lore": ["lore", "history", "background", "world", "canon", "backstory"],
            "narrative": [
                "story",
                "plot",
                "scenes",
                "narrative",
                "chapters",
                "chapter",
            ],
        }

    def discover_files(self, source_path: Path) -> dict[str, list[ContentFile]]:
        """
        Discover and categorize all supported files in the source directory.

        Args:
            source_path: Path to the source directory to scan

        Returns:
            Dictionary mapping categories to lists of ContentFile objects
        """
        discovered_files = {category: [] for category in self.content_categories.keys()}
        discovered_files["uncategorized"] = []

        if not source_path.exists():
            self.logger.warning(f"Source path does not exist: {source_path}")
            return discovered_files

        total_files = 0

        # Recursively scan for files
        try:
            for file_path in source_path.rglob("*"):
                if file_path.is_file() and self.validate_file_format(file_path):
                    try:
                        # Create ContentFile object
                        content_file = ContentFile(
                            path=file_path,
                            category=self.categorize_file(file_path),
                            size=file_path.stat().st_size,
                            encoding=self._detect_encoding(file_path),
                        )

                        discovered_files[content_file.category].append(content_file)
                        total_files += 1

                    except Exception as e:
                        self.logger.warning(f"Failed to process file {file_path}: {e}")

        except Exception as e:
            self.logger.error(f"Error scanning directory {source_path}: {e}")

        # Log discovery results
        category_counts = {
            cat: len(files) for cat, files in discovered_files.items() if files
        }
        log_system_event(
            "content_parser",
            "File discovery completed",
            {
                "source_path": str(source_path),
                "total_files": total_files,
                "categories": category_counts,
            },
        )

        return discovered_files

    def categorize_file(self, file_path: Path) -> str:
        """
        Categorize a file based on its path and filename patterns.

        Args:
            file_path: Path to the file to categorize

        Returns:
            Category name or 'uncategorized'
        """
        # Check parent directory name first (more reliable)
        for parent in file_path.parents:
            parent_name = parent.name.lower()
            for category, keywords in self.content_categories.items():
                if any(keyword in parent_name for keyword in keywords):
                    return category

        # Check filename if directory categorization fails
        filename = file_path.stem.lower()
        for category, keywords in self.content_categories.items():
            if any(keyword in filename for keyword in keywords):
                return category

        return "uncategorized"

    def read_file_content(self, file_path: Path) -> tuple[str, str]:
        """
        Read file content and return content with detected encoding.

        Args:
            file_path: Path to the file to read

        Returns:
            Tuple of (content, encoding)

        Raises:
            IOError: If file cannot be read
        """
        try:
            # Detect encoding
            encoding = self._detect_encoding(file_path)

            # Read content
            with open(file_path, encoding=encoding) as f:
                content = f.read()

            return content, encoding

        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            raise OSError(f"Cannot read file {file_path}: {e}")

    def validate_file_format(self, file_path: Path) -> bool:
        """
        Check if a file format is supported for import.

        Args:
            file_path: Path to the file to validate

        Returns:
            True if file format is supported, False otherwise
        """
        if not file_path.is_file():
            return False

        # Check file extension
        extension = file_path.suffix.lower()
        if extension not in self.supported_extensions:
            return False

        # Additional validation for specific formats
        if extension == ".json":
            return self._validate_json_file(file_path)

        # Basic validation for text files
        if extension in {".txt", ".md"}:
            return self._validate_text_file(file_path)

        return True

    def _detect_encoding(self, file_path: Path) -> str:
        """
        Detect file encoding using chardet.

        Args:
            file_path: Path to the file

        Returns:
            Detected encoding string, defaults to 'utf-8'
        """
        try:
            with open(file_path, "rb") as f:
                # Read a sample to detect encoding
                raw_data = f.read(
                    min(32768, file_path.stat().st_size)
                )  # Read up to 32KB

            if raw_data:
                if CHARDET_AVAILABLE:
                    detection = chardet.detect(raw_data)
                    if detection and detection["encoding"]:
                        confidence = detection.get("confidence", 0)
                        if confidence > 0.7:  # Only trust high-confidence detections
                            return detection["encoding"]
                else:
                    # Simple fallback encoding detection without chardet
                    try:
                        raw_data.decode("utf-8")
                        return "utf-8"
                    except UnicodeDecodeError:
                        # Try common encodings
                        for encoding in ["latin-1", "cp1252", "ascii"]:
                            try:
                                raw_data.decode(encoding)
                                return encoding
                            except UnicodeDecodeError:
                                continue

            # Default to UTF-8 if detection fails or confidence is low
            return "utf-8"

        except Exception as e:
            self.logger.warning(f"Encoding detection failed for {file_path}: {e}")
            return "utf-8"

    def _validate_json_file(self, file_path: Path) -> bool:
        """Validate that a JSON file is well-formed."""
        try:
            import json

            with open(file_path, encoding="utf-8") as f:
                json.load(f)
            return True
        except Exception:
            return False

    def _validate_text_file(self, file_path: Path) -> bool:
        """Basic validation for text files."""
        try:
            # Check file size (avoid extremely large files)
            size = file_path.stat().st_size
            if size > 50 * 1024 * 1024:  # 50MB limit
                return False

            # Try to read the first few bytes to ensure it's readable
            with open(file_path, "rb") as f:
                first_bytes = f.read(1024)

            # Check for binary content (very basic heuristic)
            if b"\x00" in first_bytes:
                return False

            return True

        except Exception:
            return False
