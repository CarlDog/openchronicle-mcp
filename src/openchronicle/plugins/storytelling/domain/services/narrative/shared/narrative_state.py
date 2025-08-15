"""
OpenChronicle Core - Narrative State Management

Centralized state management for narrative systems.

Author: OpenChronicle Development Team
"""

import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_warning


@dataclass
class NarrativeState:
    """Narrative state data structure."""

    story_id: str
    character_id: str = ""
    current_scene: str = ""
    emotional_state: dict[str, Any] = None
    memory_context: dict[str, Any] = None
    consistency_metrics: dict[str, float] = None
    last_update: str = ""

    def __post_init__(self):
        if self.emotional_state is None:
            self.emotional_state = {}
        if self.memory_context is None:
            self.memory_context = {}
        if self.consistency_metrics is None:
            self.consistency_metrics = {}
        if not self.last_update:
            self.last_update = datetime.now().isoformat()


class NarrativeStateManager:
    """Manages narrative state across all systems."""

    def __init__(self, storage_dir: str = "storage/narrative_state"):
        """Initialize state manager."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.states: dict[str, NarrativeState] = {}
        self._load_states()

    def _load_states(self):
        """Load existing states from storage."""
        try:
            state_file = self.storage_dir / "narrative_states.json"
            if state_file.exists():
                with open(state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for key, state_data in data.items():
                        self.states[key] = NarrativeState(**state_data)
        except (OSError, IOError, PermissionError) as e:
            log_warning(
                f"File system error loading narrative states: {e}",
                context_tags=[
                    "narrative_state",
                    "load_states",
                    f"storage_dir:{self.storage_dir}",
                ],
            )
        except json.JSONDecodeError as e:
            log_warning(
                f"JSON decode error loading narrative states: {e}",
                context_tags=[
                    "narrative_state",
                    "load_states",
                    f"storage_dir:{self.storage_dir}",
                ],
            )
        except Exception as e:
            log_warning(
                f"Could not load narrative states: {type(e).__name__}: {e}",
                context_tags=[
                    "narrative_state",
                    "load_states",
                    f"storage_dir:{self.storage_dir}",
                ],
            )

    def get_state(self, story_id: str, character_id: str = "") -> NarrativeState:
        """Get or create narrative state."""
        key = f"{story_id}:{character_id}" if character_id else story_id

        if key not in self.states:
            self.states[key] = NarrativeState(
                story_id=story_id, character_id=character_id
            )

        return self.states[key]

    def update_state(self, story_id: str, character_id: str = "", **kwargs) -> bool:
        """Update narrative state."""
        try:
            state = self.get_state(story_id, character_id)

            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)

            state.last_update = datetime.now().isoformat()
            self._save_states()

        except (AttributeError, KeyError) as e:
            log_error(
                f"Data structure error updating narrative state: {type(e).__name__}: {e}",
                context_tags=[
                    "narrative_state",
                    "update_state",
                    f"story:{story_id}",
                    (f"character:{character_id}" if character_id else "character:__global__"),
                ],
            )
            return False
        except (ValueError, TypeError) as e:
            log_error(
                f"Parameter error updating narrative state: {type(e).__name__}: {e}",
                context_tags=[
                    "narrative_state",
                    "update_state",
                    f"story:{story_id}",
                    (f"character:{character_id}" if character_id else "character:__global__"),
                ],
            )
            return False
        except Exception as e:
            log_error(
                f"Error updating narrative state: {type(e).__name__}: {e}",
                context_tags=[
                    "narrative_state",
                    "update_state",
                    f"story:{story_id}",
                    (f"character:{character_id}" if character_id else "character:__global__"),
                ],
            )
            return False
        else:
            return True

    def _save_states(self):
        """Save states to storage."""
        try:
            state_file = self.storage_dir / "narrative_states.json"
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({k: asdict(v) for k, v in self.states.items()}, f, indent=2)
        except (OSError, IOError, PermissionError) as e:
            log_warning(
                f"File system error saving narrative states: {e}",
                context_tags=[
                    "narrative_state",
                    "save_states",
                    f"storage_dir:{self.storage_dir}",
                ],
            )
        except (AttributeError, KeyError) as e:
            log_warning(
                f"Data structure error saving narrative states: {e}",
                context_tags=[
                    "narrative_state",
                    "save_states",
                    f"storage_dir:{self.storage_dir}",
                ],
            )
        except Exception as e:
            log_warning(
                f"Could not save narrative states: {type(e).__name__}: {e}",
                context_tags=[
                    "narrative_state",
                    "save_states",
                    f"storage_dir:{self.storage_dir}",
                ],
            )

    def cleanup(self):
        """Cleanup and save final state."""
        self._save_states()
