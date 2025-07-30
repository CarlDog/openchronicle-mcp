"""
Timeline Builder for OpenChronicle.
Creates timeline views and navigation utilities for stories.
Enhanced with tone tracking and auto-summary generation.
"""

import json
import sys
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from .database import execute_query, init_database
from .bookmark_manager import BookmarkManager
from .scene_logger import list_scenes, get_labeled_scenes

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error

class TimelineBuilder:
    """Builds story timelines and navigation structures."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.bookmark_manager = BookmarkManager(story_id)
        init_database(story_id)
    
    def get_full_timeline(self) -> Dict[str, Any]:
        """Get complete story timeline with scenes and bookmarks."""
        # Get all scenes
        scenes = execute_query(self.story_id, '''
            SELECT scene_id, timestamp, input, output, memory_snapshot, flags, canon_refs, scene_label
            FROM scenes ORDER BY timestamp ASC
        ''')
        
        # Get all bookmarks with scene info
        bookmarks = self.bookmark_manager.get_timeline_bookmarks()
        
        # Organize timeline entries
        timeline_entries = []
        
        for scene in scenes:
            entry = {
                'type': 'scene',
                'scene_id': scene[0],
                'timestamp': scene[1],
                'input': scene[2],
                'output': scene[3],
                'memory_snapshot': json.loads(scene[4] or '{}'),
                'flags': json.loads(scene[5] or '[]'),
                'canon_refs': json.loads(scene[6] or '[]'),
                'scene_label': scene[7],
                'bookmarks': []
            }
            
            # Add associated bookmarks
            scene_bookmarks = [b for b in bookmarks if b['scene_id'] == scene[0]]
            entry['bookmarks'] = scene_bookmarks
            
            timeline_entries.append(entry)
        
        return {
            'story_id': self.story_id,
            'total_scenes': len(scenes),
            'total_bookmarks': len(bookmarks),
            'timeline': timeline_entries
        }
    
    def get_chapter_timeline(self) -> Dict[str, Any]:
        """Get timeline organized by chapters (bookmarks with type 'chapter')."""
        chapters = self.bookmark_manager.get_chapter_structure()
        
        # Get scenes between chapter markers
        timeline = []
        
        # Sort chapters by timestamp
        all_chapters = []
        for level, chapter_list in chapters.items():
            for chapter in chapter_list:
                chapter['level'] = level
                all_chapters.append(chapter)
        
        all_chapters.sort(key=lambda x: x['created_at'])
        
        for i, chapter in enumerate(all_chapters):
            chapter_scenes = self._get_scenes_in_chapter(chapter, 
                                                       all_chapters[i+1] if i+1 < len(all_chapters) else None)
            
            timeline.append({
                'chapter': chapter,
                'scenes': chapter_scenes,
                'scene_count': len(chapter_scenes)
            })
        
        return {
            'story_id': self.story_id,
            'chapters': timeline,
            'total_chapters': len(timeline)
        }
    
    def get_labeled_timeline(self) -> Dict[str, Any]:
        """Get timeline showing only labeled scenes."""
        labeled_scenes = get_labeled_scenes(self.story_id)
        
        # Group by label
        grouped = {}
        for scene in labeled_scenes:
            label = scene['scene_label']
            if label not in grouped:
                grouped[label] = []
            grouped[label].append(scene)
        
        return {
            'story_id': self.story_id,
            'labeled_scenes': grouped,
            'total_labels': len(grouped),
            'total_labeled_scenes': len(labeled_scenes)
        }
    
    def get_navigation_menu(self) -> Dict[str, Any]:
        """Get navigation menu structure for story browsing."""
        # Get chapter bookmarks
        chapters = self.bookmark_manager.list_bookmarks(bookmark_type="chapter")
        
        # Get user bookmarks
        user_bookmarks = self.bookmark_manager.list_bookmarks(bookmark_type="user")
        
        # Get labeled scenes
        labeled_scenes = get_labeled_scenes(self.story_id)
        
        # Get recent scenes (last 10)
        recent_scenes = execute_query(self.story_id, '''
            SELECT scene_id, timestamp, scene_label, input
            FROM scenes ORDER BY timestamp DESC LIMIT 10
        ''')
        
        return {
            'story_id': self.story_id,
            'chapters': chapters,
            'user_bookmarks': user_bookmarks,
            'labeled_scenes': labeled_scenes,
            'recent_scenes': [{
                'scene_id': row[0],
                'timestamp': row[1],
                'scene_label': row[2],
                'input': row[3]
            } for row in recent_scenes]
        }
    
    def export_timeline_json(self, include_content: bool = True) -> str:
        """Export timeline as JSON string."""
        if include_content:
            timeline = self.get_full_timeline()
        else:
            # Minimal export without scene content
            timeline = self.get_chapter_timeline()
        
        return json.dumps(timeline, indent=2, ensure_ascii=False)
    
    def export_timeline_markdown(self) -> str:
        """Export timeline as Markdown."""
        timeline = self.get_full_timeline()
        
        md_lines = [
            f"# Story Timeline: {self.story_id}",
            f"",
            f"**Total Scenes:** {timeline['total_scenes']}",
            f"**Total Bookmarks:** {timeline['total_bookmarks']}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"---",
            f""
        ]
        
        for i, entry in enumerate(timeline['timeline'], 1):
            # Scene header
            scene_label = entry['scene_label'] or f"Scene {i}"
            md_lines.append(f"## {scene_label}")
            md_lines.append(f"**Scene ID:** `{entry['scene_id']}`")
            md_lines.append(f"**Timestamp:** {entry['timestamp']}")
            
            # Bookmarks
            if entry['bookmarks']:
                md_lines.append(f"**Bookmarks:**")
                for bookmark in entry['bookmarks']:
                    md_lines.append(f"- {bookmark['label']} ({bookmark['bookmark_type']})")
            
            # Scene content
            md_lines.append(f"")
            md_lines.append(f"**Input:** {entry['input']}")
            md_lines.append(f"")
            md_lines.append(f"**Output:**")
            md_lines.append(f"```")
            md_lines.append(entry['output'])
            md_lines.append(f"```")
            
            # Flags if any
            if entry['flags']:
                md_lines.append(f"**Flags:** {', '.join(entry['flags'])}")
            
            md_lines.append(f"")
            md_lines.append(f"---")
            md_lines.append(f"")
        
        return "\n".join(md_lines)
    
    def get_scene_context(self, scene_id: str, context_window: int = 2) -> Dict[str, Any]:
        """Get scene with surrounding context for navigation."""
        # Get all scenes in chronological order
        scenes = execute_query(self.story_id, '''
            SELECT scene_id, timestamp, input, output, scene_label
            FROM scenes ORDER BY timestamp ASC
        ''')
        
        # Find target scene index
        target_index = None
        for i, scene in enumerate(scenes):
            if scene[0] == scene_id:
                target_index = i
                break
        
        if target_index is None:
            return {'error': f'Scene {scene_id} not found'}
        
        # Get context window
        start_idx = max(0, target_index - context_window)
        end_idx = min(len(scenes), target_index + context_window + 1)
        
        context_scenes = []
        for i in range(start_idx, end_idx):
            scene = scenes[i]
            context_scenes.append({
                'scene_id': scene[0],
                'timestamp': scene[1],
                'input': scene[2],
                'output': scene[3],
                'scene_label': scene[4],
                'is_target': i == target_index,
                'position': i - target_index  # Relative position
            })
        
        return {
            'story_id': self.story_id,
            'target_scene_id': scene_id,
            'context_window': context_window,
            'scenes': context_scenes,
            'total_scenes': len(scenes),
            'target_position': target_index
        }
    
    def _get_scenes_in_chapter(self, chapter: Dict[str, Any], next_chapter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get scenes between chapter markers."""
        # Get scene info for chapter start
        chapter_scene = execute_query(self.story_id, '''
            SELECT timestamp FROM scenes WHERE scene_id = ?
        ''', (chapter['scene_id'],))
        
        if not chapter_scene:
            return []
        
        start_timestamp = chapter_scene[0][0]
        
        # Determine end timestamp
        if next_chapter:
            next_scene = execute_query(self.story_id, '''
                SELECT timestamp FROM scenes WHERE scene_id = ?
            ''', (next_chapter['scene_id'],))
            end_timestamp = next_scene[0][0] if next_scene else None
        else:
            end_timestamp = None
        
        # Get scenes in range
        if end_timestamp:
            scenes = execute_query(self.story_id, '''
                SELECT scene_id, timestamp, input, output, scene_label
                FROM scenes 
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp ASC
            ''', (start_timestamp, end_timestamp))
        else:
            scenes = execute_query(self.story_id, '''
                SELECT scene_id, timestamp, input, output, scene_label
                FROM scenes 
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            ''', (start_timestamp,))
        
        return [{
            'scene_id': scene[0],
            'timestamp': scene[1],
            'input': scene[2],
            'output': scene[3],
            'scene_label': scene[4]
        } for scene in scenes]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get timeline statistics."""
        # Scene stats
        scene_stats = execute_query(self.story_id, '''
            SELECT 
                COUNT(*) as total_scenes,
                COUNT(scene_label) as labeled_scenes,
                MIN(timestamp) as first_scene,
                MAX(timestamp) as last_scene
            FROM scenes
        ''')[0]
        
        # Bookmark stats
        bookmark_stats = self.bookmark_manager.get_stats()
        
        return {
            'story_id': self.story_id,
            'scenes': {
                'total': scene_stats[0],
                'labeled': scene_stats[1],
                'unlabeled': scene_stats[0] - scene_stats[1],
                'first_timestamp': scene_stats[2],
                'last_timestamp': scene_stats[3]
            },
            'bookmarks': bookmark_stats,
            'timeline_coverage': {
                'has_chapters': bookmark_stats['by_type'].get('chapter', 0) > 0,
                'has_user_bookmarks': bookmark_stats['by_type'].get('user', 0) > 0,
                'labeling_percentage': (scene_stats[1] / scene_stats[0] * 100) if scene_stats[0] > 0 else 0
            }
        }

    def track_tone_consistency_audit(self) -> Dict[str, Any]:
        """
        Track per-turn tone tags for LLM consistency audit.
        
        Returns:
            Tone consistency analysis with flagged inconsistencies
        """
        try:
            log_info(f"Starting tone consistency audit for story: {self.story_id}")
            
            # Get scenes with structured tags
            scenes = execute_query(self.story_id, '''
                SELECT scene_id, timestamp, structured_tags, input, output
                FROM scenes 
                WHERE structured_tags IS NOT NULL 
                ORDER BY timestamp ASC
            ''')
            
            tone_timeline = []
            tone_inconsistencies = []
            tone_transitions = {}
            character_tone_profiles = {}
            
            previous_mood = None
            previous_scene_type = None
            
            for scene in scenes:
                try:
                    structured_tags = json.loads(scene[2] or '{}')
                    scene_id = scene[0]
                    timestamp = scene[1]
                    
                    current_mood = structured_tags.get('mood', 'neutral')
                    scene_type = structured_tags.get('scene_type', 'dialogue')
                    character_moods = structured_tags.get('character_moods', {})
                    
                    # Track tone timeline
                    tone_entry = {
                        'scene_id': scene_id,
                        'timestamp': timestamp,
                        'mood': current_mood,
                        'scene_type': scene_type,
                        'character_moods': character_moods
                    }
                    tone_timeline.append(tone_entry)
                    
                    # Check for tone inconsistencies
                    if previous_mood and previous_mood != current_mood:
                        # Check if transition is too abrupt
                        mood_severity = {
                            'joyful': 3, 'excited': 3, 'happy': 2,
                            'neutral': 1, 'calm': 1,
                            'sad': -2, 'angry': -3, 'terrified': -3, 'depressed': -3
                        }
                        
                        prev_score = mood_severity.get(previous_mood, 0)
                        curr_score = mood_severity.get(current_mood, 0)
                        transition_gap = abs(curr_score - prev_score)
                        
                        if transition_gap >= 4:  # Large mood swing
                            inconsistency = {
                                'scene_id': scene_id,
                                'type': 'abrupt_mood_change',
                                'from_mood': previous_mood,
                                'to_mood': current_mood,
                                'severity': transition_gap,
                                'timestamp': timestamp
                            }
                            tone_inconsistencies.append(inconsistency)
                            log_warning(f"Abrupt mood change detected in scene {scene_id}: {previous_mood} -> {current_mood}")
                    
                    # Track tone transitions
                    if previous_mood:
                        transition_key = f"{previous_mood}->{current_mood}"
                        tone_transitions[transition_key] = tone_transitions.get(transition_key, 0) + 1
                    
                    # Track character tone profiles
                    for char_name, char_mood_data in character_moods.items():
                        if char_name not in character_tone_profiles:
                            character_tone_profiles[char_name] = {
                                'moods': [],
                                'stability_scores': [],
                                'scene_count': 0
                            }
                        
                        character_tone_profiles[char_name]['moods'].append(char_mood_data.get('mood', 'neutral'))
                        character_tone_profiles[char_name]['stability_scores'].append(char_mood_data.get('stability', 1.0))
                        character_tone_profiles[char_name]['scene_count'] += 1
                    
                    previous_mood = current_mood
                    previous_scene_type = scene_type
                    
                except json.JSONDecodeError:
                    continue
            
            # Analyze character consistency
            character_consistency = {}
            for char_name, profile in character_tone_profiles.items():
                moods = profile['moods']
                stability_scores = profile['stability_scores']
                
                # Calculate mood diversity (how many different moods)
                unique_moods = len(set(moods))
                total_scenes = len(moods)
                mood_diversity = unique_moods / total_scenes if total_scenes > 0 else 0
                
                # Calculate average stability
                avg_stability = sum(stability_scores) / len(stability_scores) if stability_scores else 1.0
                
                character_consistency[char_name] = {
                    'total_scenes': total_scenes,
                    'unique_moods': unique_moods,
                    'mood_diversity': mood_diversity,
                    'average_stability': avg_stability,
                    'most_common_mood': max(set(moods), key=moods.count) if moods else 'neutral',
                    'consistency_score': avg_stability * (1 - min(mood_diversity, 0.8))  # Penalize too much diversity
                }
            
            audit_result = {
                'story_id': self.story_id,
                'audit_timestamp': datetime.now(UTC).isoformat(),
                'tone_timeline': tone_timeline,
                'inconsistencies': tone_inconsistencies,
                'tone_transitions': tone_transitions,
                'character_consistency': character_consistency,
                'summary': {
                    'total_scenes_analyzed': len(tone_timeline),
                    'inconsistencies_found': len(tone_inconsistencies),
                    'characters_tracked': len(character_tone_profiles),
                    'most_common_mood': max(tone_transitions.keys(), key=lambda k: tone_transitions[k]) if tone_transitions else 'neutral'
                }
            }
            
            log_info(f"Tone consistency audit completed: {len(tone_inconsistencies)} inconsistencies found")
            return audit_result
            
        except Exception as e:
            log_error(f"Error during tone consistency audit: {e}")
            return {
                'story_id': self.story_id,
                'error': str(e),
                'audit_timestamp': datetime.now(UTC).isoformat()
            }
    
    def generate_auto_summary(self, scene_range: Optional[Tuple[int, int]] = None, 
                              summary_type: str = "narrative") -> Dict[str, Any]:
        """
        Generate auto-summaries for long-term memory compaction.
        
        Args:
            scene_range: Tuple of (start_index, end_index) for scene range, None for all
            summary_type: Type of summary ("narrative", "character_focused", "event_focused")
        
        Returns:
            Generated summary with metadata
        """
        try:
            log_info(f"Generating auto-summary for story: {self.story_id}, type: {summary_type}")
            
            # Get scenes in range
            if scene_range:
                scenes = execute_query(self.story_id, '''
                    SELECT scene_id, timestamp, input, output, structured_tags, scene_label
                    FROM scenes 
                    ORDER BY timestamp ASC
                    LIMIT ? OFFSET ?
                ''', (scene_range[1] - scene_range[0], scene_range[0]))
            else:
                scenes = execute_query(self.story_id, '''
                    SELECT scene_id, timestamp, input, output, structured_tags, scene_label
                    FROM scenes 
                    ORDER BY timestamp ASC
                ''')
            
            if not scenes:
                return {
                    'story_id': self.story_id,
                    'summary': "No scenes available for summarization.",
                    'metadata': {'scene_count': 0}
                }
            
            # Analyze scenes for summary generation
            key_events = []
            character_developments = {}
            mood_progression = []
            important_scenes = []
            
            for scene in scenes:
                scene_id, timestamp, user_input, output, structured_tags_raw, scene_label = scene
                
                try:
                    structured_tags = json.loads(structured_tags_raw or '{}')
                except json.JSONDecodeError:
                    structured_tags = {}
                
                # Extract key information
                scene_mood = structured_tags.get('mood', 'neutral')
                scene_type = structured_tags.get('scene_type', 'dialogue')
                character_moods = structured_tags.get('character_moods', {})
                
                # Track mood progression
                mood_progression.append({
                    'scene_id': scene_id,
                    'mood': scene_mood,
                    'timestamp': timestamp
                })
                
                # Identify important scenes (labeled, long turns, mood changes)
                is_important = (
                    scene_label is not None or
                    structured_tags.get('token_usage', {}).get('is_long_turn', False) or
                    scene_mood not in ['neutral', 'calm']
                )
                
                if is_important:
                    important_scenes.append({
                        'scene_id': scene_id,
                        'timestamp': timestamp,
                        'label': scene_label,
                        'mood': scene_mood,
                        'type': scene_type,
                        'input_preview': user_input[:100] + "..." if len(user_input) > 100 else user_input,
                        'output_preview': output[:200] + "..." if len(output) > 200 else output
                    })
                
                # Track character developments
                for char_name, char_mood_data in character_moods.items():
                    if char_name not in character_developments:
                        character_developments[char_name] = {
                            'mood_changes': [],
                            'key_scenes': [],
                            'stability_trend': []
                        }
                    
                    character_developments[char_name]['mood_changes'].append({
                        'scene_id': scene_id,
                        'mood': char_mood_data.get('mood', 'neutral'),
                        'stability': char_mood_data.get('stability', 1.0),
                        'timestamp': timestamp
                    })
                    
                    # Track scenes where character had significant mood changes
                    if char_mood_data.get('stability', 1.0) < 0.7:
                        character_developments[char_name]['key_scenes'].append(scene_id)
                
                # Extract potential key events from user input
                if any(keyword in user_input.lower() for keyword in 
                       ['fight', 'battle', 'kiss', 'death', 'leave', 'arrive', 'discover', 'reveal']):
                    key_events.append({
                        'scene_id': scene_id,
                        'event_type': 'action',
                        'description': user_input[:150] + "..." if len(user_input) > 150 else user_input,
                        'timestamp': timestamp
                    })
            
            # Generate summary based on type
            if summary_type == "narrative":
                summary_text = self._generate_narrative_summary(scenes, important_scenes, mood_progression)
            elif summary_type == "character_focused":
                summary_text = self._generate_character_summary(character_developments, important_scenes)
            elif summary_type == "event_focused":
                summary_text = self._generate_event_summary(key_events, important_scenes)
            else:
                summary_text = self._generate_narrative_summary(scenes, important_scenes, mood_progression)
            
            summary_result = {
                'story_id': self.story_id,
                'summary_type': summary_type,
                'summary': summary_text,
                'generated_at': datetime.now(UTC).isoformat(),
                'metadata': {
                    'scene_count': len(scenes),
                    'important_scenes_count': len(important_scenes),
                    'characters_tracked': len(character_developments),
                    'key_events_count': len(key_events),
                    'scene_range': scene_range,
                    'mood_diversity': len(set(entry['mood'] for entry in mood_progression)),
                    'timeline_span': {
                        'start': scenes[0][1] if scenes else None,
                        'end': scenes[-1][1] if scenes else None
                    }
                },
                'detailed_analysis': {
                    'important_scenes': important_scenes,
                    'character_developments': character_developments,
                    'key_events': key_events,
                    'mood_progression': mood_progression
                }
            }
            
            log_info(f"Auto-summary generated: {len(summary_text)} characters, {len(important_scenes)} key scenes")
            return summary_result
            
        except Exception as e:
            log_error(f"Error generating auto-summary: {e}")
            return {
                'story_id': self.story_id,
                'error': str(e),
                'generated_at': datetime.now(UTC).isoformat()
            }
    
    def _generate_narrative_summary(self, scenes: List, important_scenes: List, mood_progression: List) -> str:
        """Generate a narrative-style summary."""
        if not scenes:
            return "No scenes to summarize."
        
        summary_parts = []
        
        # Opening
        summary_parts.append(f"Story progression across {len(scenes)} scenes:")
        
        # Key developments
        if important_scenes:
            summary_parts.append(f"\nKey developments occurred in {len(important_scenes)} significant scenes:")
            for scene in important_scenes[:5]:  # Top 5 important scenes
                scene_desc = f"Scene {scene['scene_id'][:8]}..."
                if scene['label']:
                    scene_desc += f" ({scene['label']})"
                scene_desc += f": {scene['input_preview']}"
                summary_parts.append(f"• {scene_desc}")
        
        # Mood progression
        if mood_progression:
            mood_changes = [entry['mood'] for entry in mood_progression]
            unique_moods = list(set(mood_changes))
            if len(unique_moods) > 1:
                summary_parts.append(f"\nMood progression: {' → '.join(unique_moods[:5])}")
        
        return "\n".join(summary_parts)
    
    def _generate_character_summary(self, character_developments: Dict, important_scenes: List) -> str:
        """Generate a character-focused summary."""
        if not character_developments:
            return "No character developments to summarize."
        
        summary_parts = []
        summary_parts.append(f"Character developments for {len(character_developments)} characters:")
        
        for char_name, development in character_developments.items():
            char_summary = f"\n{char_name}:"
            
            moods = [change['mood'] for change in development['mood_changes']]
            if moods:
                most_common_mood = max(set(moods), key=moods.count)
                char_summary += f" Primary mood: {most_common_mood}"
                
                if len(development['key_scenes']) > 0:
                    char_summary += f", {len(development['key_scenes'])} significant moments"
            
            summary_parts.append(char_summary)
        
        return "\n".join(summary_parts)
    
    def _generate_event_summary(self, key_events: List, important_scenes: List) -> str:
        """Generate an event-focused summary."""
        if not key_events and not important_scenes:
            return "No significant events to summarize."
        
        summary_parts = []
        summary_parts.append(f"Key events summary:")
        
        # Combine events and important scenes
        all_events = key_events + [
            {
                'scene_id': scene['scene_id'],
                'event_type': 'important',
                'description': scene['input_preview'],
                'timestamp': scene['timestamp']
            }
            for scene in important_scenes
        ]
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x['timestamp'])
        
        for i, event in enumerate(all_events[:10], 1):  # Top 10 events
            summary_parts.append(f"{i}. {event['description']}")
        
        return "\n".join(summary_parts)
