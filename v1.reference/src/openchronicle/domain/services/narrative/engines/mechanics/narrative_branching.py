"""
OpenChronicle Core - Narrative Branching Component

Handles narrative branch creation and management.
Extracted from NarrativeDiceEngine for modular architecture.

Author: OpenChronicle Development Team
"""

import random
from datetime import datetime
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_error_with_context
from openchronicle.shared.logging_system import log_system_event

from ...shared.narrative_exceptions import NarrativeSystemError
from .mechanics_models import CharacterPerformance
from .mechanics_models import NarrativeBranch
from .mechanics_models import OutcomeType
from .mechanics_models import ResolutionResult
from .mechanics_models import ResolutionType


class NarrativeBranchingEngine:
    """Handles narrative branch creation and path management."""

    def __init__(self):
        """Initialize narrative branching engine."""
        self.logger = get_logger("openchronicle.mechanics.branching")

        # Branch templates for different outcome types
        self.outcome_templates = {
            OutcomeType.CRITICAL_SUCCESS: {
                "probability_boost": 0.3,
                "consequence_types": [
                    "major_benefit",
                    "skill_improvement",
                    "reputation_gain",
                ],
                "transition_types": ["advance_quickly", "unlock_special", "gain_ally"],
            },
            OutcomeType.SUCCESS: {
                "probability_boost": 0.1,
                "consequence_types": ["minor_benefit", "progress", "positive_outcome"],
                "transition_types": [
                    "advance_normally",
                    "continue_scene",
                    "resolve_conflict",
                ],
            },
            OutcomeType.PARTIAL_SUCCESS: {
                "probability_boost": 0.0,
                "consequence_types": [
                    "mixed_result",
                    "partial_progress",
                    "complication",
                ],
                "transition_types": [
                    "advance_cautiously",
                    "create_tension",
                    "add_challenge",
                ],
            },
            OutcomeType.FAILURE: {
                "probability_boost": -0.1,
                "consequence_types": ["setback", "minor_consequence", "delay"],
                "transition_types": [
                    "retry_needed",
                    "alternate_path",
                    "face_consequence",
                ],
            },
            OutcomeType.CRITICAL_FAILURE: {
                "probability_boost": -0.3,
                "consequence_types": ["major_setback", "injury", "equipment_loss"],
                "transition_types": [
                    "dramatic_change",
                    "emergency_response",
                    "seek_help",
                ],
            },
        }

        # Resolution type specific branches
        self.resolution_branches = {
            ResolutionType.SKILL_CHECK: {
                "success_branches": [
                    "demonstrate_expertise",
                    "teach_others",
                    "quick_solution",
                ],
                "failure_branches": [
                    "learn_lesson",
                    "seek_training",
                    "try_different_approach",
                ],
            },
            ResolutionType.COMBAT_ACTION: {
                "success_branches": [
                    "defeat_enemy",
                    "tactical_advantage",
                    "heroic_moment",
                ],
                "failure_branches": [
                    "tactical_retreat",
                    "injury_consequence",
                    "equipment_damage",
                ],
            },
            ResolutionType.SOCIAL_INTERACTION: {
                "success_branches": [
                    "build_relationship",
                    "gain_information",
                    "social_advantage",
                ],
                "failure_branches": [
                    "offend_character",
                    "misunderstanding",
                    "social_consequence",
                ],
            },
            ResolutionType.EXPLORATION: {
                "success_branches": [
                    "major_discovery",
                    "hidden_treasure",
                    "secret_knowledge",
                ],
                "failure_branches": ["get_lost", "trigger_trap", "waste_resources"],
            },
            ResolutionType.MAGICAL_ACTION: {
                "success_branches": [
                    "spectacular_effect",
                    "magical_insight",
                    "arcane_mastery",
                ],
                "failure_branches": [
                    "magical_mishap",
                    "spell_backfire",
                    "magical_exhaustion",
                ],
            },
        }

        log_system_event("narrative_branching_initialized", "Narrative branching engine ready")

    def create_narrative_branches(
        self,
        resolution_result: ResolutionResult,
        context: dict[str, Any] = None,
        max_branches: int = 3,
    ) -> list[NarrativeBranch]:
        """
        Create narrative branches based on resolution result.

        Args:
            resolution_result: The resolution that triggers branching
            context: Additional context for branch creation
            max_branches: Maximum number of branches to create

        Returns:
            List of narrative branches
        """
        if context is None:
            context = {}

        try:
            self.logger.log_info(
                "create_narrative_branches started",
                extra={
                    "component": "NarrativeBranchingEngine",
                    "phase": "create_branches:start",
                    "outcome": getattr(resolution_result.outcome, "name", str(resolution_result.outcome)),
                    "resolution_type": getattr(
                        resolution_result.resolution_type, "name", str(resolution_result.resolution_type)
                    ),
                    "character_id": getattr(resolution_result, "character_id", None),
                    "max_branches": max_branches,
                },
            )
            branches = []

            # Get templates for this outcome
            outcome_template = self.outcome_templates.get(
                resolution_result.outcome, self.outcome_templates[OutcomeType.SUCCESS]
            )

            # Get resolution-specific branches
            resolution_template = self.resolution_branches.get(
                resolution_result.resolution_type,
                {"success_branches": ["continue"], "failure_branches": ["retry"]},
            )

            # Determine if this was a success or failure
            is_success = resolution_result.outcome in [
                OutcomeType.CRITICAL_SUCCESS,
                OutcomeType.SUCCESS,
                OutcomeType.PARTIAL_SUCCESS,
            ]

            # Select appropriate branch templates
            branch_templates = (
                resolution_template["success_branches"] if is_success else resolution_template["failure_branches"]
            )

            # Create branches
            for i, template in enumerate(branch_templates[:max_branches]):
                branch = self._create_branch_from_template(template, resolution_result, outcome_template, context, i)
                branches.append(branch)

            # Add a default "continue" branch if needed
            if len(branches) < 2:
                default_branch = self._create_default_branch(resolution_result, context)
                branches.append(default_branch)

            # Normalize probabilities
            self._normalize_branch_probabilities(branches)

            log_system_event(
                "narrative_branches_created",
                f"Created {len(branches)} branches for {resolution_result.outcome.value}",
            )
            self.logger.log_info(
                "create_narrative_branches completed",
                extra={
                    "component": "NarrativeBranchingEngine",
                    "phase": "create_branches:complete",
                    "branch_count": len(branches),
                },
            )

        except (ValueError, TypeError) as e:
            log_error_with_context(
                e,
                context={
                    "component": "NarrativeBranchingEngine",
                    "phase": "create_branches:validation_error",
                    "outcome": getattr(resolution_result.outcome, "name", str(resolution_result.outcome)),
                    "character_id": getattr(resolution_result, "character_id", None),
                },
            )
            raise NarrativeSystemError(f"Branch parameter validation error: {e}") from e
        except (AttributeError, KeyError) as e:
            log_error_with_context(
                e,
                context={
                    "component": "NarrativeBranchingEngine",
                    "phase": "create_branches:data_structure_error",
                    "outcome": getattr(resolution_result.outcome, "name", str(resolution_result.outcome)),
                    "character_id": getattr(resolution_result, "character_id", None),
                },
            )
            raise NarrativeSystemError(f"Branch data structure error: {e}") from e
        except Exception as e:
            log_error_with_context(
                e,
                context={
                    "component": "NarrativeBranchingEngine",
                    "phase": "create_branches:exception",
                    "outcome": getattr(resolution_result.outcome, "name", str(resolution_result.outcome)),
                    "resolution_type": getattr(
                        resolution_result.resolution_type, "name", str(resolution_result.resolution_type)
                    ),
                    "character_id": getattr(resolution_result, "character_id", None),
                },
            )
            raise NarrativeSystemError(f"Branch creation failed: {e}") from e
        else:
            return branches

    def _create_branch_from_template(
        self,
        template: str,
        resolution_result: ResolutionResult,
        outcome_template: dict[str, Any],
        context: dict[str, Any],
        index: int,
    ) -> NarrativeBranch:
        """Create a branch from a template."""

        # Generate branch ID
        branch_id = f"{resolution_result.character_id}_{template}_{index}_{datetime.now().strftime('%H%M%S')}"

        # Base probability with outcome modifier
        base_probability = 0.5 + outcome_template.get("probability_boost", 0.0)

        # Adjust probability based on success margin
        margin_adjustment = min(0.2, abs(resolution_result.success_margin) * 0.01)
        if resolution_result.success_margin > 0:
            base_probability += margin_adjustment
        else:
            base_probability -= margin_adjustment

        # Clamp probability
        probability = max(0.1, min(0.9, base_probability))

        # Generate description
        description = self._generate_branch_description(template, resolution_result, context)

        # Create consequences based on outcome
        consequences = self._generate_consequences(template, resolution_result, outcome_template)

        # Create stat changes
        stat_changes = self._generate_stat_changes(template, resolution_result, outcome_template)

        # Scene transitions
        scene_transitions = self._generate_scene_transitions(template, resolution_result, context)

        return NarrativeBranch(
            branch_id=branch_id,
            description=description,
            probability=probability,
            stat_changes=stat_changes,
            scene_transitions=scene_transitions,
            character_consequences=consequences,
            required_outcome=resolution_result.outcome,
        )

    def _generate_branch_description(
        self,
        template: str,
        resolution_result: ResolutionResult,
        context: dict[str, Any],
    ) -> str:
        """Generate descriptive text for a branch."""

        # Template descriptions
        descriptions = {
            "demonstrate_expertise": f"Your skill shines through, impressively {template.replace('_', ' ')}",
            "teach_others": "You take the opportunity to share your knowledge",
            "quick_solution": "You find an efficient and elegant solution",
            "learn_lesson": "This setback provides valuable learning experience",
            "seek_training": "You realize you need to improve your skills",
            "try_different_approach": "You consider alternative methods",
            "defeat_enemy": "Your combat prowess overwhelms your opponent",
            "tactical_advantage": "You gain strategic position in the fight",
            "heroic_moment": "You perform a remarkable feat of combat",
            "tactical_retreat": "Discretion proves the better part of valor",
            "injury_consequence": "The failed action results in injury",
            "equipment_damage": "Your equipment suffers in the attempt",
            "build_relationship": "This interaction strengthens your bond",
            "gain_information": "You learn something valuable from this exchange",
            "social_advantage": "You gain social standing or influence",
            "offend_character": "Your words or actions cause offense",
            "misunderstanding": "Communication breaks down or is misinterpreted",
            "social_consequence": "There are social repercussions to consider",
            "major_discovery": "You uncover something truly significant",
            "hidden_treasure": "Your exploration reveals valuable rewards",
            "secret_knowledge": "You gain access to hidden information",
            "get_lost": "You lose your way in unfamiliar territory",
            "trigger_trap": "Your exploration activates a dangerous mechanism",
            "waste_resources": "The search consumes time and supplies",
            "spectacular_effect": "The magic manifests beyond expectations",
            "magical_insight": "You gain deeper understanding of the arcane",
            "arcane_mastery": "Your magical abilities improve significantly",
            "magical_mishap": "The spell goes awry with unexpected results",
            "spell_backfire": "The magic turns against you",
            "magical_exhaustion": "The attempt drains your magical energies",
        }

        base_description = descriptions.get(
            template,
            f"The {resolution_result.resolution_type.value.replace('_', ' ')} has consequences",
        )

        # Add context-specific details
        character_name = context.get("character_name", "character")
        location = context.get("current_location", "area")

        if "character_name" in context:
            base_description = base_description.replace("You", character_name)
            base_description = base_description.replace("Your", f"{character_name}'s")

        return base_description

    def _generate_consequences(
        self,
        template: str,
        resolution_result: ResolutionResult,
        outcome_template: dict[str, Any],
    ) -> list[str]:
        """Generate consequences for the branch."""
        consequences = []

        consequence_types = outcome_template.get("consequence_types", [])

        for consequence_type in consequence_types[:2]:  # Limit to 2 consequences
            if consequence_type == "major_benefit":
                consequences.append("Significant positive outcome")
            elif consequence_type == "skill_improvement":
                consequences.append("Skill development opportunity")
            elif consequence_type == "reputation_gain":
                consequences.append("Enhanced reputation")
            elif consequence_type == "minor_benefit":
                consequences.append("Small positive effect")
            elif consequence_type == "progress":
                consequences.append("Advancement toward goal")
            elif consequence_type == "mixed_result":
                consequences.append("Both positive and negative effects")
            elif consequence_type == "complication":
                consequences.append("New challenge emerges")
            elif consequence_type == "setback":
                consequences.append("Temporary obstacle")
            elif consequence_type == "major_setback":
                consequences.append("Significant hindrance")
            elif consequence_type == "injury":
                consequences.append("Physical harm")

        return consequences

    def _generate_stat_changes(
        self,
        template: str,
        resolution_result: ResolutionResult,
        outcome_template: dict[str, Any],
    ) -> dict[str, int]:
        """Generate stat changes for the branch."""
        stat_changes = {}

        # Base stat changes based on outcome
        if resolution_result.outcome == OutcomeType.CRITICAL_SUCCESS:
            stat_changes["experience"] = random.randint(15, 25)
            stat_changes["confidence"] = random.randint(2, 5)
        elif resolution_result.outcome == OutcomeType.SUCCESS:
            stat_changes["experience"] = random.randint(8, 15)
            stat_changes["confidence"] = random.randint(1, 3)
        elif resolution_result.outcome == OutcomeType.PARTIAL_SUCCESS:
            stat_changes["experience"] = random.randint(3, 8)
        elif resolution_result.outcome == OutcomeType.FAILURE:
            stat_changes["experience"] = random.randint(1, 5)
            stat_changes["confidence"] = random.randint(-2, 0)
        elif resolution_result.outcome == OutcomeType.CRITICAL_FAILURE:
            stat_changes["confidence"] = random.randint(-5, -2)

        # Template-specific changes
        if "expertise" in template or "mastery" in template:
            skill_bonus = random.randint(1, 3)
            stat_changes[f"{resolution_result.resolution_type.value}_skill"] = skill_bonus

        if "injury" in template:
            stat_changes["health"] = random.randint(-10, -5)

        if "treasure" in template:
            stat_changes["wealth"] = random.randint(10, 100)

        return stat_changes

    def _generate_scene_transitions(
        self,
        template: str,
        resolution_result: ResolutionResult,
        context: dict[str, Any],
    ) -> list[str]:
        """Generate scene transitions for the branch."""
        transitions = []

        # Common transitions based on template
        if "advance" in template:
            transitions.append("progress_to_next_scene")
        elif "retreat" in template:
            transitions.append("return_to_safe_location")
        elif "discovery" in template:
            transitions.append("explore_discovery")
        elif "social" in template:
            transitions.append("continue_social_interaction")

        # Context-based transitions
        current_scene = context.get("current_scene", "")
        if current_scene:
            if "combat" in current_scene.lower():
                if resolution_result.outcome in [
                    OutcomeType.SUCCESS,
                    OutcomeType.CRITICAL_SUCCESS,
                ]:
                    transitions.append("end_combat_victorious")
                else:
                    transitions.append("continue_combat_defensively")
            elif "exploration" in current_scene.lower():
                transitions.append("continue_exploration")

        return transitions if transitions else ["continue_current_scene"]

    def _create_default_branch(self, resolution_result: ResolutionResult, context: dict[str, Any]) -> NarrativeBranch:
        """Create a default continuation branch."""
        branch_id = f"default_{resolution_result.character_id}_{datetime.now().strftime('%H%M%S')}"

        return NarrativeBranch(
            branch_id=branch_id,
            description="Continue with the natural flow of events",
            probability=0.6,
            scene_transitions=["continue_current_scene"],
            character_consequences=["Natural progression"],
        )

    def _normalize_branch_probabilities(self, branches: list[NarrativeBranch]):
        """Normalize branch probabilities to sum to 1.0."""
        if not branches:
            return

        total_probability = sum(branch.probability for branch in branches)

        if total_probability > 0:
            for branch in branches:
                branch.probability = branch.probability / total_probability

    def select_branch(
        self,
        branches: list[NarrativeBranch],
        character_performance: CharacterPerformance | None = None,
        bias_factor: float = 0.0,
    ) -> NarrativeBranch | None:
        """
        Select a branch from available options.

        Args:
            branches: Available branches
            character_performance: Character's recent performance
            bias_factor: Bias toward certain outcomes (-1.0 to 1.0)

        Returns:
            Selected branch or None
        """
        if not branches:
            return None

        # Adjust probabilities based on character performance
        adjusted_branches = []
        for branch in branches:
            adjusted_prob = branch.probability

            # Performance-based adjustments
            if character_performance:
                success_rate = character_performance.calculate_success_rate()
                if success_rate > 0.7:  # High performer
                    if branch.required_outcome in [
                        OutcomeType.SUCCESS,
                        OutcomeType.CRITICAL_SUCCESS,
                    ]:
                        adjusted_prob *= 1.2
                elif success_rate < 0.3:  # Struggling performer
                    if branch.required_outcome in [
                        OutcomeType.FAILURE,
                        OutcomeType.CRITICAL_FAILURE,
                    ]:
                        adjusted_prob *= 1.2

            # Apply bias factor
            if bias_factor > 0:  # Bias toward success
                if branch.required_outcome in [
                    OutcomeType.SUCCESS,
                    OutcomeType.CRITICAL_SUCCESS,
                ]:
                    adjusted_prob *= 1 + bias_factor
            elif bias_factor < 0:  # Bias toward failure
                if branch.required_outcome in [
                    OutcomeType.FAILURE,
                    OutcomeType.CRITICAL_FAILURE,
                ]:
                    adjusted_prob *= 1 + abs(bias_factor)

            adjusted_branches.append((branch, adjusted_prob))

        # Normalize adjusted probabilities
        total_prob = sum(prob for _, prob in adjusted_branches)
        if total_prob <= 0:
            return random.choice(branches)

        # Select branch using weighted random choice
        rand_val = random.random() * total_prob
        cumulative = 0.0

        for branch, prob in adjusted_branches:
            cumulative += prob
            if rand_val <= cumulative:
                return branch

        # Fallback to last branch
        return adjusted_branches[-1][0] if adjusted_branches else branches[-1]

    def evaluate_branch_requirements(self, branch: NarrativeBranch, character_state: dict[str, Any]) -> bool:
        """
        Check if character meets branch requirements.

        Args:
            branch: Branch to evaluate
            character_state: Current character state

        Returns:
            True if requirements are met
        """
        # Check required skills
        for skill, required_level in branch.required_skills.items():
            character_skill = character_state.get("skills", {}).get(skill, 0)
            if character_skill < required_level:
                return False

        # Check required items
        character_items = character_state.get("inventory", [])
        for required_item in branch.required_items:
            if required_item not in character_items:
                return False

        return True
