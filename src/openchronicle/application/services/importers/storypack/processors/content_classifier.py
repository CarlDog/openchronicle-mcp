from openchronicle.domain.ports.storypack_port import IStorypackProcessorPort\n\n#!/usr/bin/env python3
"""
OpenChronicle Content Classifier

Focused component for content classification and analysis.
Works independently of AI processing for basic classification.
"""

import re
from typing import Any

from openchronicle.shared.logging_system import get_logger




class ContentClassifier(IContentClassifier):
    """Classifies content based on patterns and heuristics."""

    def __init__(self):
        """Initialize the content classifier."""
        self.logger = get_logger()

        # Classification patterns
        self.classification_patterns = {
            "character_profile": {
                "keywords": [
                    "age:",
                    "personality:",
                    "appearance:",
                    "background:",
                    "occupation:",
                    "skills:",
                ],
                "structures": [
                    r"^\s*\*\*\s*(name|age|personality|appearance)\s*:\*\*",
                    r"^#+\s+(personality|background|appearance)",
                ],
                "weight": 0.8,
            },
            "location_description": {
                "keywords": [
                    "geography:",
                    "climate:",
                    "population:",
                    "description:",
                    "notable features:",
                    "history:",
                ],
                "structures": [
                    r"^\s*\*\*\s*(location|geography|climate|population)\s*:\*\*",
                    r"^#+\s+(geography|climate|description)",
                ],
                "weight": 0.8,
            },
            "narrative_scene": {
                "keywords": ['"', "said", "walked", "looked", "felt", "thought"],
                "structures": [
                    r'"[^"]*"',
                    r"\b(he|she|they)\s+(said|walked|looked|felt)",
                ],
                "weight": 0.7,
            },
            "lore_document": {
                "keywords": [
                    "history:",
                    "legend:",
                    "mythology:",
                    "ancient",
                    "tradition:",
                    "origin:",
                ],
                "structures": [
                    r"^#+\s+(history|legend|mythology|origin)",
                    r"long ago",
                    r"in the beginning",
                ],
                "weight": 0.8,
            },
            "dialogue_heavy": {
                "keywords": [
                    '"',
                    "'",
                    "said",
                    "asked",
                    "replied",
                    "whispered",
                    "shouted",
                ],
                "structures": [r'"[^"]*"', r"'[^']*'", r"\b\w+\s+said\b"],
                "weight": 0.6,
            },
            "structured_notes": {
                "keywords": ["note:", "todo:", "important:", "remember:", "ideas:"],
                "structures": [r"^\s*-\s+", r"^\s*\*\s+", r"^\s*\d+\.\s+"],
                "weight": 0.5,
            },
        }

        # Confidence thresholds
        self.confidence_thresholds = {"high": 0.8, "medium": 0.6, "low": 0.4}

    def classify_by_content(self, content: str) -> str:
        """
        Classify content based on its actual content.

        Args:
            content: Text content to classify

        Returns:
            Classification type
        """
        if not content or not content.strip():
            return "empty"

        content_lower = content.lower()
        classification_scores = {}

        # Calculate scores for each classification type
        for classification_type, patterns in self.classification_patterns.items():
            score = self._calculate_classification_score(
                content, content_lower, patterns
            )
            classification_scores[classification_type] = score

        # Find the best classification
        if classification_scores:
            best_classification = max(classification_scores.items(), key=lambda x: x[1])

            if best_classification[1] >= self.confidence_thresholds["low"]:
                return best_classification[0]

        # Default classification based on simple heuristics
        return self._fallback_classification(content, content_lower)

    def classify_by_structure(self, content: str) -> dict[str, Any]:
        """
        Analyze content structure patterns.

        Args:
            content: Text content to analyze

        Returns:
            Dictionary containing structure analysis
        """
        structure_analysis = {
            "line_count": 0,
            "paragraph_count": 0,
            "header_count": 0,
            "list_items": 0,
            "dialogue_lines": 0,
            "has_metadata_fields": False,
            "structure_type": "unstructured",
            "formatting_style": "plain",
        }

        if not content:
            return structure_analysis

        lines = content.split("\n")
        structure_analysis["line_count"] = len(lines)

        # Count paragraphs (groups of non-empty lines)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        structure_analysis["paragraph_count"] = len(paragraphs)

        # Analyze line patterns
        header_pattern = re.compile(r"^#+\s+")
        list_pattern = re.compile(r"^\s*[-*+]\s+|^\s*\d+\.\s+")
        dialogue_pattern = re.compile(r'"[^"]*"')
        metadata_pattern = re.compile(r"^\s*\w+\s*:\s*.+$")

        metadata_lines = 0

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Count headers
            if header_pattern.match(line):
                structure_analysis["header_count"] += 1

            # Count list items
            if list_pattern.match(line):
                structure_analysis["list_items"] += 1

            # Count dialogue
            if dialogue_pattern.search(line):
                structure_analysis["dialogue_lines"] += 1

            # Check for metadata fields (key: value patterns)
            if metadata_pattern.match(line):
                metadata_lines += 1

        structure_analysis["has_metadata_fields"] = metadata_lines >= 2

        # Determine structure type
        structure_analysis["structure_type"] = self._determine_structure_type(
            structure_analysis
        )

        # Determine formatting style
        structure_analysis["formatting_style"] = self._determine_formatting_style(
            content
        )

        return structure_analysis

    def get_confidence_score(self, content: str, category: str) -> float:
        """
        Get confidence score for content categorization.

        Args:
            content: Text content
            category: Category to score against

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if category not in self.classification_patterns:
            return 0.0

        content_lower = content.lower()
        patterns = self.classification_patterns[category]

        score = self._calculate_classification_score(content, content_lower, patterns)
        return min(1.0, score)

    def _calculate_classification_score(
        self, content: str, content_lower: str, patterns: dict[str, Any]
    ) -> float:
        """Calculate classification score for given patterns."""
        score = 0.0
        total_weight = patterns["weight"]

        # Score keywords
        keyword_matches = 0
        for keyword in patterns["keywords"]:
            if keyword.lower() in content_lower:
                keyword_matches += 1

        if patterns["keywords"]:
            keyword_score = (keyword_matches / len(patterns["keywords"])) * 0.6
            score += keyword_score

        # Score structural patterns
        structure_matches = 0
        for pattern in patterns["structures"]:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                structure_matches += 1

        if patterns["structures"]:
            structure_score = (structure_matches / len(patterns["structures"])) * 0.4
            score += structure_score

        return score * total_weight

    def _fallback_classification(self, content: str, content_lower: str) -> str:
        """Provide fallback classification using simple heuristics."""
        # Check for dialogue indicators
        if '"' in content and content.count('"') >= 4:
            return "dialogue_heavy"

        # Check for list-like structure
        if re.search(r"^\s*[-*+]\s+", content, re.MULTILINE):
            return "structured_notes"

        # Check for metadata structure
        if re.search(r"^\s*\w+\s*:\s*.+$", content, re.MULTILINE):
            metadata_lines = len(
                re.findall(r"^\s*\w+\s*:\s*.+$", content, re.MULTILINE)
            )
            if metadata_lines >= 3:
                return "structured_data"

        # Check content length and complexity
        word_count = len(content.split())
        if word_count < 50:
            return "notes_or_fragments"
        if word_count > 500:
            return "long_form_content"
        return "standard_text"

    def _determine_structure_type(self, structure_analysis: dict[str, Any]) -> str:
        """Determine overall structure type from analysis."""
        if structure_analysis["has_metadata_fields"]:
            return "metadata_structured"
        if structure_analysis["header_count"] >= 3:
            return "header_structured"
        if structure_analysis["list_items"] >= 5:
            return "list_structured"
        if structure_analysis["dialogue_lines"] >= 3:
            return "dialogue_structured"
        if structure_analysis["paragraph_count"] >= 3:
            return "paragraph_structured"
        return "unstructured"

    def _determine_formatting_style(self, content: str) -> str:
        """Determine formatting style used in content."""
        # Check for Markdown indicators
        markdown_indicators = [
            r"^#+\s+",  # Headers
            r"\*\*[^*]+\*\*",  # Bold
            r"\*[^*]+\*",  # Italic
            r"^\s*[-*+]\s+",  # Lists
            r"```",  # Code blocks
        ]

        markdown_matches = sum(
            1
            for pattern in markdown_indicators
            if re.search(pattern, content, re.MULTILINE)
        )

        if markdown_matches >= 2:
            return "markdown"

        # Check for other formatting
        if re.search(r"<[^>]+>", content):
            return "html"
        if re.search(r"^\s*\w+\s*:\s*.+$", content, re.MULTILINE):
            return "structured_fields"
        return "plain_text"
