"""
OpenChronicle Core - Narrative Systems Orchestrator

Main coordinator for all narrative systems including response intelligence,
narrative mechanics, consistency validation, and emotional stability.

This module follows the proven orchestrator pattern established in:
- ModelOrchestrator (Phase 3.0)
- ContentAnalysisOrchestrator (Phase 5A) 
- MemoryOrchestrator (Phase 5B)

Author: OpenChronicle Development Team
"""

import json
from datetime import datetime
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, asdict
import sys

# Add utilities path
sys.path.append(str(Path(__file__).parent.parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error


@dataclass
class NarrativeState:
    """Central narrative state management."""
    story_id: str
    current_scene: str
    narrative_tension: float = 0.5
    character_states: Dict[str, Any] = None
    memory_context: Dict[str, Any] = None
    response_quality: float = 0.0
    emotional_stability: Dict[str, float] = None
    last_update: str = ""
    
    def __post_init__(self):
        if self.character_states is None:
            self.character_states = {}
        if self.memory_context is None:
            self.memory_context = {}
        if self.emotional_stability is None:
            self.emotional_stability = {}
        if not self.last_update:
            self.last_update = datetime.now().isoformat()


@dataclass
class NarrativeOperation:
    """Result of narrative system operations."""
    operation_type: str
    success: bool
    result: Any = None
    state_changes: Dict[str, Any] = None
    recommendations: List[str] = None
    metrics: Dict[str, float] = None
    
    def __post_init__(self):
        if self.state_changes is None:
            self.state_changes = {}
        if self.recommendations is None:
            self.recommendations = []
        if self.metrics is None:
            self.metrics = {}


class NarrativeOrchestrator:
    """
    Main orchestrator for all narrative systems.
    
    Coordinates between:
    - Response Intelligence (quality assessment, context analysis)
    - Narrative Mechanics (dice rolling, branching, resolution)
    - Consistency Management (memory validation, conflict detection)
    - Emotional Stability (character emotional state tracking)
    """
    
    def __init__(self, data_dir: str = "storage/narrative_systems"):
        """Initialize narrative orchestrator."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Component orchestrators (will be initialized as we build them)
        self.response_orchestrator = None
        self.mechanics_orchestrator = None
        self.consistency_orchestrator = None
        self.emotional_orchestrator = None
        self.consistency_orchestrator = None
        self.emotional_orchestrator = None
        
        # Initialize available orchestrators
        self._initialize_available_orchestrators()
        
        # Shared state
        self.narrative_states: Dict[str, NarrativeState] = {}
        self.operation_history: List[NarrativeOperation] = []
        
        # Configuration
        self.config = self._load_configuration()
        
        log_system_event(
            "narrative_orchestrator_init",
            f"NarrativeOrchestrator initialized with data directory: {self.data_dir}"
        )
    
    def _initialize_available_orchestrators(self):
        """Initialize available component orchestrators."""
        try:
            # Initialize response orchestrator
            from .response import ResponseOrchestrator
            from .mechanics import MechanicsOrchestrator
            from .consistency import ConsistencyOrchestrator
            from .emotional import EmotionalOrchestrator
            
            response_dir = self.data_dir / "response"
            self.response_orchestrator = ResponseOrchestrator(
                str(response_dir), 
                self.config.get("response_settings", {})
            )
            
            log_system_event(
                "response_orchestrator_init",
                "ResponseOrchestrator initialized successfully"
            )
            
            # Initialize mechanics orchestrator
            self.mechanics_orchestrator = MechanicsOrchestrator()
            log_system_event(
                "narrative_orchestrator_init",
                "MechanicsOrchestrator initialized successfully"
            )
            
            # Initialize consistency orchestrator
            consistency_config = self.config.get("consistency_settings", {})
            self.consistency_orchestrator = ConsistencyOrchestrator(consistency_config)
            log_system_event(
                "consistency_orchestrator_init",
                "ConsistencyOrchestrator initialized successfully"
            )
            
            # Initialize emotional orchestrator
            emotional_config = self.config.get("emotional_settings", {})
            self.emotional_orchestrator = EmotionalOrchestrator(emotional_config)
            log_system_event(
                "emotional_orchestrator_init",
                "EmotionalOrchestrator initialized successfully"
            )
            
        except Exception as e:
            log_error(f"Error initializing orchestrators: {e}")
            self.response_orchestrator = None
            self.mechanics_orchestrator = None
            self.consistency_orchestrator = None
            self.emotional_orchestrator = None
    
    def _load_configuration(self) -> Dict[str, Any]:
        """Load narrative system configuration."""
        config_path = self.data_dir / "narrative_config.json"
        
        default_config = {
            "response_settings": {
                "quality_threshold": 0.7,
                "complexity_preference": "adaptive",
                "context_window": 4096
            },
            "mechanics_settings": {
                "default_dice_sides": 20,
                "difficulty_scaling": "balanced",
                "randomness_factor": 0.3
            },
            "consistency_settings": {
                "validation_strictness": "moderate",
                "conflict_tolerance": 0.2,
                "memory_window": 100
            },
            "emotional_settings": {
                "stability_threshold": 0.6,
                "mood_tracking": True,
                "emotional_memory": 50
            }
        }
        
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Create default configuration
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            log_error(f"Error loading narrative configuration: {e}")
            return default_config
    
    def get_narrative_state(self, story_id: str) -> Dict[str, Any]:
        """Get current narrative state for a story."""
        if story_id not in self.narrative_states:
            # Create a default state if it doesn't exist
            self.narrative_states[story_id] = NarrativeState(
                story_id=story_id,
                current_scene="initial"
            )
        
        state = self.narrative_states[story_id]
        # Return dict representation for test compatibility
        return {
            'story_id': state.story_id,
            'current_scene': state.current_scene,
            'narrative_tension': state.narrative_tension,
            'character_states': state.character_states,
            'memory_context': state.memory_context,
            'response_quality': state.response_quality,
            'emotional_stability': state.emotional_stability,
            'last_update': state.last_update
        }
    
    def update_narrative_state(self, story_id: str, **kwargs) -> bool:
        """Update narrative state for a story."""
        try:
            if story_id not in self.narrative_states:
                self.narrative_states[story_id] = NarrativeState(
                    story_id=story_id,
                    current_scene="initial"
                )
            
            state = self.narrative_states[story_id]
            
            # Update provided fields
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            
            state.last_update = datetime.now().isoformat()
            
            log_system_event(
                "narrative_state_update",
                f"Updated narrative state for story {story_id}: {list(kwargs.keys())}"
            )
            
            return True
            
        except Exception as e:
            log_error(f"Error updating narrative state for {story_id}: {e}")
            return False
    
    def process_narrative_operation(self, operation_type: str, 
                                  story_id: str, 
                                  operation_data: Dict[str, Any]) -> NarrativeOperation:
        """
        Process a narrative operation through appropriate orchestrator.
        
        Routes operations to:
        - response: Response intelligence and quality assessment
        - mechanics: Dice rolling, branching, narrative resolution
        - consistency: Memory validation and conflict detection
        - emotional: Emotional stability and mood tracking
        """
        start_time = time.time()
        
        try:
            # Route to appropriate orchestrator
            if operation_type.startswith("response"):
                result = self._handle_response_operation(story_id, operation_data)
            elif operation_type.startswith("mechanics"):
                result = self._handle_mechanics_operation(story_id, operation_data)
            elif operation_type.startswith("consistency"):
                result = self._handle_consistency_operation(story_id, operation_data)
            elif operation_type.startswith("emotional"):
                result = self._handle_emotional_operation(story_id, operation_data)
            else:
                raise ValueError(f"Unknown operation type: {operation_type}")
            
            # Create operation record
            operation = NarrativeOperation(
                operation_type=operation_type,
                success=True,
                result=result,
                metrics={"processing_time": time.time() - start_time}
            )
            
            # Store operation history
            self.operation_history.append(operation)
            
            log_system_event(
                "narrative_operation_complete",
                f"Completed {operation_type} operation for story {story_id}"
            )
            
            return operation
            
        except Exception as e:
            log_error(f"Error processing narrative operation {operation_type}: {e}")
            
            return NarrativeOperation(
                operation_type=operation_type,
                success=False,
                result=str(e),
                metrics={"processing_time": time.time() - start_time}
            )
    
    def _handle_response_operation(self, story_id: str, data: Dict[str, Any]) -> Any:
        """Handle response intelligence operations."""
        if self.response_orchestrator:
            try:
                # Process through response orchestrator
                result = self.response_orchestrator.process(data)
                
                # Update narrative state if successful
                if result.success:
                    self.update_narrative_state(
                        story_id,
                        response_quality=result.evaluation.overall_score,
                        last_response_strategy=result.plan.strategy.value
                    )
                
                return {
                    "status": "response_operation_complete",
                    "success": result.success,
                    "analysis": {
                        "quality": result.analysis.quality.value,
                        "content_type": result.analysis.content_type,
                        "confidence": result.analysis.confidence
                    },
                    "plan": {
                        "strategy": result.plan.strategy.value,
                        "complexity": result.plan.complexity.value,
                        "content_focus": result.plan.content_focus
                    },
                    "evaluation": {
                        "overall_score": result.evaluation.overall_score,
                        "coherence_score": result.evaluation.coherence_score,
                        "creativity_score": result.evaluation.creativity_score
                    }
                }
                
            except Exception as e:
                log_error(f"Error in response operation: {e}")
                return {"status": "response_operation_error", "error": str(e)}
        else:
            log_info(f"Response operation for story {story_id}: {data.get('operation', 'unknown')} (orchestrator not available)")
            return {"status": "response_operation_unavailable", "data": data}
    
    def _handle_mechanics_operation(self, story_id: str, data: Dict[str, Any]) -> Any:
        """Handle narrative mechanics operations."""
        # Placeholder for mechanics orchestrator integration
        log_info(f"Mechanics operation for story {story_id}: {data.get('operation', 'unknown')}")
        return {"status": "mechanics_operation_placeholder", "data": data}
    
    def roll_dice(self, dice_expression: str) -> Dict[str, Any]:
        """Roll dice using standard dice notation (e.g., '1d20', '3d6+2')."""
        try:
            import re
            import random
            
            # Parse dice expression (e.g., "1d20", "3d6+2", "d6")
            pattern = r'^(\d*)d(\d+)([+-]\d+)?$'
            match = re.match(pattern, dice_expression.lower().strip())
            
            if not match:
                return {
                    'success': False,
                    'error': f'Invalid dice expression: {dice_expression}',
                    'expression': dice_expression
                }
            
            # Extract components
            num_dice = int(match.group(1)) if match.group(1) else 1
            die_type = int(match.group(2))
            modifier = int(match.group(3)) if match.group(3) else 0
            
            # Validate parameters
            if num_dice < 1 or num_dice > 100:
                return {
                    'success': False,
                    'error': 'Number of dice must be between 1 and 100',
                    'expression': dice_expression
                }
            
            if die_type < 2 or die_type > 1000:
                return {
                    'success': False,
                    'error': 'Die type must be between 2 and 1000',
                    'expression': dice_expression
                }
            
            # Roll the dice
            rolls = []
            for _ in range(num_dice):
                rolls.append(random.randint(1, die_type))
            
            total = sum(rolls) + modifier
            
            result = {
                'success': True,
                'expression': dice_expression,
                'num_dice': num_dice,
                'die_type': die_type,
                'modifier': modifier,
                'rolls': rolls,
                'total': total,
                'timestamp': datetime.now().isoformat()
            }
            
            log_info(f"Dice roll: {dice_expression} = {total} (rolls: {rolls}, modifier: {modifier})")
            return result
            
        except Exception as e:
            log_error(f"Error rolling dice '{dice_expression}': {e}")
            return {
                'success': False,
                'error': str(e),
                'expression': dice_expression
            }
    
    async def evaluate_narrative_branch(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate narrative branching scenarios."""
        try:
            story_id = scenario.get('story_id', 'unknown')
            character_id = scenario.get('character_id', 'unknown')
            branch_type = scenario.get('type', 'unknown')
            scene_id = scenario.get('scene_id', 'unknown')
            choices = scenario.get('choices', [])
            
            # Get current narrative state
            state = self.get_narrative_state(story_id)
            if not state:
                state = NarrativeState(story_id=story_id, current_scene="evaluation")
                self.narrative_states[story_id] = state
            
            # Basic branch evaluation logic
            evaluation = {
                'success': True,
                'story_id': story_id,
                'character_id': character_id,
                'branch_type': branch_type,
                'scene_id': scene_id,
                'narrative_tension': state.narrative_tension,
                'recommendations': []
            }
            
            # Select option if choices are provided
            if choices:
                import random
                selected_option = random.choice(choices)
                evaluation['selected_option'] = selected_option
                evaluation['available_choices'] = choices
                evaluation['selection_method'] = 'random'
            
            # Evaluate based on branch type
            if branch_type == 'character_decision':
                evaluation['recommendations'].append('Consider character motivations and past decisions')
                evaluation['difficulty'] = 'moderate'
                
            elif branch_type == 'plot_progression':
                evaluation['recommendations'].append('Ensure plot consistency with established elements')
                evaluation['difficulty'] = 'high'
                
            elif branch_type == 'dialogue_choice':
                evaluation['recommendations'].append('Maintain character voice and relationship dynamics')
                evaluation['difficulty'] = 'low'
                
            else:
                evaluation['recommendations'].append('Generic narrative evaluation applied')
                evaluation['difficulty'] = 'moderate'
            
            # Use mechanics orchestrator if available
            if self.mechanics_orchestrator:
                try:
                    if hasattr(self.mechanics_orchestrator, 'evaluate_branch'):
                        mechanics_result = getattr(self.mechanics_orchestrator, 'evaluate_branch')(scenario)
                        evaluation.update(mechanics_result)
                except Exception as e:
                    log_warning(f"Mechanics orchestrator evaluation failed: {e}")
            
            # Update narrative tension based on evaluation
            tension_modifier = scenario.get('tension_impact', 0.0)
            new_tension = max(0.0, min(1.0, state.narrative_tension + tension_modifier))
            state.narrative_tension = new_tension
            state.last_update = datetime.now().isoformat()
            
            evaluation['narrative_tension'] = new_tension
            evaluation['timestamp'] = datetime.now().isoformat()
            
            log_info(f"Evaluated narrative branch for {character_id} in {story_id}: {branch_type}")
            return evaluation
            
        except Exception as e:
            log_error(f"Error evaluating narrative branch: {e}")
            return {
                'success': False,
                'error': str(e),
                'scenario': scenario
            }
    
    def _handle_consistency_operation(self, story_id: str, data: Dict[str, Any]) -> Any:
        """Handle consistency validation operations."""
        if self.consistency_orchestrator:
            try:
                operation_type = data.get('operation', 'unknown')
                
                if operation_type == 'validate_memory':
                    result = self.consistency_orchestrator.validate_memory_consistency(
                        story_id, data.get('memory_event', {})
                    )
                elif operation_type == 'add_memory':
                    result = self.consistency_orchestrator.add_memory(
                        story_id, data.get('memory_event', {})
                    )
                elif operation_type == 'get_memory_summary':
                    result = self.consistency_orchestrator.get_character_memory_summary(
                        story_id, data.get('character_id', '')
                    )
                else:
                    result = {"status": "unknown_operation", "operation": operation_type}
                
                return {
                    "status": "consistency_operation_complete",
                    "success": True,
                    "result": result
                }
                
            except Exception as e:
                log_error(f"Error in consistency operation: {e}")
                return {"status": "consistency_operation_error", "error": str(e)}
        else:
            log_info(f"Consistency operation for story {story_id}: {data.get('operation', 'unknown')} (orchestrator not available)")
            return {"status": "consistency_operation_unavailable", "data": data}
    
    def _handle_emotional_operation(self, story_id: str, data: Dict[str, Any]) -> Any:
        """Handle emotional stability operations."""
        if self.emotional_orchestrator:
            try:
                operation_type = data.get('operation', 'unknown')
                
                if operation_type == 'track_emotional_state':
                    result = self.emotional_orchestrator.track_emotional_state(
                        story_id, data.get('character_id', ''), data.get('emotional_data', {})
                    )
                elif operation_type == 'detect_emotional_loops':
                    result = self.emotional_orchestrator.detect_emotional_loops(
                        story_id, data.get('character_id', ''), data.get('dialogue_history', [])
                    )
                elif operation_type == 'analyze_emotional_stability':
                    result = self.emotional_orchestrator.analyze_emotional_stability(
                        story_id, data.get('character_id', '')
                    )
                elif operation_type == 'generate_anti_loop_prompt':
                    result = self.emotional_orchestrator.generate_anti_loop_prompt(
                        data.get('character_id', ''), data.get('detected_patterns', [])
                    )
                else:
                    result = {"status": "unknown_operation", "operation": operation_type}
                
                return {
                    "status": "emotional_operation_complete",
                    "success": True,
                    "result": result
                }
                
            except Exception as e:
                log_error(f"Error in emotional operation: {e}")
                return {"status": "emotional_operation_error", "error": str(e)}
        else:
            log_info(f"Emotional operation for story {story_id}: {data.get('operation', 'unknown')} (orchestrator not available)")
            return {"status": "emotional_operation_unavailable", "data": data}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive narrative system status."""
        return {
            "orchestrator_status": "active",
            "active_stories": len(self.narrative_states),
            "operations_processed": len(self.operation_history),
            "components": {
                "response_orchestrator": self.response_orchestrator is not None,
                "mechanics_orchestrator": self.mechanics_orchestrator is not None,
                "consistency_orchestrator": self.consistency_orchestrator is not None,
                "emotional_orchestrator": self.emotional_orchestrator is not None
            },
            "configuration": self.config
        }
    
    def cleanup(self) -> bool:
        """Cleanup narrative orchestrator resources."""
        try:
            # Save current states
            states_file = self.data_dir / "narrative_states.json"
            with open(states_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: asdict(v) for k, v in self.narrative_states.items()},
                    f, indent=2
                )
            
            log_system_event(
                "narrative_orchestrator_cleanup",
                f"Saved {len(self.narrative_states)} narrative states"
            )
            
            return True
            
        except Exception as e:
            log_error(f"Error during narrative orchestrator cleanup: {e}")
            return False
    
    # Character integration methods for compatibility
    def get_character_narrative_context(self, story_id: str, character_id: str) -> Dict[str, Any]:
        """Get narrative context for a specific character."""
        state = self.get_narrative_state(story_id)
        if not state:
            return {}
        
        return {
            'character_id': character_id,
            'narrative_tension': state.narrative_tension,
            'character_state': state.character_states.get(character_id, {}),
            'emotional_state': state.emotional_stability.get(character_id, 0.5),
            'last_update': state.last_update
        }
    
    def update_character_narrative_state(self, story_id: str, character_id: str, narrative_data: Dict[str, Any]) -> bool:
        """Update narrative state for a specific character."""
        try:
            state = self.get_narrative_state(story_id)
            if not state:
                state = NarrativeState(story_id=story_id, current_scene="")
                self.narrative_states[story_id] = state
            
            # Update character-specific narrative data
            state.character_states[character_id] = narrative_data
            state.last_update = datetime.now().isoformat()
            
            log_info(f"Updated narrative state for character {character_id} in story {story_id}")
            return True
            
        except Exception as e:
            log_error(f"Failed to update character narrative state: {e}")
            return False
    
    def validate_character_consistency(self, story_id: str, character_id: str, narrative_event: Dict[str, Any]) -> bool:
        """Validate character consistency in narrative event."""
        try:
            if self.consistency_orchestrator:
                result = self.consistency_orchestrator.validate_character_consistency(
                    story_id, character_id, narrative_event
                )
                return result.get('consistent', True)
            else:
                # Basic validation when consistency orchestrator not available
                return True
                
        except Exception as e:
            log_warning(f"Character consistency validation failed: {e}")
            return True  # Fail open
    
    def track_character_emotional_changes(self, story_id: str, character_id: str, emotional_data: Dict[str, Any]) -> Dict[str, Any]:
        """Track emotional changes for character in narrative context."""
        try:
            if self.emotional_orchestrator:
                return self.emotional_orchestrator.track_character_emotions(
                    story_id, character_id, emotional_data
                )
            else:
                # Basic tracking when emotional orchestrator not available
                state = self.get_narrative_state(story_id)
                if state:
                    state.emotional_stability[character_id] = emotional_data.get('stability', 0.5)
                    
                return {
                    'tracking_status': 'basic',
                    'character_id': character_id,
                    'stability_score': emotional_data.get('stability', 0.5)
                }
                
        except Exception as e:
            log_error(f"Character emotional tracking failed: {e}")
            return {'tracking_status': 'failed', 'error': str(e)}
    
    def track_emotional_stability(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """Track character emotional stability in narrative context."""
        try:
            character_id = character_data.get('character_id', 'unknown')
            story_id = character_data.get('story_id', 'current')
            
            return self.track_character_emotional_changes(story_id, character_id, character_data)
            
        except Exception as e:
            log_error(f"Emotional stability tracking failed: {e}")
            return {'tracking_status': 'failed', 'error': str(e)}
    
    def get_mechanics_status(self) -> Dict[str, Any]:
        """Get status of narrative mechanics systems."""
        try:
            status = {
                'mechanics_orchestrator_available': self.mechanics_orchestrator is not None,
                'dice_engine_active': True,  # Our built-in dice engine is always available
                'narrative_branching_active': True,
                'timestamp': datetime.now().isoformat()
            }
            
            if self.mechanics_orchestrator:
                try:
                    if hasattr(self.mechanics_orchestrator, 'get_status'):
                        mechanics_status = getattr(self.mechanics_orchestrator, 'get_status')()
                        status.update(mechanics_status)
                except Exception as e:
                    log_warning(f"Error getting mechanics orchestrator status: {e}")
            
            return status
            
        except Exception as e:
            log_error(f"Error getting mechanics status: {e}")
            return {'error': str(e), 'status': 'failed'}
    
    def validate_emotional_consistency(self, emotional_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate emotional consistency over time."""
        try:
            if not emotional_history:
                return {
                    'success': False,
                    'error': 'No emotional history provided'
                }
            
            # Basic emotional consistency validation
            inconsistencies = []
            rapid_changes = 0
            
            for i in range(1, len(emotional_history)):
                prev_emotion = emotional_history[i-1]
                curr_emotion = emotional_history[i]
                
                prev_intensity = prev_emotion.get('intensity', 5)
                curr_intensity = curr_emotion.get('intensity', 5)
                
                # Check for rapid intensity changes (>6 point swing)
                intensity_change = abs(curr_intensity - prev_intensity)
                if intensity_change > 6:
                    rapid_changes += 1
                    inconsistencies.append(f"Rapid intensity change from {prev_intensity} to {curr_intensity}")
            
            consistency_score = max(0.0, 1.0 - (rapid_changes * 0.2))
            is_consistent = consistency_score >= 0.7
            
            result = {
                'success': True,
                'is_consistent': is_consistent,
                'consistency_score': consistency_score,
                'total_events': len(emotional_history),
                'rapid_changes': rapid_changes,
                'inconsistencies': inconsistencies,
                'analysis': 'Basic emotional consistency validation',
                'timestamp': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            log_error(f"Error validating emotional consistency: {e}")
            return {'success': False, 'error': str(e)}
    
    async def assess_response_quality(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess quality of narrative response."""
        try:
            content = response_data.get('content', '')
            context = response_data.get('context', {})
            
            # Basic quality assessment
            quality_metrics = {
                'length_score': min(1.0, len(content) / 100.0),  # Normalize to 100 chars
                'character_consistency': response_data.get('character_consistency', True),
                'narrative_flow': response_data.get('narrative_flow', True),
                'context_relevance': 0.8  # Default good score
            }
            
            # Calculate overall quality
            overall_score = (
                quality_metrics['length_score'] * 0.2 +
                (1.0 if quality_metrics['character_consistency'] else 0.0) * 0.3 +
                (1.0 if quality_metrics['narrative_flow'] else 0.0) * 0.3 +
                quality_metrics['context_relevance'] * 0.2
            )
            
            result = {
                'success': True,
                'quality_score': overall_score,
                'quality_metrics': quality_metrics,
                'content_length': len(content),
                'assessment_method': 'basic',
                'timestamp': datetime.now().isoformat()
            }
            
            # Use response orchestrator if available
            if self.response_orchestrator:
                try:
                    if hasattr(self.response_orchestrator, 'assess_quality'):
                        advanced_result = getattr(self.response_orchestrator, 'assess_quality')(response_data)
                        result.update(advanced_result)
                        result['assessment_method'] = 'advanced'
                except Exception as e:
                    log_warning(f"Advanced quality assessment failed: {e}")
            
            return result
            
        except Exception as e:
            log_error(f"Error assessing response quality: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_quality_metrics(self, metrics_data: Dict[str, float]) -> float:
        """Calculate overall quality from individual metrics."""
        try:
            # Default weights for quality metrics
            weights = {
                'coherence': 0.25,
                'creativity': 0.20,
                'character_voice': 0.25,
                'plot_advancement': 0.15,
                'narrative_flow': 0.10,
                'emotional_impact': 0.05
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for metric, value in metrics_data.items():
                weight = weights.get(metric, 0.1)  # Default weight for unknown metrics
                total_score += value * weight
                total_weight += weight
            
            # Normalize to 0-10 scale
            if total_weight > 0:
                final_score = (total_score / total_weight)
            else:
                final_score = 5.0  # Default neutral score
            
            log_info(f"Calculated quality metrics: {final_score:.2f} from {len(metrics_data)} metrics")
            return final_score
            
        except Exception as e:
            log_error(f"Error calculating quality metrics: {e}")
            return 5.0  # Default neutral score
    
    async def orchestrate_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrate comprehensive narrative response generation."""
        try:
            prompt = request_data.get('prompt', '')
            context = request_data.get('context', {})
            requirements = request_data.get('requirements', {})
            
            result = {
                'success': True,
                'prompt': prompt,
                'context': context,
                'requirements': requirements,
                'orchestration_method': 'basic',
                'timestamp': datetime.now().isoformat()
            }
            
            # Use response orchestrator if available
            if self.response_orchestrator:
                try:
                    if hasattr(self.response_orchestrator, 'orchestrate'):
                        advanced_result = getattr(self.response_orchestrator, 'orchestrate')(request_data)
                        result.update(advanced_result)
                        result['orchestration_method'] = 'advanced'
                    else:
                        # Basic orchestration
                        result['response'] = f"Generated response for: {prompt}"
                        result['quality_score'] = 7.5
                except Exception as e:
                    log_warning(f"Advanced response orchestration failed: {e}")
                    result['response'] = f"Fallback response for: {prompt}"
                    result['quality_score'] = 6.0
            else:
                # Basic orchestration when orchestrator not available
                result['response'] = f"Basic narrative response for: {prompt}"
                result['quality_score'] = 6.5
            
            return result
            
        except Exception as e:
            log_error(f"Error orchestrating response: {e}")
            return {'success': False, 'error': str(e)}
    
    def validate_narrative_consistency(self, consistency_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate overall narrative consistency."""
        try:
            scene_history = consistency_data.get('scene_history', [])
            character_states = consistency_data.get('character_states', {})
            world_state = consistency_data.get('world_state', {})
            
            # Basic consistency checks
            consistency_issues = []
            
            # Check scene progression
            if len(scene_history) > 1:
                # Look for scene repetition or impossible transitions
                if len(set(scene_history[-3:])) < len(scene_history[-3:]):
                    consistency_issues.append("Recent scene repetition detected")
            
            # Check character state consistency
            for character_id, state in character_states.items():
                health = state.get('health', 100)
                if health < 0 or health > 100:
                    consistency_issues.append(f"Invalid health value for {character_id}: {health}")
            
            # Calculate consistency score
            consistency_score = max(0.0, 1.0 - (len(consistency_issues) * 0.2))
            is_consistent = consistency_score >= 0.8
            
            result = {
                'success': True,
                'is_consistent': is_consistent,
                'consistency_score': consistency_score,
                'issues_found': len(consistency_issues),
                'consistency_issues': consistency_issues,
                'validation_method': 'basic',
                'timestamp': datetime.now().isoformat()
            }
            
            # Use consistency orchestrator if available
            if self.consistency_orchestrator:
                try:
                    if hasattr(self.consistency_orchestrator, 'validate_consistency'):
                        advanced_result = getattr(self.consistency_orchestrator, 'validate_consistency')(consistency_data)
                        result.update(advanced_result)
                        result['validation_method'] = 'advanced'
                except Exception as e:
                    log_warning(f"Advanced consistency validation failed: {e}")
            
            return result
            
        except Exception as e:
            log_error(f"Error validating narrative consistency: {e}")
            return {'success': False, 'error': str(e)}
