"""
OpenChronicle Core - Narrative State Management

Centralized state management for narrative systems.

Author: OpenChronicle Development Team
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class NarrativeState:
    """Narrative state data structure."""

    story_id: str
    character_id: str = ""
    current_scene: str = ""
    emotional_state: Dict[str, Any] = None
    memory_context: Dict[str, Any] = None
    consistency_metrics: Dict[str, float] = None
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
        self.states: Dict[str, NarrativeState] = {}
        self._load_states()

    def _load_states(self):
        """Load existing states from storage."""
        try:
            state_file = self.storage_dir / "narrative_states.json"
            if state_file.exists():
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, state_data in data.items():
                        self.states[key] = NarrativeState(**state_data)
        except Exception as e:
            print(f"Warning: Could not load narrative states: {e}")

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
            return True

        except Exception as e:
            print(f"Error updating narrative state: {e}")
            return False

    def _save_states(self):
        """Save states to storage."""
        try:
            state_file = self.storage_dir / "narrative_states.json"
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({k: asdict(v) for k, v in self.states.items()}, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save narrative states: {e}")

    def cleanup(self):
        """Cleanup and save final state."""
        self._save_states()
