"""
Bookmark Management - Search Engine

Extracted from bookmark_manager.py
Handles bookmark searching and advanced querying capabilities.
"""

import json
import sys
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
from src.openchronicle.shared.logging_system import (
    log_system_event,
    log_info,
    log_warning,
)

from ..shared import BookmarkRecord, BookmarkType, BookmarkManagerException


class BookmarkSearchEngine:
    """Advanced search capabilities for bookmarks."""

    def __init__(self, story_id: str):
        self.story_id = story_id
        # Import database utilities with fallback
        try:
            from src.openchronicle.infrastructure.persistence import execute_query

            self.execute_query = execute_query
        except ImportError:
            # Fallback for testing
            self.execute_query = self._mock_execute_query

    def _mock_execute_query(self, *args, **kwargs):
        """Mock query function for testing."""
        return []

    def search_bookmarks(
        self,
        query: str,
        bookmark_type: Optional[BookmarkType] = None,
        search_fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search bookmarks by label or description with advanced options."""
        try:
            # Default search fields
            if search_fields is None:
                search_fields = ["label", "description"]

            # Build search conditions
            search_conditions = []
            params = [self.story_id]

            for field in search_fields:
                if field in ["label", "description"]:
                    search_conditions.append(f"{field} LIKE ?")
                    params.append(f"%{query}%")

            if not search_conditions:
                return []

            # Build full query
            search_query = f"""
                SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
                FROM bookmarks WHERE story_id = ? AND ({' OR '.join(search_conditions)})
            """

            if bookmark_type:
                search_query += " AND bookmark_type = ?"
                params.append(bookmark_type.value)

            search_query += " ORDER BY created_at DESC"

            if limit:
                search_query += " LIMIT ?"
                params.append(limit)

            rows = self.execute_query(self.story_id, search_query, params)

            results = []
            for row in rows:
                result = {
                    "id": row["id"],
                    "story_id": row["story_id"],
                    "scene_id": row["scene_id"],
                    "label": row["label"],
                    "description": row["description"],
                    "bookmark_type": row["bookmark_type"],
                    "created_at": row["created_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                }

                # Add relevance scoring
                result["relevance_score"] = self._calculate_relevance(query, result)
                results.append(result)

            # Sort by relevance
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

            log_system_event(
                "bookmark_search", f"Search '{query}' returned {len(results)} results"
            )

            return results

        except Exception as e:
            log_warning(f"Bookmark search failed: {e}")
            return []

    def search_by_metadata(
        self,
        metadata_filters: Dict[str, Any],
        bookmark_type: Optional[BookmarkType] = None,
    ) -> List[Dict[str, Any]]:
        """Search bookmarks by metadata fields."""
        try:
            # Get all bookmarks (we'll filter by metadata in Python since SQLite JSON support varies)
            query = """
                SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
                FROM bookmarks WHERE story_id = ?
            """
            params = [self.story_id]

            if bookmark_type:
                query += " AND bookmark_type = ?"
                params.append(bookmark_type.value)

            rows = self.execute_query(self.story_id, query, params)

            # Filter by metadata
            results = []
            for row in rows:
                metadata = json.loads(row["metadata"] or "{}")

                # Check if all metadata filters match
                match = True
                for key, value in metadata_filters.items():
                    if key not in metadata or metadata[key] != value:
                        match = False
                        break

                if match:
                    results.append(
                        {
                            "id": row["id"],
                            "story_id": row["story_id"],
                            "scene_id": row["scene_id"],
                            "label": row["label"],
                            "description": row["description"],
                            "bookmark_type": row["bookmark_type"],
                            "created_at": row["created_at"],
                            "metadata": metadata,
                        }
                    )

            log_system_event(
                "bookmark_metadata_search",
                f"Metadata search returned {len(results)} results",
            )

            return results

        except Exception as e:
            log_warning(f"Metadata search failed: {e}")
            return []

    def search_by_scene_content(
        self, content_query: str, bookmark_type: Optional[BookmarkType] = None
    ) -> List[Dict[str, Any]]:
        """Search bookmarks by their associated scene content."""
        try:
            query = """
                SELECT b.id, b.story_id, b.scene_id, b.label, b.description, b.bookmark_type, 
                       b.created_at, b.metadata, s.input, s.output
                FROM bookmarks b
                JOIN scenes s ON b.scene_id = s.scene_id
                WHERE b.story_id = ? AND (s.input LIKE ? OR s.output LIKE ?)
            """
            params = [self.story_id, f"%{content_query}%", f"%{content_query}%"]

            if bookmark_type:
                query += " AND b.bookmark_type = ?"
                params.append(bookmark_type.value)

            query += " ORDER BY b.created_at DESC"

            rows = self.execute_query(self.story_id, query, params)

            results = []
            for row in rows:
                result = {
                    "id": row["id"],
                    "story_id": row["story_id"],
                    "scene_id": row["scene_id"],
                    "label": row["label"],
                    "description": row["description"],
                    "bookmark_type": row["bookmark_type"],
                    "created_at": row["created_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "scene_input": row["input"],
                    "scene_output": row["output"],
                }

                # Add content relevance
                result["content_relevance"] = self._calculate_content_relevance(
                    content_query, result
                )
                results.append(result)

            # Sort by content relevance
            results.sort(key=lambda x: x["content_relevance"], reverse=True)

            log_system_event(
                "bookmark_content_search",
                f"Content search '{content_query}' returned {len(results)} results",
            )

            return results

        except Exception as e:
            log_warning(f"Content search failed: {e}")
            return []

    def find_similar_bookmarks(
        self, bookmark_id: int, similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Find bookmarks similar to the given bookmark."""
        try:
            # Get reference bookmark
            reference_row = self.execute_query(
                self.story_id,
                """
                SELECT id, label, description, bookmark_type, metadata
                FROM bookmarks WHERE id = ?
            """,
                (bookmark_id,),
            )

            if not reference_row:
                return []

            reference = reference_row[0]
            reference_metadata = json.loads(reference["metadata"] or "{}")

            # Get all other bookmarks
            all_rows = self.execute_query(
                self.story_id,
                """
                SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
                FROM bookmarks WHERE story_id = ? AND id != ?
            """,
                (self.story_id, bookmark_id),
            )

            similar_bookmarks = []

            for row in all_rows:
                similarity_score = self._calculate_similarity(reference, row)

                if similarity_score >= similarity_threshold:
                    similar_bookmarks.append(
                        {
                            "id": row["id"],
                            "story_id": row["story_id"],
                            "scene_id": row["scene_id"],
                            "label": row["label"],
                            "description": row["description"],
                            "bookmark_type": row["bookmark_type"],
                            "created_at": row["created_at"],
                            "metadata": json.loads(row["metadata"] or "{}"),
                            "similarity_score": similarity_score,
                        }
                    )

            # Sort by similarity
            similar_bookmarks.sort(key=lambda x: x["similarity_score"], reverse=True)

            return similar_bookmarks

        except Exception as e:
            log_warning(f"Similar bookmark search failed: {e}")
            return []

    def get_bookmark_suggestions(
        self, current_scene_id: str, context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get bookmark suggestions based on current context."""
        try:
            suggestions = []

            # Suggest based on recent bookmarks
            recent_bookmarks = self.execute_query(
                self.story_id,
                """
                SELECT id, label, description, bookmark_type, scene_id
                FROM bookmarks WHERE story_id = ?
                ORDER BY created_at DESC LIMIT 10
            """,
                (self.story_id,),
            )

            for bookmark in recent_bookmarks:
                if (
                    bookmark["scene_id"] != current_scene_id
                ):  # Don't suggest current scene
                    suggestions.append(
                        {
                            "type": "recent",
                            "bookmark_id": bookmark["id"],
                            "label": bookmark["label"],
                            "description": bookmark["description"],
                            "reason": "Recently created bookmark",
                        }
                    )

            # If context provided, suggest based on content similarity
            if context:
                content_matches = self.search_by_scene_content(
                    context[:100]
                )  # Limit context length
                for match in content_matches[:5]:  # Top 5 matches
                    if match["scene_id"] != current_scene_id:
                        suggestions.append(
                            {
                                "type": "content_match",
                                "bookmark_id": match["id"],
                                "label": match["label"],
                                "description": match["description"],
                                "reason": f"Similar content (relevance: {match.get('content_relevance', 0):.2f})",
                            }
                        )

            return suggestions[:10]  # Return top 10 suggestions

        except Exception as e:
            log_warning(f"Bookmark suggestions failed: {e}")
            return []

    def _calculate_relevance(self, query: str, bookmark: Dict[str, Any]) -> float:
        """Calculate relevance score for search results."""
        score = 0.0
        query_lower = query.lower()

        # Exact match in label gets highest score
        if query_lower in bookmark["label"].lower():
            score += 1.0

        # Partial match in label
        label_words = bookmark["label"].lower().split()
        query_words = query_lower.split()
        label_matches = sum(
            1
            for word in query_words
            if any(word in label_word for label_word in label_words)
        )
        score += (label_matches / len(query_words)) * 0.8

        # Description matches
        if bookmark["description"]:
            if query_lower in bookmark["description"].lower():
                score += 0.6

            desc_words = bookmark["description"].lower().split()
            desc_matches = sum(
                1
                for word in query_words
                if any(word in desc_word for desc_word in desc_words)
            )
            score += (desc_matches / len(query_words)) * 0.4

        return score

    def _calculate_content_relevance(
        self, query: str, bookmark: Dict[str, Any]
    ) -> float:
        """Calculate content relevance score."""
        score = 0.0
        query_lower = query.lower()

        # Check scene input
        if bookmark.get("scene_input"):
            input_text = bookmark["scene_input"].lower()
            if query_lower in input_text:
                score += 1.0

        # Check scene output
        if bookmark.get("scene_output"):
            output_text = bookmark["scene_output"].lower()
            if query_lower in output_text:
                score += 0.8

        return score

    def _calculate_similarity(
        self, bookmark1: Dict[str, Any], bookmark2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two bookmarks."""
        score = 0.0

        # Same bookmark type
        if bookmark1["bookmark_type"] == bookmark2["bookmark_type"]:
            score += 0.3

        # Similar labels
        label1_words = set(bookmark1["label"].lower().split())
        label2_words = set(bookmark2["label"].lower().split())
        if label1_words and label2_words:
            label_similarity = len(label1_words & label2_words) / len(
                label1_words | label2_words
            )
            score += label_similarity * 0.4

        # Similar descriptions
        if bookmark1.get("description") and bookmark2.get("description"):
            desc1_words = set(bookmark1["description"].lower().split())
            desc2_words = set(bookmark2["description"].lower().split())
            if desc1_words and desc2_words:
                desc_similarity = len(desc1_words & desc2_words) / len(
                    desc1_words | desc2_words
                )
                score += desc_similarity * 0.3

        return score
