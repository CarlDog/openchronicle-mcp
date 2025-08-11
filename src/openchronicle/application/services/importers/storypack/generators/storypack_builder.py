#!/usr/bin/env python3
"""
OpenChronicle Storypack Builder

Focused component for creating storypack structures and organizing content.
Handles filesystem operations and storypack generation.
"""

import json
import shutil
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from src.openchronicle.shared.logging_system import get_logger
from src.openchronicle.shared.logging_system import log_system_event

from ..interfaces import ContentFile
from ..interfaces import ImportContext
from ..interfaces import IStorypackBuilder


class StorypackBuilder(IStorypackBuilder):
    """Builds storypack directory structures and organizes content files."""

    def __init__(self):
        """Initialize the storypack builder."""
        self.logger = get_logger()

        # Standard storypack structure
        self.standard_directories = ['characters', 'locations', 'lore', 'narrative']

        # File organization rules
        self.file_extensions = {
            'content': '.json',
            'readme': '.md',
            'metadata': '.json'
        }

    def create_storypack_structure(self, context: ImportContext) -> Path:
        """
        Create the directory structure for a new storypack.
        
        Args:
            context: Import context containing storypack information
            
        Returns:
            Path to the created storypack directory
        """
        storypack_path = context.target_path

        try:
            # Create main storypack directory
            storypack_path.mkdir(parents=True, exist_ok=True)

            # Create standard content directories
            created_dirs = []
            for directory in self.standard_directories:
                dir_path = storypack_path / directory
                dir_path.mkdir(exist_ok=True)
                created_dirs.append(directory)

                # Create a placeholder README in each directory
                self._create_directory_readme(dir_path, directory)

            # Create main storypack README
            self._create_main_readme(storypack_path, context)

            log_system_event("storypack_builder", "Storypack structure created", {
                "storypack_path": str(storypack_path),
                "storypack_name": context.storypack_name,
                "directories_created": created_dirs,
                "import_mode": context.import_mode
            })

            return storypack_path

        except Exception as e:
            self.logger.error(f"Failed to create storypack structure at {storypack_path}: {e}")
            raise

    def generate_metadata_file(self, context: ImportContext, content_summary: dict[str, Any]) -> dict[str, Any]:
        """
        Generate the meta.json file for the storypack.
        
        Args:
            context: Import context
            content_summary: Summary of processed content
            
        Returns:
            Dictionary containing metadata that was written to file
        """
        metadata = {
            "storypack_id": context.storypack_name.lower().replace(" ", "_"),
            "title": context.storypack_name,
            "version": "1.0.0",
            "description": f"Storypack imported from {context.source_path.name}",
            "author": "Imported Content",
            "created_date": datetime.now(UTC).isoformat(),
            "last_modified": datetime.now(UTC).isoformat(),
            "import_info": {
                "source_path": str(context.source_path),
                "import_mode": context.import_mode,
                "import_timestamp": datetime.now(UTC).isoformat(),
                "total_files_imported": content_summary.get('total_files', 0),
                "ai_processing_used": context.ai_available,
                "content_categories": list(content_summary.get('files_by_category', {}).keys())
            },
            "content_stats": {
                "total_files": content_summary.get('total_files', 0),
                "files_by_category": content_summary.get('files_by_category', {}),
                "content_types": content_summary.get('content_types_detected', []),
                "structure_quality_score": content_summary.get('structure_score', 0.0)
            },
            "storypack_format_version": "2.0",
            "openchronicle_version": "0.1.x"
        }

        # Add template information if templates were used
        if context.templates_available:
            metadata["template_info"] = {
                "templates_available": context.templates_available,
                "templates_used": []  # Will be populated by template engine
            }

        try:
            # Write metadata file
            meta_path = context.target_path / "meta.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            log_system_event("storypack_builder", "Metadata file generated", {
                "meta_path": str(meta_path),
                "storypack_id": metadata["storypack_id"],
                "total_files": metadata["content_stats"]["total_files"]
            })

        except Exception as e:
            self.logger.error(f"Failed to generate metadata file: {e}")
            raise

        return metadata

    def organize_content_files(self, discovered_files: dict[str, list[ContentFile]],
                              target_path: Path) -> dict[str, list[Path]]:
        """
        Organize and copy content files to storypack structure.
        
        Args:
            discovered_files: Categorized content files
            target_path: Target storypack directory
            
        Returns:
            Dictionary mapping categories to lists of copied file paths
        """
        organized_files = {category: [] for category in self.standard_directories}
        organized_files['uncategorized'] = []

        for category, files in discovered_files.items():
            if not files:
                continue

            # Determine target directory
            if category in self.standard_directories:
                target_dir = target_path / category
            else:
                target_dir = target_path / 'uncategorized'
                category = 'uncategorized'  # Remap for tracking

            # Ensure target directory exists
            target_dir.mkdir(exist_ok=True)

            for content_file in files:
                try:
                    # Generate target filename
                    target_filename = self._generate_target_filename(content_file, target_dir)
                    target_file_path = target_dir / target_filename

                    # Copy file with content processing
                    self._copy_and_process_file(content_file.path, target_file_path)

                    organized_files[category].append(target_file_path)

                except Exception as e:
                    self.logger.error(f"Failed to organize file {content_file.path}: {e}")
                    continue

        # Remove empty categories from result
        organized_files = {cat: files for cat, files in organized_files.items() if files}

        log_system_event("storypack_builder", "Content files organized", {
            "target_path": str(target_path),
            "categories_organized": list(organized_files.keys()),
            "total_files_organized": sum(len(files) for files in organized_files.values())
        })

        return organized_files

    def _create_directory_readme(self, dir_path: Path, category: str) -> None:
        """Create a helpful README file in content directories."""
        readme_content = self._get_directory_readme_content(category)
        readme_path = dir_path / "README.md"

        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
        except Exception as e:
            self.logger.warning(f"Failed to create directory README for {category}: {e}")

    def _create_main_readme(self, storypack_path: Path, context: ImportContext) -> None:
        """Create the main README file for the storypack."""
        readme_content = f"""# {context.storypack_name}

This storypack was imported from `{context.source_path.name}` on {datetime.now(UTC).strftime('%Y-%m-%d at %H:%M UTC')}.

## Structure

- **characters/**: Character profiles and information
- **locations/**: Setting descriptions and world-building
- **lore/**: Background information, history, and world lore
- **narrative/**: Story content, scenes, and plot elements

## Import Information

- **Import Mode**: {context.import_mode}
- **AI Processing**: {'Enabled' if context.ai_available else 'Disabled'}
- **Templates Available**: {len(context.templates_available)}
- **Source Path**: `{context.source_path}`

## Usage

This storypack is compatible with OpenChronicle's narrative AI engine. You can:

1. Load the storypack in OpenChronicle
2. Explore the organized content
3. Use the AI system to generate new content based on the imported material
4. Expand and modify the content as needed

## File Format

All content files are stored in JSON format for compatibility with OpenChronicle's processing systems.
Original file formats and content have been preserved during import.
"""

        readme_path = storypack_path / "README.md"

        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
        except Exception as e:
            self.logger.warning(f"Failed to create main README: {e}")

    def _get_directory_readme_content(self, category: str) -> str:
        """Get README content for specific content directories."""
        content_descriptions = {
            'characters': """# Characters

This directory contains character profiles and information.

## File Organization

Each character should have their own JSON file with the following structure:

```json
{
  "name": "Character Name",
  "description": "Brief description",
  "attributes": {
    "age": "Character age",
    "occupation": "What they do",
    "personality": "Key personality traits",
    "appearance": "Physical description"
  },
  "background": "Character backstory",
  "relationships": [],
  "notes": "Additional notes"
}
```

## Guidelines

- Use descriptive filenames (e.g., `protagonist_john_smith.json`)
- Include both major and minor characters
- Keep descriptions concise but informative
""",
            'locations': """# Locations

This directory contains setting descriptions and world-building information.

## File Organization

Each location should have its own JSON file with the following structure:

```json
{
  "name": "Location Name",
  "description": "Detailed description",
  "attributes": {
    "type": "city/forest/building/etc",
    "size": "small/medium/large",
    "climate": "Climate description",
    "population": "Who lives/visits here"
  },
  "notable_features": [],
  "connections": [],
  "notes": "Additional notes"
}
```

## Guidelines

- Organize by scale (regions > cities > buildings > rooms)
- Include both major locations and minor settings
- Describe atmosphere and mood, not just physical features
""",
            'lore': """# Lore

This directory contains background information, history, and world lore.

## File Organization

Lore files can cover various topics:

```json
{
  "title": "Lore Topic",
  "type": "history/legend/culture/religion/etc",
  "description": "Detailed information",
  "related_characters": [],
  "related_locations": [],
  "timeline": "When this occurred or applies",
  "notes": "Additional context"
}
```

## Guidelines

- Organize by topic or chronology
- Include myths, legends, and cultural information
- Connect lore to characters and locations when relevant
""",
            'narrative': """# Narrative

This directory contains story content, scenes, and plot elements.

## File Organization

Narrative files can include:

```json
{
  "title": "Scene or Chapter Title",
  "type": "scene/chapter/outline/notes",
  "content": "The actual narrative content",
  "characters_involved": [],
  "location": "Where this takes place",
  "timeline": "When this occurs",
  "notes": "Plot notes or directions"
}
```

## Guidelines

- Organize chronologically or by story arc
- Include both finished scenes and plot outlines
- Reference characters and locations from other directories
"""
        }

        return content_descriptions.get(category, f"# {category.title()}\n\nContent files for {category}.")

    def _generate_target_filename(self, content_file: ContentFile, target_dir: Path) -> str:
        """Generate an appropriate filename for the target location."""
        original_name = content_file.path.stem
        original_extension = content_file.path.suffix

        # Clean up the filename
        clean_name = original_name.replace(' ', '_').replace('-', '_')
        clean_name = ''.join(c for c in clean_name if c.isalnum() or c in ['_', '.']).lower()

        # Ensure it's not empty
        if not clean_name:
            clean_name = "imported_content"

        # Use JSON extension for content files
        target_extension = self.file_extensions['content']

        # Ensure uniqueness
        base_filename = f"{clean_name}{target_extension}"
        target_path = target_dir / base_filename

        counter = 1
        while target_path.exists():
            target_path = target_dir / f"{clean_name}_{counter}{target_extension}"
            counter += 1

        return target_path.name

    def _copy_and_process_file(self, source_path: Path, target_path: Path) -> None:
        """Copy and process a file to the target location."""
        try:
            # Read source content
            with open(source_path, encoding='utf-8') as f:
                content = f.read()

            # Convert content to JSON format for standardization
            processed_content = self._convert_to_json_format(content, source_path)

            # Write processed content
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(processed_content, f, indent=2, ensure_ascii=False)

        except Exception as e:
            # If processing fails, fall back to direct copy
            self.logger.warning(f"Content processing failed for {source_path}, copying directly: {e}")
            try:
                shutil.copy2(source_path, target_path)
            except Exception as copy_error:
                self.logger.error(f"Failed to copy {source_path} to {target_path}: {copy_error}")
                raise

    def _convert_to_json_format(self, content: str, source_path: Path) -> dict[str, Any]:
        """Convert content to standardized JSON format."""
        # If already JSON, parse and return
        if source_path.suffix.lower() == '.json':
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass  # Fall through to text processing

        # Convert text content to structured JSON
        json_content = {
            "title": source_path.stem.replace('_', ' ').title(),
            "source_file": source_path.name,
            "content": content,
            "format": "imported_text",
            "import_timestamp": datetime.now(UTC).isoformat(),
            "original_extension": source_path.suffix
        }

        # Try to extract structure from Markdown
        if source_path.suffix.lower() == '.md':
            json_content["format"] = "imported_markdown"
            json_content.update(self._parse_markdown_structure(content))

        return json_content

    def _parse_markdown_structure(self, content: str) -> dict[str, Any]:
        """Parse Markdown content to extract structure."""
        import re

        structure = {
            "headers": [],
            "sections": {},
            "metadata_fields": {}
        }

        # Extract headers
        header_pattern = re.compile(r'^(#+)\s+(.+)$', re.MULTILINE)
        headers = header_pattern.findall(content)

        for level_hashes, title in headers:
            structure["headers"].append({
                "level": len(level_hashes),
                "title": title.strip()
            })

        # Extract metadata-like fields (key: value patterns)
        metadata_pattern = re.compile(r'^\*\*([^*]+)\*\*:\s*(.+)$', re.MULTILINE)
        metadata_matches = metadata_pattern.findall(content)

        for key, value in metadata_matches:
            structure["metadata_fields"][key.strip().lower()] = value.strip()

        return structure
