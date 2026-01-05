"""
OpenChronicle Core - Narrative State Manager

Handles all narrative state management, validation, and persistence.
Extracted from narrative_orchestrator.py for better separation of concerns.
            log_system_event(
                "narrative_states_loaded",
                f"Loaded {len(self.narrative_states)} narrative states",
            )

        except (OSError, IOError, PermissionError) as e:
            log_error(f"File access error loading narrative states: {e}")
            return False
        except json.JSONDecodeError as e:
            log_error(f"JSON decode error loading narrative states: {e}")
            return False
        except (ValueError, TypeError) as e:
            log_error(f"Data validation error loading narrative states: {e}")
            return False
        except Exception as e:
            log_error(f"Error loading narrative states: {e}")
            return False
        else:
            return True

Author: OpenChronicle Development Team
"""

import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_system_event


@dataclass
class NarrativeState:
    """Central narrative state management."""

    story_id: str
    current_scene: str
    narrative_tension: float = 0.5
    character_states: dict[str, Any] = None
    memory_context: dict[str, Any] = None
    response_quality: float = 0.0
    emotional_stability: dict[str, float] = None
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


class NarrativeStateManager:
    """Manages narrative states for all stories."""

    def __init__(self, data_dir: Path):
        """Initialize narrative state manager."""
        self.data_dir = data_dir
        self.narrative_states: dict[str, NarrativeState] = {}

    def get_narrative_state(self, story_id: str) -> dict[str, Any]:
        """Get current narrative state for a story."""
        if story_id not in self.narrative_states:
            # Create a default state if it doesn't exist
            self.narrative_states[story_id] = NarrativeState(story_id=story_id, current_scene="initial")

        state = self.narrative_states[story_id]
        # Return dict representation for test compatibility
        return {
            "story_id": state.story_id,
            "current_scene": state.current_scene,
            "narrative_tension": state.narrative_tension,
            "character_states": state.character_states,
            "memory_context": state.memory_context,
            "response_quality": state.response_quality,
            "emotional_stability": state.emotional_stability,
            "last_update": state.last_update,
        }

    def update_narrative_state(self, story_id: str, **kwargs) -> bool:
        """Update narrative state for a story."""
        try:
            if story_id not in self.narrative_states:
                self.narrative_states[story_id] = NarrativeState(story_id=story_id, current_scene="initial")

            state = self.narrative_states[story_id]

            # Update provided fields
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)

            state.last_update = datetime.now().isoformat()

            log_system_event(
                "narrative_state_update",
                f"Updated narrative state for story {story_id}: {list(kwargs.keys())}",
            )

        except (AttributeError, TypeError, ValueError) as e:
            log_error(f"Invalid narrative state data for {story_id}: {e}")
            return False
        except Exception as e:
            log_error(f"Unexpected error updating narrative state for {story_id}: {e}")
            return False
        else:
            return True

    def get_character_narrative_context(self, story_id: str, character_id: str) -> dict[str, Any]:
        """Get narrative context for a specific character."""
        state = self.get_narrative_state(story_id)
        if not state:
            return {}

        return {
            "character_id": character_id,
            "narrative_tension": state["narrative_tension"],
            "character_state": state["character_states"].get(character_id, {}),
            "emotional_state": state["emotional_stability"].get(character_id, 0.5),
            "last_update": state["last_update"],
        }

    def update_character_narrative_state(self, story_id: str, character_id: str, updates: dict[str, Any]) -> bool:
        """Update narrative state for a specific character."""
        try:
            if story_id not in self.narrative_states:
                self.narrative_states[story_id] = NarrativeState(story_id=story_id, current_scene="initial")

            state = self.narrative_states[story_id]

            # Update character-specific state
            if character_id not in state.character_states:
                state.character_states[character_id] = {}

            state.character_states[character_id].update(updates)
            state.last_update = datetime.now().isoformat()

            log_system_event(
                "character_narrative_update",
                f"Updated narrative state for character {character_id} in story {story_id}",
            )

        except (AttributeError, TypeError, KeyError) as e:
            log_error(f"Invalid character narrative data for {character_id} in {story_id}: {e}")
            return False
        except Exception as e:
            log_error(f"Unexpected error updating character narrative state for {character_id} in {story_id}: {e}")
            return False
        else:
            return True

    def save_states(self) -> bool:
        """Save current narrative states to disk."""
        try:
            states_file = self.data_dir / "narrative_states.json"
            with open(states_file, "w", encoding="utf-8") as f:
                json.dump(
                    {k: asdict(v) for k, v in self.narrative_states.items()},
                    f,
                    indent=2,
                )

            log_system_event(
                "narrative_states_saved",
                f"Saved {len(self.narrative_states)} narrative states",
            )

        except (OSError, IOError, PermissionError) as e:
            log_error(f"File system error saving narrative states: {e}")
            return False
        except (TypeError, ValueError) as e:
            log_error(f"JSON serialization error saving narrative states: {e}")
            return False
        except Exception as e:
            log_error(f"Unexpected error saving narrative states: {e}")
            return False
        else:
            return True

    def load_states(self) -> bool:
        """Load narrative states from disk."""
        try:
            states_file = self.data_dir / "narrative_states.json"
            if not states_file.exists():
                return True  # No states to load is OK

            with open(states_file, encoding="utf-8") as f:
                states_data = json.load(f)

            self.narrative_states = {
                story_id: NarrativeState(**state_data) for story_id, state_data in states_data.items()
            }

            log_system_event(
                "narrative_states_loaded",
                f"Loaded {len(self.narrative_states)} narrative states",
            )

        except (OSError, IOError, PermissionError) as e:
            log_error(f"File access error loading narrative states: {e}")
            return False
        except json.JSONDecodeError as e:
            log_error(f"JSON decode error loading narrative states: {e}")
            return False
        except (ValueError, TypeError) as e:
            log_error(f"Data validation error loading narrative states: {e}")
            return False
        except Exception as e:
            log_error(f"Error loading narrative states: {e}")
            return False
        else:
            return True

    def get_active_stories_count(self) -> int:
        """Get count of active stories."""
        return len(self.narrative_states)

    def cleanup_old_states(self, max_age_days: int = 30) -> int:
        """Clean up old narrative states."""
        try:
            from datetime import timedelta

            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            removed_count = 0

            stories_to_remove = []
            for story_id, state in self.narrative_states.items():
                try:
                    last_update = datetime.fromisoformat(state.last_update)
                    if last_update < cutoff_date:
                        stories_to_remove.append(story_id)
                except (ValueError, TypeError):
                    # Invalid date format, keep the state
                    continue

            for story_id in stories_to_remove:
                del self.narrative_states[story_id]
                removed_count += 1

            if removed_count > 0:
                log_system_event(
                    "narrative_states_cleanup",
                    f"Cleaned up {removed_count} old narrative states",
                )

        except (AttributeError, KeyError) as e:
            log_error(f"Data structure error cleaning up narrative states: {e}")
            return 0
        except (ValueError, TypeError) as e:
            log_error(f"Date processing error cleaning up narrative states: {e}")
            return 0
        except Exception as e:
            log_error(f"Error cleaning up narrative states: {e}")
            return 0
        else:
            return removed_count
