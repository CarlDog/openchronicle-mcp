"""
State Manager - Rollback and State Management

Handles rollback point creation, state snapshots, and restoration functionality
extracted from the legacy rollback_engine.py. Provides versioning and state
management in a modular architecture.
"""

import json
import sys
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Database imports from parent core directory
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.database import execute_query, execute_update, init_database
from core.scene_logger import load_scene
from core.memory_management import MemoryOrchestrator

# Add utilities to path for logging system  
sys.path.append(str(Path(__file__).parent.parent.parent / "utilities"))
from core.shared.logging_system import log_system_event, log_info, log_warning, log_error

class StateManager:
    """Manages rollback points and state restoration."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.memory_orchestrator = MemoryOrchestrator()
        init_database(story_id)
    
    async def create_rollback_point(self, scene_id: str, description: str = "Manual rollback point") -> Dict[str, Any]:
        """Create a rollback point at a specific scene."""
        
        # Verify scene exists
        scene_data = load_scene(self.story_id, scene_id)
        if not scene_data:
            raise ValueError(f"Scene {scene_id} not found")
        
        rollback_id = f"rollback_{scene_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        
        # Create comprehensive state snapshot
        state_snapshot = await self._create_state_snapshot(scene_id)
        
        # Store rollback point
        execute_update(self.story_id, '''
            INSERT OR REPLACE INTO rollback_points 
            (rollback_id, scene_id, timestamp, description, scene_data, state_snapshot)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            rollback_id,
            scene_id,
            datetime.now(UTC).isoformat(),
            description,
            json.dumps(scene_data),
            json.dumps(state_snapshot)
        ))
        
        log_info(f"Created rollback point {rollback_id} for scene {scene_id}")
        
        return {
            "id": rollback_id,
            "scene_id": scene_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "description": description,
            "scene_data": scene_data,
            "state_snapshot": state_snapshot,
            "created_at": datetime.now(UTC).isoformat()
        }
    
    async def list_rollback_points(self) -> List[Dict[str, Any]]:
        """List all available rollback points."""
        
        rows = execute_query(self.story_id, '''
            SELECT rollback_id, scene_id, timestamp, description, scene_data, state_snapshot
            FROM rollback_points ORDER BY timestamp DESC
        ''')
        
        rollback_points = []
        for row in rows:
            try:
                scene_data = json.loads(row[4]) if row[4] else {}
                state_snapshot = json.loads(row[5]) if row[5] else {}
                
                rollback_point = {
                    "id": row[0],
                    "scene_id": row[1],
                    "timestamp": row[2],
                    "description": row[3],
                    "scene_data": scene_data,
                    "state_snapshot": state_snapshot,
                    "age_hours": self._calculate_age_hours(row[2])
                }
                rollback_points.append(rollback_point)
                
            except json.JSONDecodeError as e:
                log_warning(f"Failed to parse rollback point {row[0]}: {e}")
                continue
        
        return rollback_points
    
    async def rollback_to_point(self, rollback_id: str) -> Dict[str, Any]:
        """Restore story state to a specific rollback point."""
        
        # Get rollback point data
        rollback_data = execute_query(self.story_id, '''
            SELECT rollback_id, scene_id, timestamp, description, scene_data, state_snapshot
            FROM rollback_points WHERE rollback_id = ?
        ''', (rollback_id,))
        
        if not rollback_data:
            raise ValueError(f"Rollback point {rollback_id} not found")
        
        rollback_point = rollback_data[0]
        scene_id = rollback_point[1]
        scene_data = json.loads(rollback_point[4]) if rollback_point[4] else {}
        state_snapshot = json.loads(rollback_point[5]) if rollback_point[5] else {}
        
        # Perform rollback operations
        restoration_results = []
        
        try:
            # 1. Restore memory state
            if 'memory_state' in state_snapshot:
                memory_result = await self._restore_memory_state(state_snapshot['memory_state'])
                restoration_results.append({"component": "memory", "status": "success", "details": memory_result})
            
            # 2. Remove scenes after rollback point
            scenes_removed = await self._remove_scenes_after(scene_id)
            restoration_results.append({"component": "scenes", "status": "success", "details": f"Removed {scenes_removed} scenes"})
            
            # 3. Restore scene state if needed
            scene_result = await self._restore_scene_state(scene_id, scene_data)
            restoration_results.append({"component": "scene", "status": "success", "details": scene_result})
            
            # 4. Update rollback metadata
            await self._update_rollback_metadata(rollback_id)
            
            log_info(f"Successfully rolled back to {rollback_id}")
            
            return {
                "rollback_id": rollback_id,
                "target_scene_id": scene_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "restoration_results": restoration_results,
                "status": "success"
            }
            
        except Exception as e:
            log_error(f"Rollback to {rollback_id} failed: {e}")
            return {
                "rollback_id": rollback_id,
                "target_scene_id": scene_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "restoration_results": restoration_results,
                "status": "failed",
                "error": str(e)
            }
    
    async def cleanup_old_rollback_points(self, retention_days: int = 30) -> Dict[str, Any]:
        """Clean up rollback points older than specified days."""
        
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()
        
        # Get rollback points to remove
        old_points = execute_query(self.story_id, '''
            SELECT rollback_id FROM rollback_points 
            WHERE timestamp < ? ORDER BY timestamp ASC
        ''', (cutoff_iso,))
        
        if not old_points:
            return {"removed_count": 0, "message": "No old rollback points found"}
        
        # Remove old points
        removed_ids = [point[0] for point in old_points]
        
        execute_update(self.story_id, '''
            DELETE FROM rollback_points WHERE timestamp < ?
        ''', (cutoff_iso,))
        
        log_info(f"Cleaned up {len(removed_ids)} old rollback points")
        
        return {
            "removed_count": len(removed_ids),
            "removed_ids": removed_ids,
            "cutoff_date": cutoff_iso,
            "retention_days": retention_days
        }
    
    async def _create_state_snapshot(self, scene_id: str) -> Dict[str, Any]:
        """Create comprehensive state snapshot for rollback."""
        
        snapshot = {
            "scene_id": scene_id,
            "snapshot_timestamp": datetime.now(UTC).isoformat()
        }
        
        try:
            # Capture memory state
            memory_state = await self.memory_orchestrator.load_current_memory(self.story_id)
            snapshot["memory_state"] = memory_state
            
            # Capture scene count and latest scenes
            recent_scenes = execute_query(self.story_id, '''
                SELECT scene_id, timestamp FROM scenes 
                ORDER BY timestamp DESC LIMIT 5
            ''')
            
            snapshot["recent_scenes"] = [
                {"scene_id": scene[0], "timestamp": scene[1]} 
                for scene in recent_scenes
            ]
            
            # Capture story metadata
            snapshot["story_metadata"] = {
                "total_scenes": len(execute_query(self.story_id, 'SELECT scene_id FROM scenes')),
                "capture_time": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            log_warning(f"Failed to create complete state snapshot: {e}")
            snapshot["error"] = str(e)
        
        return snapshot
    
    async def _restore_memory_state(self, memory_state: Dict[str, Any]) -> str:
        """Restore memory state from snapshot."""
        try:
            # Use memory orchestrator to restore state
            await self.memory_orchestrator.restore_memory_snapshot(self.story_id, memory_state)
            return "Memory state restored successfully"
        except Exception as e:
            log_error(f"Failed to restore memory state: {e}")
            return f"Memory restoration failed: {e}"
    
    async def _remove_scenes_after(self, target_scene_id: str) -> int:
        """Remove all scenes that occurred after the target scene."""
        
        # Get target scene timestamp
        target_scene = execute_query(self.story_id, '''
            SELECT timestamp FROM scenes WHERE scene_id = ?
        ''', (target_scene_id,))
        
        if not target_scene:
            return 0
        
        target_timestamp = target_scene[0][0]
        
        # Count scenes to remove
        scenes_to_remove = execute_query(self.story_id, '''
            SELECT COUNT(*) FROM scenes WHERE timestamp > ?
        ''', (target_timestamp,))
        
        remove_count = scenes_to_remove[0][0] if scenes_to_remove else 0
        
        # Remove scenes after target
        execute_update(self.story_id, '''
            DELETE FROM scenes WHERE timestamp > ?
        ''', (target_timestamp,))
        
        return remove_count
    
    async def _restore_scene_state(self, scene_id: str, scene_data: Dict[str, Any]) -> str:
        """Restore specific scene state if needed."""
        # For now, just verify scene exists
        current_scene = load_scene(self.story_id, scene_id)
        if current_scene:
            return f"Scene {scene_id} verified and accessible"
        else:
            return f"Warning: Scene {scene_id} not found after rollback"
    
    async def _update_rollback_metadata(self, rollback_id: str):
        """Update rollback point metadata after use."""
        execute_update(self.story_id, '''
            UPDATE rollback_points 
            SET last_used = ?, usage_count = COALESCE(usage_count, 0) + 1
            WHERE rollback_id = ?
        ''', (datetime.now(UTC).isoformat(), rollback_id))
    
    def _calculate_age_hours(self, timestamp_iso: str) -> float:
        """Calculate age of rollback point in hours."""
        try:
            rollback_time = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
            age_delta = datetime.now(UTC) - rollback_time.replace(tzinfo=UTC)
            return age_delta.total_seconds() / 3600
        except Exception:
            return 0.0
