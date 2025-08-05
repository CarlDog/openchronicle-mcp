"""
Shared Timeline Utilities - Common Temporal State Management

Provides shared utilities, validation patterns, and common functionality
for timeline and state management operations.
"""

import json
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional

class TemporalStateManager:
    """Shared temporal state management utilities."""
    
    @staticmethod
    def validate_timeline_entry(entry: Dict[str, Any]) -> bool:
        """Validate timeline entry structure."""
        required_fields = ['type', 'timestamp']
        return all(field in entry for field in required_fields)
    
    @staticmethod
    def normalize_timestamp(timestamp: str) -> str:
        """Normalize timestamp to ISO format."""
        try:
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            dt = datetime.fromisoformat(timestamp)
            return dt.isoformat()
        except Exception:
            return datetime.now(UTC).isoformat()
    
    @staticmethod
    def calculate_timeline_gaps(entries: List[Dict[str, Any]], max_gap_hours: int = 24) -> List[Dict[str, Any]]:
        """Identify significant gaps in timeline."""
        if len(entries) < 2:
            return []
        
        gaps = []
        for i in range(1, len(entries)):
            prev_entry = entries[i-1]
            curr_entry = entries[i]
            
            try:
                prev_time = datetime.fromisoformat(prev_entry['timestamp'])
                curr_time = datetime.fromisoformat(curr_entry['timestamp'])
                gap_hours = (curr_time - prev_time).total_seconds() / 3600
                
                if gap_hours > max_gap_hours:
                    gaps.append({
                        'start_entry': prev_entry,
                        'end_entry': curr_entry,
                        'gap_hours': gap_hours,
                        'gap_type': 'significant' if gap_hours > 72 else 'moderate'
                    })
            except Exception:
                continue
        
        return gaps

class CheckpointPatterns:
    """Common checkpoint and rollback patterns."""
    
    @staticmethod
    def should_auto_checkpoint(scene_count: int, interval: int = 10) -> bool:
        """Determine if automatic checkpoint should be created."""
        return scene_count > 0 and scene_count % interval == 0
    
    @staticmethod
    def generate_checkpoint_description(scene_data: Dict[str, Any]) -> str:
        """Generate automatic description for checkpoint."""
        scene_input = scene_data.get('input', '')
        if len(scene_input) > 50:
            return f"Auto-checkpoint: {scene_input[:50]}..."
        return f"Auto-checkpoint: {scene_input}"
    
    @staticmethod
    def prioritize_checkpoints(checkpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize checkpoints by importance for retention."""
        # Sort by age and usage patterns
        return sorted(checkpoints, key=lambda x: (
            x.get('usage_count', 0),
            -x.get('age_hours', 0)  # Negative to prefer recent
        ), reverse=True)

class HistoryUtilities:
    """History tracking and analysis utilities."""
    
    @staticmethod
    def extract_narrative_arc(timeline_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract basic narrative arc from timeline."""
        scene_entries = [e for e in timeline_entries if e.get('type') == 'scene']
        
        if len(scene_entries) < 3:
            return {'arc_type': 'insufficient_data', 'scenes': len(scene_entries)}
        
        # Simple arc analysis
        beginning = scene_entries[:len(scene_entries)//3]
        middle = scene_entries[len(scene_entries)//3:2*len(scene_entries)//3]
        end = scene_entries[2*len(scene_entries)//3:]
        
        return {
            'arc_type': 'three_act',
            'beginning': {
                'scene_count': len(beginning),
                'start_time': beginning[0]['timestamp'] if beginning else None
            },
            'middle': {
                'scene_count': len(middle),
                'complexity': len(middle) / len(scene_entries)
            },
            'end': {
                'scene_count': len(end),
                'end_time': end[-1]['timestamp'] if end else None
            },
            'total_scenes': len(scene_entries)
        }
    
    @staticmethod
    def detect_story_phases(timeline_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect distinct phases in story progression."""
        scene_entries = [e for e in timeline_entries if e.get('type') == 'scene']
        
        phases = []
        phase_size = max(3, len(scene_entries) // 5)  # At least 3 scenes per phase
        
        for i in range(0, len(scene_entries), phase_size):
            phase_scenes = scene_entries[i:i + phase_size]
            if phase_scenes:
                phases.append({
                    'phase_number': len(phases) + 1,
                    'start_scene': phase_scenes[0]['scene_id'],
                    'end_scene': phase_scenes[-1]['scene_id'],
                    'scene_count': len(phase_scenes),
                    'timespan': {
                        'start': phase_scenes[0]['timestamp'],
                        'end': phase_scenes[-1]['timestamp']
                    }
                })
        
        return phases
