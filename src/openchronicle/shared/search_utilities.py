"""
Search Utilities - Consolidates search and query logic from OpenChronicle core modules

This module provides shared infrastructure for:
- Query building and parameterization
- Result ranking and scoring
- Search filtering and pagination
- Full-text search (FTS) operations
- SQL query optimization

Consolidates patterns from:
- search_engine.py (15+ search methods)
- bookmark_manager.py (search_bookmarks)
- scene_logger.py (scene queries)
- timeline_builder.py (timeline searches)
- memory_manager.py (memory searches)
- character_consistency_engine.py (character searches)
- rollback_engine.py (rollback searches)

Key Features:
- Unified query interface across modules
- FTS integration with ranking
- Pagination and result limiting
- SQL injection protection
- Performance optimization
- Result formatting and snippets
"""

import logging
import re
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any

# Import shared utilities
from .database_operations import DatabaseOperations


# Logging setup
logger = logging.getLogger(__name__)


@dataclass
class SearchOptions:
    """Configuration for search operations"""

    limit: int = 50
    offset: int = 0
    order_by: str = "timestamp DESC"
    include_content: bool = True
    include_snippets: bool = False
    snippet_length: int = 32
    snippet_markers: tuple[str, str] = ("<mark>", "</mark>")
    case_sensitive: bool = False
    exact_match: bool = False
    use_fts: bool = True
    score_threshold: float = 0.0


@dataclass
class SearchResult:
    """Standardized search result structure"""

    id: str
    score: float = 0.0
    content: dict[str, Any] = field(default_factory=dict)
    snippets: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime | None = None
    rank: int = 0


class QueryProcessor:
    """Processes and builds SQL queries with safety checks"""

    # SQL injection protection patterns
    SAFE_ORDER_PATTERN = re.compile(
        r"^[a-zA-Z_][a-zA-Z0-9_]*(\s+(ASC|DESC))?$", re.IGNORECASE
    )
    SAFE_COLUMN_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    @staticmethod
    def validate_order_by(order_by: str) -> bool:
        """Validate ORDER BY clause for SQL injection prevention"""
        if not order_by:
            return False
        return bool(QueryProcessor.SAFE_ORDER_PATTERN.match(order_by.strip()))

    @staticmethod
    def validate_column_name(column: str) -> bool:
        """Validate column name for SQL injection prevention"""
        if not column:
            return False
        return bool(QueryProcessor.SAFE_COLUMN_PATTERN.match(column.strip()))

    @staticmethod
    def build_where_clause(
        filters: dict[str, Any], table_prefix: str = ""
    ) -> tuple[str, list[Any]]:
        """Build WHERE clause from filters dictionary"""
        if not filters:
            return "", []

        conditions = []
        params = []
        prefix = f"{table_prefix}." if table_prefix else ""

        for column, value in filters.items():
            if not QueryProcessor.validate_column_name(column):
                logger.warning(f"Invalid column name skipped: {column}")
                continue

            if isinstance(value, (list, tuple)):
                # IN clause for multiple values
                placeholders = ",".join("?" * len(value))
                conditions.append(f"{prefix}{column} IN ({placeholders})")
                params.extend(value)
            elif isinstance(value, dict):
                # Handle range queries
                if "min" in value:
                    conditions.append(f"{prefix}{column} >= ?")
                    params.append(value["min"])
                if "max" in value:
                    conditions.append(f"{prefix}{column} <= ?")
                    params.append(value["max"])
                if "like" in value:
                    conditions.append(f"{prefix}{column} LIKE ?")
                    params.append(value["like"])
            else:
                # Simple equality
                conditions.append(f"{prefix}{column} = ?")
                params.append(value)

        where_clause = " AND ".join(conditions)
        return f" WHERE {where_clause}" if where_clause else "", params

    @staticmethod
    def build_pagination(limit: int, offset: int = 0) -> tuple[str, list[int]]:
        """Build LIMIT/OFFSET clause with validation"""
        # Validate and sanitize pagination parameters
        limit = max(1, min(limit, 10000))  # Between 1 and 10,000
        offset = max(0, offset)

        return " LIMIT ? OFFSET ?", [limit, offset]

    @staticmethod
    def build_order_by(order_by: str, default: str = "timestamp DESC") -> str:
        """Build ORDER BY clause with validation"""
        if not order_by or not QueryProcessor.validate_order_by(order_by):
            logger.warning(f"Invalid ORDER BY clause, using default: {default}")
            return f" ORDER BY {default}"

        return f" ORDER BY {order_by}"


class FTSQueryBuilder:
    """Specialized query builder for Full-Text Search operations"""

    @staticmethod
    def escape_fts_query(query: str) -> str:
        """Escape FTS query for safe execution"""
        if not query:
            return ""

        # First, escape quotes by doubling them
        query = query.replace('"', '""')

        # Remove dangerous special characters but keep basic operators
        # Allow: alphanumeric, whitespace, basic operators, quotes
        query = re.sub(r'[^\w\s\-\*\+\(\)"\:]', " ", query)

        # Normalize whitespace
        query = re.sub(r"\s+", " ", query).strip()

        return query

    @staticmethod
    def build_fts_query(
        search_terms: str, columns: list[str] = None, boost_exact: bool = True
    ) -> str:
        """Build FTS MATCH query with column targeting and boosting"""
        if not search_terms:
            return ""

        escaped_terms = FTSQueryBuilder.escape_fts_query(search_terms)
        if not escaped_terms:
            return ""

        # Build column-specific search if specified
        if columns:
            column_queries = []
            for col in columns:
                if QueryProcessor.validate_column_name(col):
                    column_queries.append(f"{col}:{escaped_terms}")

            if column_queries:
                base_query = f"({' OR '.join(column_queries)})"
            else:
                base_query = escaped_terms
        else:
            base_query = escaped_terms

        # Add exact match boosting
        if boost_exact and " " in escaped_terms:
            base_query = f'("{escaped_terms}" OR {base_query})'

        return base_query

    @staticmethod
    def build_snippet_select(
        table_name: str,
        columns: list[str],
        start_mark: str = "<mark>",
        end_mark: str = "</mark>",
        ellipsis: str = "...",
        max_tokens: int = 32,
    ) -> list[str]:
        """Build snippet() function calls for FTS highlighting"""
        snippets = []

        for i, column in enumerate(columns):
            if not QueryProcessor.validate_column_name(column):
                continue

            snippet_sql = (
                f"snippet({table_name}, {i}, '{start_mark}', '{end_mark}', "
                f"'{ellipsis}', {max_tokens}) as snippet_{column}"
            )
            snippets.append(snippet_sql)

        return snippets


class ResultRanker:
    """Handles result ranking and scoring"""

    @staticmethod
    def calculate_relevance_score(
        fts_score: float,
        timestamp_weight: float = 0.1,
        content_length_weight: float = 0.05,
        **kwargs,
    ) -> float:
        """Calculate composite relevance score"""
        base_score = fts_score if fts_score > 0 else 0.0

        # Add timestamp recency bonus
        if "timestamp" in kwargs:
            try:
                timestamp = kwargs["timestamp"]
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

                # More recent = higher score (within last 30 days gets bonus)
                days_old = (datetime.now() - timestamp).days
                recency_bonus = max(0, (30 - days_old) / 30) * timestamp_weight
                base_score += recency_bonus
            except (ValueError, TypeError):
                pass

        # Add content length factor
        if "content_length" in kwargs:
            try:
                length = kwargs["content_length"]
                # Optimal content length around 500 chars
                length_factor = min(1.0, length / 500) * content_length_weight
                base_score += length_factor
            except (ValueError, TypeError):
                pass

        return round(base_score, 4)

    @staticmethod
    def rank_results(
        results: list[SearchResult], sort_by: str = "score", ascending: bool = False
    ) -> list[SearchResult]:
        """Rank and sort search results"""
        if not results:
            return results

        # Define sort key function
        if sort_by == "score":
            key_func = lambda r: r.score
        elif sort_by == "timestamp":
            key_func = lambda r: r.timestamp or datetime.min
        elif sort_by == "id":
            key_func = lambda r: r.id
        else:
            # Default to score
            key_func = lambda r: r.score

        # Sort results
        sorted_results = sorted(results, key=key_func, reverse=not ascending)

        # Assign ranks
        for i, result in enumerate(sorted_results):
            result.rank = i + 1

        return sorted_results


class SearchUtilities:
    """Main search utilities class consolidating all search operations"""

    def __init__(self, db_ops: DatabaseOperations = None):
        """Initialize with optional database operations instance"""
        # Note: db_ops should be provided by calling code with proper story_id
        # If not provided, will be initialized when needed per-story
        self.db_ops = db_ops
        self.query_processor = QueryProcessor()
        self.fts_builder = FTSQueryBuilder()
        self.ranker = ResultRanker()

    def _ensure_db_ops(self, story_id: str) -> DatabaseOperations:
        """Ensure db_ops is available for the given story_id"""
        if self.db_ops is None:
            self.db_ops = DatabaseOperations(story_id)
        return self.db_ops

    def execute_search(
        self,
        story_id: str,
        query: str,
        table: str,
        columns: list[str] = None,
        filters: dict[str, Any] = None,
        options: SearchOptions = None,
    ) -> list[SearchResult]:
        """Execute comprehensive search with FTS and filtering"""
        if not options:
            options = SearchOptions()

        # Ensure database operations are available
        db_ops = self._ensure_db_ops(story_id)

        try:
            if options.use_fts and query:
                return self._execute_fts_search(
                    story_id, query, table, columns, filters, options, db_ops
                )
            return self._execute_simple_search(
                story_id, table, columns, filters, options, db_ops
            )
        except Exception as e:
            logger.error(f"Search execution failed: {e}")
            return []

    def _execute_fts_search(
        self,
        story_id: str,
        query: str,
        table: str,
        columns: list[str],
        filters: dict[str, Any],
        options: SearchOptions,
        db_ops: DatabaseOperations,
    ) -> list[SearchResult]:
        """Execute FTS-based search"""
        fts_table = f"{table}_fts"

        # Build FTS query
        fts_query = self.fts_builder.build_fts_query(query, columns, boost_exact=True)
        if not fts_query:
            return []

        # Build additional filters
        where_clause, where_params = self.query_processor.build_where_clause(
            filters or {}, table[0]
        )

        # Build snippet selections
        snippet_columns = []
        if options.include_snippets and columns:
            snippet_columns = self.fts_builder.build_snippet_select(
                fts_table,
                columns,
                options.snippet_markers[0],
                options.snippet_markers[1],
                "...",
                options.snippet_length,
            )

        # Build ORDER BY
        order_clause = self.query_processor.build_order_by(
            options.order_by, "score DESC"
        )

        # Build pagination
        limit_clause, limit_params = self.query_processor.build_pagination(
            options.limit, options.offset
        )

        # Construct full query
        snippet_select = ", " + ", ".join(snippet_columns) if snippet_columns else ""

        sql = f"""
            SELECT 
                {table[0]}.rowid,
                {table[0]}.*,
                bm25({fts_table}) as score{snippet_select}
            FROM {fts_table}
            JOIN {table} {table[0]} ON {table[0]}.rowid = {fts_table}.rowid
            WHERE {fts_table} MATCH ?{where_clause}
                AND {table[0]}.story_id = ?
                AND bm25({fts_table}) >= ?
            {order_clause}
            {limit_clause}
        """

        # Combine all parameters
        params = (
            [fts_query]
            + where_params
            + [story_id, options.score_threshold]
            + limit_params
        )

        # Execute query
        rows = db_ops.execute_query(story_id, sql, params)

        # Convert to SearchResult objects
        return self._convert_rows_to_results(rows, options, has_fts_score=True)

    def _execute_simple_search(
        self,
        story_id: str,
        table: str,
        columns: list[str],
        filters: dict[str, Any],
        options: SearchOptions,
        db_ops: DatabaseOperations,
    ) -> list[SearchResult]:
        """Execute simple non-FTS search"""
        # Build WHERE clause
        all_filters = (filters or {}).copy()
        all_filters["story_id"] = story_id

        where_clause, where_params = self.query_processor.build_where_clause(
            all_filters
        )

        # Build ORDER BY
        order_clause = self.query_processor.build_order_by(options.order_by)

        # Build pagination
        limit_clause, limit_params = self.query_processor.build_pagination(
            options.limit, options.offset
        )

        # Construct query
        column_select = ", ".join(columns) if columns else "*"

        sql = f"""
            SELECT rowid, {column_select}
            FROM {table}
            {where_clause}
            {order_clause}
            {limit_clause}
        """

        params = where_params + limit_params

        # Execute query
        rows = db_ops.execute_query(story_id, sql, params)

        # Convert to SearchResult objects
        return self._convert_rows_to_results(rows, options, has_fts_score=False)

    def _convert_rows_to_results(
        self,
        rows: list[dict[str, Any]],
        options: SearchOptions,
        has_fts_score: bool = False,
    ) -> list[SearchResult]:
        """Convert database rows to SearchResult objects"""
        results = []

        for row in rows:
            # Extract basic data
            row_id = str(row.get("rowid", ""))
            score = float(row.get("score", 0.0)) if has_fts_score else 0.0

            # Build content dictionary (exclude system columns)
            content = {}
            snippets = {}
            metadata = {}

            for key, value in row.items():
                if key in ("rowid", "score"):
                    continue
                if key.startswith("snippet_"):
                    # Extract snippet
                    column_name = key.replace("snippet_", "")
                    snippets[column_name] = value
                elif key in ("timestamp", "created_at", "updated_at"):
                    # Handle timestamp
                    metadata[key] = value
                    try:
                        if isinstance(value, str):
                            timestamp = datetime.fromisoformat(
                                value.replace("Z", "+00:00")
                            )
                        else:
                            timestamp = value
                    except (ValueError, TypeError):
                        timestamp = None
                # Regular content
                elif options.include_content:
                    content[key] = value

            # Calculate enhanced score if needed
            if has_fts_score:
                enhanced_score = self.ranker.calculate_relevance_score(
                    score,
                    timestamp=metadata.get("timestamp"),
                    content_length=len(str(content.get("content", ""))),
                )
            else:
                enhanced_score = score

            # Create result
            result = SearchResult(
                id=row_id,
                score=enhanced_score,
                content=content,
                snippets=snippets,
                metadata=metadata,
                timestamp=metadata.get("timestamp"),
            )

            results.append(result)

        # Rank results
        return self.ranker.rank_results(results, "score", ascending=False)

    def search_scenes(
        self,
        story_id: str,
        query: str = None,
        filters: dict[str, Any] = None,
        options: SearchOptions = None,
    ) -> list[SearchResult]:
        """Search scenes with full-text capabilities"""
        columns = [
            "scene_id",
            "input",
            "output",
            "scene_label",
            "timestamp",
            "flags",
            "analysis",
        ]
        return self.execute_search(story_id, query, "scenes", columns, filters, options)

    def search_characters(
        self,
        story_id: str,
        query: str = None,
        filters: dict[str, Any] = None,
        options: SearchOptions = None,
    ) -> list[SearchResult]:
        """Search characters with filtering"""
        columns = [
            "character_id",
            "character_name",
            "description",
            "personality",
            "background",
        ]
        return self.execute_search(
            story_id, query, "characters", columns, filters, options
        )

    def search_bookmarks(
        self,
        story_id: str,
        query: str = None,
        filters: dict[str, Any] = None,
        options: SearchOptions = None,
    ) -> list[SearchResult]:
        """Search bookmarks with metadata"""
        columns = [
            "bookmark_id",
            "scene_id",
            "label",
            "description",
            "tags",
            "created_at",
        ]
        return self.execute_search(
            story_id, query, "bookmarks", columns, filters, options
        )

    def search_memories(
        self,
        story_id: str,
        query: str = None,
        filters: dict[str, Any] = None,
        options: SearchOptions = None,
    ) -> list[SearchResult]:
        """Search character memories"""
        columns = ["memory_id", "character_id", "content", "importance", "timestamp"]
        return self.execute_search(
            story_id, query, "character_memories", columns, filters, options
        )


# Export main classes and functions
__all__ = [
    "FTSQueryBuilder",
    "QueryProcessor",
    "ResultRanker",
    "SearchOptions",
    "SearchResult",
    "SearchUtilities",
]
