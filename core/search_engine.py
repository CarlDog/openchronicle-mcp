"""
OpenChronicle Full-Text Search Engine with FTS5 Integration

This module provides comprehensive full-text search capabilities for OpenChronicle stories
using SQLite FTS5 virtual tables. It supports advanced query operators, relevance ranking,
and seamless integration with existing scene labeling and bookmark systems.

Features:
- Fast full-text search across scenes and memory
- Advanced query operators (AND, OR, NOT, quotes, wildcards)
- Relevance ranking and scoring
- Search result highlighting and snippets
- Query sanitization and validation
- Integration with scene labels and bookmarks
- Search statistics and analytics
"""

import sqlite3
import json
import re
import time
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from functools import lru_cache

from .database import get_connection, check_fts_support, optimize_fts_index


@dataclass
class SearchResult:
    """Represents a search result with metadata."""
    id: str
    content_type: str  # 'scene' or 'memory'
    title: str
    content: str
    snippet: str
    score: float
    timestamp: Optional[str] = None
    scene_label: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class SearchQuery:
    """Represents a parsed search query."""
    original: str
    sanitized: str
    terms: List[str]
    operators: List[str]
    quoted_phrases: List[str]
    filters: Dict[str, str]
    content_types: List[str]
    wildcards: List[str] = field(default_factory=list)
    proximity_searches: List[Tuple[str, str, int]] = field(default_factory=list)
    sort_order: str = "relevance"
    limit: int = 50


@dataclass
class SearchHistory:
    """Represents a search history entry."""
    query: str
    timestamp: datetime
    results_count: int
    execution_time: float
    filters: Dict[str, str] = field(default_factory=dict)


@dataclass
class SavedSearch:
    """Represents a saved search."""
    name: str
    query: str
    description: str = ""
    filters: Optional[Dict[str, str]] = None
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    use_count: int = 0
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.created_at is None:
            self.created_at = datetime.now()


class SearchEngine:
    """Enhanced full-text search engine with FTS5 integration."""
    
    def __init__(self, story_id: str, cache_size: int = 100, history_limit: int = 10):
        """Initialize search engine for a specific story."""
        self.story_id = story_id
        self.fts_supported = check_fts_support()
        self.cache_size = cache_size
        self.history_limit = history_limit
        self.search_history: List[SearchHistory] = []
        self.saved_searches: Dict[str, SavedSearch] = {}
        self.query_cache: Dict[str, Tuple[List[SearchResult], float]] = {}
        self.performance_stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'avg_query_time': 0.0,
            'total_query_time': 0.0
        }
        
        if not self.fts_supported:
            raise RuntimeError("FTS5 is not supported in this SQLite version")
    
    def parse_query(self, query: str) -> SearchQuery:
        """Parse and sanitize a search query with advanced features."""
        original = query.strip()
        
        # Extract quoted phrases
        quoted_phrases = re.findall(r'"([^"]*)"', original)
        
        # Extract wildcards (terms with * or ?)
        wildcards = re.findall(r'\w*[*?]\w*', original)
        
        # Remove wildcards from terms extraction
        temp_sanitized = original
        for wildcard in wildcards:
            temp_sanitized = temp_sanitized.replace(wildcard, '')
        
        # Extract proximity searches (word1 NEAR/5 word2)
        proximity_searches = []
        proximity_pattern = r'(\w+)\s+NEAR/(\d+)\s+(\w+)'
        for match in re.finditer(proximity_pattern, temp_sanitized, re.IGNORECASE):
            term1, distance, term2 = match.groups()
            proximity_searches.append((term1, term2, int(distance)))
        
        # Extract filters (e.g., type:scene, label:chapter, sort:date)
        filters = {}
        filter_pattern = r'(\w+):(\w+)'
        for match in re.finditer(filter_pattern, original):
            key, value = match.groups()
            filters[key] = value
        
        # Extract sort order
        sort_order = filters.pop('sort', 'relevance')
        
        # Extract limit
        limit = int(filters.pop('limit', '50'))
        
        # Remove quoted phrases, wildcards, proximity searches, and filters from main query
        sanitized = original
        for phrase in quoted_phrases:
            sanitized = sanitized.replace(f'"{phrase}"', '')
        for wildcard in wildcards:
            sanitized = sanitized.replace(wildcard, '')
        for term1, term2, distance in proximity_searches:
            sanitized = sanitized.replace(f'{term1} NEAR/{distance} {term2}', '')
        for key, value in {**filters, 'sort': sort_order, 'limit': str(limit)}.items():
            sanitized = sanitized.replace(f'{key}:{value}', '')
        
        # Extract individual terms and operators
        terms = []
        operators = []
        
        # Split by common operators while preserving them
        parts = re.split(r'\s+(AND|OR|NOT)\s+', sanitized, flags=re.IGNORECASE)
        
        for i, part in enumerate(parts):
            part = part.strip()
            if part.upper() in ['AND', 'OR', 'NOT']:
                operators.append(part.upper())
            elif part:
                # Split by whitespace and filter out empty strings
                words = [word.strip() for word in part.split() if word.strip()]
                terms.extend(words)
        
        # Determine content types from filters
        content_types = []
        if 'type' in filters:
            content_types = [filters['type']]
        else:
            content_types = ['scene', 'memory']
        
        # Clean up sanitized query
        sanitized = ' '.join(terms + quoted_phrases + wildcards)
        
        return SearchQuery(
            original=original,
            sanitized=sanitized,
            terms=terms,
            operators=operators,
            quoted_phrases=quoted_phrases,
            filters=filters,
            content_types=content_types,
            wildcards=wildcards,
            proximity_searches=proximity_searches,
            sort_order=sort_order,
            limit=limit
        )
    
    def search_scenes(self, query: SearchQuery, limit: int = 50) -> List[SearchResult]:
        """Search scenes using FTS5."""
        if 'scene' not in query.content_types:
            return []
        
        with get_connection(self.story_id) as conn:
            cursor = conn.cursor()
            
            # Build FTS5 query
            fts_query = self._build_fts_query(query)
            
            # Apply filters
            where_conditions = []
            params = [fts_query]
            
            if 'label' in query.filters:
                where_conditions.append("s.scene_label LIKE ?")
                params.append(f"%{query.filters['label']}%")
            
            where_clause = ""
            if where_conditions:
                where_clause = " AND " + " AND ".join(where_conditions)
            
            # Execute search with ranking
            sql = f"""
                SELECT 
                    s.scene_id,
                    s.input,
                    s.output,
                    s.scene_label,
                    s.timestamp,
                    s.flags,
                    s.analysis,
                    bm25(scenes_fts) as score,
                    snippet(scenes_fts, 1, '<mark>', '</mark>', '...', 32) as snippet_input,
                    snippet(scenes_fts, 2, '<mark>', '</mark>', '...', 32) as snippet_output
                FROM scenes_fts
                JOIN scenes s ON s.rowid = scenes_fts.rowid
                WHERE scenes_fts MATCH ?{where_clause}
                ORDER BY score
                LIMIT ?
            """
            
            params.append(limit)
            cursor.execute(sql, params)
            
            results = []
            for row in cursor.fetchall():
                # Choose best snippet
                snippet = row['snippet_input']
                if '<mark>' not in snippet and '<mark>' in row['snippet_output']:
                    snippet = row['snippet_output']
                
                result = SearchResult(
                    id=row['scene_id'],
                    content_type='scene',
                    title=row['scene_label'] or f"Scene {row['scene_id'][:8]}",
                    content=f"{row['input']}\n\n{row['output']}",
                    snippet=snippet,
                    score=row['score'],
                    timestamp=row['timestamp'],
                    scene_label=row['scene_label'],
                    metadata={
                        'flags': json.loads(row['flags'] or '[]'),
                        'analysis': json.loads(row['analysis'] or '{}')
                    }
                )
                results.append(result)
            
            return results
    
    def search_memory(self, query: SearchQuery, limit: int = 50) -> List[SearchResult]:
        """Search memory using FTS5."""
        if 'memory' not in query.content_types:
            return []
        
        with get_connection(self.story_id) as conn:
            cursor = conn.cursor()
            
            # Build FTS5 query
            fts_query = self._build_fts_query(query)
            
            # Apply filters
            where_conditions = []
            params = [fts_query]
            
            if 'memtype' in query.filters:
                where_conditions.append("m.type = ?")
                params.append(query.filters['memtype'])
            
            where_clause = ""
            if where_conditions:
                where_clause = " AND " + " AND ".join(where_conditions)
            
            # Execute search with ranking
            sql = f"""
                SELECT 
                    m.id,
                    m.type,
                    m.key,
                    m.value,
                    m.created_at,
                    m.updated_at,
                    bm25(memory_fts) as score,
                    snippet(memory_fts, 3, '<mark>', '</mark>', '...', 32) as snippet_key,
                    snippet(memory_fts, 4, '<mark>', '</mark>', '...', 32) as snippet_value
                FROM memory_fts
                JOIN memory m ON m.id = memory_fts.memory_id
                WHERE memory_fts MATCH ?{where_clause}
                ORDER BY score
                LIMIT ?
            """
            
            params.append(limit)
            cursor.execute(sql, params)
            
            results = []
            for row in cursor.fetchall():
                # Choose best snippet
                snippet = row['snippet_key']
                if '<mark>' not in snippet and '<mark>' in row['snippet_value']:
                    snippet = row['snippet_value']
                
                result = SearchResult(
                    id=str(row['id']),
                    content_type='memory',
                    title=f"{row['type']}: {row['key']}",
                    content=row['value'],
                    snippet=snippet,
                    score=row['score'],
                    timestamp=row['updated_at'],
                    metadata={
                        'memory_type': row['type'],
                        'key': row['key'],
                        'created_at': row['created_at']
                    }
                )
                results.append(result)
            
            return results
    
    def search_all(self, query_string: str, limit: int = 50) -> List[SearchResult]:
        """Search across all content types with caching and performance tracking."""
        start_time = time.time()
        
        # Check cache first
        cache_key = f"{query_string}::{limit}"
        if cache_key in self.query_cache:
            cached_results, cached_time = self.query_cache[cache_key]
            # Return cached results if they're less than 5 minutes old
            if time.time() - cached_time < 300:
                self.performance_stats['cache_hits'] += 1
                self.performance_stats['total_queries'] += 1
                return cached_results
        
        # Parse query
        query = self.parse_query(query_string)
        
        # Determine actual limit for each content type
        scene_limit = limit // 2 if len(query.content_types) > 1 else limit
        memory_limit = limit // 2 if len(query.content_types) > 1 else limit
        
        # Search scenes and memory
        scene_results = self.search_scenes(query, scene_limit)
        memory_results = self.search_memory(query, memory_limit)
        
        # Combine results
        all_results = scene_results + memory_results
        
        # Sort results based on sort order
        if query.sort_order == 'relevance':
            all_results.sort(key=lambda x: x.score)
        elif query.sort_order == 'date':
            all_results.sort(key=lambda x: x.timestamp or '', reverse=True)
        elif query.sort_order == 'title':
            all_results.sort(key=lambda x: x.title.lower())
        
        # Apply final limit
        final_results = all_results[:query.limit]
        
        # Update performance stats
        execution_time = time.time() - start_time
        self.performance_stats['total_queries'] += 1
        self.performance_stats['total_query_time'] += execution_time
        self.performance_stats['avg_query_time'] = (
            self.performance_stats['total_query_time'] / 
            self.performance_stats['total_queries']
        )
        
        # Cache results
        self.query_cache[cache_key] = (final_results, time.time())
        
        # Limit cache size
        if len(self.query_cache) > self.cache_size:
            # Remove oldest entry
            oldest_key = min(self.query_cache.keys(), 
                           key=lambda k: self.query_cache[k][1])
            del self.query_cache[oldest_key]
        
        # Add to search history
        self.search_history.append(SearchHistory(
            query=query_string,
            timestamp=datetime.now(),
            results_count=len(final_results),
            execution_time=execution_time,
            filters=query.filters
        ))
        
        # Limit history size
        if len(self.search_history) > self.history_limit:
            self.search_history = self.search_history[-self.history_limit:]
        
        return final_results
    
    def _build_fts_query(self, query: SearchQuery) -> str:
        """Build FTS5 query from parsed query with advanced features."""
        parts = []
        
        # Add quoted phrases
        for phrase in query.quoted_phrases:
            parts.append(f'"{phrase}"')
        
        # Add wildcards
        for wildcard in query.wildcards:
            parts.append(wildcard)
        
        # Add proximity searches
        for term1, term2, distance in query.proximity_searches:
            parts.append(f'"{term1}" NEAR/{distance} "{term2}"')
        
        # Add terms with operators
        if query.terms:
            if query.operators:
                # Build complex query with operators
                term_parts = []
                term_idx = 0
                
                for i, op in enumerate(query.operators):
                    if term_idx < len(query.terms):
                        term_parts.append(query.terms[term_idx])
                        term_idx += 1
                    
                    term_parts.append(op)
                    
                    if term_idx < len(query.terms):
                        term_parts.append(query.terms[term_idx])
                        term_idx += 1
                
                # Add remaining terms
                while term_idx < len(query.terms):
                    term_parts.append(query.terms[term_idx])
                    term_idx += 1
                
                if term_parts:
                    parts.append(' '.join(term_parts))
            else:
                # Simple term matching with implicit AND
                if len(query.terms) > 1:
                    parts.append(' AND '.join(query.terms))
                elif query.terms:
                    parts.extend(query.terms)
        
        # Join with AND if multiple parts
        if len(parts) > 1:
            return ' AND '.join(parts)
        elif parts:
            return parts[0]
        else:
            return '*'  # Match all if no terms
    
    def get_search_stats(self) -> Dict:
        """Get search engine statistics."""
        with get_connection(self.story_id) as conn:
            cursor = conn.cursor()
            
            stats = {
                'fts_supported': self.fts_supported,
                'story_id': self.story_id
            }
            
            # Count indexed scenes
            try:
                cursor.execute("SELECT COUNT(*) FROM scenes_fts")
                stats['indexed_scenes'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats['indexed_scenes'] = 0
            
            # Count indexed memory entries
            try:
                cursor.execute("SELECT COUNT(*) FROM memory_fts")
                stats['indexed_memory'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats['indexed_memory'] = 0
            
            return stats
    
    def optimize_indexes(self):
        """Optimize FTS5 indexes for better performance."""
        optimize_fts_index(self.story_id)
        # Clear cache after optimization
        self.query_cache.clear()
    
    def clear_cache(self):
        """Clear search result cache."""
        self.query_cache.clear()
    
    def get_search_history(self, limit: int = 20) -> List[SearchHistory]:
        """Get recent search history."""
        return list(reversed(self.search_history[-limit:]))
    
    def clear_search_history(self):
        """Clear search history."""
        self.search_history.clear()
    
    def save_search(self, name: str, query: str, description: str = "", filters: Dict[str, str] = None) -> SavedSearch:
        """Save a search for later reuse."""
        saved_search = SavedSearch(
            name=name,
            query=query,
            description=description,
            filters=filters or {}
        )
        self.saved_searches[name] = saved_search
        return saved_search
    
    def get_saved_search(self, name: str) -> Optional[SavedSearch]:
        """Get a saved search by name."""
        saved_search = self.saved_searches.get(name)
        if saved_search:
            saved_search.last_used = datetime.now()
            saved_search.use_count += 1
        return saved_search
    
    def list_saved_searches(self) -> List[SavedSearch]:
        """List all saved searches."""
        return list(self.saved_searches.values())
    
    def delete_saved_search(self, name: str) -> bool:
        """Delete a saved search."""
        if name in self.saved_searches:
            del self.saved_searches[name]
            return True
        return False
    
    def execute_saved_search(self, name: str, limit: int = 50) -> List[SearchResult]:
        """Execute a saved search."""
        saved_search = self.get_saved_search(name)
        if saved_search:
            # Build query with filters
            query_with_filters = saved_search.query
            if saved_search.filters:
                for key, value in saved_search.filters.items():
                    query_with_filters += f" {key}:{value}"
            
            return self.search_all(query_with_filters, limit)
        return []
    
    def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get search suggestions based on history and saved searches."""
        suggestions = []
        
        # Get suggestions from search history
        for history_entry in reversed(self.search_history):
            if partial_query.lower() in history_entry.query.lower():
                if history_entry.query not in suggestions:
                    suggestions.append(history_entry.query)
                    if len(suggestions) >= limit:
                        break
        
        # Get suggestions from saved searches
        if len(suggestions) < limit:
            for saved_search in self.saved_searches.values():
                if partial_query.lower() in saved_search.query.lower():
                    if saved_search.query not in suggestions:
                        suggestions.append(saved_search.query)
                        if len(suggestions) >= limit:
                            break
        
        return suggestions[:limit]
    
    def export_search_results(self, results: List[SearchResult], format: str = 'json') -> str:
        """Export search results in various formats."""
        if format == 'json':
            return self._export_json(results)
        elif format == 'markdown':
            return self._export_markdown(results)
        elif format == 'csv':
            return self._export_csv(results)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self, results: List[SearchResult]) -> str:
        """Export results as JSON."""
        export_data = []
        for result in results:
            export_data.append({
                'id': result.id,
                'content_type': result.content_type,
                'title': result.title,
                'content': result.content,
                'snippet': result.snippet,
                'score': result.score,
                'timestamp': result.timestamp,
                'scene_label': result.scene_label,
                'metadata': result.metadata
            })
        return json.dumps(export_data, indent=2)
    
    def _export_markdown(self, results: List[SearchResult]) -> str:
        """Export results as Markdown."""
        markdown = "# Search Results\n\n"
        for i, result in enumerate(results, 1):
            markdown += f"## {i}. {result.title}\n\n"
            markdown += f"**Type:** {result.content_type}\n"
            markdown += f"**Score:** {result.score:.6f}\n"
            if result.timestamp:
                markdown += f"**Timestamp:** {result.timestamp}\n"
            if result.scene_label:
                markdown += f"**Scene Label:** {result.scene_label}\n"
            markdown += f"\n**Content:**\n{result.content}\n\n"
            markdown += f"**Snippet:**\n{result.snippet}\n\n"
            markdown += "---\n\n"
        return markdown
    
    def _export_csv(self, results: List[SearchResult]) -> str:
        """Export results as CSV."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Content Type', 'Title', 'Content', 'Snippet', 
                        'Score', 'Timestamp', 'Scene Label'])
        
        # Write data
        for result in results:
            writer.writerow([
                result.id,
                result.content_type,
                result.title,
                result.content.replace('\n', ' '),
                result.snippet.replace('\n', ' '),
                result.score,
                result.timestamp or '',
                result.scene_label or ''
            ])
        
        return output.getvalue()
    
    def get_performance_stats(self) -> Dict:
        """Get search engine performance statistics."""
        stats = self.performance_stats.copy()
        stats.update({
            'cache_size': len(self.query_cache),
            'cache_hit_rate': (stats['cache_hits'] / max(stats['total_queries'], 1)) * 100,
            'search_history_size': len(self.search_history),
            'saved_searches_count': len(self.saved_searches)
        })
        return stats
    
    def health_check(self) -> Dict:
        """Perform a health check on the search engine."""
        health = {
            'status': 'healthy',
            'fts_supported': self.fts_supported,
            'issues': []
        }
        
        try:
            # Test basic functionality
            test_results = self.search_all('test', limit=1)
            health['search_functional'] = True
        except Exception as e:
            health['status'] = 'unhealthy'
            health['search_functional'] = False
            health['issues'].append(f"Search test failed: {str(e)}")
        
        # Check FTS5 table integrity
        try:
            with get_connection(self.story_id) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO scenes_fts(scenes_fts) VALUES('integrity-check')")
                cursor.execute("INSERT INTO memory_fts(memory_fts) VALUES('integrity-check')")
                health['fts_integrity'] = True
        except Exception as e:
            health['status'] = 'unhealthy'
            health['fts_integrity'] = False
            health['issues'].append(f"FTS5 integrity check failed: {str(e)}")
        
        return health


# Convenience functions for easy access
def search_story(story_id: str, query: str, limit: int = 50) -> List[SearchResult]:
    """Search a story with a simple query string."""
    engine = SearchEngine(story_id)
    return engine.search_all(query, limit)


def search_scenes_only(story_id: str, query: str, limit: int = 50) -> List[SearchResult]:
    """Search only scenes in a story."""
    engine = SearchEngine(story_id)
    parsed_query = engine.parse_query(query)
    return engine.search_scenes(parsed_query, limit)


def search_memory_only(story_id: str, query: str, limit: int = 50) -> List[SearchResult]:
    """Search only memory in a story."""
    engine = SearchEngine(story_id)
    parsed_query = engine.parse_query(query)
    return engine.search_memory(parsed_query, limit)
