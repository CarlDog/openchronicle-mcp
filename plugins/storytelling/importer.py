"""Import pipeline for storytelling projects.

Walks a directory of text files, classifies them, parses them into
memory items, and saves them via the handler context closures.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .parsers import classify_file, parse_file, should_skip_file

logger = logging.getLogger(__name__)

# File extensions we attempt to parse
_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}


@dataclass
class ImportResult:
    """Summary of an import operation."""

    project_name: str
    imported: dict[str, int] = field(default_factory=dict)
    assets_uploaded: int = 0
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def import_project(
    source_dir: str,
    project_name: str,
    memory_save: Callable[..., Any],
    dry_run: bool = False,
    asset_upload: Callable[..., Any] | None = None,
) -> ImportResult:
    """Import a storytelling project from a directory of text files.

    Args:
        source_dir: Path to the project directory.
        project_name: Human-readable project name (used in content formatting).
        memory_save: Pre-bound memory_save closure from handler context.
        dry_run: If True, parse and classify but don't save anything.
        asset_upload: Optional asset upload function for preserving original files.

    Returns:
        ImportResult with counts, skipped files, and warnings.
    """
    source_path = Path(source_dir)
    if not source_path.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    result = ImportResult(project_name=project_name)
    counts: Counter[str] = Counter()

    # Collect all text files recursively
    text_files = sorted(f for f in source_path.rglob("*") if f.is_file() and f.suffix.lower() in _TEXT_EXTENSIONS)

    if not text_files:
        result.warnings.append(f"No text files found in {source_dir}")
        return result

    for file_path in text_files:
        filename = file_path.name

        # Skip known junk files
        if should_skip_file(filename):
            result.skipped.append(filename)
            logger.info("Skipped: %s (excluded by skip pattern)", filename)
            continue

        # Read file content
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.warnings.append(f"Could not read {filename}: {exc}")
            result.skipped.append(filename)
            continue

        if not text.strip():
            result.skipped.append(filename)
            continue

        # Classify and parse
        content_type = classify_file(filename)
        entities = parse_file(text, content_type, project_name, filename)

        # Save each parsed entity as a memory item
        for entity in entities:
            if not dry_run:
                memory_save(
                    content=entity.formatted_content,
                    tags=entity.tags,
                    pinned=entity.pinned,
                )
            counts[entity.content_type.value] += 1

        # Upload original file as asset
        if asset_upload and not dry_run:
            try:
                asset_upload(str(file_path))
                result.assets_uploaded += 1
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"Asset upload failed for {filename}: {exc}")

    # Create project metadata entry
    if not dry_run:
        meta_content = _build_project_meta(project_name, counts)
        memory_save(content=meta_content, tags=["story", "project-meta"], pinned=False)
    counts["project-meta"] += 1

    result.imported = dict(counts)
    logger.info(
        "Import complete for '%s': %s items, %d assets, %d skipped",
        project_name,
        dict(counts),
        result.assets_uploaded,
        len(result.skipped),
    )
    return result


def _build_project_meta(project_name: str, counts: Counter[str]) -> str:
    """Build the project metadata memory content."""
    lines = [
        f"[Project] {project_name}",
        "Type: Storytelling Project",
        "",
    ]

    # Summarize imported content
    for content_type, count in sorted(counts.items()):
        if content_type != "project-meta":
            lines.append(f"{content_type}: {count} items")

    return "\n".join(lines)
