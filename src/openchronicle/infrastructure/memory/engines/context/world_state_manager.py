"""
World State Manager

Specialized component for managing world state, flags, and events.
Handles world consistency, event tracking, and state transitions.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from typing import Any

from ..shared.memory_models import MemoryFlag
from ..shared.memory_models import MemorySnapshot
from ..shared.memory_models import WorldEvent


@dataclass
class WorldStateUpdate:
    """Represents a world state update operation."""

    updates: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "system"
    description: str = ""


@dataclass
class EventFilter:
    """Filter criteria for querying events."""

    event_type: str | None = None
    character_involved: str | None = None
    location: str | None = None
    date_range: tuple | None = None
    max_results: int = 50


@dataclass
class WorldStateAnalysis:
    """Analysis of world state consistency and completeness."""

    total_state_items: int
    categories_present: list[str]
    missing_critical_states: list[str]
    potential_inconsistencies: list[str]
    completeness_score: float  # 0.0 to 1.0


class WorldStateManager:
    """Advanced world state and event management."""

    def __init__(self):
        """Initialize world state manager."""
        self.critical_world_states = {
            "time_of_day",
            "current_location",
            "weather",
            "season",
            "political_climate",
            "economic_status",
            "threat_level",
        }

        self.world_categories = {
            "temporal": ["time_of_day", "season", "year", "era"],
            "environmental": ["weather", "climate", "natural_disasters"],
            "social": ["political_climate", "social_tensions", "cultural_events"],
            "economic": [
                "economic_status",
                "trade_conditions",
                "resource_availability",
            ],
            "security": ["threat_level", "active_conflicts", "peace_status"],
            "magical": ["magical_activity", "supernatural_events", "magical_stability"],
            "technological": ["tech_level", "available_technology", "innovation_rate"],
        }

    def update_world_state(
        self,
        memory: MemorySnapshot,
        updates: dict[str, Any],
        source: str = "system",
        description: str = "",
    ) -> WorldStateUpdate:
        """
        Update world state with validation and tracking.

        Args:
            memory: Current memory snapshot
            updates: Dictionary of state updates
            source: Source of the update (system, character, event)
            description: Description of why the update occurred

        Returns:
            WorldStateUpdate record
        """
        try:
            validated_updates = self._validate_world_state_updates(
                updates, memory.world_state
            )
            memory.world_state.update(validated_updates)
            update_record = WorldStateUpdate(
                updates=validated_updates, source=source, description=description
            )
            self._log_world_state_changes(validated_updates, source)
            return update_record
        except (TypeError, ValueError, KeyError, AttributeError):
            return WorldStateUpdate(updates={}, description="Update failed")

    def add_world_event(
        self,
        memory: MemorySnapshot,
        event_description: str,
        event_type: str = "general",
        event_data: dict[str, Any] = None,
        characters_involved: list[str] = None,
        location: str = None,
    ) -> WorldEvent:
        """
        Add a significant world event to memory.

        Args:
            memory: Current memory snapshot
            event_description: Description of the event
            event_type: Type/category of event
            event_data: Additional event data
            characters_involved: Characters involved in event
            location: Location where event occurred

        Returns:
            Created WorldEvent
        """
        try:
            event = WorldEvent(
                description=event_description,
                event_type=event_type,
                timestamp=datetime.now(UTC),
                data=event_data or {},
                characters_involved=characters_involved or [],
                location=location,
            )

            # Add to memory
            memory.recent_events.append(event.to_dict())

            # Maintain event limit (keep last 20)
            memory.recent_events = memory.recent_events[-20:]

            # Check for world state implications
            self._process_event_implications(event, memory)

            return event

        except (TypeError, ValueError, KeyError, AttributeError):
            return WorldEvent(
                description=event_description,
                event_type="error",
                timestamp=datetime.now(UTC),
            )

    def add_memory_flag(
        self,
        memory: MemorySnapshot,
        flag_name: str,
        flag_data: dict[str, Any] = None,
        flag_type: str = "general",
        expires_at: datetime | None = None,
    ) -> MemoryFlag:
        """
        Add a memory flag for tracking important conditions.

        Args:
            memory: Current memory snapshot
            flag_name: Name/identifier of the flag
            flag_data: Additional flag data
            flag_type: Type of flag (condition, reminder, trigger)
            expires_at: Optional expiration time

        Returns:
            Created MemoryFlag
        """
        try:
            flag = MemoryFlag(
                name=flag_name,
                flag_type=flag_type,
                timestamp=datetime.now(UTC),
                data=flag_data or {},
                expires_at=expires_at,
            )

            # Add to memory
            memory.flags.append(flag.to_dict())

            # Clean up expired flags
            self._cleanup_expired_flags(memory)

            return flag

        except (TypeError, ValueError, KeyError, AttributeError):
            return MemoryFlag(
                name=flag_name, flag_type="error", timestamp=datetime.now(UTC)
            )

    def remove_memory_flag(self, memory: MemorySnapshot, flag_name: str) -> bool:
        """Remove a memory flag by name."""
        try:
            original_count = len(memory.flags)
            memory.flags = [f for f in memory.flags if f.get("name") != flag_name]
            return len(memory.flags) < original_count

        except (TypeError, ValueError, KeyError, AttributeError):
            return False

    def has_memory_flag(self, memory: MemorySnapshot, flag_name: str) -> bool:
        """Check if a memory flag exists and is active."""
        try:
            # Clean up expired flags first
            self._cleanup_expired_flags(memory)

            return any(f.get("name") == flag_name for f in memory.flags)

        except (TypeError, ValueError, KeyError, AttributeError):
            return False

    def get_active_flags(
        self, memory: MemorySnapshot, flag_type: str = None
    ) -> list[MemoryFlag]:
        """Get all active flags, optionally filtered by type."""
        try:
            # Clean up expired flags
            self._cleanup_expired_flags(memory)

            flags = []
            for flag_data in memory.flags:
                if flag_type is None or flag_data.get("flag_type") == flag_type:
                    flags.append(MemoryFlag.from_dict(flag_data))

            return flags

        except (TypeError, ValueError, KeyError, AttributeError):
            return []

    def query_events(
        self, memory: MemorySnapshot, event_filter: EventFilter
    ) -> list[WorldEvent]:
        """Query events based on filter criteria."""
        try:
            events = []

            for event_data in memory.recent_events:
                event = WorldEvent.from_dict(event_data)

                # Apply filters
                if (
                    event_filter.event_type
                    and event.event_type != event_filter.event_type
                ):
                    continue

                if event_filter.character_involved:
                    if event_filter.character_involved not in event.characters_involved:
                        continue

                if event_filter.location and event.location != event_filter.location:
                    continue

                if event_filter.date_range:
                    start_date, end_date = event_filter.date_range
                    if not (start_date <= event.timestamp <= end_date):
                        continue

                events.append(event)

                if len(events) >= event_filter.max_results:
                    break

            return events

        except (TypeError, ValueError, KeyError, AttributeError):
            return []

    def analyze_world_state(self, memory: MemorySnapshot) -> WorldStateAnalysis:
        """Analyze world state for consistency and completeness."""
        try:
            world_state = memory.world_state

            # Get present categories
            categories_present = []
            for category, states in self.world_categories.items():
                if any(state in world_state for state in states):
                    categories_present.append(category)

            # Check for missing critical states
            missing_critical = [
                state
                for state in self.critical_world_states
                if state not in world_state
            ]

            # Detect potential inconsistencies
            inconsistencies = self._detect_world_state_inconsistencies(world_state)

            # Calculate completeness score
            completeness = len(categories_present) / len(self.world_categories)

            return WorldStateAnalysis(
                total_state_items=len(world_state),
                categories_present=categories_present,
                missing_critical_states=missing_critical,
                potential_inconsistencies=inconsistencies,
                completeness_score=completeness,
            )

        except (TypeError, ValueError, KeyError, AttributeError):
            return WorldStateAnalysis(
                total_state_items=0,
                categories_present=[],
                missing_critical_states=list(self.critical_world_states),
                potential_inconsistencies=[],
                completeness_score=0.0,
            )

    def get_world_state_summary(
        self, memory: MemorySnapshot, category: str = None
    ) -> dict[str, Any]:
        """Get a summary of world state, optionally filtered by category."""
        try:
            world_state = memory.world_state

            if category and category in self.world_categories:
                # Filter by category
                category_states = self.world_categories[category]
                return {
                    key: value
                    for key, value in world_state.items()
                    if key in category_states
                }
            # Return all world state
            return dict(world_state)

        except (TypeError, ValueError, KeyError, AttributeError):
            return {}

    def _validate_world_state_updates(
        self, updates: dict[str, Any], current_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate world state updates for consistency."""
        validated = {}

        for key, value in updates.items():
            # Basic validation
            if key and value is not None:
                # Convert to string for consistency
                validated[key] = (
                    str(value) if not isinstance(value, (dict, list)) else value
                )

        return validated

    def _log_world_state_changes(self, updates: dict[str, Any], source: str):
        """Log significant world state changes."""
        # In a full implementation, this would integrate with the logging system
        # For now, we just track critical changes
        critical_changes = [key for key in updates if key in self.critical_world_states]

        if critical_changes:
            # This would be logged to the system
            pass

    def _process_event_implications(self, event: WorldEvent, memory: MemorySnapshot):
        """Process potential world state implications of an event."""
        try:
            # Basic event implications (could be expanded with NLP)
            event_desc_lower = event.description.lower()

            # Weather-related events
            if any(word in event_desc_lower for word in ["rain", "storm", "snow"]):
                if "weather" not in memory.world_state:
                    memory.world_state["weather"] = "stormy"

            # Conflict-related events
            if any(word in event_desc_lower for word in ["battle", "war", "conflict"]):
                memory.world_state["threat_level"] = "high"

            # Peace-related events
            if any(
                word in event_desc_lower for word in ["peace", "treaty", "celebration"]
            ):
                memory.world_state["threat_level"] = "low"

        except (TypeError, ValueError, KeyError, AttributeError):
            # Optional implication enrichment failed
            pass

    def _cleanup_expired_flags(self, memory: MemorySnapshot):
        """Remove expired flags from memory."""
        try:
            current_time = datetime.now(UTC)

            active_flags = []
            for flag_data in memory.flags:
                expires_at_str = flag_data.get("expires_at")
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(
                            expires_at_str.replace("Z", "+00:00")
                        )
                        if current_time < expires_at:
                            active_flags.append(flag_data)
                    except (ValueError, TypeError):
                        active_flags.append(flag_data)
                else:
                    # Keep flags without expiration
                    active_flags.append(flag_data)

            memory.flags = active_flags

        except (TypeError, ValueError, KeyError, AttributeError):
            # Optional cleanup failed
            pass

    def _detect_world_state_inconsistencies(
        self, world_state: dict[str, Any]
    ) -> list[str]:
        """Detect potential inconsistencies in world state."""
        inconsistencies = []

        try:
            # Time inconsistencies
            if "time_of_day" in world_state and "weather" in world_state:
                time_val = str(world_state["time_of_day"]).lower()
                weather_val = str(world_state["weather"]).lower()

                if "night" in time_val and "sunny" in weather_val:
                    inconsistencies.append("Sunny weather at night is unusual")

            # Economic vs threat level
            if "economic_status" in world_state and "threat_level" in world_state:
                economic = str(world_state["economic_status"]).lower()
                threat = str(world_state["threat_level"]).lower()

                if "prosperous" in economic and "high" in threat:
                    inconsistencies.append(
                        "High threat level contradicts prosperous economy"
                    )

            # Season vs weather
            if "season" in world_state and "weather" in world_state:
                season = str(world_state["season"]).lower()
                weather = str(world_state["weather"]).lower()

                if "winter" in season and "hot" in weather:
                    inconsistencies.append("Hot weather in winter is inconsistent")

        except (TypeError, ValueError, KeyError, AttributeError):
            # Optional consistency check failed
            pass

        return inconsistencies
