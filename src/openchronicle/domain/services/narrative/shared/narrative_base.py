"""
OpenChronicle Core - Narrative Systems Shared Components

Shared utilities and base classes for narrative system components.
Provides common patterns for state management, validation, and event processing
used across response, mechanics, consistency, and emotional systems.

Author: OpenChronicle Development Team
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any


@dataclass
class NarrativeEvent:
    """Base class for narrative events."""

    event_type: str
    timestamp: str
    story_id: str
    source_component: str
    event_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ValidationResult:
    """Standard validation result across all narrative components."""

    is_valid: bool
    confidence: float
    validation_type: str
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class NarrativeComponent(ABC):
    """Base class for all narrative system components."""

    def __init__(self, component_name: str, config: dict[str, Any] = None):
        self.component_name = component_name
        self.config = config or {}
        self.event_history: list[NarrativeEvent] = []
        self.metrics: dict[str, float] = {}

    @abstractmethod
    def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process component-specific data."""

    @abstractmethod
    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate component-specific data."""

    def record_event(self, event: NarrativeEvent) -> None:
        """Record a narrative event."""
        self.event_history.append(event)

        # Keep only recent events (configurable limit)
        max_events = self.config.get("max_event_history", 1000)
        if len(self.event_history) > max_events:
            self.event_history = self.event_history[-max_events:]

    def get_recent_events(self, limit: int = 10) -> list[NarrativeEvent]:
        """Get recent narrative events."""
        return self.event_history[-limit:] if self.event_history else []

    def update_metrics(self, metrics: dict[str, float]) -> None:
        """Update component metrics."""
        self.metrics.update(metrics)

    def get_component_status(self) -> dict[str, Any]:
        """Get component status and metrics."""
        return {
            "component_name": self.component_name,
            "events_processed": len(self.event_history),
            "metrics": self.metrics,
            "config": self.config,
        }


class StateManager:
    """Shared state management functionality."""

    def __init__(self):
        self.states: dict[str, dict[str, Any]] = {}
        self.state_history: dict[str, list[dict[str, Any]]] = {}

    def get_state(self, key: str) -> dict[str, Any] | None:
        """Get current state by key."""
        return self.states.get(key)

    def set_state(self, key: str, state: dict[str, Any]) -> bool:
        """Set state and record in history."""
        try:
            # Record previous state in history
            if key in self.states:
                if key not in self.state_history:
                    self.state_history[key] = []
                self.state_history[key].append(self.states[key].copy())

                # Keep limited history
                max_history = 100
                if len(self.state_history[key]) > max_history:
                    self.state_history[key] = self.state_history[key][-max_history:]

            # Set new state
            self.states[key] = state.copy()
            return True

        except Exception:
            return False

    def update_state(self, key: str, updates: dict[str, Any]) -> bool:
        """Update specific fields in state."""
        try:
            if key not in self.states:
                self.states[key] = {}

            current_state = self.states[key].copy()
            current_state.update(updates)
            return self.set_state(key, current_state)

        except Exception:
            return False

    def get_state_history(self, key: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get state history for key."""
        if key not in self.state_history:
            return []
        return self.state_history[key][-limit:] if limit else self.state_history[key]

    def clear_state(self, key: str) -> bool:
        """Clear state and history for key."""
        try:
            self.states.pop(key, None)
            self.state_history.pop(key, None)
            return True
        except Exception:
            return False


class EventProcessor:
    """Shared event processing functionality."""

    def __init__(self):
        self.event_handlers: dict[str, list[callable]] = {}
        self.processed_events: list[NarrativeEvent] = []

    def register_handler(self, event_type: str, handler: callable) -> bool:
        """Register an event handler for specific event type."""
        try:
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = []
            self.event_handlers[event_type].append(handler)
            return True
        except Exception:
            return False

    def process_event(self, event: NarrativeEvent) -> list[dict[str, Any]]:
        """Process event through registered handlers."""
        results = []

        try:
            # Get handlers for this event type
            handlers = self.event_handlers.get(event.event_type, [])
            handlers.extend(self.event_handlers.get("*", []))  # Universal handlers

            # Process through each handler
            for handler in handlers:
                try:
                    result = handler(event)
                    if result:
                        results.append(result)
                except Exception as e:
                    results.append({"error": str(e), "handler": str(handler)})

            # Record processed event
            self.processed_events.append(event)

            # Keep limited history
            max_events = 10000
            if len(self.processed_events) > max_events:
                self.processed_events = self.processed_events[-max_events:]

            return results

        except Exception as e:
            return [{"error": str(e)}]

    def get_event_statistics(self) -> dict[str, Any]:
        """Get event processing statistics."""
        event_types = {}
        for event in self.processed_events:
            event_type = event.event_type
            if event_type not in event_types:
                event_types[event_type] = 0
            event_types[event_type] += 1

        return {
            "total_events": len(self.processed_events),
            "event_types": event_types,
            "registered_handlers": {k: len(v) for k, v in self.event_handlers.items()},
        }


class ValidationBase:
    """Base validation patterns used across narrative components."""

    @staticmethod
    def validate_required_fields(
        data: dict[str, Any], required_fields: list[str]
    ) -> ValidationResult:
        """Validate required fields are present."""
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                validation_type="required_fields",
                issues=[f"Missing required field: {field}" for field in missing_fields],
                recommendations=[f"Add {field} to data" for field in missing_fields],
            )

        return ValidationResult(
            is_valid=True, confidence=1.0, validation_type="required_fields"
        )

    @staticmethod
    def validate_data_types(
        data: dict[str, Any], type_specs: dict[str, type]
    ) -> ValidationResult:
        """Validate data types match specifications."""
        issues = []

        for field, expected_type in type_specs.items():
            if field in data:
                value = data[field]
                if not isinstance(value, expected_type):
                    issues.append(
                        f"Field '{field}' should be {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )

        if issues:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                validation_type="data_types",
                issues=issues,
            )

        return ValidationResult(
            is_valid=True, confidence=1.0, validation_type="data_types"
        )

    @staticmethod
    def validate_ranges(
        data: dict[str, Any], range_specs: dict[str, tuple[float, float]]
    ) -> ValidationResult:
        """Validate numeric values are within specified ranges."""
        issues = []

        for field, (min_val, max_val) in range_specs.items():
            if field in data:
                value = data[field]
                if isinstance(value, (int, float)):
                    if value < min_val or value > max_val:
                        issues.append(
                            f"Field '{field}' value {value} outside range "
                            f"[{min_val}, {max_val}]"
                        )

        if issues:
            return ValidationResult(
                is_valid=False, confidence=0.5, validation_type="ranges", issues=issues
            )

        return ValidationResult(is_valid=True, confidence=1.0, validation_type="ranges")
