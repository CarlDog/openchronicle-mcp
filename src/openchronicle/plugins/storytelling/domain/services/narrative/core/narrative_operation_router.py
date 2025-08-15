"""
OpenChronicle Core - Narrative Operation Router

Handles operation routing and coordination between narrative subsystems.
Extracted from narrative_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

import time
from dataclasses import dataclass
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_system_event


@dataclass
class NarrativeOperation:
    """Result of narrative system operations."""

    operation_type: str
    success: bool
    result: Any = None
    state_changes: dict[str, Any] = None
    recommendations: list[str] = None
    metrics: dict[str, float] = None

    def __post_init__(self):
        if self.state_changes is None:
            self.state_changes = {}
        if self.recommendations is None:
            self.recommendations = []
        if self.metrics is None:
            self.metrics = {}


class NarrativeOperationRouter:
    """Routes narrative operations to appropriate handlers."""

    def __init__(self, orchestrators: dict[str, Any]):
        """Initialize operation router with orchestrator references."""
        self.orchestrators = orchestrators
        self.operation_history: list[NarrativeOperation] = []

    def process_narrative_operation(
        self, operation_type: str, story_id: str, operation_data: dict[str, Any]
    ) -> NarrativeOperation:
        """
        Process a narrative operation through appropriate orchestrator.

        Routes operations to:
        - response: Response intelligence and quality assessment
        - mechanics: Dice rolling, branching, narrative resolution
        - consistency: Memory validation and conflict detection
        - emotional: Emotional stability and mood tracking
        """

        def _raise_unknown_operation_error(operation_type: str):
            raise ValueError(f"Unknown operation type: {operation_type}")

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
                _raise_unknown_operation_error(operation_type)

            # Create operation record
            operation = NarrativeOperation(
                operation_type=operation_type,
                success=True,
                result=result,
                metrics={"processing_time": time.time() - start_time},
            )

            # Store operation history
            self.operation_history.append(operation)

            log_system_event(
                "narrative_operation_complete",
                f"Completed {operation_type} operation for story {story_id}",
            )

        except (ValueError, KeyError) as e:
            log_error(f"Invalid operation data for {operation_type}: {e}")

            return NarrativeOperation(
                operation_type=operation_type,
                success=False,
                result=str(e),
                metrics={"processing_time": time.time() - start_time},
            )
        except Exception as e:
            log_error(f"Unexpected error processing narrative operation {operation_type}: {e}")

            return NarrativeOperation(
                operation_type=operation_type,
                success=False,
                result=str(e),
                metrics={"processing_time": time.time() - start_time},
            )
        else:
            return operation

    def _handle_response_operation(self, story_id: str, data: dict[str, Any]) -> Any:
        """Handle response intelligence operations."""
        response_orchestrator = self.orchestrators.get("response")

        if response_orchestrator:
            try:
                # Process through response orchestrator
                result = response_orchestrator.process(data)

                # Extract and return structured result
                if hasattr(result, 'success') and result.success:
                    return {
                        "status": "response_operation_complete",
                        "success": result.success,
                        "analysis": {
                            "quality": result.analysis.quality.value,
                            "content_type": result.analysis.content_type,
                            "confidence": result.analysis.confidence,
                        },
                        "plan": {
                            "strategy": result.plan.strategy.value,
                            "complexity": result.plan.complexity.value,
                            "content_focus": result.plan.content_focus,
                        },
                        "evaluation": {
                            "overall_score": result.evaluation.overall_score,
                            "coherence_score": result.evaluation.coherence_score,
                            "creativity_score": result.evaluation.creativity_score,
                        },
                    }
                else:
                    return {
                        "status": "response_operation_failed",
                        "success": False,
                        "error": getattr(result, 'error', 'Unknown error')
                    }

            except Exception as e:
                log_error(f"Error in response operation: {e}")
                return {"status": "response_operation_error", "error": str(e)}
        else:
            return {"status": "response_operation_unavailable", "data": data}

    def _handle_mechanics_operation(self, story_id: str, data: dict[str, Any]) -> Any:
        """Handle narrative mechanics operations."""
        mechanics_orchestrator = self.orchestrators.get("mechanics")

        if mechanics_orchestrator:
            try:
                operation_type = data.get("operation", "unknown")

                if operation_type == "roll_dice":
                    return mechanics_orchestrator.roll_dice(data.get("expression", "1d20"))
                elif operation_type == "evaluate_branch":
                    return mechanics_orchestrator.evaluate_narrative_branch(data.get("scenario", {}))
                else:
                    return {"status": "unknown_mechanics_operation", "operation": operation_type}

            except Exception as e:
                log_error(f"Error in mechanics operation: {e}")
                return {"status": "mechanics_operation_error", "error": str(e)}
        else:
            return {"status": "mechanics_operation_unavailable", "data": data}

    def _handle_consistency_operation(self, story_id: str, data: dict[str, Any]) -> Any:
        """Handle consistency validation operations."""
        consistency_orchestrator = self.orchestrators.get("consistency")

        if consistency_orchestrator:
            try:
                operation_type = data.get("operation", "unknown")

                if operation_type == "validate_memory":
                    result = consistency_orchestrator.validate_memory_consistency(
                        story_id, data.get("memory_event", {})
                    )
                elif operation_type == "add_memory":
                    result = consistency_orchestrator.add_memory(
                        story_id, data.get("memory_event", {})
                    )
                elif operation_type == "get_memory_summary":
                    result = consistency_orchestrator.get_character_memory_summary(
                        story_id, data.get("character_id", "")
                    )
                else:
                    result = {
                        "status": "unknown_operation",
                        "operation": operation_type,
                    }

            except Exception as e:
                log_error(f"Error in consistency operation: {e}")
                return {"status": "consistency_operation_error", "error": str(e)}
            else:
                return {
                    "status": "consistency_operation_complete",
                    "success": True,
                    "result": result,
                }
        else:
            return {"status": "consistency_operation_unavailable", "data": data}

    def _handle_emotional_operation(self, story_id: str, data: dict[str, Any]) -> Any:
        """Handle emotional stability operations."""
        emotional_orchestrator = self.orchestrators.get("emotional")

        if emotional_orchestrator:
            try:
                operation_type = data.get("operation", "unknown")

                if operation_type == "track_emotional_state":
                    result = emotional_orchestrator.track_emotional_state(
                        story_id,
                        data.get("character_id", ""),
                        data.get("emotional_data", {}),
                    )
                elif operation_type == "detect_emotional_loops":
                    result = emotional_orchestrator.detect_emotional_loops(
                        story_id,
                        data.get("character_id", ""),
                        data.get("dialogue_history", []),
                    )
                elif operation_type == "analyze_emotional_stability":
                    result = emotional_orchestrator.analyze_emotional_stability(
                        story_id, data.get("character_id", "")
                    )
                elif operation_type == "generate_anti_loop_prompt":
                    result = emotional_orchestrator.generate_anti_loop_prompt(
                        data.get("character_id", ""), data.get("detected_patterns", [])
                    )
                else:
                    result = {
                        "status": "unknown_operation",
                        "operation": operation_type,
                    }

            except Exception as e:
                log_error(f"Error in emotional operation: {e}")
                return {"status": "emotional_operation_error", "error": str(e)}
            else:
                return {
                    "status": "emotional_operation_complete",
                    "success": True,
                    "result": result,
                }
        else:
            return {"status": "emotional_operation_unavailable", "data": data}

    def get_operation_history(self) -> list[NarrativeOperation]:
        """Get history of processed operations."""
        return self.operation_history.copy()

    def get_operations_count(self) -> int:
        """Get count of processed operations."""
        return len(self.operation_history)

    def clear_operation_history(self) -> None:
        """Clear operation history."""
        self.operation_history.clear()
        log_system_event("operation_history_cleared", "Cleared narrative operation history")
