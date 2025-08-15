"""
Scene ID Generator - Provides unique scene identifiers

Generates unique scene IDs using timestamp-based approach for
backward compatibility with existing systems.
"""

import time


class SceneIdGenerator:
    """Generates unique scene identifiers."""

    def __init__(self):
        """Initialize the ID generator."""
        self.last_timestamp = 0
        self.counter = 0

    def generate_scene_id(self) -> str:
        """
        Generate a unique scene ID using microsecond timestamp.

        Returns:
            Unique scene identifier string
        """
        current_time = int(time.time() * 1000000)  # Use microseconds for uniqueness

        # Handle potential time collisions (rare but possible)
        if current_time == self.last_timestamp:
            self.counter += 1
            current_time += self.counter
        else:
            self.counter = 0
            self.last_timestamp = current_time

        return str(current_time)

    def is_valid_scene_id(self, scene_id: str) -> bool:
        """
        Validate if a scene ID has the expected format.

        Args:
            scene_id: Scene ID to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Scene IDs should be numeric strings representing microsecond timestamps
            int(scene_id)
            # Should be reasonable length (not too short, not too long)
            return 10 <= len(scene_id) <= 20
        except (ValueError, TypeError):
            return False

    def extract_timestamp(self, scene_id: str) -> float:
        """
        Extract timestamp from scene ID.

        Args:
            scene_id: Scene ID to extract from

        Returns:
            Timestamp as seconds since epoch
        """
        try:
            microseconds = int(scene_id)
            return microseconds / 1000000.0  # Convert to seconds
        except (ValueError, TypeError):
            return 0.0
