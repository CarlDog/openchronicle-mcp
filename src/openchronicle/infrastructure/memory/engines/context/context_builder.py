"""
Context Builder

Specialized component for generating narrative context from memory data.
Handles context formatting, prompt generation, and narrative consistency.
"""

from dataclasses import dataclass

from ..character.character_manager import CharacterManager
from ..shared.memory_models import CharacterMemory
from ..shared.memory_models import MemorySnapshot


@dataclass
class ContextConfiguration:
    """Configuration for context generation."""

    include_character_details: bool = True
    include_world_state: bool = True
    include_recent_events: bool = True
    include_active_flags: bool = True
    max_recent_events: int = 5
    max_context_length: int = 2000
    character_detail_level: str = "full"  # "full", "summary", "minimal"
    prioritize_primary_characters: bool = True


@dataclass
class ContextMetrics:
    """Metrics about generated context."""

    total_length: int
    character_count: int
    world_state_items: int
    recent_events_count: int
    active_flags_count: int
    context_completeness: float  # 0.0 to 1.0


class ContextBuilder:
    """Advanced context generation for narrative AI prompts."""

    def __init__(self):
        """Initialize context builder."""
        self.character_manager = CharacterManager()
        self.default_config = ContextConfiguration()

        # Context section templates
        self.section_templates = {
            "header": "=== MEMORY CONTEXT ===",
            "primary_characters": "\n=== PRIMARY CHARACTERS ===",
            "other_characters": "\n=== OTHER CHARACTERS ===",
            "all_characters": "\n=== ALL CHARACTERS ===",
            "world_state": "\n=== WORLD STATE ===",
            "active_flags": "\n=== ACTIVE FLAGS ===",
            "recent_events": "\n=== RECENT EVENTS ===",
        }

    def build_memory_context(
        self,
        memory: MemorySnapshot,
        primary_characters: list[str] = None,
        config: ContextConfiguration = None,
    ) -> str:
        """
        Build comprehensive memory context for prompt injection.

        Args:
            memory: The memory snapshot to build context from
            primary_characters: Characters to prioritize in context
            config: Context configuration options

        Returns:
            Formatted context string ready for prompt injection
        """
        try:
            if config is None:
                config = self.default_config

            context_lines = [self.section_templates["header"]]

            # Build character context
            if config.include_character_details:
                character_context = self._build_character_context(
                    memory, primary_characters, config
                )
                context_lines.extend(character_context)

            # Build world state context
            if config.include_world_state:
                world_context = self._build_world_state_context(memory, config)
                context_lines.extend(world_context)

            # Build flags context
            if config.include_active_flags:
                flags_context = self._build_flags_context(memory, config)
                context_lines.extend(flags_context)

            # Build events context
            if config.include_recent_events:
                events_context = self._build_events_context(memory, config)
                context_lines.extend(events_context)

            # Join and apply length limits
            full_context = "\n".join(context_lines)

            if len(full_context) > config.max_context_length:
                full_context = self._truncate_context(
                    full_context, config.max_context_length
                )

            return full_context

        except Exception:
            return f"{self.section_templates['header']}\n[Error loading memory context]"

    def build_character_focused_context(
        self,
        memory: MemorySnapshot,
        focus_character: str,
        config: ContextConfiguration = None,
    ) -> str:
        """Build context focused on a specific character."""
        if config is None:
            config = self.default_config

        # Prioritize the focus character
        return self.build_memory_context(
            memory, primary_characters=[focus_character], config=config
        )

    def build_minimal_context(self, memory: MemorySnapshot) -> str:
        """Build minimal context for simple prompts."""
        config = ContextConfiguration(
            include_character_details=True,
            include_world_state=False,
            include_recent_events=True,
            include_active_flags=False,
            max_recent_events=3,
            max_context_length=500,
            character_detail_level="minimal",
        )

        return self.build_memory_context(memory, config=config)

    def build_comprehensive_context(
        self, memory: MemorySnapshot, primary_characters: list[str] = None
    ) -> str:
        """Build comprehensive context with all available information."""
        config = ContextConfiguration(
            include_character_details=True,
            include_world_state=True,
            include_recent_events=True,
            include_active_flags=True,
            max_recent_events=10,
            max_context_length=5000,
            character_detail_level="full",
        )

        return self.build_memory_context(memory, primary_characters, config)

    def analyze_context_metrics(
        self, context: str, memory: MemorySnapshot
    ) -> ContextMetrics:
        """Analyze metrics about generated context."""
        return ContextMetrics(
            total_length=len(context),
            character_count=len(memory.characters),
            world_state_items=len(memory.world_state),
            recent_events_count=len(memory.recent_events),
            active_flags_count=len(memory.flags),
            context_completeness=self._calculate_context_completeness(context, memory),
        )

    def _build_character_context(
        self,
        memory: MemorySnapshot,
        primary_characters: list[str],
        config: ContextConfiguration,
    ) -> list[str]:
        """Build character-specific context sections."""
        context_lines = []
        characters = memory.characters

        if not characters:
            return context_lines

        if primary_characters and config.prioritize_primary_characters:
            # Primary characters section
            primary_chars_in_memory = [
                char for char in primary_characters if char in characters
            ]

            if primary_chars_in_memory:
                context_lines.append(self.section_templates["primary_characters"])
                for char_name in primary_chars_in_memory:
                    char_context = self._format_character_context(
                        characters[char_name], config.character_detail_level
                    )
                    context_lines.append(char_context)

            # Other characters section
            other_chars = [
                name for name in characters.keys() if name not in primary_characters
            ]
            if other_chars and config.character_detail_level != "minimal":
                context_lines.append(self.section_templates["other_characters"])
                for char_name in other_chars:
                    char_context = self._format_character_context(
                        characters[char_name], "summary"
                    )
                    context_lines.append(char_context)
        else:
            # All characters with equal treatment
            context_lines.append(self.section_templates["all_characters"])
            for char_name, char_data in characters.items():
                char_context = self._format_character_context(
                    char_data, config.character_detail_level
                )
                context_lines.append(char_context)

        return context_lines

    def _build_world_state_context(
        self, memory: MemorySnapshot, config: ContextConfiguration
    ) -> list[str]:
        """Build world state context section."""
        context_lines = []
        world_state = memory.world_state

        if world_state:
            context_lines.append(self.section_templates["world_state"])
            for key, value in world_state.items():
                context_lines.append(f"{key}: {value}")

        return context_lines

    def _build_flags_context(
        self, memory: MemorySnapshot, config: ContextConfiguration
    ) -> list[str]:
        """Build active flags context section."""
        context_lines = []
        flags = memory.flags

        if flags:
            context_lines.append(self.section_templates["active_flags"])
            for flag in flags:
                flag_name = flag.get("name", "Unknown")
                flag_data = flag.get("data", {})
                if flag_data:
                    context_lines.append(f"- {flag_name}: {flag_data}")
                else:
                    context_lines.append(f"- {flag_name}")

        return context_lines

    def _build_events_context(
        self, memory: MemorySnapshot, config: ContextConfiguration
    ) -> list[str]:
        """Build recent events context section."""
        context_lines = []
        recent_events = memory.recent_events

        if recent_events:
            context_lines.append(self.section_templates["recent_events"])
            events_to_show = recent_events[-config.max_recent_events :]

            for event in events_to_show:
                event_desc = event.get("description", "Unknown event")
                timestamp = event.get("timestamp", "")[:10]  # Just date part
                context_lines.append(f"- {event_desc} ({timestamp})")

        return context_lines

    def _format_character_context(
        self, character: CharacterMemory, detail_level: str
    ) -> str:
        """Format character data for context inclusion."""
        if detail_level == "minimal":
            mood = character.current_mood or "neutral"
            return f"{character.name}: {mood} mood"

        if detail_level == "summary":
            mood = character.current_mood or "neutral"
            state_items = []
            if character.current_state:
                state_items = [f"{k}: {v}" for k, v in character.current_state.items()]

            state_summary = (
                ", ".join(state_items) if state_items else "no specific state"
            )
            return f"{character.name}: {mood} mood, {state_summary}"

        # "full"
        return self.character_manager.format_character_snapshot_for_prompt(character)

    def _truncate_context(self, context: str, max_length: int) -> str:
        """Intelligently truncate context to fit length limits."""
        if len(context) <= max_length:
            return context

        # Split into lines and prioritize sections
        lines = context.split("\n")
        priority_sections = ["=== MEMORY CONTEXT ===", "=== PRIMARY CHARACTERS ==="]

        # Always keep header and critical sections
        kept_lines = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline

            # Always keep priority sections
            if (
                any(priority in line for priority in priority_sections)
                or current_length + line_length <= max_length
            ):
                kept_lines.append(line)
                current_length += line_length
            else:
                # Add truncation indicator
                if current_length + 20 <= max_length:  # Room for indicator
                    kept_lines.append("[... context truncated ...]")
                break

        return "\n".join(kept_lines)

    def _calculate_context_completeness(
        self, context: str, memory: MemorySnapshot
    ) -> float:
        """Calculate how complete the context is compared to available memory."""
        # Check for presence of different sections
        sections_present = 0
        total_sections = 4  # characters, world_state, flags, events

        if "CHARACTERS" in context:
            sections_present += 1
        if "WORLD STATE" in context:
            sections_present += 1
        if "ACTIVE FLAGS" in context:
            sections_present += 1
        if "RECENT EVENTS" in context:
            sections_present += 1

        return sections_present / total_sections
