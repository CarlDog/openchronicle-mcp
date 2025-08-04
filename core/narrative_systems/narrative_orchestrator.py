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
    
    def get_narrative_state(self, story_id: str) -> Optional[NarrativeState]:
        """Get current narrative state for a story."""
        return self.narrative_states.get(story_id)
    
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
