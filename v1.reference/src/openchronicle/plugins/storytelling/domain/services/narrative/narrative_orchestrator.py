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
from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event

from .core.narrative_character_integration import NarrativeCharacterIntegration
from .core.narrative_mechanics_handler import NarrativeMechanicsHandler
from .core.narrative_operation_router import NarrativeOperation
from .core.narrative_operation_router import NarrativeOperationRouter
from .core.narrative_state_manager import NarrativeStateManager


class NarrativeOrchestrator:
    """
    Main orchestrator for all narrative systems.

    Coordinates between:
    - State Management (narrative states, persistence)
    - Operation Routing (request delegation, result coordination)
    - Mechanics Handling (dice rolling, branching, resolution)
    - Character Integration (character-specific narrative operations)
    - Component Orchestrators (response, consistency, emotional)
    """

    def __init__(self, data_dir: str = "storage/narrative_systems"):
        """Initialize narrative orchestrator."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load configuration first
        self.config = self._load_configuration()

        # Initialize core components
        self.state_manager = NarrativeStateManager(self.data_dir)
        self.mechanics_handler = NarrativeMechanicsHandler(self.config.get("mechanics_settings", {}))

        # Component orchestrators (will be initialized as we build them)
        self.component_orchestrators = {}
        self._initialize_available_orchestrators()

        # Initialize operation router with orchestrator references
        self.operation_router = NarrativeOperationRouter(self.component_orchestrators)

        # Initialize character integration
        self.character_integration = NarrativeCharacterIntegration(self.state_manager, self.component_orchestrators)

        log_system_event(
            "narrative_orchestrator_init",
            f"NarrativeOrchestrator initialized with data directory: {self.data_dir}",
        )

    def _initialize_available_orchestrators(self):
        """Initialize available component orchestrators."""
        try:
            # Initialize response orchestrator
            try:
                from .engines.response import ResponseOrchestrator

                response_dir = self.data_dir / "response"
                self.component_orchestrators["response"] = ResponseOrchestrator(
                    str(response_dir), self.config.get("response_settings", {})
                )
                log_system_event("response_orchestrator_init", "ResponseOrchestrator initialized successfully")
            except ImportError:
                log_info("ResponseOrchestrator not available")

            # Initialize mechanics orchestrator
            try:
                from .engines.mechanics import MechanicsOrchestrator

                self.component_orchestrators["mechanics"] = MechanicsOrchestrator()
                log_system_event("mechanics_orchestrator_init", "MechanicsOrchestrator initialized successfully")
            except ImportError:
                log_info("MechanicsOrchestrator not available - using built-in mechanics handler")

            # Initialize consistency orchestrator
            try:
                from .engines.consistency import ConsistencyOrchestrator

                consistency_config = self.config.get("consistency_settings", {})
                self.component_orchestrators["consistency"] = ConsistencyOrchestrator(consistency_config)
                log_system_event("consistency_orchestrator_init", "ConsistencyOrchestrator initialized successfully")
            except ImportError:
                log_info("ConsistencyOrchestrator not available")

            # Initialize emotional orchestrator
            try:
                from .engines.emotional import EmotionalOrchestrator

                emotional_config = self.config.get("emotional_settings", {})
                self.component_orchestrators["emotional"] = EmotionalOrchestrator(emotional_config)
                log_system_event("emotional_orchestrator_init", "EmotionalOrchestrator initialized successfully")
            except ImportError:
                log_info("EmotionalOrchestrator not available")

        except Exception as e:
            log_error(f"Error initializing orchestrators: {e}")

    def _load_configuration(self) -> dict[str, Any]:
        """Load narrative system configuration."""
        config_path = self.data_dir / "narrative_config.json"

        default_config = {
            "response_settings": {
                "quality_threshold": 0.7,
                "complexity_preference": "adaptive",
                "context_window": 4096,
            },
            "mechanics_settings": {
                "default_dice_sides": 20,
                "difficulty_scaling": "balanced",
                "randomness_factor": 0.3,
            },
            "consistency_settings": {
                "validation_strictness": "moderate",
                "conflict_tolerance": 0.2,
                "memory_window": 100,
            },
            "emotional_settings": {
                "stability_threshold": 0.6,
                "mood_tracking": True,
                "emotional_memory": 50,
            },
        }

        try:
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    return json.load(f)
            else:
                # Create default configuration
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            log_error(f"Error loading narrative configuration: {e}")
            return default_config

    # State Management Interface
    def get_narrative_state(self, story_id: str) -> dict[str, Any]:
        """Get current narrative state for a story."""
        return self.state_manager.get_narrative_state(story_id)

    def update_narrative_state(self, story_id: str, **kwargs) -> bool:
        """Update narrative state for a story."""
        result = self.state_manager.update_narrative_state(story_id, **kwargs)

        # Update mechanics handler configuration if needed
        if "narrative_tension" in kwargs:
            self.mechanics_handler.config["current_tension"] = kwargs["narrative_tension"]

        return result

    # Operation Processing Interface
    def process_narrative_operation(
        self, operation_type: str, story_id: str, operation_data: dict[str, Any]
    ) -> NarrativeOperation:
        """Process a narrative operation through appropriate handler."""
        # Handle mechanics operations locally if no mechanics orchestrator
        if operation_type.startswith("mechanics") and "mechanics" not in self.component_orchestrators:
            return self._handle_local_mechanics_operation(story_id, operation_data)

        # Route other operations through the operation router
        return self.operation_router.process_narrative_operation(operation_type, story_id, operation_data)

    def _handle_local_mechanics_operation(self, story_id: str, data: dict[str, Any]) -> NarrativeOperation:
        """Handle mechanics operations using local mechanics handler."""
        try:
            operation_type = data.get("operation", "unknown")

            if operation_type == "roll_dice":
                result = self.mechanics_handler.roll_dice(data.get("expression", "1d20"))
            elif operation_type == "evaluate_branch":
                # Add current narrative state to scenario
                scenario = data.get("scenario", {})
                scenario["narrative_tension"] = self.get_narrative_state(story_id)["narrative_tension"]
                result = self.mechanics_handler.evaluate_narrative_branch(scenario)

                # Update narrative tension if the evaluation includes tension changes
                if result.get("success") and "tension_modifier" in result:
                    current_state = self.get_narrative_state(story_id)
                    new_tension = max(0.0, min(1.0, current_state["narrative_tension"] + result["tension_modifier"]))
                    self.update_narrative_state(story_id, narrative_tension=new_tension)
                    result["updated_tension"] = new_tension

            else:
                result = {"status": "unknown_mechanics_operation", "operation": operation_type}

            return NarrativeOperation(
                operation_type=f"mechanics_{operation_type}", success=result.get("success", True), result=result
            )

        except Exception as e:
            log_error(f"Error in local mechanics operation: {e}")
            return NarrativeOperation(
                operation_type=f"mechanics_{data.get('operation', 'unknown')}", success=False, result={"error": str(e)}
            )

    # Mechanics Interface
    def roll_dice(self, dice_expression: str) -> dict[str, Any]:
        """Roll dice using standard dice notation."""
        return self.mechanics_handler.roll_dice(dice_expression)

    def evaluate_narrative_branch(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Evaluate narrative branching scenarios."""
        # Add current narrative state context
        story_id = scenario.get("story_id")
        if story_id:
            state = self.get_narrative_state(story_id)
            scenario["narrative_tension"] = state["narrative_tension"]

        return self.mechanics_handler.evaluate_narrative_branch(scenario)

    # Character Integration Interface
    def get_character_narrative_context(self, story_id: str, character_id: str) -> dict[str, Any]:
        """Get narrative context for a specific character."""
        return self.character_integration.state_manager.get_character_narrative_context(story_id, character_id)

    def update_character_narrative_state(self, story_id: str, character_id: str, updates: dict[str, Any]) -> bool:
        """Update narrative state for a specific character."""
        return self.character_integration.state_manager.update_character_narrative_state(
            story_id, character_id, updates
        )

    def validate_character_consistency(
        self, story_id: str, character_id: str, proposed_action: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate character action consistency."""
        return self.character_integration.validate_character_consistency(story_id, character_id, proposed_action)

    def track_character_emotional_changes(
        self, story_id: str, character_id: str, emotional_event: dict[str, Any]
    ) -> dict[str, Any]:
        """Track character emotional changes."""
        return self.character_integration.track_character_emotional_changes(story_id, character_id, emotional_event)

    def track_emotional_stability(
        self, story_id: str, character_id: str, stability_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Track character emotional stability."""
        return self.character_integration.track_emotional_stability(story_id, character_id, stability_data)

    def validate_emotional_consistency(
        self, story_id: str, character_id: str, emotional_transition: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate emotional consistency for character transitions."""
        return self.character_integration.validate_emotional_consistency(story_id, character_id, emotional_transition)

    def calculate_quality_metrics(self, metrics_data: dict[str, float]) -> float:
        """Calculate overall quality metrics."""
        return self.character_integration.calculate_quality_metrics(metrics_data)

    def validate_narrative_consistency(self, story_id: str, narrative_element: dict[str, Any]) -> dict[str, Any]:
        """Validate narrative consistency."""
        return self.character_integration.validate_narrative_consistency(story_id, narrative_element)

    # System Management Interface
    def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive narrative system status."""
        return {
            "orchestrator_status": "active",
            "active_stories": self.state_manager.get_active_stories_count(),
            "operations_processed": self.operation_router.get_operations_count(),
            "components": {
                "state_manager": True,
                "operation_router": True,
                "mechanics_handler": True,
                "character_integration": True,
                **{name: True for name in self.component_orchestrators.keys()},
            },
            "configuration": self.config,
        }

    def get_mechanics_status(self) -> dict[str, Any]:
        """Get mechanics handler status."""
        return self.mechanics_handler.get_mechanics_status()

    def cleanup(self) -> bool:
        """Cleanup narrative orchestrator resources."""
        try:
            # Save states through state manager
            success = self.state_manager.save_states()

            if success:
                log_system_event(
                    "narrative_orchestrator_cleanup",
                    "Narrative orchestrator cleanup completed successfully",
                )
        except Exception as e:
            log_error(f"Error during narrative orchestrator cleanup: {e}")
            return False
        else:
            return success
