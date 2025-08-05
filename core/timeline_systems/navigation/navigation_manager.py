"""
Navigation Manager - Timeline Navigation & History

Handles timeline navigation, history tracking, and scene transitions.
Extracted from legacy timeline_builder.py navigation functionality.
"""

import json
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
from pathlib import Path

class NavigationManager:
    """Handles timeline navigation and history tracking."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
    
    async def get_navigation_history(self) -> List[Dict[str, Any]]:
        """Retrieve navigation history for timeline."""
        try:
            from core.database import execute_query, init_database
            
            init_database(self.story_id)
            
            # Get recent navigation entries
            rows = execute_query(self.story_id, '''
                SELECT scene_id, scene_title, timestamp, scene_summary,
                       navigation_type, user_choice
                FROM scenes 
                ORDER BY timestamp DESC 
                LIMIT 20
            ''')
            
            history = []
            for row in rows:
                history.append({
                    "scene_id": row[0],
                    "title": row[1] or "Untitled Scene",
                    "timestamp": row[2],
                    "summary": row[3],
                    "navigation_type": row[4] or "standard",
                    "user_choice": row[5],
                    "display_time": self._format_display_time(row[2])
                })
            
            return history
            
        except Exception as e:
            from utilities.logging_system import log_system_event
            log_system_event("error", f"Navigation history retrieval failed: {e}")
            return []
    
    async def find_scene_by_criteria(self, 
                                   title_pattern: Optional[str] = None,
                                   content_pattern: Optional[str] = None,
                                   time_range: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Find scenes matching navigation criteria."""
        try:
            from core.database import execute_query, init_database
            
            init_database(self.story_id)
            
            # Build dynamic query based on criteria
            query_parts = ['SELECT scene_id, scene_title, timestamp, scene_summary FROM scenes WHERE 1=1']
            params = []
            
            if title_pattern:
                query_parts.append('AND scene_title LIKE ?')
                params.append(f'%{title_pattern}%')
            
            if content_pattern:
                query_parts.append('AND (scene_content LIKE ? OR scene_summary LIKE ?)')
                params.extend([f'%{content_pattern}%', f'%{content_pattern}%'])
            
            if time_range:
                if time_range.get('start'):
                    query_parts.append('AND timestamp >= ?')
                    params.append(time_range['start'])
                if time_range.get('end'):
                    query_parts.append('AND timestamp <= ?')
                    params.append(time_range['end'])
            
            query_parts.append('ORDER BY timestamp DESC LIMIT 50')
            query = ' '.join(query_parts)
            
            rows = execute_query(self.story_id, query, params)
            
            results = []
            for row in rows:
                results.append({
                    "scene_id": row[0],
                    "title": row[1] or "Untitled Scene",
                    "timestamp": row[2],
                    "summary": row[3],
                    "relevance_score": self._calculate_relevance_score(row, title_pattern, content_pattern)
                })
            
            # Sort by relevance score
            return sorted(results, key=lambda x: x['relevance_score'], reverse=True)
            
        except Exception as e:
            from utilities.logging_system import log_system_event
            log_system_event("error", f"Scene search failed: {e}")
            return []
    
    async def get_scene_context(self, scene_id: str, context_window: int = 3) -> Dict[str, Any]:
        """Get contextual scenes around target scene."""
        try:
            from core.database import execute_query, init_database
            
            init_database(self.story_id)
            
            # Get target scene timestamp
            target_row = execute_query(self.story_id, '''
                SELECT timestamp, scene_title, scene_summary 
                FROM scenes WHERE scene_id = ?
            ''', (scene_id,))
            
            if not target_row:
                return {"error": "Scene not found"}
            
            target_timestamp = target_row[0][0]
            
            # Get surrounding scenes
            context_rows = execute_query(self.story_id, '''
                (SELECT scene_id, scene_title, timestamp, scene_summary, 'before' as position
                 FROM scenes 
                 WHERE timestamp < ? 
                 ORDER BY timestamp DESC 
                 LIMIT ?)
                UNION ALL
                (SELECT scene_id, scene_title, timestamp, scene_summary, 'current' as position
                 FROM scenes 
                 WHERE scene_id = ?)
                UNION ALL
                (SELECT scene_id, scene_title, timestamp, scene_summary, 'after' as position
                 FROM scenes 
                 WHERE timestamp > ? 
                 ORDER BY timestamp ASC 
                 LIMIT ?)
                ORDER BY timestamp ASC
            ''', (target_timestamp, context_window, scene_id, target_timestamp, context_window))
            
            context_scenes = []
            for row in context_rows:
                context_scenes.append({
                    "scene_id": row[0],
                    "title": row[1] or "Untitled Scene",
                    "timestamp": row[2],
                    "summary": row[3],
                    "position": row[4],
                    "is_target": row[0] == scene_id
                })
            
            return {
                "target_scene_id": scene_id,
                "context_window": context_window,
                "context_scenes": context_scenes,
                "total_context": len(context_scenes)
            }
            
        except Exception as e:
            from utilities.logging_system import log_system_event
            log_system_event("error", f"Scene context retrieval failed: {e}")
            return {"error": str(e)}
    
    async def track_navigation_path(self, from_scene: str, to_scene: str, navigation_type: str = "manual") -> bool:
        """Track navigation between scenes."""
        try:
            from core.database import execute_update, init_database
            
            init_database(self.story_id)
            
            # Log navigation event
            execute_update(self.story_id, '''
                INSERT INTO navigation_history 
                (from_scene, to_scene, navigation_type, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (from_scene, to_scene, navigation_type, datetime.now(UTC).isoformat()))
            
            from utilities.logging_system import log_system_event
            log_system_event("timeline_navigation", 
                            f"Navigation: {from_scene} -> {to_scene} ({navigation_type})")
            
            return True
            
        except Exception as e:
            from utilities.logging_system import log_system_event
            log_system_event("error", f"Navigation tracking failed: {e}")
            return False
    
    async def get_navigation_statistics(self) -> Dict[str, Any]:
        """Get navigation pattern statistics."""
        try:
            from core.database import execute_query, init_database
            
            init_database(self.story_id)
            
            # Count total scenes
            scene_count = execute_query(self.story_id, 'SELECT COUNT(*) FROM scenes')[0][0]
            
            # Get navigation patterns
            nav_patterns = execute_query(self.story_id, '''
                SELECT navigation_type, COUNT(*) as count
                FROM navigation_history 
                GROUP BY navigation_type
                ORDER BY count DESC
            ''')
            
            # Get recent activity
            recent_activity = execute_query(self.story_id, '''
                SELECT COUNT(*) FROM scenes 
                WHERE timestamp > datetime('now', '-7 days')
            ''')[0][0]
            
            return {
                "total_scenes": scene_count,
                "recent_activity": recent_activity,
                "navigation_patterns": [
                    {"type": row[0], "count": row[1]} 
                    for row in nav_patterns
                ],
                "statistics_timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            from utilities.logging_system import log_system_event
            log_system_event("error", f"Navigation statistics failed: {e}")
            return {"error": str(e)}
    
    async def navigate(self, navigation_type: str, **kwargs) -> Dict[str, Any]:
        """Main navigation interface for different types of navigation."""
        try:
            if navigation_type == "history":
                return {"type": "history", "data": await self.get_navigation_history()}
            
            elif navigation_type == "search":
                results = await self.find_scene_by_criteria(
                    title_pattern=kwargs.get('title_pattern'),
                    content_pattern=kwargs.get('content_pattern'),
                    time_range=kwargs.get('time_range')
                )
                return {"type": "search", "results": results}
            
            elif navigation_type == "context":
                scene_id = kwargs.get('scene_id')
                if not scene_id:
                    raise ValueError("scene_id required for context navigation")
                
                context = await self.get_scene_context(
                    scene_id, kwargs.get('context_window', 3)
                )
                return {"type": "context", "data": context}
            
            elif navigation_type == "track":
                from_scene = kwargs.get('from_scene')
                to_scene = kwargs.get('to_scene')
                if not from_scene or not to_scene:
                    raise ValueError("from_scene and to_scene required for tracking")
                
                success = await self.track_navigation_path(
                    from_scene, to_scene, kwargs.get('nav_type', 'manual')
                )
                return {"type": "track", "success": success}
            
            elif navigation_type == "statistics":
                stats = await self.get_navigation_statistics()
                return {"type": "statistics", "data": stats}
            
            else:
                raise ValueError(f"Unknown navigation type: {navigation_type}")
                
        except Exception as e:
            from utilities.logging_system import log_system_event
            log_system_event("error", f"Navigation operation failed: {e}")
            return {"error": str(e), "navigation_type": navigation_type}
    
    def _format_display_time(self, timestamp: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return timestamp
    
    def _calculate_relevance_score(self, row, title_pattern: Optional[str], content_pattern: Optional[str]) -> float:
        """Calculate relevance score for search results."""
        score = 0.0
        
        if title_pattern and row[1]:
            if title_pattern.lower() in row[1].lower():
                score += 10.0
        
        if content_pattern and row[3]:
            if content_pattern.lower() in row[3].lower():
                score += 5.0
        
        # Recency bonus (newer scenes get slight boost)
        try:
            dt = datetime.fromisoformat(row[2].replace('Z', '+00:00'))
            days_old = (datetime.now(UTC) - dt).days
            score += max(0, 2.0 - (days_old * 0.1))
        except:
            pass
        
        return score
