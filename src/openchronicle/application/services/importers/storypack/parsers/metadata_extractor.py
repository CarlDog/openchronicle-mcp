#!/usr/bin/env python3
"""
OpenChronicle Metadata Extractor

Focused component for extracting metadata from content files.
Handles basic content analysis without AI dependencies.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.openchronicle.shared.logging_system import get_logger

from ..interfaces import IMetadataExtractor


class MetadataExtractor(IMetadataExtractor):
    """Extracts metadata from content files using pattern matching and analysis."""

    def __init__(self):
        """Initialize the metadata extractor."""
        self.logger = get_logger()

        # Common patterns for content analysis
        self.patterns = {
            'markdown_headers': re.compile(r'^#+\s+(.+)$', re.MULTILINE),
            'character_mentions': re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'),
            'location_indicators': re.compile(r'\b(?:in|at|from|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'),
            'dialogue': re.compile(r'"([^"]+)"'),
            'scene_breaks': re.compile(r'^[-*=]{3,}$', re.MULTILINE),
            'time_indicators': re.compile(r'\b(?:morning|afternoon|evening|night|dawn|dusk|yesterday|today|tomorrow)\b', re.IGNORECASE)
        }

    def extract_basic_metadata(self, content: str, file_path: Path) -> dict[str, Any]:
        """
        Extract basic metadata from file content using pattern matching.
        
        Args:
            content: Text content of the file
            file_path: Path to the source file
            
        Returns:
            Dictionary containing extracted metadata
        """
        metadata = {
            'file_info': self.extract_file_metadata(file_path),
            'content_stats': self._analyze_content_stats(content),
            'structure': self.detect_content_structure(content),
            'entities': self._extract_basic_entities(content),
            'language_features': self._analyze_language_features(content)
        }

        return metadata

    def detect_content_structure(self, content: str) -> dict[str, Any]:
        """
        Analyze content structure and organization patterns.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Dictionary describing content structure
        """
        structure = {
            'type': 'unknown',
            'has_headers': False,
            'header_count': 0,
            'headers': [],
            'has_dialogue': False,
            'dialogue_count': 0,
            'scene_breaks': 0,
            'paragraph_count': 0,
            'estimated_reading_time': 0
        }

        # Detect headers (Markdown style)
        headers = self.patterns['markdown_headers'].findall(content)
        if headers:
            structure['has_headers'] = True
            structure['header_count'] = len(headers)
            structure['headers'] = headers[:10]  # Limit to first 10

        # Detect dialogue
        dialogue_matches = self.patterns['dialogue'].findall(content)
        if dialogue_matches:
            structure['has_dialogue'] = True
            structure['dialogue_count'] = len(dialogue_matches)

        # Count scene breaks
        scene_breaks = self.patterns['scene_breaks'].findall(content)
        structure['scene_breaks'] = len(scene_breaks)

        # Count paragraphs (simple heuristic)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        structure['paragraph_count'] = len(paragraphs)

        # Estimate reading time (250 words per minute)
        word_count = len(content.split())
        structure['estimated_reading_time'] = max(1, word_count // 250)

        # Determine content type based on structure
        structure['type'] = self._classify_content_type(structure, content)

        return structure

    def extract_file_metadata(self, file_path: Path) -> dict[str, Any]:
        """
        Extract filesystem metadata from the file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary containing file metadata
        """
        try:
            stat = file_path.stat()

            metadata = {
                'filename': file_path.name,
                'stem': file_path.stem,
                'extension': file_path.suffix,
                'size_bytes': stat.st_size,
                'size_kb': round(stat.st_size / 1024, 2),
                'created_timestamp': stat.st_ctime,
                'modified_timestamp': stat.st_mtime,
                'created_date': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'relative_path': str(file_path)
            }

            return metadata

        except Exception as e:
            self.logger.warning(f"Failed to extract file metadata for {file_path}: {e}")
            return {
                'filename': file_path.name,
                'error': str(e)
            }

    def _analyze_content_stats(self, content: str) -> dict[str, Any]:
        """Analyze basic content statistics."""
        lines = content.split('\n')
        words = content.split()

        stats = {
            'character_count': len(content),
            'character_count_no_spaces': len(content.replace(' ', '')),
            'word_count': len(words),
            'line_count': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'average_words_per_line': len(words) / max(1, len([line for line in lines if line.strip()])),
            'average_chars_per_word': len(content.replace(' ', '')) / max(1, len(words))
        }

        return stats

    def _extract_basic_entities(self, content: str) -> dict[str, Any]:
        """Extract basic entities using pattern matching."""
        entities = {
            'potential_characters': [],
            'potential_locations': [],
            'time_references': [],
            'proper_nouns': []
        }

        # Extract potential character names (capitalized words)
        character_matches = self.patterns['character_mentions'].findall(content)
        # Filter out common words and very short/long names
        potential_characters = [
            name for name in set(character_matches)
            if 2 <= len(name.split()) <= 3 and
               name.lower() not in {'the', 'this', 'that', 'and', 'but', 'when', 'where', 'what'}
        ]
        entities['potential_characters'] = list(set(potential_characters))[:20]  # Limit results

        # Extract location indicators
        location_matches = self.patterns['location_indicators'].findall(content)
        entities['potential_locations'] = list(set(location_matches))[:15]

        # Extract time references
        time_matches = self.patterns['time_indicators'].findall(content)
        entities['time_references'] = list(set(time_matches))[:10]

        return entities

    def _analyze_language_features(self, content: str) -> dict[str, Any]:
        """Analyze language and writing features."""
        features = {
            'has_first_person': False,
            'has_second_person': False,
            'has_third_person': False,
            'tense_indicators': {
                'past': 0,
                'present': 0,
                'future': 0
            },
            'complexity_score': 0
        }

        # Check for person perspective
        content_lower = content.lower()
        if re.search(r'\bi\s|me\s|my\s|myself\b', content_lower):
            features['has_first_person'] = True
        if re.search(r'\byou\s|your\s|yourself\b', content_lower):
            features['has_second_person'] = True
        if re.search(r'\bhe\s|she\s|they\s|him\s|her\s|them\b', content_lower):
            features['has_third_person'] = True

        # Basic tense analysis (simplified)
        past_indicators = len(re.findall(r'\b\w+ed\b|\bwas\b|\bwere\b|\bhad\b', content_lower))
        present_indicators = len(re.findall(r'\bis\b|\bare\b|\bam\b|\bhas\b', content_lower))
        future_indicators = len(re.findall(r'\bwill\b|\bshall\b|\bgoing to\b', content_lower))

        features['tense_indicators']['past'] = past_indicators
        features['tense_indicators']['present'] = present_indicators
        features['tense_indicators']['future'] = future_indicators

        # Simple complexity score based on sentence length and vocabulary
        sentences = re.split(r'[.!?]+', content)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
        unique_words = len(set(content.lower().split()))
        total_words = len(content.split())
        vocabulary_ratio = unique_words / max(1, total_words)

        features['complexity_score'] = min(10, (avg_sentence_length / 15) + (vocabulary_ratio * 5))

        return features

    def _classify_content_type(self, structure: dict[str, Any], content: str) -> str:
        """Classify content type based on structural analysis."""
        # Character file indicators
        if any(keyword in content.lower() for keyword in ['character', 'age:', 'occupation:', 'personality:']):
            return 'character_profile'

        # Location file indicators
        if any(keyword in content.lower() for keyword in ['location', 'description:', 'geography:', 'climate:']):
            return 'location_description'

        # Narrative indicators
        if structure['has_dialogue'] and structure['paragraph_count'] > 5:
            return 'narrative_scene'

        # Lore indicators
        if structure['has_headers'] and any(keyword in content.lower() for keyword in ['history', 'legend', 'mythology']):
            return 'lore_document'

        # Structured document
        if structure['has_headers'] and structure['header_count'] >= 3:
            return 'structured_document'

        # Default classification
        if structure['paragraph_count'] > 3:
            return 'narrative_text'
        return 'notes_or_fragments'
