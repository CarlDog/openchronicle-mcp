"""
Production Mock Adapter for OpenChronicle

A production-ready mock LLM adapter that users can configure in their model registry
for development, prototyping, and demonstration purposes. This adapter provides
realistic behavior and responses suitable for user-facing environments.

Example config (user_models.json):
{
    "mock_creative": {
        "provider": "mock",
        "model_name": "creative-writer-v1",
        "personality": "creative",
        "response_quality": "high",
        "max_tokens": 1000
    }
}
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any

from openchronicle.shared.exceptions import ModelResponseError


# TODO: Import logging system when available
# from utilities.logging_system import log_system_event


def log_system_event(event_type: str, description: str):
    """Temporary logging function until utilities.logging_system is available."""
    print(f"[{event_type}] {description}")


@dataclass
class MockModelConfig:
    """Configuration for mock model behavior."""

    personality: str = "balanced"  # creative, analytical, balanced, concise
    response_quality: str = "high"  # high, medium, low
    response_length: str = "medium"  # short, medium, long, variable
    creativity_level: float = 0.7  # 0.0-1.0
    consistency_level: float = 0.9  # 0.0-1.0
    error_rate: float = 0.0  # 0.0-1.0 (for testing error handling)
    response_time_ms: int = 800  # Average response time in milliseconds


@dataclass
class MockResponse:
    """Response structure for mock adapter."""

    content: str
    model: str
    provider: str = "mock"
    tokens_used: int = 0
    finish_reason: str = "completed"
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MockAdapter:
    """
    Production-ready mock adapter for user configuration.

    Provides realistic, configurable responses suitable for development,
    demonstrations, and user testing without requiring external API access.
    """

    def __init__(self, model_name: str = "mock-model", **config):
        self.model_name = model_name
        self.provider_name = "mock"

        # Parse configuration
        self.config = MockModelConfig(
            personality=config.get("personality", "balanced"),
            response_quality=config.get("response_quality", "high"),
            response_length=config.get("response_length", "medium"),
            creativity_level=float(config.get("creativity_level", 0.7)),
            consistency_level=float(config.get("consistency_level", 0.9)),
            error_rate=float(config.get("error_rate", 0.0)),
            response_time_ms=int(config.get("response_time_ms", 800)),
        )

        # Load response templates
        self._load_response_templates()

        # State tracking
        self.conversation_history = []
        self.character_memories = {}
        self.story_context = {}

        log_system_event(
            "adapter_initialized",
            f"Mock adapter '{model_name}' initialized with {self.config.personality} personality",
        )

    def _load_response_templates(self):
        """Load realistic response templates for different scenarios."""
        self.templates = {
            "content_continuation": [
                "The {entity} moved through the {setting}, {action}. {emotion_description}",
                "As {time_period}, {entity} found themselves {situation}. {dialogue}",
                "{entity}'s eyes {eye_action} as they {entity_action}. {internal_thought}",
            ],
            "entity_dialogue": [
                '"{quote}," {entity} {dialogue_tag}, {body_language}.',
                '{entity} {emotion_verb}, "{quote}" {voice_description}.',
                '"We need to {action}," {entity} declared, {entity_trait}.',
            ],
            "environment_setting": [
                "The {location} was {atmosphere}. {sensory_detail} filled the air.",
                "{weather} cast {lighting} across the {landscape}, creating {mood}.",
                "In the distance, {distant_element} while {immediate_element}.",
            ],
            "content_development": [
                "This development changed key conditions. {consequence}",
                "The stakes had never been higher. {tension_description}",
                "A new path forward emerged. {opportunity_description}",
            ],
        }

        # Content libraries for realistic generation
        self.content_library = {
            "characters": ["Aria", "Marcus", "Elena", "Thorne", "Lydia", "Gareth"],
            "emotions": [
                "determined",
                "conflicted",
                "hopeful",
                "wary",
                "excited",
                "contemplative",
            ],
            "settings": [
                "ancient library",
                "moonlit forest",
                "bustling marketplace",
                "abandoned tower",
            ],
            "actions": [
                "searching for answers",
                "confronting their fears",
                "making a difficult choice",
            ],
            "dialogue_tags": [
                "whispered",
                "declared",
                "murmured",
                "stated firmly",
                "asked softly",
            ],
        }

    async def generate_response(self, prompt: str, **kwargs) -> MockResponse:
        """
        Generate a realistic response based on the prompt and configuration.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (unit_id, participant_focus, etc.)

        Returns:
            MockResponse with generated content
        """
        try:
            # Simulate realistic response time
            await self._simulate_processing_time()

            # Check for error simulation
            if random.random() < self.config.error_rate:
                raise ModelResponseError("Simulated API error for testing")

            # Analyze prompt for context
            context = self._analyze_prompt(prompt, **kwargs)

            # Generate response based on personality and context
            response_content = await self._generate_contextual_response(context, prompt)

            # Apply quality and length adjustments
            response_content = self._adjust_response_quality(response_content)

            # Track conversation
            self.conversation_history.append(
                {
                    "prompt": prompt,
                    "response": response_content,
                    "timestamp": time.time(),
                    "context": context,
                }
            )

            return MockResponse(
                content=response_content,
                model=self.model_name,
                provider=self.provider_name,
                tokens_used=self._estimate_tokens(response_content),
                finish_reason="completed",
                metadata={
                    "personality": self.config.personality,
                    "quality": self.config.response_quality,
                    "context_type": context.get("type", "general"),
                    "creativity_applied": self.config.creativity_level,
                },
            )

        except Exception as e:
            log_system_event("adapter_error", f"Mock adapter error: {e!s}")
            raise ModelResponseError(f"Mock adapter error: {e!s}") from e

    async def _simulate_processing_time(self):
        """Simulate realistic API response time."""
        base_time = self.config.response_time_ms / 1000.0
        # Add realistic variance (±20%)
        variance = base_time * 0.2 * (random.random() - 0.5)
        actual_time = max(0.1, base_time + variance)
        await asyncio.sleep(actual_time)

    def _analyze_prompt(self, prompt: str, **kwargs) -> dict[str, Any]:
        """Analyze prompt to determine response context and style."""
        prompt_lower = prompt.lower()

        context = {
            "type": "general",
            "focus": "content",
            "tone": "neutral",
            "characters": [],
            "requires_dialogue": False,
            "requires_action": False,
        }

        # Detect content type
        if any(word in prompt_lower for word in ["continue", "content", "compose"]):
            context["type"] = "content_continuation"
        elif any(word in prompt_lower for word in ["entity", "dialogue", "said", "speak"]):
            context["type"] = "entity_interaction"

        # Extract participant mentions
        for char in self.content_library["characters"]:
            if char.lower() in prompt_lower:
                context["characters"].append(char)

        return context

    async def _generate_contextual_response(self, context: dict[str, Any], prompt: str) -> str:
        """Generate response based on analyzed context."""
        response_type = context["type"]

        if response_type == "unit_continuation":
            return self._generate_story_continuation(context)
        if response_type == "participant_interaction":
            return self._generate_character_interaction(context)
        if response_type == "environment_description":
            return self._generate_scene_description(context)
        if response_type == "sequence_development":
            return self._generate_narrative_development(context)
        return self._generate_general_response(context, prompt)

    def _generate_story_continuation(self, context: dict[str, Any]) -> str:
        """Generate continuation based on personality and context."""
        if self.config.personality == "creative":
            return self._creative_story_response(context)
        if self.config.personality == "analytical":
            return self._analytical_story_response(context)
        if self.config.personality == "concise":
            return self._concise_story_response(context)
        # balanced
        return self._balanced_story_response(context)

    def _creative_story_response(self, context: dict[str, Any]) -> str:
        """Generate creative, imaginative content."""
        # Ensure we have characters to choose from
        choices = context.get("characters") or self.content_library["characters"]
        entity = random.choice(choices)
        setting = random.choice(self.content_library["settings"])
        emotion = random.choice(self.content_library["emotions"])

        creative_elements = [
            f"In a moment that would change everything, {entity} discovered "
            f"something extraordinary in the {setting}.",
            f"The {emotion} expression on {entity}'s face told a tale of its own.",
            "What happened next defied all expectations—the very air seemed to shimmer with possibility.",
            f"Time seemed to slow as {entity} realized the true significance of this moment.",
        ]

        return " ".join(random.sample(creative_elements, k=random.randint(2, 3)))

    def _analytical_story_response(self, context: dict[str, Any]) -> str:
        """Generate logical, structured content."""
        return (
            "The sequence of events followed a clear pattern. First, the protagonist "
            "assessed their situation methodically. Then, they weighed their options "
            "carefully, considering both immediate and long-term consequences. "
            "Finally, they made a calculated decision that would advance their objectives "
            "while minimizing potential risks."
        )

    def _concise_story_response(self, context: dict[str, Any]) -> str:
        """Generate brief, focused content."""
        choices = context.get("characters") or ["the protagonist"]
        entity = random.choice(choices)
        action = random.choice(self.content_library["actions"])
        return f"{entity} moved forward, {action}. The path ahead was clear."

    def _balanced_story_response(self, context: dict[str, Any]) -> str:
        """Generate balanced content with good pacing."""
        choices = context.get("characters") or self.content_library["characters"]
        entity = random.choice(choices)
        setting = random.choice(self.content_library["settings"])
        emotion = random.choice(self.content_library["emotions"])

        return (
            f"As {entity} stepped into the {setting}, they felt {emotion}. "
            f"The events of the past few hours had led to this moment, and now "
            f"they faced a choice that would determine their future. "
            f"With careful consideration, they decided to move forward."
        )

    def _generate_character_interaction(self, context: dict[str, Any]) -> str:
        """Generate participant dialogue and interaction."""
        choices = context.get("characters") or self.content_library["characters"]
        entity = random.choice(choices)
        dialogue_tag = random.choice(self.content_library["dialogue_tags"])

        dialogue_options = [
            f'"We need to find another way," {entity} {dialogue_tag}.',
            f'"I understand now," {entity} replied thoughtfully.',
            f'"This changes everything," {entity} admitted.',
            f'"Are you certain about this?" {entity} asked carefully.',
        ]

        return random.choice(dialogue_options)

    def _generate_scene_description(self, context: dict[str, Any]) -> str:
        """Generate environmental and setting descriptions."""
        setting = random.choice(self.content_library["settings"])

        return (
            f"The {setting} stretched out before them, filled with "
            f"countless details that brought the environment to life. "
            f"Every element contributed to the overall atmosphere."
        )

    def _generate_narrative_development(self, context: dict[str, Any]) -> str:
        """Generate plot advancement and development."""
        developments = [
            "A new revelation emerged that would reshape their understanding.",
            "The pieces began falling into place, revealing a larger pattern.",
            "An unexpected development changed the course of events.",
            "The situation evolved in ways no one had anticipated.",
        ]

        return random.choice(developments)

    def _generate_general_response(self, context: dict[str, Any], prompt: str) -> str:
        """Generate general response for unspecified contexts."""
        return (
            "I understand your request. Based on the context provided, "
            "I can help develop this context further with interesting "
            "possibilities for participant development and plot advancement."
        )

    def _adjust_response_quality(self, content: str) -> str:
        """Adjust response based on quality settings."""
        if self.config.response_quality == "high":
            # Add more detail and polish
            if len(content.split()) < 50:
                content += " The richness of the moment was enhanced by subtle details."
        elif self.config.response_quality == "low":
            # Simplify response
            sentences = content.split(". ")
            content = ". ".join(sentences[:2]) + "."

        # Adjust length
        if self.config.response_length == "short":
            sentences = content.split(". ")
            content = sentences[0] + "."
        elif self.config.response_length == "long":
            content += " This opened new avenues for exploration within the broader context."

        return content

    def _estimate_tokens(self, content: str) -> int:
        """Estimate token count for response."""
        # Rough approximation: 1 token ≈ 0.75 words
        word_count = len(content.split())
        return int(word_count / 0.75)

    async def validate_connection(self) -> bool:
        """Validate adapter connection (always succeeds for mock)."""
        return True

    def get_supported_features(self) -> list[str]:
        """Return list of supported features."""
        return [
            "text_generation",
            "conversation_tracking",
            "configurable_personality",
            "quality_adjustment",
            "error_simulation",
        ]

    def get_model_info(self) -> dict[str, Any]:
        """Return model information."""
        return {
            "name": self.model_name,
            "provider": self.provider_name,
            "type": "mock",
            "personality": self.config.personality,
            "response_quality": self.config.response_quality,
            "features": self.get_supported_features(),
            "configuration": {
                "creativity_level": self.config.creativity_level,
                "consistency_level": self.config.consistency_level,
                "average_response_time_ms": self.config.response_time_ms,
            },
        }
