from openchronicle.domain.ports.storypack_port import IStorypackProcessorPort\n\n#!/usr/bin/env python3
"""
OpenChronicle Validation Engine

Focused component for validating content and system readiness.
Handles all validation logic for the import process.
"""

import json
from pathlib import Path

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_system_event





class ValidationEngine(IValidationEngine):
    """Handles content validation and system readiness checks."""

    def __init__(self):
        """Initialize the validation engine."""
        self.logger = get_logger()

        # Validation rules
        self.content_rules = {
            "min_content_length": 10,
            "max_content_length": 10 * 1024 * 1024,  # 10MB
            "max_line_length": 10000,
            "required_encoding": ["utf-8", "ascii", "latin-1"],
        }

        # Storypack structure requirements
        self.storypack_requirements = {
            "required_files": ["meta.json"],
            "optional_files": ["README.md", "style_guide.json"],
            "required_directories": [],  # Can be created as needed
            "optional_directories": ["characters", "locations", "lore", "narrative"],
        }

    def validate_content_format(
        self, content: str, expected_type: str
    ) -> tuple[bool, list[str]]:
        """
        Validate content format against expected type.

        Args:
            content: Content to validate
            expected_type: Expected content type

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Basic content validation
        if not content:
            issues.append("Content is empty")
            return False, issues

        if not content.strip():
            issues.append("Content contains only whitespace")
            return False, issues

        # Length validation
        if len(content) < self.content_rules["min_content_length"]:
            issues.append(
                f"Content too short (minimum {self.content_rules['min_content_length']} characters)"
            )

        if len(content) > self.content_rules["max_content_length"]:
            issues.append(
                f"Content too long (maximum {self.content_rules['max_content_length']} characters)"
            )

        # Line length validation
        lines = content.split("\n")
        long_lines = [
            i
            for i, line in enumerate(lines, 1)
            if len(line) > self.content_rules["max_line_length"]
        ]
        if long_lines:
            issues.append(
                f"Lines too long (lines {long_lines[:5]}): maximum {self.content_rules['max_line_length']} characters"
            )

        # Type-specific validation
        type_issues = self._validate_content_by_type(content, expected_type)
        issues.extend(type_issues)

        # Character encoding validation
        try:
            content.encode("utf-8")
        except UnicodeEncodeError as e:
            issues.append(f"Content contains invalid characters: {e}")

        is_valid = len(issues) == 0

        if is_valid:
            log_system_event(
                "validation_engine",
                "Content validation passed",
                {
                    "content_length": len(content),
                    "expected_type": expected_type,
                    "line_count": len(lines),
                },
            )
        else:
            log_system_event(
                "validation_engine",
                "Content validation failed",
                {
                    "content_length": len(content),
                    "expected_type": expected_type,
                    "issues_count": len(issues),
                    "issues": issues[:5],  # Log first 5 issues
                },
            )

        return is_valid, issues

    def validate_import_readiness(
        self, context: ImportContext
    ) -> tuple[bool, list[str]]:
        """
        Validate that system is ready for import operation.

        Args:
            context: Import context to validate

        Returns:
            Tuple of (is_ready, list_of_issues)
        """
        issues = []

        # Validate source path
        if not context.source_path.exists():
            issues.append(f"Source path does not exist: {context.source_path}")
        elif not context.source_path.is_dir():
            issues.append(f"Source path is not a directory: {context.source_path}")

        # Validate target path
        try:
            context.target_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create target directory {context.target_path}: {e}")

        # Check if storypack already exists
        if context.target_path.exists():
            existing_files = list(context.target_path.glob("*"))
            if existing_files:
                issues.append(f"Target directory not empty: {context.target_path}")

        # Validate storypack name
        name_issues = self._validate_storypack_name(context.storypack_name)
        issues.extend(name_issues)

        # Check for supported content files in source
        if context.source_path.exists():
            supported_files = self._find_supported_files(context.source_path)
            if not supported_files:
                issues.append("No supported content files found in source directory")

        # Validate import mode
        if context.import_mode not in ["basic", "ai"]:
            issues.append(f"Invalid import mode: {context.import_mode}")

        # AI-specific validation
        if context.import_mode == "ai" and not context.ai_available:
            issues.append("AI import mode requested but AI capabilities not available")

        is_ready = len(issues) == 0

        log_system_event(
            "validation_engine",
            "Import readiness validation",
            {
                "is_ready": is_ready,
                "source_path": str(context.source_path),
                "target_path": str(context.target_path),
                "storypack_name": context.storypack_name,
                "import_mode": context.import_mode,
                "issues_count": len(issues),
            },
        )

        return is_ready, issues

    def validate_storypack_structure(
        self, storypack_path: Path
    ) -> tuple[bool, list[str]]:
        """
        Validate generated storypack structure.

        Args:
            storypack_path: Path to the storypack to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        if not storypack_path.exists():
            issues.append(f"Storypack path does not exist: {storypack_path}")
            return False, issues

        if not storypack_path.is_dir():
            issues.append(f"Storypack path is not a directory: {storypack_path}")
            return False, issues

        # Check required files
        for required_file in self.storypack_requirements["required_files"]:
            file_path = storypack_path / required_file
            if not file_path.exists():
                issues.append(f"Required file missing: {required_file}")
            # Validate specific file formats
            elif required_file == "meta.json":
                json_issues = self._validate_meta_json(file_path)
                issues.extend(json_issues)

        # Check directory structure
        content_dirs = ["characters", "locations", "lore", "narrative"]
        found_content_dirs = []

        for item in storypack_path.iterdir():
            if item.is_dir() and item.name in content_dirs:
                found_content_dirs.append(item.name)

                # Validate content directory
                dir_issues = self._validate_content_directory(item)
                issues.extend(dir_issues)

        if not found_content_dirs:
            issues.append(
                "No content directories found (characters, locations, lore, narrative)"
            )

        # Check for empty storypack
        total_content_files = 0
        for content_dir in found_content_dirs:
            content_path = storypack_path / content_dir
            content_files = list(content_path.glob("*.json"))
            total_content_files += len(content_files)

        if total_content_files == 0:
            issues.append("Storypack contains no content files")

        is_valid = len(issues) == 0

        log_system_event(
            "validation_engine",
            "Storypack structure validation",
            {
                "is_valid": is_valid,
                "storypack_path": str(storypack_path),
                "content_directories": found_content_dirs,
                "total_content_files": total_content_files,
                "issues_count": len(issues),
            },
        )

        return is_valid, issues

    def _validate_content_by_type(self, content: str, expected_type: str) -> list[str]:
        """Validate content based on its expected type."""
        issues = []

        if expected_type == "json":
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                issues.append(f"Invalid JSON format: {e}")

        elif expected_type == "character_profile":
            # Character profiles should have certain structure
            content_lower = content.lower()
            required_fields = ["name"]
            missing_fields = []

            for field in required_fields:
                if field not in content_lower:
                    missing_fields.append(field)

            if missing_fields:
                issues.append(
                    f"Character profile missing required fields: {missing_fields}"
                )

        elif expected_type == "location_description":
            # Location descriptions should have basic structure
            if len(content.split()) < 20:
                issues.append("Location description too brief (minimum 20 words)")

        elif expected_type == "narrative":
            # Narrative content validation
            if not any(
                indicator in content for indicator in ['"', "'", "said", "walked"]
            ):
                issues.append("Narrative content lacks typical story elements")

        return issues

    def _validate_storypack_name(self, name: str) -> list[str]:
        """Validate storypack name."""
        issues = []

        if not name:
            issues.append("Storypack name cannot be empty")
            return issues

        if len(name) < 2:
            issues.append("Storypack name too short (minimum 2 characters)")

        if len(name) > 50:
            issues.append("Storypack name too long (maximum 50 characters)")

        # Check for invalid characters
        invalid_chars = ["<", ">", ":", '"', "|", "?", "*", "\\", "/"]
        found_invalid = [char for char in invalid_chars if char in name]
        if found_invalid:
            issues.append(
                f"Storypack name contains invalid characters: {found_invalid}"
            )

        # Check for reserved names
        reserved_names = ["con", "prn", "aux", "nul", "com1", "com2", "lpt1", "lpt2"]
        if name.lower() in reserved_names:
            issues.append(f"Storypack name '{name}' is reserved")

        return issues

    def _find_supported_files(self, source_path: Path) -> list[Path]:
        """Find supported files in source directory."""
        supported_extensions = {".txt", ".md", ".json"}
        supported_files = []

        try:
            for file_path in source_path.rglob("*"):
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in supported_extensions
                ):
                    supported_files.append(file_path)
        except Exception as e:
            self.logger.warning(f"Error scanning source directory {source_path}: {e}")

        return supported_files

    def _validate_meta_json(self, meta_path: Path) -> list[str]:
        """Validate meta.json file."""
        issues = []

        try:
            with open(meta_path, encoding="utf-8") as f:
                meta_data = json.load(f)

            # Check required fields
            required_fields = ["storypack_id", "title", "version"]
            for field in required_fields:
                if field not in meta_data:
                    issues.append(f"meta.json missing required field: {field}")

            # Validate field types
            if "storypack_id" in meta_data and not isinstance(
                meta_data["storypack_id"], str
            ):
                issues.append("meta.json field 'storypack_id' must be a string")

            if "title" in meta_data and not isinstance(meta_data["title"], str):
                issues.append("meta.json field 'title' must be a string")

        except json.JSONDecodeError as e:
            issues.append(f"meta.json is not valid JSON: {e}")
        except Exception as e:
            issues.append(f"Error reading meta.json: {e}")

        return issues

    def _validate_content_directory(self, dir_path: Path) -> list[str]:
        """Validate a content directory."""
        issues = []

        # Check if directory is accessible
        try:
            files = list(dir_path.glob("*"))
        except Exception as e:
            issues.append(f"Cannot access directory {dir_path.name}: {e}")
            return issues

        # Check for content files
        content_files = [f for f in files if f.suffix.lower() == ".json"]

        # Validate each content file
        for content_file in content_files[:5]:  # Limit validation to first 5 files
            try:
                with open(content_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError:
                issues.append(f"Invalid JSON in {dir_path.name}/{content_file.name}")
            except Exception as e:
                issues.append(f"Error reading {dir_path.name}/{content_file.name}: {e}")

        return issues
