"""File classification and content parsing for storytelling import.

Classifies files by filename patterns and splits multi-entity files into
individual ParsedEntity instances. No LLM calls — all parsing is heuristic.
"""

from __future__ import annotations

import re
from pathlib import Path

from .domain.entities import ContentType, ParsedEntity

# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

_CLASSIFICATION_RULES: list[tuple[list[str], ContentType]] = [
    (["character", "profile", "cast"], ContentType.CHARACTER),
    (["location", "setting", "place", "landmark"], ContentType.LOCATION),
    (["style*guide", "writing*guide", "style_guide"], ContentType.STYLE_GUIDE),
    (["instruction", "directive", "rules", "canon*tracking"], ContentType.INSTRUCTIONS),
    (["scene", "chapter", "episode"], ContentType.SCENE),
]

# Files to skip entirely (case-insensitive substring match)
_SKIP_PATTERNS = ["non-canon firepit", "non_canon_firepit"]


def should_skip_file(filename: str) -> bool:
    """Check if a file should be skipped during import."""
    lower = filename.lower()
    return any(skip in lower for skip in _SKIP_PATTERNS)


def classify_file(filename: str) -> ContentType:
    """Classify a file by its filename into a content type.

    Uses case-insensitive pattern matching against filename.
    Falls back to WORLDBUILDING for unrecognized files.
    """
    lower = filename.lower()
    for patterns, content_type in _CLASSIFICATION_RULES:
        for pattern in patterns:
            if "*" in pattern:
                # Glob-like: "style*guide" matches "style guide", "style_guide", etc.
                parts = pattern.split("*")
                if all(part in lower for part in parts):
                    return content_type
            elif pattern in lower:
                return content_type
    return ContentType.WORLDBUILDING


# ---------------------------------------------------------------------------
# Content parsers
# ---------------------------------------------------------------------------

# Threshold (in lines) above which a character profile is classified as primary
_PRIMARY_LINE_THRESHOLD = 15


def _strip_file_header(text: str) -> str:
    """Remove common file-level headers like [CORE FILE – DO NOT MODIFY...]."""
    # Strip leading lines that are file-level metadata
    lines = text.strip().split("\n")
    cleaned: list[str] = []
    skipping_header = True
    for line in lines:
        stripped = line.strip()
        if skipping_header:
            if stripped.startswith("[CORE FILE") or stripped == "":
                continue
            skipping_header = False
        cleaned.append(line)
    return "\n".join(cleaned)


def parse_character_file(text: str, project_name: str) -> list[ParsedEntity]:
    """Parse a character file into individual character entities.

    Handles two formats:
    1. Bracketed headers: [CHARACTER PROFILE – NAME]
    2. Name-line entries: Name: Foo (for minor characters)
    """
    text = _strip_file_header(text)

    # Try bracketed header format first (primary characters)
    bracketed = re.split(r"\[(?:CHARACTER PROFILE|MINOR CHARACTER PROFILE)\s*[–—-]\s*", text)
    if len(bracketed) > 1:
        return _parse_bracketed_characters(bracketed, project_name)

    # Try section-header format: [MINOR CHARACTER PROFILE – REGION]
    # followed by Name: entries separated by blank lines
    if re.search(r"^Name:\s+", text, re.MULTILINE):
        return _parse_name_line_characters(text, project_name)

    # Single character — entire file is one profile
    name = _extract_first_name(text) or "Unknown Character"
    is_primary = len(text.strip().split("\n")) >= _PRIMARY_LINE_THRESHOLD
    role_tag = "primary" if is_primary else "npc"
    return [
        ParsedEntity(
            name=name,
            content_type=ContentType.CHARACTER,
            formatted_content=_format_character(name, role_tag, project_name, text.strip()),
            tags=["story", "character", role_tag],
        )
    ]


def _parse_bracketed_characters(sections: list[str], project_name: str) -> list[ParsedEntity]:
    """Parse characters from bracketed [CHARACTER PROFILE – NAME] sections."""
    entities: list[str | ParsedEntity] = []
    for section in sections[1:]:  # Skip text before first bracket
        # The section starts right after the bracket, so first line has the name + closing ]
        lines = section.strip().split("\n")
        if not lines:
            continue
        # First line: "CARL ASHCOMBE]\n" or "DOVECOAST & REGION]\n"
        header = lines[0].rstrip("]").strip()

        # Skip region/category headers (not character names)
        if any(kw in header.upper() for kw in ["REGION", "SURROUNDINGS", "CATEGORY"]):
            # This is a category header for minor characters, parse body below
            body = "\n".join(lines[1:]).strip()
            if re.search(r"^Name:\s+", body, re.MULTILINE):
                entities.extend(_parse_name_line_characters(body, project_name))
            continue

        name = header.title()
        body = "\n".join(lines[1:]).strip()
        line_count = len(body.split("\n"))
        is_primary = line_count >= _PRIMARY_LINE_THRESHOLD
        role_tag = "primary" if is_primary else "npc"
        entities.append(
            ParsedEntity(
                name=name,
                content_type=ContentType.CHARACTER,
                formatted_content=_format_character(name, role_tag, project_name, body),
                tags=["story", "character", role_tag],
            )
        )
    return [e for e in entities if isinstance(e, ParsedEntity)]


def _parse_name_line_characters(text: str, project_name: str) -> list[ParsedEntity]:
    """Parse characters from Name: line format (typically minor/NPC characters)."""
    entities: list[ParsedEntity] = []
    # Split on blank lines between entries
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name_match = re.match(r"^Name:\s*(.+)", block)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        line_count = len(block.split("\n"))
        is_primary = line_count >= _PRIMARY_LINE_THRESHOLD
        role_tag = "primary" if is_primary else "npc"
        entities.append(
            ParsedEntity(
                name=name,
                content_type=ContentType.CHARACTER,
                formatted_content=_format_character(name, role_tag, project_name, block),
                tags=["story", "character", role_tag],
            )
        )
    return entities


def _format_character(name: str, role_tag: str, project_name: str, body: str) -> str:
    """Format a character into the standard memory content format."""
    role_label = "Primary" if role_tag == "primary" else "NPC"
    return f"[Character] {name}\nRole: {role_label} | Status: Active\nProject: {project_name}\n\n{body}"


def _extract_first_name(text: str) -> str | None:
    """Try to extract a character name from the first few lines."""
    for line in text.strip().split("\n")[:5]:
        line = line.strip()
        name_match = re.match(r"^(?:Name|Character):\s*(.+)", line, re.IGNORECASE)
        if name_match:
            return name_match.group(1).strip()
    return None


def parse_location_file(text: str, project_name: str) -> list[ParsedEntity]:
    """Parse a location file into individual location entities.

    Handles numbered entries (1. Name), named entries separated by blank lines,
    and section-based organization with --- separators.
    """
    text = _strip_file_header(text)
    entities: list[ParsedEntity] = []

    # Split on --- separators for major sections
    sections = re.split(r"\n---\n", text)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Check for section category header (ALL CAPS line at the start)
        lines = section.split("\n")
        category_header = ""
        body_start = 0
        if lines and lines[0].strip().isupper() and len(lines[0].strip().split()) <= 6:
            category_header = lines[0].strip()
            body_start = 1

        body = "\n".join(lines[body_start:]).strip()
        if not body:
            continue

        # Try numbered entries (1. Name\nDescription...)
        numbered = re.split(r"\n(?=\d+\.\s+)", body)
        if len(numbered) > 1 or re.match(r"^\d+\.\s+", body):
            for entry in numbered:
                entry = entry.strip()
                if not entry:
                    continue
                match = re.match(r"^\d+\.\s+(.+?)(?:\n|$)", entry)
                if match:
                    name = match.group(1).strip()
                    entities.append(
                        ParsedEntity(
                            name=name,
                            content_type=ContentType.LOCATION,
                            formatted_content=_format_location(name, project_name, entry),
                            tags=["story", "location"],
                        )
                    )
            continue

        # Try blank-line-separated entries with a name on the first line
        blocks = re.split(r"\n\s*\n", body)
        if len(blocks) > 1:
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                first_line = block.split("\n")[0].strip()
                # Skip if it looks like metadata (Key: Value on first line with no name-like content)
                if re.match(r"^(Town Name|Population|Vibe|Atmosphere):", first_line, re.IGNORECASE):
                    # This is a town overview block — treat as a single location
                    name = _extract_location_name(block) or "Overview"
                    entities.append(
                        ParsedEntity(
                            name=name,
                            content_type=ContentType.LOCATION,
                            formatted_content=_format_location(name, project_name, block),
                            tags=["story", "location"],
                        )
                    )
                    continue
                # Use first line as location name
                name = re.sub(r"\s*\(.*?\)\s*$", "", first_line)  # Strip parentheticals
                entities.append(
                    ParsedEntity(
                        name=name,
                        content_type=ContentType.LOCATION,
                        formatted_content=_format_location(name, project_name, block),
                        tags=["story", "location"],
                    )
                )
            continue

        # Single entry — whole section is one location
        name = _extract_location_name(body) or category_header or "Unknown Location"
        entities.append(
            ParsedEntity(
                name=name,
                content_type=ContentType.LOCATION,
                formatted_content=_format_location(name, project_name, body),
                tags=["story", "location"],
            )
        )

    return entities


def _format_location(name: str, project_name: str, body: str) -> str:
    """Format a location into the standard memory content format."""
    return f"[Location] {name}\nProject: {project_name}\n\n{body}"


def _extract_location_name(text: str) -> str | None:
    """Try to extract a location name from text."""
    match = re.match(r"^(?:Town Name|Location|Name):\s*(.+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def parse_style_guide_file(text: str, project_name: str) -> list[ParsedEntity]:
    """Parse a style guide into individual section entities.

    Handles sections separated by ===== rule + TITLE + ===== rule.
    Also handles ## markdown headers.
    """
    text = _strip_file_header(text)
    entities: list[ParsedEntity] = []

    # Try ===== separator format first
    sections = re.split(r"={5,}\n(.+?)\n={5,}", text)
    if len(sections) > 1:
        # sections[0] is text before first separator (header/preamble)
        # sections[1] is first title, sections[2] is first body, etc.
        for i in range(1, len(sections), 2):
            title = sections[i].strip()
            body = sections[i + 1].strip() if i + 1 < len(sections) else ""
            if not body or title.upper() == "VERSION CHANGELOG":
                continue
            # Skip duplicate "End of" markers
            if title.upper().startswith("CLOSING ETHOS") and _is_duplicate_closing(body, entities):
                continue
            entities.append(
                ParsedEntity(
                    name=title.title(),
                    content_type=ContentType.STYLE_GUIDE,
                    formatted_content=_format_style_section(title, project_name, body),
                    tags=["story", "style-guide"],
                )
            )
        return entities

    # Try ## markdown header format
    md_sections = re.split(r"\n(?=##\s+)", text)
    if len(md_sections) > 1:
        for section in md_sections:
            section = section.strip()
            if not section:
                continue
            match = re.match(r"^##\s+(.+)", section)
            if match:
                title = match.group(1).strip()
                body = section[match.end() :].strip()
                entities.append(
                    ParsedEntity(
                        name=title,
                        content_type=ContentType.STYLE_GUIDE,
                        formatted_content=_format_style_section(title, project_name, body),
                        tags=["story", "style-guide"],
                    )
                )
        return entities

    # Single section — whole file
    entities.append(
        ParsedEntity(
            name="Style Guide",
            content_type=ContentType.STYLE_GUIDE,
            formatted_content=_format_style_section("Style Guide", project_name, text.strip()),
            tags=["story", "style-guide"],
        )
    )
    return entities


def _is_duplicate_closing(body: str, existing: list[ParsedEntity]) -> bool:
    """Check if a Closing Ethos section is a duplicate."""
    return any(e.name.upper() == "CLOSING ETHOS" for e in existing)


def _format_style_section(title: str, project_name: str, body: str) -> str:
    """Format a style guide section into the standard memory content format."""
    return f"[Style Guide] {title}\nProject: {project_name}\n\n{body}"


def parse_instructions_file(text: str, project_name: str) -> ParsedEntity:
    """Parse an instructions/directive file as a single entity."""
    text = _strip_file_header(text)
    # Try to extract a title from the first line
    first_line = text.strip().split("\n")[0].strip() if text.strip() else "Project Instructions"
    name = first_line[:80] if first_line else "Project Instructions"
    return ParsedEntity(
        name=name,
        content_type=ContentType.INSTRUCTIONS,
        formatted_content=f"[Instructions] {name}\nProject: {project_name}\n\n{text.strip()}",
        tags=["story", "instructions"],
    )


def parse_scene_file(text: str, project_name: str) -> ParsedEntity:
    """Parse a scene file as a single entity."""
    text = _strip_file_header(text)
    # Try to extract scene header: [Scene: Location – Date – Chapter]
    match = re.search(r"\[Scene:\s*(.+?)\]", text)
    name = match.group(1).strip() if match else "Untitled Scene"
    return ParsedEntity(
        name=name,
        content_type=ContentType.SCENE,
        formatted_content=f"[Scene] {name}\nProject: {project_name}\n\n{text.strip()}",
        tags=["story", "scene", "canon"],
    )


def parse_generic_file(text: str, project_name: str, filename: str) -> ParsedEntity:
    """Parse a generic/worldbuilding file as a single entity."""
    text = _strip_file_header(text)
    name = Path(filename).stem
    # Clean up common prefixes like "GhostHunters - "
    name = re.sub(r"^.*?\s*[-–—]\s*", "", name) if " - " in name or " – " in name else name
    return ParsedEntity(
        name=name,
        content_type=ContentType.WORLDBUILDING,
        formatted_content=f"[Worldbuilding] {name}\nProject: {project_name}\n\n{text.strip()}",
        tags=["story", "worldbuilding"],
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def parse_file(text: str, content_type: ContentType, project_name: str, filename: str) -> list[ParsedEntity]:
    """Parse a file into entities based on its classified content type."""
    if content_type == ContentType.CHARACTER:
        return parse_character_file(text, project_name)
    if content_type == ContentType.LOCATION:
        return parse_location_file(text, project_name)
    if content_type == ContentType.STYLE_GUIDE:
        return parse_style_guide_file(text, project_name)
    if content_type == ContentType.INSTRUCTIONS:
        return [parse_instructions_file(text, project_name)]
    if content_type == ContentType.SCENE:
        return [parse_scene_file(text, project_name)]
    return [parse_generic_file(text, project_name, filename)]
