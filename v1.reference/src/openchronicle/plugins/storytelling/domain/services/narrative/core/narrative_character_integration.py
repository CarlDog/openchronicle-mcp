"""
OpenChronicle Core - Narrative Character Integration

Handles character-specific narrative operations and integrations.
Extracted from narrative_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

from datetime import datetime
from typing import Any

from openchronicle.shared.error_handling import NarrativeError
from openchronicle.shared.exceptions import CacheConnectionError
from openchronicle.shared.exceptions import CacheError
from openchronicle.shared.exceptions import InfrastructureError
from openchronicle.shared.exceptions import ModelError
from openchronicle.shared.exceptions import OpenChronicleError
from openchronicle.shared.exceptions import ValidationError
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event


class NarrativeCharacterIntegration:
    """Handles character-specific narrative operations."""

    def __init__(self, state_manager, orchestrators: dict[str, Any]):
        """Initialize character integration with state manager and orchestrators."""
        self.state_manager = state_manager
        self.orchestrators = orchestrators

    def validate_character_consistency(
        self, story_id: str, character_id: str, proposed_action: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate that a proposed character action is consistent with their established traits."""
        try:
            # Get character narrative context
            context = self.state_manager.get_character_narrative_context(story_id, character_id)

            # Basic consistency validation
            validation = {
                "success": True,
                "character_id": character_id,
                "story_id": story_id,
                "action": proposed_action,
                "consistency_score": 0.8,  # Default score
                "issues": [],
                "recommendations": [],
            }

            # Use consistency orchestrator if available
            consistency_orchestrator = self.orchestrators.get("consistency")
            if consistency_orchestrator:
                try:
                    if hasattr(consistency_orchestrator, "validate_character_action"):
                        orchestrator_result = consistency_orchestrator.validate_character_action(
                            story_id, character_id, proposed_action
                        )
                        validation.update(orchestrator_result)
                except (NarrativeError, ValidationError, CacheError) as e:
                    log_error(f"Consistency orchestrator validation failed: {e}")
                    validation["orchestrator_error"] = str(e)
                except Exception as e:
                    # Unexpected error during character action validation
                    log_error(f"Unexpected consistency orchestrator error: {e}")
                    validation["orchestrator_error"] = str(e)

            # Add basic heuristic validation
            action_type = proposed_action.get("type", "unknown")
            action_intensity = proposed_action.get("intensity", "moderate")

            if action_type == "emotional_outburst" and context.get("emotional_state", 0.5) < 0.3:
                validation["issues"].append("Emotional outburst unlikely given current calm state")
                validation["consistency_score"] -= 0.2

            if action_intensity == "extreme" and context.get("narrative_tension", 0.5) < 0.4:
                validation["recommendations"].append("Consider building tension before extreme actions")

            validation["timestamp"] = datetime.now().isoformat()

            log_info(f"Validated character consistency for {character_id}: {validation['consistency_score']}")

        except (NarrativeError, ValidationError, CacheError, InfrastructureError) as e:
            log_error(f"Error validating character consistency: {e}")
            return {"success": False, "error": str(e), "consistency_score": 0.0}
        except Exception as e:
            # Unexpected error during character consistency validation
            log_error(f"Unexpected character consistency validation error: {e}")
            return {"success": False, "error": str(e), "character_id": character_id, "story_id": story_id}
        else:
            return validation

    def track_character_emotional_changes(
        self, story_id: str, character_id: str, emotional_event: dict[str, Any]
    ) -> dict[str, Any]:
        """Track and analyze character emotional changes."""
        try:
            # Update character emotional state
            emotional_data = {
                "event": emotional_event,
                "timestamp": datetime.now().isoformat(),
                "emotional_impact": emotional_event.get("impact", 0.0),
            }

            # Update state through state manager
            updates = {
                "last_emotional_event": emotional_data,
                "emotional_history": emotional_data,  # Would append to list in real implementation
            }

            success = self.state_manager.update_character_narrative_state(story_id, character_id, updates)

            # Use emotional orchestrator if available
            emotional_orchestrator = self.orchestrators.get("emotional")
            if emotional_orchestrator:
                try:
                    if hasattr(emotional_orchestrator, "track_emotional_changes"):
                        orchestrator_result = emotional_orchestrator.track_emotional_changes(
                            story_id, character_id, emotional_event
                        )
                        return {
                            "success": success,
                            "character_id": character_id,
                            "emotional_tracking": orchestrator_result,
                            "timestamp": datetime.now().isoformat(),
                        }
                except (NarrativeError, ModelError, CacheError) as e:
                    log_error(f"Emotional orchestrator tracking failed: {e}")
                except Exception as e:
                    # Unexpected error during emotional tracking
                    log_error(f"Unexpected emotional orchestrator error: {e}")

            # Basic emotional tracking result
            return {
                "success": success,
                "character_id": character_id,
                "emotional_event": emotional_event,
                "state_updated": success,
                "timestamp": datetime.now().isoformat(),
            }

        except (NarrativeError, ValidationError, CacheError, InfrastructureError) as e:
            log_error(f"Error tracking character emotional changes: {e}")
            return {
                "success": False,
                "error": str(e),
                "character_id": character_id,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            # Unexpected error during emotional tracking
            log_error(f"Unexpected error tracking character emotional changes: {e}")
            return {"success": False, "error": str(e), "character_id": character_id, "story_id": story_id}

    def track_emotional_stability(
        self, story_id: str, character_id: str, stability_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Track character emotional stability over time."""
        try:
            # Get current emotional state
            context = self.state_manager.get_character_narrative_context(story_id, character_id)
            current_stability = context.get("emotional_state", 0.5)

            # Calculate new stability based on input data
            stability_change = stability_data.get("change", 0.0)
            new_stability = max(0.0, min(1.0, current_stability + stability_change))

            # Update emotional stability in narrative state
            success = self.state_manager.update_narrative_state(
                story_id,
                emotional_stability={
                    **self.state_manager.get_narrative_state(story_id)["emotional_stability"],
                    character_id: new_stability,
                },
            )

            return {
                "success": success,
                "character_id": character_id,
                "previous_stability": current_stability,
                "current_stability": new_stability,
                "stability_change": stability_change,
                "stability_data": stability_data,
                "timestamp": datetime.now().isoformat(),
            }

        except (NarrativeError, ValidationError, CacheError, InfrastructureError) as e:
            log_error(f"Error tracking emotional stability: {e}")
            return {
                "success": False,
                "error": str(e),
                "character_id": character_id,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            # Unexpected error during emotional stability tracking
            log_error(f"Unexpected error tracking emotional stability: {e}")
            return {"success": False, "error": str(e), "character_id": character_id, "story_id": story_id}

    def validate_emotional_consistency(
        self, story_id: str, character_id: str, emotional_transition: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate emotional consistency for character transitions."""
        try:
            # Get character context
            context = self.state_manager.get_character_narrative_context(story_id, character_id)
            current_emotional_state = context.get("emotional_state", 0.5)

            # Extract transition details
            from_emotion = emotional_transition.get("from", "neutral")
            to_emotion = emotional_transition.get("to", "neutral")
            transition_speed = emotional_transition.get("speed", "moderate")
            trigger_event = emotional_transition.get("trigger", {})

            # Basic validation logic
            validation = {
                "success": True,
                "character_id": character_id,
                "story_id": story_id,
                "transition": emotional_transition,
                "consistency_score": 0.8,
                "issues": [],
                "recommendations": [],
            }

            # Check for rapid emotional swings
            if transition_speed == "instant" and from_emotion != to_emotion:
                validation["issues"].append("Instant emotional transitions may seem unnatural")
                validation["consistency_score"] -= 0.3
                validation["recommendations"].append("Consider gradual emotional transitions")

            # Check for emotional extremes
            extreme_emotions = ["rage", "ecstasy", "despair", "terror"]
            if to_emotion in extreme_emotions and not trigger_event:
                validation["issues"].append("Extreme emotions require triggering events")
                validation["consistency_score"] -= 0.4
                validation["recommendations"].append("Provide clear trigger for extreme emotional state")

            # Use emotional orchestrator for detailed validation
            emotional_orchestrator = self.orchestrators.get("emotional")
            if emotional_orchestrator:
                try:
                    if hasattr(emotional_orchestrator, "validate_emotional_transition"):
                        orchestrator_result = emotional_orchestrator.validate_emotional_transition(
                            story_id, character_id, emotional_transition
                        )
                        validation.update(orchestrator_result)
                except (NarrativeError, ModelError, CacheError) as e:
                    log_error(f"Emotional orchestrator validation failed: {e}")
                    validation["orchestrator_error"] = str(e)
                except Exception as e:
                    # Unexpected error during emotional validation
                    log_error(f"Unexpected emotional orchestrator validation error: {e}")
                    validation["orchestrator_error"] = str(e)

            validation["timestamp"] = datetime.now().isoformat()

            log_info(f"Validated emotional consistency for {character_id}: {validation['consistency_score']}")

        except (NarrativeError, ValidationError, CacheError, InfrastructureError) as e:
            log_error(f"Error validating emotional consistency: {e}")
            return {"success": False, "error": str(e), "character_id": character_id, "story_id": story_id}
        except Exception as e:
            # Unexpected error during emotional consistency validation
            log_error(f"Unexpected error validating emotional consistency: {e}")
            return {"success": False, "error": str(e), "character_id": character_id, "story_id": story_id}
        else:
            return validation

    def calculate_quality_metrics(self, metrics_data: dict[str, float]) -> float:
        """Calculate overall quality metrics for character narrative integration."""
        try:
            # Default weights for different metrics
            weights = {
                "consistency_score": 0.3,
                "emotional_stability": 0.25,
                "narrative_coherence": 0.25,
                "character_development": 0.2,
            }

            total_score = 0.0
            total_weight = 0.0

            for metric, value in metrics_data.items():
                weight = weights.get(metric, 0.1)  # Default weight for unknown metrics
                total_score += value * weight
                total_weight += weight

            # Normalize score
            if total_weight > 0:
                final_score = total_score / total_weight
            else:
                final_score = 0.5  # Default neutral score

            log_info(f"Calculated quality metrics: {final_score:.3f}")
            return min(1.0, max(0.0, final_score))  # Clamp to [0, 1]

        except (ValidationError, NarrativeError) as e:
            log_error(f"Error calculating quality metrics: {e}")
            return 0.5  # Return neutral score on error
        except Exception as e:
            # Unexpected error during quality metrics calculation
            log_error(f"Unexpected error calculating quality metrics: {e}")
            return 0.5  # Return neutral score on error

    def validate_narrative_consistency(self, story_id: str, narrative_element: dict[str, Any]) -> dict[str, Any]:
        """Validate narrative consistency for story elements."""
        try:
            element_type = narrative_element.get("type", "unknown")
            element_content = narrative_element.get("content", {})

            validation = {
                "success": True,
                "story_id": story_id,
                "element": narrative_element,
                "consistency_score": 0.8,
                "issues": [],
                "recommendations": [],
            }

            # Use consistency orchestrator if available
            consistency_orchestrator = self.orchestrators.get("consistency")
            if consistency_orchestrator:
                try:
                    if hasattr(consistency_orchestrator, "validate_narrative_element"):
                        orchestrator_result = consistency_orchestrator.validate_narrative_element(
                            story_id, narrative_element
                        )
                        validation.update(orchestrator_result)
                        return validation
                except (NarrativeError, ValidationError, CacheError) as e:
                    log_error(f"Consistency orchestrator validation failed: {e}")
                    validation["orchestrator_error"] = str(e)
                except Exception as e:
                    # Unexpected error during narrative validation
                    log_error(f"Unexpected consistency orchestrator validation error: {e}")
                    validation["orchestrator_error"] = str(e)

            # Basic narrative validation
            if element_type == "plot_point":
                validation["recommendations"].append("Ensure plot point connects to story arc")
            elif element_type == "character_action":
                validation["recommendations"].append("Verify action aligns with character motivations")
            elif element_type == "scene_transition":
                validation["recommendations"].append("Check for smooth scene flow")

            validation["timestamp"] = datetime.now().isoformat()

            log_info(f"Validated narrative consistency: {validation['consistency_score']}")

        except (NarrativeError, ValidationError, CacheError, InfrastructureError) as e:
            log_error(f"Error validating narrative consistency: {e}")
            return {"success": False, "error": str(e), "story_id": story_id}
        except Exception as e:
            # Unexpected error during narrative consistency validation
            log_error(f"Unexpected error validating narrative consistency: {e}")
            return {"success": False, "error": str(e), "story_id": story_id}
        else:
            return validation
