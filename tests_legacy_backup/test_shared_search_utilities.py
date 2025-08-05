"""
Tests for search_utilities.py - Comprehensive validation of search consolidation

Tests cover:
- Query processing and SQL injection protection
- FTS query building and escaping
- Result ranking and scoring
- Search utilities integration
- Backward compatibility functions
- Real-world usage patterns from core modules
"""

import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Test imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.shared.search_utilities import (
    SearchUtilities, SearchOptions, SearchResult,
    QueryProcessor, FTSQueryBuilder, ResultRanker,
    search_scenes_fts, search_with_pagination
)
from core.shared.database_operations import DatabaseOperations


class TestQueryProcessor:
    """Test query processing and SQL safety"""
    
    def test_validate_order_by_safe_patterns(self):
        """Test ORDER BY validation with safe patterns"""
        # Valid patterns
        assert QueryProcessor.validate_order_by("timestamp DESC")
        assert QueryProcessor.validate_order_by("scene_id ASC")
        assert QueryProcessor.validate_order_by("score")
        assert QueryProcessor.validate_order_by("created_at")
        
        # Invalid patterns (SQL injection attempts)
        assert not QueryProcessor.validate_order_by("timestamp; DROP TABLE users;")
        assert not QueryProcessor.validate_order_by("1=1 UNION SELECT")
        assert not QueryProcessor.validate_order_by("timestamp DESC, (SELECT 1)")
        assert not QueryProcessor.validate_order_by("")
        assert not QueryProcessor.validate_order_by(None)
    
    def test_validate_column_name_safety(self):
        """Test column name validation for injection protection"""
        # Valid column names
        assert QueryProcessor.validate_column_name("scene_id")
        assert QueryProcessor.validate_column_name("timestamp")
        assert QueryProcessor.validate_column_name("character_name")
        assert QueryProcessor.validate_column_name("_internal_field")
        
        # Invalid column names
        assert not QueryProcessor.validate_column_name("scene_id; DROP TABLE")
        assert not QueryProcessor.validate_column_name("1=1 OR 1")
        assert not QueryProcessor.validate_column_name("scene-id")  # Hyphens not allowed
        assert not QueryProcessor.validate_column_name("")
        assert not QueryProcessor.validate_column_name(None)
    
    def test_build_where_clause_simple_filters(self):
        """Test WHERE clause building with simple filters"""
        filters = {
            'story_id': 'test-story',
            'character_id': 'char-123',
            'active': True
        }
        
        where_clause, params = QueryProcessor.build_where_clause(filters)
        
        assert where_clause == " WHERE story_id = ? AND character_id = ? AND active = ?"
        assert params == ['test-story', 'char-123', True]
    
    def test_build_where_clause_list_filters(self):
        """Test WHERE clause with IN clauses"""
        filters = {
            'character_id': ['char-1', 'char-2', 'char-3'],
            'status': ['active', 'pending']
        }
        
        where_clause, params = QueryProcessor.build_where_clause(filters)
        
        assert "character_id IN (?,?,?)" in where_clause
        assert "status IN (?,?)" in where_clause
        assert params == ['char-1', 'char-2', 'char-3', 'active', 'pending']
    
    def test_build_where_clause_range_filters(self):
        """Test WHERE clause with range filters"""
        filters = {
            'timestamp': {'min': '2023-01-01', 'max': '2023-12-31'},
            'score': {'min': 0.5},
            'content': {'like': '%important%'}
        }
        
        where_clause, params = QueryProcessor.build_where_clause(filters)
        
        assert "timestamp >= ?" in where_clause
        assert "timestamp <= ?" in where_clause
        assert "score >= ?" in where_clause
        assert "content LIKE ?" in where_clause
        assert params == ['2023-01-01', '2023-12-31', 0.5, '%important%']
    
    def test_build_where_clause_with_prefix(self):
        """Test WHERE clause with table prefix"""
        filters = {'scene_id': 'scene-123'}
        
        where_clause, params = QueryProcessor.build_where_clause(filters, "s")
        
        assert where_clause == " WHERE s.scene_id = ?"
        assert params == ['scene-123']
    
    def test_build_pagination_validation(self):
        """Test pagination parameter validation"""
        # Normal case
        clause, params = QueryProcessor.build_pagination(50, 100)
        assert clause == " LIMIT ? OFFSET ?"
        assert params == [50, 100]
        
        # Edge cases
        clause, params = QueryProcessor.build_pagination(-10, -5)  # Should be corrected
        assert params == [1, 0]  # Min values
        
        clause, params = QueryProcessor.build_pagination(50000, 0)  # Should be limited
        assert params == [10000, 0]  # Max limit
    
    def test_build_order_by_with_validation(self):
        """Test ORDER BY clause building with validation"""
        # Valid order by
        result = QueryProcessor.build_order_by("timestamp DESC")
        assert result == " ORDER BY timestamp DESC"
        
        # Invalid order by - should use default
        result = QueryProcessor.build_order_by("1=1; DROP TABLE", "scene_id ASC")
        assert result == " ORDER BY scene_id ASC"
        
        # Empty order by - should use default
        result = QueryProcessor.build_order_by("", "created_at DESC")
        assert result == " ORDER BY created_at DESC"


class TestFTSQueryBuilder:
    """Test Full-Text Search query building"""
    
    def test_escape_fts_query_basic(self):
        """Test basic FTS query escaping"""
        # Normal queries
        assert FTSQueryBuilder.escape_fts_query("hello world") == "hello world"
        assert FTSQueryBuilder.escape_fts_query("character development") == "character development"
        
        # Quotes should be escaped
        assert FTSQueryBuilder.escape_fts_query('say "hello"') == 'say ""hello""'
        
        # Special characters should be removed (except allowed ones)
        result = FTSQueryBuilder.escape_fts_query("hello@world!#$%")
        assert result == "hello world"
        
        # Preserve basic operators and quotes/colons/asterisks
        assert FTSQueryBuilder.escape_fts_query("hello AND world") == "hello AND world"
        assert FTSQueryBuilder.escape_fts_query("story* OR character*") == "story* OR character*"
        assert FTSQueryBuilder.escape_fts_query("field:value") == "field:value"
    
    def test_build_fts_query_simple(self):
        """Test simple FTS query building"""
        query = FTSQueryBuilder.build_fts_query("hello world")
        assert "hello world" in query
        
        # Should add exact match boosting for multi-word
        query = FTSQueryBuilder.build_fts_query("hello battle", boost_exact=True)
        assert '"hello battle"' in query
        assert "hello battle" in query
    
    def test_build_fts_query_with_columns(self):
        """Test FTS query with column targeting"""
        columns = ['input', 'output']
        query = FTSQueryBuilder.build_fts_query("dragon", columns=columns)
        
        assert "input:dragon" in query
        assert "output:dragon" in query
        assert " OR " in query
    
    def test_build_snippet_select(self):
        """Test FTS snippet generation"""
        columns = ['input', 'output']
        snippets = FTSQueryBuilder.build_snippet_select(
            'scenes_fts', columns, '<b>', '</b>', '...', 20
        )
        
        assert len(snippets) == 2
        assert "snippet(scenes_fts, 0, '<b>', '</b>', '...', 20)" in snippets[0]
        assert "snippet(scenes_fts, 1, '<b>', '</b>', '...', 20)" in snippets[1]
        assert "snippet_input" in snippets[0]
        assert "snippet_output" in snippets[1]


class TestResultRanker:
    """Test result ranking and scoring"""
    
    def test_calculate_relevance_score_basic(self):
        """Test basic relevance score calculation"""
        # Base FTS score
        score = ResultRanker.calculate_relevance_score(0.75)
        assert score == 0.75
        
        # Zero score handling
        score = ResultRanker.calculate_relevance_score(0.0)
        assert score == 0.0
    
    def test_calculate_relevance_score_with_timestamp(self):
        """Test relevance scoring with timestamp weighting"""
        recent_time = datetime.now() - timedelta(days=5)
        old_time = datetime.now() - timedelta(days=100)
        
        # Recent content should get bonus
        recent_score = ResultRanker.calculate_relevance_score(
            0.5, timestamp_weight=0.2, timestamp=recent_time
        )
        
        old_score = ResultRanker.calculate_relevance_score(
            0.5, timestamp_weight=0.2, timestamp=old_time
        )
        
        assert recent_score > old_score
        assert recent_score > 0.5  # Should have bonus
    
    def test_calculate_relevance_score_with_content_length(self):
        """Test relevance scoring with content length factor"""
        # Optimal content length (around 500 chars) should get full bonus
        score_optimal = ResultRanker.calculate_relevance_score(
            0.5, content_length_weight=0.1, content_length=500
        )
        
        # Short content should get proportional bonus
        score_short = ResultRanker.calculate_relevance_score(
            0.5, content_length_weight=0.1, content_length=250
        )
        
        assert score_optimal > score_short
        assert score_optimal > 0.5
    
    def test_rank_results_by_score(self):
        """Test result ranking by score"""
        results = [
            SearchResult(id="1", score=0.3),
            SearchResult(id="2", score=0.8),
            SearchResult(id="3", score=0.5),
        ]
        
        ranked = ResultRanker.rank_results(results, "score", ascending=False)
        
        # Should be sorted by score (highest first)
        assert ranked[0].id == "2"  # score 0.8
        assert ranked[1].id == "3"  # score 0.5
        assert ranked[2].id == "1"  # score 0.3
        
        # Ranks should be assigned
        assert ranked[0].rank == 1
        assert ranked[1].rank == 2
        assert ranked[2].rank == 3
    
    def test_rank_results_by_timestamp(self):
        """Test result ranking by timestamp"""
        now = datetime.now()
        results = [
            SearchResult(id="1", timestamp=now - timedelta(hours=2)),
            SearchResult(id="2", timestamp=now - timedelta(hours=1)),
            SearchResult(id="3", timestamp=now - timedelta(hours=3)),
        ]
        
        ranked = ResultRanker.rank_results(results, "timestamp", ascending=False)
        
        # Should be sorted by timestamp (newest first)
        assert ranked[0].id == "2"  # 1 hour ago
        assert ranked[1].id == "1"  # 2 hours ago
        assert ranked[2].id == "3"  # 3 hours ago


class TestSearchUtilities:
    """Test main SearchUtilities class"""
    
    @pytest.fixture
    def mock_db_ops(self):
        """Create mock database operations"""
        mock_db = Mock(spec=DatabaseOperations)
        return mock_db
    
    @pytest.fixture
    def search_util(self, mock_db_ops):
        """Create SearchUtilities instance with mock DB"""
        return SearchUtilities(mock_db_ops)
    
    def test_search_utilities_initialization(self):
        """Test SearchUtilities initialization"""
        # With custom db_ops
        mock_db = Mock(spec=DatabaseOperations)
        search_util = SearchUtilities(mock_db)
        assert search_util.db_ops == mock_db
        
        # With default db_ops (None until needed)
        search_util = SearchUtilities()
        assert search_util.db_ops is None
        assert isinstance(search_util.query_processor, QueryProcessor)
        assert isinstance(search_util.fts_builder, FTSQueryBuilder)
        assert isinstance(search_util.ranker, ResultRanker)
    
    def test_execute_search_with_fts(self, search_util, mock_db_ops):
        """Test FTS search execution"""
        # Mock database response
        mock_db_ops.execute_query.return_value = [
            {
                'rowid': 1,
                'scene_id': 'scene-1',
                'input': 'The dragon appeared',
                'output': 'You see a mighty dragon',
                'timestamp': '2023-01-01T10:00:00',
                'score': 0.75,
                'snippet_input': 'The <mark>dragon</mark> appeared',
                'snippet_output': 'You see a mighty <mark>dragon</mark>'
            }
        ]
        
        options = SearchOptions(use_fts=True, include_snippets=True)
        results = search_util.execute_search(
            'test-story', 'dragon', 'scenes',
            ['input', 'output'], None, options
        )
        
        assert len(results) == 1
        result = results[0]
        assert result.id == '1'
        assert result.score == 0.75
        assert result.content['scene_id'] == 'scene-1'
        assert 'dragon' in result.snippets['input']
        
        # Verify database call
        mock_db_ops.execute_query.assert_called_once()
        call_args = mock_db_ops.execute_query.call_args[0]
        assert call_args[0] == 'test-story'  # story_id
        assert 'scenes_fts' in call_args[1]  # SQL contains FTS table
        assert 'MATCH' in call_args[1]  # SQL contains MATCH clause
    
    def test_execute_search_simple(self, search_util, mock_db_ops):
        """Test simple non-FTS search execution"""
        # Mock database response
        mock_db_ops.execute_query.return_value = [
            {
                'rowid': 1,
                'scene_id': 'scene-1',
                'input': 'Some content',
                'timestamp': '2023-01-01T10:00:00'
            }
        ]
        
        options = SearchOptions(use_fts=False)
        filters = {'scene_id': 'scene-1'}
        
        results = search_util.execute_search(
            'test-story', '', 'scenes',
            ['scene_id', 'input'], filters, options
        )
        
        assert len(results) == 1
        result = results[0]
        assert result.id == '1'
        assert result.content['scene_id'] == 'scene-1'
        
        # Verify database call
        mock_db_ops.execute_query.assert_called_once()
        call_args = mock_db_ops.execute_query.call_args[0]
        assert 'scenes_fts' not in call_args[1]  # No FTS table
        assert 'MATCH' not in call_args[1]  # No MATCH clause
    
    def test_search_scenes_convenience_method(self, search_util, mock_db_ops):
        """Test search_scenes convenience method"""
        mock_db_ops.execute_query.return_value = []
        
        search_util.search_scenes('test-story', 'dragon fight')
        
        # Should call execute_search with correct parameters
        mock_db_ops.execute_query.assert_called_once()
        call_args = mock_db_ops.execute_query.call_args[0]
        assert call_args[0] == 'test-story'
        assert 'scenes' in call_args[1]
    
    def test_search_characters_convenience_method(self, search_util, mock_db_ops):
        """Test search_characters convenience method"""
        mock_db_ops.execute_query.return_value = []
        
        search_util.search_characters('test-story', 'wizard')
        
        mock_db_ops.execute_query.assert_called_once()
        call_args = mock_db_ops.execute_query.call_args[0]
        assert 'characters' in call_args[1]
    
    def test_search_error_handling(self, search_util, mock_db_ops):
        """Test search error handling"""
        # Mock database error
        mock_db_ops.execute_query.side_effect = Exception("Database error")
        
        results = search_util.execute_search('test-story', 'query', 'scenes')
        
        # Should return empty list on error
        assert results == []
    
    def test_convert_rows_to_results(self, search_util):
        """Test row to SearchResult conversion"""
        rows = [
            {
                'rowid': 1,
                'scene_id': 'scene-1',
                'input': 'Dragon battle content',
                'timestamp': '2023-01-01T10:00:00',
                'score': 0.8,
                'snippet_input': 'Dragon <mark>battle</mark> content'
            }
        ]
        
        options = SearchOptions(include_content=True, include_snippets=True)
        results = search_util._convert_rows_to_results(rows, options, has_fts_score=True)
        
        assert len(results) == 1
        result = results[0]
        
        # Check basic fields
        assert result.id == '1'
        assert result.score >= 0.8  # May be enhanced
        
        # Check content
        assert result.content['scene_id'] == 'scene-1'
        assert result.content['input'] == 'Dragon battle content'
        
        # Check snippets
        assert result.snippets['input'] == 'Dragon <mark>battle</mark> content'
        
        # Check metadata
        assert result.metadata['timestamp'] == '2023-01-01T10:00:00'


class TestBackwardCompatibility:
    """Test backward compatibility functions"""
    
    @patch('core.shared.search_utilities.SearchUtilities')
    def test_search_scenes_fts_compatibility(self, mock_search_class):
        """Test search_scenes_fts backward compatibility"""
        # Mock SearchUtilities and its results
        mock_search_util = Mock()
        mock_search_class.return_value = mock_search_util
        
        mock_result = SearchResult(
            id='1',
            score=0.75,
            content={
                'scene_id': 'scene-1',
                'input': 'Dragon fight',
                'output': 'Epic battle ensues',
                'scene_label': 'Battle Scene',
                'timestamp': '2023-01-01T10:00:00'
            },
            snippets={
                'input': 'Dragon <mark>fight</mark>',
                'output': 'Epic <mark>battle</mark> ensues'
            }
        )
        
        mock_search_util.search_scenes.return_value = [mock_result]
        
        # Call backward compatibility function
        results = search_scenes_fts('test-story', 'fight', limit=25)
        
        # Check call was made correctly
        mock_search_util.search_scenes.assert_called_once()
        call_args = mock_search_util.search_scenes.call_args
        assert call_args[0][0] == 'test-story'  # story_id
        assert call_args[0][1] == 'fight'  # query
        assert call_args[1]['options'].limit == 25
        assert call_args[1]['options'].include_snippets == True
        
        # Check result format matches old format
        assert len(results) == 1
        result = results[0]
        assert result['scene_id'] == 'scene-1'
        assert result['input'] == 'Dragon fight'
        assert result['output'] == 'Epic battle ensues'
        assert result['score'] == 0.75
        assert result['snippet_input'] == 'Dragon <mark>fight</mark>'
        assert result['snippet_output'] == 'Epic <mark>battle</mark> ensues'
    
    @patch('core.shared.search_utilities.SearchUtilities')
    def test_search_with_pagination_compatibility(self, mock_search_class):
        """Test search_with_pagination backward compatibility"""
        # Mock SearchUtilities and its results
        mock_search_util = Mock()
        mock_search_class.return_value = mock_search_util
        
        mock_result = SearchResult(
            id='1',
            content={'scene_id': 'scene-1', 'content': 'Test content'}
        )
        
        mock_search_util.execute_search.return_value = [mock_result]
        
        # Call backward compatibility function
        filters = {'character_id': 'char-1'}
        results = search_with_pagination(
            'test-story', 'scenes', filters,
            order_by='timestamp ASC', limit=20, offset=40
        )
        
        # Check call was made correctly
        mock_search_util.execute_search.assert_called_once()
        call_args = mock_search_util.execute_search.call_args
        assert call_args[0][0] == 'test-story'  # story_id
        assert call_args[0][1] == ""  # empty query
        assert call_args[0][2] == 'scenes'  # table
        assert call_args[0][4] == filters  # filters
        
        options = call_args[0][5]  # SearchOptions
        assert options.limit == 20
        assert options.offset == 40
        assert options.order_by == 'timestamp ASC'
        assert options.use_fts == False
        
        # Check result format
        assert len(results) == 1
        assert results[0] == {'scene_id': 'scene-1', 'content': 'Test content'}


class TestRealWorldPatterns:
    """Test patterns extracted from actual OpenChronicle modules"""
    
    @pytest.fixture
    def search_util_with_real_db(self):
        """Create SearchUtilities with real database for integration testing"""
        # Create mock DatabaseOperations with proper story_id
        mock_db = Mock(spec=DatabaseOperations)
        return SearchUtilities(mock_db)
    
    def test_search_engine_pattern_fts_with_ranking(self, search_util_with_real_db):
        """Test pattern from search_engine.py: FTS with BM25 ranking"""
        # This tests the core pattern from search_engine.py lines 220-240
        
        # Mock the execute_query to simulate search_engine behavior
        with patch.object(search_util_with_real_db, '_ensure_db_ops') as mock_ensure_db:
            mock_db = Mock()
            mock_ensure_db.return_value = mock_db
            mock_db.execute_query.return_value = [
                {
                    'rowid': 1,
                    'scene_id': 'scene-1',
                    'input': 'The brave knight faced the dragon',
                    'output': 'Dragon roars menacingly',
                    'score': 2.34,
                    'snippet_input': 'The brave knight faced the <mark>dragon</mark>',
                    'snippet_output': '<mark>Dragon</mark> roars menacingly'
                }
            ]
            
            options = SearchOptions(
                limit=50,
                include_snippets=True,
                use_fts=True,
                order_by="score DESC"
            )
            
            results = search_util_with_real_db.search_scenes(
                'test-story', 'dragon', options=options
            )
            
            # Verify the SQL pattern matches search_engine.py
            call_args = mock_db.execute_query.call_args[0]
            sql = call_args[1]
            
            assert 'bm25(scenes_fts)' in sql
            assert 'snippet(scenes_fts' in sql
            assert 'JOIN scenes' in sql
            assert 'MATCH ?' in sql
            assert 'ORDER BY score' in sql
            assert 'LIMIT ?' in sql
            
            # Verify results
            assert len(results) == 1
            assert results[0].score == 2.34
            assert 'dragon' in results[0].snippets['input']
    
    def test_bookmark_manager_search_pattern(self, search_util_with_real_db):
        """Test pattern from bookmark_manager.py search functionality"""
        
        with patch.object(search_util_with_real_db, '_ensure_db_ops') as mock_ensure_db:
            mock_db = Mock()
            mock_ensure_db.return_value = mock_db
            mock_db.execute_query.return_value = [
                {
                    'rowid': 1,
                    'bookmark_id': 'bm-1',
                    'scene_id': 'scene-1',
                    'label': 'Important Scene',
                    'tags': 'battle,dragon',
                    'created_at': '2023-01-01T10:00:00'
                }
            ]
            
            # Test bookmark search with tag filtering
            filters = {'tags': {'like': '%dragon%'}}
            options = SearchOptions(use_fts=False, order_by="created_at DESC")
            
            results = search_util_with_real_db.search_bookmarks(
                'test-story', filters=filters, options=options
            )
            
            # Verify bookmark-specific columns are included
            call_args = mock_db.execute_query.call_args[0]
            sql = call_args[1]
            
            assert 'bookmark_id' in sql
            assert 'scene_id' in sql
            assert 'label' in sql
            assert 'tags' in sql
            assert 'created_at' in sql
            assert 'LIKE ?' in sql
            
            assert len(results) == 1
            assert results[0].content['bookmark_id'] == 'bm-1'
    
    def test_timeline_builder_pagination_pattern(self, search_util_with_real_db):
        """Test pattern from timeline_builder.py: LIMIT/OFFSET pagination"""
        
        with patch.object(search_util_with_real_db, '_ensure_db_ops') as mock_ensure_db:
            mock_db = Mock()
            mock_ensure_db.return_value = mock_db
            mock_db.execute_query.return_value = []
            
            # Test timeline-style pagination (from timeline_builder.py line 493)
            options = SearchOptions(
                limit=10,
                offset=20,
                order_by="timestamp ASC",
                use_fts=False
            )
            
            search_util_with_real_db.search_scenes(
                'test-story', options=options
            )
            
            # Verify LIMIT/OFFSET pattern
            call_args = mock_db.execute_query.call_args[0]
            sql = call_args[1]
            params = call_args[2]
            
            assert 'LIMIT ? OFFSET ?' in sql
            assert 10 in params  # limit
            assert 20 in params  # offset
            assert 'ORDER BY timestamp ASC' in sql


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
