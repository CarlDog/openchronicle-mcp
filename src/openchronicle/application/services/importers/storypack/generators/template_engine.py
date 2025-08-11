from openchronicle.domain.ports.storypack_port import IStorypackProcessorPort\n\n#!/usr/bin/env python3
"""
OpenChronicle Template Engine

Focused component for template loading and processing.
Handles template selection and application for storypack generation.
"""

import json
from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_system_event





class TemplateEngine(ITemplateEngine):
    """Handles template loading, selection, and processing."""

    def __init__(self):
        """Initialize the template engine."""
        self.logger = get_logger()
        self._templates_cache: dict[str, dict[str, Any]] = {}

        # Template selection criteria
        self.selection_criteria = {
            "content_types": {
                "character_profile": ["character", "rpg", "fantasy"],
                "location_description": ["world", "setting", "fantasy"],
                "narrative_scene": ["story", "narrative", "fiction"],
                "lore_document": ["world", "lore", "fantasy"],
            },
            "file_count_thresholds": {"small": 10, "medium": 50, "large": 100},
        }

    def load_templates(self, templates_dir: Path) -> dict[str, dict[str, Any]]:
        """
        Load all available templates from the templates directory.

        Args:
            templates_dir: Path to the templates directory

        Returns:
            Dictionary mapping template names to template data
        """
        templates = {}

        if not templates_dir.exists():
            self.logger.warning(f"Templates directory does not exist: {templates_dir}")
            return templates

        try:
            template_files = list(templates_dir.glob("*.json"))

            for template_file in template_files:
                try:
                    template_data = self._load_single_template(template_file)
                    if template_data:
                        template_name = template_file.stem
                        templates[template_name] = template_data
                        self.logger.info(f"Loaded template: {template_name}")

                except Exception as e:
                    self.logger.error(f"Failed to load template {template_file}: {e}")
                    continue

            # Cache loaded templates
            self._templates_cache = templates

            log_system_event(
                "template_engine",
                "Templates loaded",
                {
                    "templates_directory": str(templates_dir),
                    "templates_found": len(template_files),
                    "templates_loaded": len(templates),
                    "template_names": list(templates.keys()),
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to load templates from {templates_dir}: {e}")

        return templates

    def select_template(self, content_analysis: dict[str, Any]) -> str | None:
        """
        Select appropriate template based on content analysis.

        Args:
            content_analysis: Analysis of the content being imported

        Returns:
            Template name or None if no suitable template found
        """
        if not self._templates_cache:
            return None

        # Score each template based on content analysis
        template_scores = {}

        for template_name, template_data in self._templates_cache.items():
            score = self._calculate_template_score(template_data, content_analysis)
            template_scores[template_name] = score

        # Select the highest scoring template
        if template_scores:
            best_template = max(template_scores.items(), key=lambda x: x[1])

            if best_template[1] > 0.3:  # Minimum threshold
                log_system_event(
                    "template_engine",
                    "Template selected",
                    {
                        "selected_template": best_template[0],
                        "score": best_template[1],
                        "all_scores": template_scores,
                    },
                )
                return best_template[0]

        self.logger.info("No suitable template found for content analysis")
        return None

    def process_template(
        self, template_name: str, context: ImportContext
    ) -> dict[str, Any]:
        """
        Process template with given context.

        Args:
            template_name: Name of the template to process
            context: Import context information

        Returns:
            Processed template data
        """
        if template_name not in self._templates_cache:
            self.logger.error(f"Template not found: {template_name}")
            return {}

        template_data = self._templates_cache[template_name].copy()

        try:
            # Process template variables
            processed_data = self._process_template_variables(template_data, context)

            # Apply template customizations
            customized_data = self._apply_template_customizations(
                processed_data, context
            )

            log_system_event(
                "template_engine",
                "Template processed",
                {
                    "template_name": template_name,
                    "storypack_name": context.storypack_name,
                    "import_mode": context.import_mode,
                },
            )

            return customized_data

        except Exception as e:
            self.logger.error(f"Failed to process template {template_name}: {e}")
            return template_data  # Return unprocessed template as fallback

    def _load_single_template(self, template_file: Path) -> dict[str, Any] | None:
        """Load a single template file."""
        try:
            with open(template_file, encoding="utf-8") as f:
                template_data = json.load(f)

            # Validate template structure
            if self._validate_template_structure(template_data):
                return template_data
            self.logger.warning(f"Invalid template structure in {template_file}")
            return None

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in template {template_file}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading template {template_file}: {e}")
            return None

    def _validate_template_structure(self, template_data: dict[str, Any]) -> bool:
        """Validate that template has required structure."""
        required_fields = ["template_info", "storypack_template"]

        for field in required_fields:
            if field not in template_data:
                return False

        # Validate template_info section
        template_info = template_data["template_info"]
        if not isinstance(template_info, dict):
            return False

        required_info_fields = ["name", "description", "version"]
        for field in required_info_fields:
            if field not in template_info:
                return False

        return True

    def _calculate_template_score(
        self, template_data: dict[str, Any], content_analysis: dict[str, Any]
    ) -> float:
        """Calculate how well a template matches the content analysis."""
        score = 0.0

        template_info = template_data.get("template_info", {})

        # Score based on template tags
        template_tags = template_info.get("tags", [])
        content_types = content_analysis.get("content_types_detected", [])

        # Tag matching
        matching_tags = set(template_tags) & set(content_types)
        if template_tags:
            tag_score = len(matching_tags) / len(template_tags)
            score += tag_score * 0.4

        # Content category matching
        template_categories = template_info.get("target_categories", [])
        content_categories = list(content_analysis.get("files_by_category", {}).keys())

        matching_categories = set(template_categories) & set(content_categories)
        if template_categories:
            category_score = len(matching_categories) / len(template_categories)
            score += category_score * 0.3

        # File count appropriateness
        total_files = content_analysis.get("total_files", 0)
        template_size = template_info.get("target_size", "medium")

        size_score = self._calculate_size_score(total_files, template_size)
        score += size_score * 0.2

        # Genre/theme matching
        template_themes = template_info.get("themes", [])
        if template_themes:
            # This would be enhanced with AI analysis of themes
            theme_score = 0.1  # Default small boost for having themes
            score += theme_score * 0.1

        return min(1.0, score)

    def _calculate_size_score(self, file_count: int, template_size: str) -> float:
        """Calculate score based on file count vs template target size."""
        thresholds = self.selection_criteria["file_count_thresholds"]

        if template_size == "small":
            return 1.0 if file_count <= thresholds["small"] else 0.5
        if template_size == "medium":
            return (
                1.0 if thresholds["small"] < file_count <= thresholds["medium"] else 0.7
            )
        if template_size == "large":
            return 1.0 if file_count > thresholds["medium"] else 0.6
        return 0.5  # Unknown size

    def _process_template_variables(
        self, template_data: dict[str, Any], context: ImportContext
    ) -> dict[str, Any]:
        """Process template variables with context values."""
        # Define template variables
        variables = {
            "${STORYPACK_NAME}": context.storypack_name,
            "${SOURCE_NAME}": context.source_path.name,
            "${IMPORT_MODE}": context.import_mode,
            "${CREATION_DATE}": context.target_path.stat().st_ctime
            if context.target_path.exists()
            else "",
            "${AI_ENABLED}": "Yes" if context.ai_available else "No",
        }

        # Process the template recursively
        processed_data = self._replace_variables_recursive(template_data, variables)

        return processed_data

    def _replace_variables_recursive(self, data: Any, variables: dict[str, str]) -> Any:
        """Recursively replace variables in template data."""
        if isinstance(data, str):
            # Replace all variables in the string
            result = data
            for var, value in variables.items():
                result = result.replace(var, str(value))
            return result

        if isinstance(data, dict):
            return {
                key: self._replace_variables_recursive(value, variables)
                for key, value in data.items()
            }

        if isinstance(data, list):
            return [self._replace_variables_recursive(item, variables) for item in data]

        return data

    def _apply_template_customizations(
        self, template_data: dict[str, Any], context: ImportContext
    ) -> dict[str, Any]:
        """Apply context-specific customizations to the template."""
        customized_data = template_data.copy()

        # Update storypack template with context-specific information
        if "storypack_template" in customized_data:
            storypack_template = customized_data["storypack_template"]

            # Update metadata fields
            if "metadata" in storypack_template:
                metadata = storypack_template["metadata"]
                metadata["storypack_id"] = context.storypack_name.lower().replace(
                    " ", "_"
                )
                metadata["title"] = context.storypack_name

                # Add import-specific metadata
                if "import_info" not in metadata:
                    metadata["import_info"] = {}

                metadata["import_info"].update(
                    {
                        "source_path": str(context.source_path),
                        "import_mode": context.import_mode,
                        "ai_processing": context.ai_available,
                        "template_used": template_data.get("template_info", {}).get(
                            "name", "Unknown"
                        ),
                    }
                )

        return customized_data
