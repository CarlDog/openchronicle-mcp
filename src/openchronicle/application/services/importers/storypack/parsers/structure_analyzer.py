#!/usr/bin/env python3
from openchronicle.application.services.importers.storypack.interfaces import (
    ContentFile,
    IStructureAnalyzer,
)
"""
OpenChronicle Structure Analyzer

Focused component for analyzing directory structures and organizing content.
Handles filesystem analysis and organization recommendations.
"""

from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_system_event





class StructureAnalyzer(IStructureAnalyzer):
    """Analyzes directory structures and provides organization recommendations."""

    def __init__(self):
        """Initialize the structure analyzer."""
        self.logger = get_logger()

        # Standard directory patterns
        self.expected_patterns = {
            "characters": ["characters", "people", "npcs", "char"],
            "locations": ["locations", "places", "settings", "world"],
            "lore": ["lore", "history", "background", "canon"],
            "narrative": ["story", "plot", "scenes", "chapters"],
        }

        # File organization preferences
        self.organization_weights = {
            "directory_structure": 0.4,
            "filename_patterns": 0.3,
            "content_analysis": 0.3,
        }

    def analyze_directory_structure(self, source_path: Path) -> dict[str, Any]:
        """
        Analyze the overall directory structure of the source.

        Args:
            source_path: Path to the source directory

        Returns:
            Dictionary containing structure analysis
        """
        if not source_path.exists():
            return {
                "status": "not_found",
                "error": f"Source path does not exist: {source_path}",
            }

        analysis = {
            "source_path": str(source_path),
            "is_organized": False,
            "organization_score": 0.0,
            "directory_count": 0,
            "file_count": 0,
            "subdirectories": {},
            "recognized_patterns": [],
            "organization_recommendations": [],
        }

        try:
            # Count files and directories
            directories = []
            all_files = []

            for item in source_path.rglob("*"):
                if item.is_file():
                    all_files.append(item)
                elif item.is_dir() and item != source_path:
                    directories.append(item)

            analysis["directory_count"] = len(directories)
            analysis["file_count"] = len(all_files)

            # Analyze subdirectory structure
            immediate_subdirs = [d for d in source_path.iterdir() if d.is_dir()]
            for subdir in immediate_subdirs:
                subdir_analysis = self._analyze_subdirectory(subdir)
                analysis["subdirectories"][subdir.name] = subdir_analysis

            # Check for recognized patterns
            analysis["recognized_patterns"] = self._identify_recognized_patterns(
                immediate_subdirs
            )

            # Calculate organization score
            analysis["organization_score"] = self._calculate_organization_score(
                analysis
            )
            analysis["is_organized"] = analysis["organization_score"] > 0.6

            # Generate recommendations
            analysis[
                "organization_recommendations"
            ] = self._generate_organization_recommendations(analysis)

            log_system_event(
                "structure_analyzer",
                "Directory analysis completed",
                {
                    "source_path": str(source_path),
                    "directory_count": analysis["directory_count"],
                    "file_count": analysis["file_count"],
                    "organization_score": analysis["organization_score"],
                    "is_organized": analysis["is_organized"],
                },
            )

        except Exception as e:
            self.logger.error(f"Error analyzing directory structure {source_path}: {e}")
            analysis["status"] = "error"
            analysis["error"] = str(e)

        return analysis

    def suggest_organization(
        self, discovered_files: dict[str, list[ContentFile]]
    ) -> dict[str, str]:
        """
        Suggest how to organize content files in the storypack.

        Args:
            discovered_files: Dictionary of categorized content files

        Returns:
            Dictionary mapping file paths to suggested organization paths
        """
        suggestions = {}

        for category, files in discovered_files.items():
            if not files:
                continue

            for content_file in files:
                suggested_path = self._suggest_file_organization(content_file, category)
                suggestions[str(content_file.path)] = suggested_path

        log_system_event(
            "structure_analyzer",
            "Organization suggestions generated",
            {
                "total_files": sum(len(files) for files in discovered_files.values()),
                "suggestions_count": len(suggestions),
                "categories": list(discovered_files.keys()),
            },
        )

        return suggestions

    def validate_source_structure(self, source_path: Path) -> tuple[bool, list[str]]:
        """
        Validate source directory structure for import readiness.

        Args:
            source_path: Path to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check if path exists
        if not source_path.exists():
            issues.append(f"Source path does not exist: {source_path}")
            return False, issues

        # Check if it's a directory
        if not source_path.is_dir():
            issues.append(f"Source path is not a directory: {source_path}")
            return False, issues

        # Check for any supported files
        supported_extensions = {".txt", ".md", ".json"}
        found_files = []

        try:
            for file_path in source_path.rglob("*"):
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in supported_extensions
                ):
                    found_files.append(file_path)
        except Exception as e:
            issues.append(f"Error scanning directory: {e}")
            return False, issues

        if not found_files:
            issues.append(
                "No supported content files (.txt, .md, .json) found in source directory"
            )

        # Check for overly complex structure
        if len(found_files) > 500:
            issues.append(
                f"Very large number of files ({len(found_files)}) may slow import process"
            )

        # Check for extremely deep nesting
        max_depth = 0
        for file_path in found_files:
            depth = len(file_path.relative_to(source_path).parts) - 1
            max_depth = max(max_depth, depth)

        if max_depth > 8:
            issues.append(
                f"Directory structure is very deep ({max_depth} levels) which may indicate poor organization"
            )

        # Check for very large files
        large_files = []
        for file_path in found_files:
            try:
                size = file_path.stat().st_size
                if size > 10 * 1024 * 1024:  # 10MB
                    large_files.append((file_path.name, size // (1024 * 1024)))
            except Exception:
                pass

        if large_files:
            files_info = ", ".join(
                f"{name} ({size}MB)" for name, size in large_files[:3]
            )
            issues.append(
                f"Found very large files that may slow processing: {files_info}"
            )

        is_valid = len(issues) == 0

        # Add warnings for non-critical issues
        if not is_valid and found_files:
            # If we have files but other issues, downgrade to warnings
            is_valid = True

        return is_valid, issues

    def _analyze_subdirectory(self, subdir_path: Path) -> dict[str, Any]:
        """Analyze a specific subdirectory."""
        analysis = {
            "name": subdir_path.name,
            "file_count": 0,
            "subdirectory_count": 0,
            "recognized_type": None,
            "confidence": 0.0,
        }

        try:
            files = []
            subdirs = []

            for item in subdir_path.iterdir():
                if item.is_file():
                    files.append(item)
                elif item.is_dir():
                    subdirs.append(item)

            analysis["file_count"] = len(files)
            analysis["subdirectory_count"] = len(subdirs)

            # Try to recognize the directory type
            dir_name_lower = subdir_path.name.lower()
            for content_type, keywords in self.expected_patterns.items():
                for keyword in keywords:
                    if keyword in dir_name_lower:
                        analysis["recognized_type"] = content_type
                        analysis["confidence"] = len(keyword) / len(dir_name_lower)
                        break
                if analysis["recognized_type"]:
                    break

        except Exception as e:
            self.logger.warning(f"Error analyzing subdirectory {subdir_path}: {e}")
            analysis["error"] = str(e)

        return analysis

    def _identify_recognized_patterns(
        self, subdirectories: list[Path]
    ) -> list[dict[str, Any]]:
        """Identify recognized organizational patterns in subdirectories."""
        patterns = []

        for subdir in subdirectories:
            dir_name_lower = subdir.name.lower()

            for content_type, keywords in self.expected_patterns.items():
                for keyword in keywords:
                    if keyword in dir_name_lower:
                        patterns.append(
                            {
                                "directory": subdir.name,
                                "recognized_as": content_type,
                                "keyword_match": keyword,
                                "confidence": len(keyword) / len(dir_name_lower),
                            }
                        )
                        break

        return patterns

    def _calculate_organization_score(self, analysis: dict[str, Any]) -> float:
        """Calculate how well-organized the source structure is."""
        score = 0.0

        # Bonus for recognized patterns
        if analysis["recognized_patterns"]:
            pattern_score = min(
                1.0, len(analysis["recognized_patterns"]) / 4
            )  # Up to 4 main categories
            score += pattern_score * 0.4

        # Penalty for too many files in root
        if analysis["subdirectories"]:
            # Check if most files are organized into subdirectories
            total_files = analysis["file_count"]
            root_files = total_files - sum(
                subdir["file_count"] for subdir in analysis["subdirectories"].values()
            )

            if total_files > 0:
                organization_ratio = 1 - (root_files / total_files)
                score += organization_ratio * 0.4

        # Bonus for reasonable structure depth and file distribution
        if analysis["subdirectories"]:
            avg_files_per_dir = sum(
                subdir["file_count"] for subdir in analysis["subdirectories"].values()
            ) / len(analysis["subdirectories"])

            # Optimal range: 3-20 files per directory
            if 3 <= avg_files_per_dir <= 20:
                score += 0.2
            elif avg_files_per_dir > 0:
                score += 0.1

        return min(1.0, score)

    def _generate_organization_recommendations(
        self, analysis: dict[str, Any]
    ) -> list[str]:
        """Generate recommendations for improving organization."""
        recommendations = []

        if analysis["organization_score"] < 0.3:
            recommendations.append(
                "Consider organizing files into category-based directories (characters, locations, lore, narrative)"
            )

        if not analysis["recognized_patterns"]:
            recommendations.append(
                "Use standard directory names: 'characters', 'locations', 'lore', 'narrative'"
            )

        if analysis["file_count"] > 50 and analysis["directory_count"] == 0:
            recommendations.append(
                "Large number of files would benefit from directory organization"
            )

        # Check for poor file distribution
        if analysis["subdirectories"]:
            large_dirs = [
                name
                for name, info in analysis["subdirectories"].items()
                if info["file_count"] > 30
            ]
            if large_dirs:
                recommendations.append(
                    f"Consider subdividing large directories: {', '.join(large_dirs)}"
                )

        return recommendations

    def _suggest_file_organization(
        self, content_file: ContentFile, category: str
    ) -> str:
        """Suggest organization path for a specific file."""
        # Use the detected category as the primary organization
        base_path = category

        # For uncategorized files, try to infer from filename
        if category == "uncategorized":
            filename_lower = content_file.path.stem.lower()
            for cat, keywords in self.expected_patterns.items():
                if any(keyword in filename_lower for keyword in keywords):
                    base_path = cat
                    break

        # Suggest filename based on content type and original name
        suggested_filename = content_file.path.name

        # Clean up filename if needed
        if suggested_filename.startswith("_") or suggested_filename.startswith("."):
            suggested_filename = suggested_filename.lstrip("_.")

        return f"{base_path}/{suggested_filename}"
