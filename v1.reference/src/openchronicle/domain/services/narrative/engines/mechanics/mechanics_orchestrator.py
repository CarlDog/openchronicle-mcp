"""
OpenChronicle Core - Mechanics Orchestrator

Main orchestrator for narrative mechanics system.
Coordinates dice engine, branching, and resolution components.

Author: OpenChronicle Development Team
"""

from datetime import datetime
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_error_with_context
from openchronicle.shared.logging_system import log_system_event

from .dice_engine import DiceEngine
from .mechanics_models import CharacterPerformance
from .mechanics_models import DifficultyLevel
from .mechanics_models import MechanicsRequest
from .mechanics_models import MechanicsResult
from .mechanics_models import NarrativeBranch
from .mechanics_models import OutcomeType
from .mechanics_models import ResolutionConfig
from .mechanics_models import ResolutionResult
from .mechanics_models import ResolutionType
from .narrative_branching import NarrativeBranchingEngine


class MechanicsOrchestrator:
    """Main orchestrator for narrative mechanics operations."""

    def __init__(self, config: ResolutionConfig | None = None):
        """
        Initialize mechanics orchestrator.

        Args:
            config: Optional resolution configuration
        """
        self.config = config or ResolutionConfig()
        self.logger = get_logger("openchronicle.mechanics")

        # Initialize components
        self.dice_engine = DiceEngine(self.config)
        self.branching_engine = NarrativeBranchingEngine()

        # Performance tracking
        self.character_performance: dict[str, CharacterPerformance] = {}

        # Metrics and statistics
        self.operation_count = 0
        self.success_count = 0
        self.error_count = 0

        log_system_event("mechanics_orchestrator_initialized", "Mechanics orchestrator ready")

    async def resolve_action(
        self,
        request: MechanicsRequest,
        character_state: dict[str, Any] = None,
        create_branches: bool = True,
    ) -> MechanicsResult:
        """
        Resolve a narrative action using dice mechanics.

        Args:
            request: The mechanics request
            character_state: Current character state
            create_branches: Whether to create narrative branches

        Returns:
            Mechanics result with resolution and branches
        """
        if character_state is None:
            character_state = {}

        try:
            self.operation_count += 1

            # Get character skill and modifiers
            character_skill = self._get_character_skill(request.character_id, request.resolution_type, character_state)

            # Determine difficulty
            difficulty_dc = self._determine_difficulty(request)

            # Roll dice
            dice_roll = self.dice_engine.roll_d20(
                modifier=sum(request.modifiers.values()),
                advantage=request.advantage,
                disadvantage=request.disadvantage,
            )

            # Calculate result
            success, margin, outcome = self.dice_engine.calculate_difficulty_check(
                dice_roll=dice_roll,
                difficulty=difficulty_dc,
                character_skill=character_skill,
                situation_modifiers=request.modifiers,
            )

            # Create resolution result
            resolution_result = ResolutionResult(
                resolution_type=request.resolution_type,
                outcome=outcome,
                dice_roll=dice_roll,
                difficulty_check=difficulty_dc,
                success_margin=margin,
                character_id=request.character_id,
                character_skill=character_skill,
                situation_modifiers=request.modifiers,
                timestamp=datetime.now().isoformat(),
                scene_context=request.context,
            )

            # Generate narrative impact
            resolution_result.narrative_impact = self._generate_narrative_impact(resolution_result, character_state)

            # Generate consequences and benefits
            (
                resolution_result.consequences,
                resolution_result.benefits,
            ) = self._generate_consequences_and_benefits(resolution_result, character_state)

            # Create branches if requested
            branches = []
            if create_branches:
                branches = self.branching_engine.create_narrative_branches(
                    resolution_result=resolution_result,
                    context=request.context,
                    max_branches=3,
                )

            # Update character performance
            self._update_character_performance(request.character_id, resolution_result)

            # Generate narrative prompt
            narrative_prompt = await self._generate_narrative_prompt(resolution_result, branches, character_state)

            # Create result
            result = MechanicsResult(
                request=request,
                resolution_result=resolution_result,
                narrative_branches=branches,
                success=True,
                narrative_prompt=narrative_prompt,
                performance_data=self._get_performance_summary(request.character_id),
            )

            self.success_count += 1

            log_system_event(
                "action_resolved",
                f"Resolved {request.resolution_type.value} for {request.character_id}: {outcome.value}",
            )

        except Exception as e:
            self.error_count += 1
            log_error_with_context(
                e,
                context={
                    "component": "MechanicsOrchestrator",
                    "phase": "resolve_action",
                    "character_id": getattr(request, "character_id", None),
                    "resolution_type": getattr(getattr(request, "resolution_type", None), "value", None),
                },
            )

            return MechanicsResult(request=request, success=False, error_message=str(e))
        else:
            return result

    async def create_narrative_branches(
        self,
        resolution_result: ResolutionResult,
        context: dict[str, Any] = None,
        max_branches: int = 3,
    ) -> list[NarrativeBranch]:
        """Create narrative branches for a resolution result."""
        try:
            return self.branching_engine.create_narrative_branches(
                resolution_result=resolution_result,
                context=context or {},
                max_branches=max_branches,
            )
        except Exception as e:
            log_error_with_context(
                e,
                context={
                    "component": "MechanicsOrchestrator",
                    "phase": "create_narrative_branches",
                    "character_id": getattr(resolution_result, "character_id", None),
                    "max_branches": max_branches,
                },
            )
            return []

    async def simulate_action(self, request: MechanicsRequest, iterations: int = 100) -> dict[str, Any]:
        """
        Simulate an action multiple times for statistical analysis.

        Args:
            request: The mechanics request
            iterations: Number of simulations

        Returns:
            Simulation statistics
        """
        try:
            results = []
            outcomes = dict.fromkeys(OutcomeType, 0)

            for _ in range(iterations):
                # Create a temporary copy of the request
                sim_request = MechanicsRequest(
                    operation_type="simulate",
                    resolution_type=request.resolution_type,
                    character_id=request.character_id,
                    difficulty=request.difficulty,
                    modifiers=request.modifiers.copy(),
                    advantage=request.advantage,
                    disadvantage=request.disadvantage,
                )

                # Run simulation
                result = await self.resolve_action(sim_request, create_branches=False)
                if result.success and result.resolution_result:
                    results.append(result.resolution_result)
                    outcomes[result.resolution_result.outcome] += 1

            # Calculate statistics
            if results:
                success_rate = sum(
                    1
                    for r in results
                    if r.outcome
                    in [
                        OutcomeType.SUCCESS,
                        OutcomeType.CRITICAL_SUCCESS,
                        OutcomeType.PARTIAL_SUCCESS,
                    ]
                ) / len(results)

                average_roll = sum(r.dice_roll.total for r in results) / len(results)
                average_margin = sum(r.success_margin for r in results) / len(results)
            else:
                success_rate = 0.0
                average_roll = 0.0
                average_margin = 0.0

            return {
                "iterations": iterations,
                "success_rate": success_rate,
                "average_roll": average_roll,
                "average_margin": average_margin,
                "outcome_distribution": {k.value: v for k, v in outcomes.items()},
                "sample_results": [r.to_dict() for r in results[:10]],
            }

        except Exception as e:
            log_error_with_context(
                e,
                context={
                    "component": "MechanicsOrchestrator",
                    "phase": "simulate_action",
                    "character_id": getattr(request, "character_id", None),
                    "iterations": iterations,
                },
            )
            return {"error": str(e)}

    def _get_character_skill(
        self,
        character_id: str,
        resolution_type: ResolutionType,
        character_state: dict[str, Any],
    ) -> int:
        """Get character skill for resolution type."""
        skills = character_state.get("skills", {})

        # Map resolution types to skill names
        skill_mappings = {
            ResolutionType.SKILL_CHECK: "general",
            ResolutionType.COMBAT_ACTION: "combat",
            ResolutionType.SOCIAL_INTERACTION: "social",
            ResolutionType.EXPLORATION: "exploration",
            ResolutionType.CREATIVE_ACTION: "creativity",
            ResolutionType.MENTAL_CHALLENGE: "intelligence",
            ResolutionType.PHYSICAL_CHALLENGE: "athletics",
            ResolutionType.MAGICAL_ACTION: "magic",
            ResolutionType.STEALTH_ACTION: "stealth",
            ResolutionType.SURVIVAL_ACTION: "survival",
        }

        skill_name = skill_mappings.get(resolution_type, "general")
        return skills.get(skill_name, 0)

    def _determine_difficulty(self, request: MechanicsRequest) -> int:
        """Determine difficulty DC for the request."""
        if request.difficulty:
            return self.dice_engine.get_difficulty_dc(request.difficulty)

        # Default difficulty based on resolution type
        default_difficulties = {
            ResolutionType.SKILL_CHECK: DifficultyLevel.MODERATE,
            ResolutionType.COMBAT_ACTION: DifficultyLevel.HARD,
            ResolutionType.SOCIAL_INTERACTION: DifficultyLevel.MODERATE,
            ResolutionType.EXPLORATION: DifficultyLevel.MODERATE,
            ResolutionType.MAGICAL_ACTION: DifficultyLevel.HARD,
            ResolutionType.LUCK_CHECK: DifficultyLevel.MODERATE,
        }

        default_difficulty = default_difficulties.get(request.resolution_type, DifficultyLevel.MODERATE)

        return self.dice_engine.get_difficulty_dc(default_difficulty)

    def _generate_narrative_impact(self, resolution_result: ResolutionResult, character_state: dict[str, Any]) -> str:
        """Generate narrative impact description."""
        impact_templates = {
            OutcomeType.CRITICAL_SUCCESS: [
                "The action succeeds spectacularly, exceeding all expectations",
                "An exceptional performance that will be remembered",
                "Perfect execution with outstanding results",
            ],
            OutcomeType.SUCCESS: [
                "The action succeeds as intended",
                "A solid performance with positive results",
                "The goal is achieved effectively",
            ],
            OutcomeType.PARTIAL_SUCCESS: [
                "The action succeeds, but with complications",
                "Progress is made, though not without challenges",
                "Mixed results that require further action",
            ],
            OutcomeType.FAILURE: [
                "The action fails to achieve its goal",
                "Despite effort, the attempt falls short",
                "The approach proves unsuccessful",
            ],
            OutcomeType.CRITICAL_FAILURE: [
                "The action fails catastrophically",
                "Not only does it fail, but creates new problems",
                "A dramatic setback with serious consequences",
            ],
        }

        templates = impact_templates.get(resolution_result.outcome, ["Something happens"])
        import random

        return random.choice(templates)

    def _generate_consequences_and_benefits(
        self, resolution_result: ResolutionResult, character_state: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Generate consequences and benefits for the resolution."""
        consequences = []
        benefits = []

        if resolution_result.outcome == OutcomeType.CRITICAL_SUCCESS:
            benefits.extend(
                [
                    "Significant skill improvement",
                    "Enhanced reputation",
                    "Bonus rewards or opportunities",
                ]
            )
        elif resolution_result.outcome == OutcomeType.SUCCESS:
            benefits.extend(["Progress toward goals", "Positive recognition", "Standard rewards"])
        elif resolution_result.outcome == OutcomeType.PARTIAL_SUCCESS:
            benefits.append("Partial progress made")
            consequences.append("Additional challenges arise")
        elif resolution_result.outcome == OutcomeType.FAILURE:
            consequences.extend(
                [
                    "Time and resources lost",
                    "Need to reassess approach",
                    "Temporary setback",
                ]
            )
        elif resolution_result.outcome == OutcomeType.CRITICAL_FAILURE:
            consequences.extend(
                [
                    "Significant setback",
                    "Potential injury or loss",
                    "Reputation damage",
                    "Need for recovery time",
                ]
            )

        return consequences, benefits

    def _update_character_performance(self, character_id: str, resolution_result: ResolutionResult):
        """Update character performance tracking."""
        if character_id not in self.character_performance:
            self.character_performance[character_id] = CharacterPerformance(character_id=character_id)

        perf = self.character_performance[character_id]
        perf.total_actions += 1

        # Update success/failure counts
        if resolution_result.outcome in [
            OutcomeType.SUCCESS,
            OutcomeType.CRITICAL_SUCCESS,
            OutcomeType.PARTIAL_SUCCESS,
        ]:
            perf.successes += 1
        else:
            perf.failures += 1

        # Update critical counts
        if resolution_result.outcome == OutcomeType.CRITICAL_SUCCESS:
            perf.critical_successes += 1
        elif resolution_result.outcome == OutcomeType.CRITICAL_FAILURE:
            perf.critical_failures += 1

        # Update skill tracking
        skill_type = resolution_result.resolution_type.value
        perf.skill_usage[skill_type] = perf.skill_usage.get(skill_type, 0) + 1

        if resolution_result.outcome in [
            OutcomeType.SUCCESS,
            OutcomeType.CRITICAL_SUCCESS,
        ]:
            perf.skill_successes[skill_type] = perf.skill_successes.get(skill_type, 0) + 1

        # Update recent rolls (keep last 10)
        perf.recent_rolls.append(resolution_result)
        if len(perf.recent_rolls) > 10:
            perf.recent_rolls.pop(0)

        # Update average roll
        if perf.recent_rolls:
            perf.average_roll = sum(r.dice_roll.total for r in perf.recent_rolls) / len(perf.recent_rolls)

    async def _generate_narrative_prompt(
        self,
        resolution_result: ResolutionResult,
        branches: list[NarrativeBranch],
        character_state: dict[str, Any],
    ) -> str:
        """Generate narrative prompt for the resolution."""
        # This would integrate with the model manager in a real implementation
        # For now, return a basic prompt structure

        prompt_parts = [
            f"Resolution: {resolution_result.narrative_impact}",
            f"Outcome: {resolution_result.outcome.value.replace('_', ' ').title()}",
            f"Roll: {resolution_result.dice_roll.total} vs DC {resolution_result.difficulty_check}",
        ]

        if resolution_result.benefits:
            prompt_parts.append(f"Benefits: {', '.join(resolution_result.benefits)}")

        if resolution_result.consequences:
            prompt_parts.append(f"Consequences: {', '.join(resolution_result.consequences)}")

        if branches:
            prompt_parts.append("Possible narrative directions:")
            for i, branch in enumerate(branches[:3], 1):
                prompt_parts.append(f"{i}. {branch.description}")

        return "\n".join(prompt_parts)

    def _get_performance_summary(self, character_id: str) -> dict[str, Any]:
        """Get performance summary for character."""
        if character_id not in self.character_performance:
            return {}

        perf = self.character_performance[character_id]

        return {
            "total_actions": perf.total_actions,
            "success_rate": perf.calculate_success_rate(),
            "average_roll": perf.average_roll,
            "critical_successes": perf.critical_successes,
            "critical_failures": perf.critical_failures,
            "recent_performance": len(
                [r for r in perf.recent_rolls[-5:] if r.outcome in [OutcomeType.SUCCESS, OutcomeType.CRITICAL_SUCCESS]]
            ),
        }

    def get_orchestrator_stats(self) -> dict[str, Any]:
        """Get orchestrator performance statistics."""
        return {
            "total_operations": self.operation_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_count / max(1, self.operation_count),
            "characters_tracked": len(self.character_performance),
            "config": self.config.to_dict(),
        }

    async def cleanup(self):
        """Cleanup orchestrator resources."""
        log_system_event("mechanics_orchestrator_cleanup", "Cleaning up mechanics orchestrator")
        # Any cleanup tasks would go here
