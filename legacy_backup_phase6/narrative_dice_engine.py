"""
Narrative Dice Engine: Story-Driven Success/Failure System

This module implements an RPG-style success/failure engine for OpenChronicle that allows
characters to succeed or fail based on dice rolls, influenced by character stats.
Failures are narratively meaningful and open new branches in the story.

Key Features:
- Pluggable dice systems (d20, 2d10, d6, etc.)
- Character stat modifiers from Character Stat Engine
- Difficulty-based resolution with meaningful failure paths
- Integration with story branching and emotional consequences
- Configurable per-story enabling/disabling
- Narrative outcome generation for both success and failure
"""

import json
import logging
import random
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from enum import Enum
import math

# Setup logging
logger = logging.getLogger(__name__)

class DiceType(Enum):
    """Types of dice systems supported."""
    D6 = "d6"
    D10 = "d10"
    D12 = "d12"
    D20 = "d20"
    D100 = "d100"
    TWO_D10 = "2d10"
    THREE_D6 = "3d6"
    FOUR_D6_DROP_LOWEST = "4d6dl"

class ResolutionType(Enum):
    """Types of resolution checks."""
    SKILL_CHECK = "skill_check"
    PERSUASION = "persuasion"
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    INVESTIGATION = "investigation"
    PERCEPTION = "perception"
    STEALTH = "stealth"
    ATHLETICS = "athletics"
    CREATIVITY = "creativity"
    WILLPOWER = "willpower"
    KNOWLEDGE = "knowledge"
    SOCIAL = "social"
    COMBAT = "combat"
    MAGIC = "magic"
    SURVIVAL = "survival"

class DifficultyLevel(Enum):
    """Standard difficulty levels."""
    TRIVIAL = 5      # Almost impossible to fail
    EASY = 8         # Simple tasks
    MODERATE = 12    # Average difficulty
    HARD = 16        # Challenging tasks
    VERY_HARD = 20   # Expert-level difficulty
    LEGENDARY = 25   # Near-impossible tasks

class OutcomeType(Enum):
    """Types of resolution outcomes."""
    CRITICAL_FAILURE = "critical_failure"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    SUCCESS = "success"
    CRITICAL_SUCCESS = "critical_success"

@dataclass
class ResolutionResult:
    """Result of a narrative dice resolution."""
    resolution_id: str
    character_id: str
    resolution_type: ResolutionType
    dice_rolled: List[int]
    total_roll: int
    modifiers: Dict[str, int]
    final_result: int
    difficulty: int
    outcome: OutcomeType
    success: bool
    margin: int  # How much over/under the difficulty
    narrative_impact: str
    timestamp: datetime
    scene_context: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'resolution_id': self.resolution_id,
            'character_id': self.character_id,
            'resolution_type': self.resolution_type.value,
            'dice_rolled': self.dice_rolled,
            'total_roll': self.total_roll,
            'modifiers': self.modifiers,
            'final_result': self.final_result,
            'difficulty': self.difficulty,
            'outcome': self.outcome.value,
            'success': self.success,
            'margin': self.margin,
            'narrative_impact': self.narrative_impact,
            'timestamp': self.timestamp.isoformat(),
            'scene_context': self.scene_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ResolutionResult':
        """Create from dictionary."""
        return cls(
            resolution_id=data['resolution_id'],
            character_id=data['character_id'],
            resolution_type=ResolutionType(data['resolution_type']),
            dice_rolled=data['dice_rolled'],
            total_roll=data['total_roll'],
            modifiers=data['modifiers'],
            final_result=data['final_result'],
            difficulty=data['difficulty'],
            outcome=OutcomeType(data['outcome']),
            success=data['success'],
            margin=data['margin'],
            narrative_impact=data['narrative_impact'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            scene_context=data.get('scene_context', '')
        )

@dataclass
class ResolutionConfig:
    """Configuration for the narrative dice engine."""
    enabled: bool = True
    dice_type: DiceType = DiceType.D20
    modifier_tolerance: int = 3  # Max modifier from stats
    skill_dependency: bool = True  # Use character stats as modifiers
    failure_narrative_required: bool = True
    critical_range: int = 1  # Natural 1s and 20s (for d20)
    advantage_enabled: bool = True  # Roll twice, take higher
    disadvantage_enabled: bool = True  # Roll twice, take lower
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'enabled': self.enabled,
            'dice_type': self.dice_type.value,
            'modifier_tolerance': self.modifier_tolerance,
            'skill_dependency': self.skill_dependency,
            'failure_narrative_required': self.failure_narrative_required,
            'critical_range': self.critical_range,
            'advantage_enabled': self.advantage_enabled,
            'disadvantage_enabled': self.disadvantage_enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ResolutionConfig':
        """Create from dictionary."""
        return cls(
            enabled=data.get('enabled', True),
            dice_type=DiceType(data.get('dice_type', 'd20')),
            modifier_tolerance=data.get('modifier_tolerance', 3),
            skill_dependency=data.get('skill_dependency', True),
            failure_narrative_required=data.get('failure_narrative_required', True),
            critical_range=data.get('critical_range', 1),
            advantage_enabled=data.get('advantage_enabled', True),
            disadvantage_enabled=data.get('disadvantage_enabled', True)
        )

@dataclass
class NarrativeBranch:
    """Represents a story branch based on resolution outcome."""
    branch_id: str
    outcome_type: OutcomeType
    narrative_text: str
    emotional_impact: str = ""
    stat_changes: Dict[str, int] = field(default_factory=dict)
    scene_transitions: List[str] = field(default_factory=list)
    character_consequences: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'branch_id': self.branch_id,
            'outcome_type': self.outcome_type.value,
            'narrative_text': self.narrative_text,
            'emotional_impact': self.emotional_impact,
            'stat_changes': self.stat_changes,
            'scene_transitions': self.scene_transitions,
            'character_consequences': self.character_consequences
        }

class NarrativeDiceEngine:
    """
    Manages narrative dice rolls, success/failure resolution, and story branching.
    
    This engine provides RPG-style gameplay mechanics integrated with storytelling,
    where character stats influence outcomes and failures create meaningful story branches.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the narrative dice engine."""
        config_dict = config or {}
        self.config = ResolutionConfig.from_dict(config_dict)
        
        # Data storage
        self.resolution_history: List[ResolutionResult] = []
        self.narrative_branches: Dict[str, List[NarrativeBranch]] = {}
        self.character_performance: Dict[str, Dict[str, Any]] = {}
        
        # Dice rolling functions
        self.dice_functions: Dict[DiceType, Callable] = {
            DiceType.D6: self._roll_d6,
            DiceType.D10: self._roll_d10,
            DiceType.D12: self._roll_d12,
            DiceType.D20: self._roll_d20,
            DiceType.D100: self._roll_d100,
            DiceType.TWO_D10: self._roll_2d10,
            DiceType.THREE_D6: self._roll_3d6,
            DiceType.FOUR_D6_DROP_LOWEST: self._roll_4d6_drop_lowest
        }
        
        # Resolution type to stat mapping
        self.stat_mappings = {
            ResolutionType.PERSUASION: "charisma",
            ResolutionType.DECEPTION: "charisma",
            ResolutionType.INTIMIDATION: "charisma",
            ResolutionType.INVESTIGATION: "intelligence",
            ResolutionType.PERCEPTION: "perception",
            ResolutionType.STEALTH: "intelligence",
            ResolutionType.ATHLETICS: "willpower",
            ResolutionType.CREATIVITY: "creativity",
            ResolutionType.WILLPOWER: "willpower",
            ResolutionType.KNOWLEDGE: "intelligence",
            ResolutionType.SOCIAL: "charisma",
            ResolutionType.COMBAT: "courage",
            ResolutionType.SURVIVAL: "wisdom"
        }
    
    def resolve_action(self, character_id: str, resolution_type: ResolutionType,
                      difficulty: Union[int, DifficultyLevel], scene_context: str = "",
                      character_stats: Optional[Dict[str, int]] = None,
                      advantage: bool = False, disadvantage: bool = False) -> ResolutionResult:
        """Resolve a character action with dice roll and stat modifiers."""
        if not self.config.enabled:
            # Return automatic success if engine disabled
            return self._create_auto_success(character_id, resolution_type, difficulty, scene_context)
        
        # Convert difficulty level to number
        if isinstance(difficulty, DifficultyLevel):
            difficulty_value = difficulty.value
        else:
            difficulty_value = difficulty
        
        # Roll dice
        dice_rolled = self._roll_dice(advantage, disadvantage)
        total_roll = sum(dice_rolled)
        
        # Calculate modifiers
        modifiers = self._calculate_modifiers(character_id, resolution_type, character_stats)
        final_result = total_roll + sum(modifiers.values())
        
        # Determine outcome
        success = final_result >= difficulty_value
        margin = final_result - difficulty_value
        outcome = self._determine_outcome(dice_rolled, final_result, difficulty_value)
        
        # Generate narrative impact
        narrative_impact = self._generate_narrative_impact(
            character_id, resolution_type, outcome, margin, scene_context
        )
        
        # Create result
        result = ResolutionResult(
            resolution_id=f"res_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}",
            character_id=character_id,
            resolution_type=resolution_type,
            dice_rolled=dice_rolled,
            total_roll=total_roll,
            modifiers=modifiers,
            final_result=final_result,
            difficulty=difficulty_value,
            outcome=outcome,
            success=success,
            margin=margin,
            narrative_impact=narrative_impact,
            timestamp=datetime.now(),
            scene_context=scene_context
        )
        
        # Store result
        self.resolution_history.append(result)
        self._update_character_performance(result)
        
        logger.info(f"Resolution for {character_id}: {resolution_type.value} "
                   f"({final_result} vs {difficulty_value}) = {outcome.value}")
        
        return result
    
    def create_narrative_branches(self, resolution_type: ResolutionType, 
                                scene_context: str) -> Dict[OutcomeType, NarrativeBranch]:
        """Create narrative branches for different resolution outcomes."""
        branches = {}
        
        # Create branches for each possible outcome
        for outcome in OutcomeType:
            branch = NarrativeBranch(
                branch_id=f"branch_{scene_context}_{outcome.value}",
                outcome_type=outcome,
                narrative_text=self._generate_branch_narrative(resolution_type, outcome, scene_context),
                emotional_impact=self._get_emotional_impact(outcome),
                stat_changes=self._get_stat_changes(outcome),
                character_consequences=self._get_character_consequences(outcome)
            )
            branches[outcome] = branch
        
        # Store branches
        branch_key = f"{resolution_type.value}_{scene_context}"
        self.narrative_branches[branch_key] = list(branches.values())
        
        return branches
    
    def get_resolution_prompt(self, result: ResolutionResult, 
                            include_branches: bool = True) -> str:
        """Generate a prompt snippet for including resolution results in story generation."""
        prompt_parts = []
        
        # Basic resolution information
        prompt_parts.append(
            f"[RESOLUTION_RESULT: {result.character_id} attempted {result.resolution_type.value} "
            f"(rolled {result.final_result} vs difficulty {result.difficulty}) = {result.outcome.value.upper()}]"
        )
        
        # Add margin information for context
        if result.success:
            if result.margin >= 10:
                prompt_parts.append("[RESULT_CONTEXT: Overwhelming success, character excels beyond expectations]")
            elif result.margin >= 5:
                prompt_parts.append("[RESULT_CONTEXT: Clear success, character handles the situation well]")
            else:
                prompt_parts.append("[RESULT_CONTEXT: Narrow success, character barely manages to succeed]")
        else:
            if result.margin <= -10:
                prompt_parts.append("[RESULT_CONTEXT: Catastrophic failure, significant negative consequences]")
            elif result.margin <= -5:
                prompt_parts.append("[RESULT_CONTEXT: Clear failure, obvious negative outcome]")
            else:
                prompt_parts.append("[RESULT_CONTEXT: Close failure, partial success or minor setback]")
        
        # Add narrative impact
        if result.narrative_impact:
            prompt_parts.append(f"[NARRATIVE_GUIDANCE: {result.narrative_impact}]")
        
        # Include emotional consequences for failures
        if not result.success and result.outcome in [OutcomeType.FAILURE, OutcomeType.CRITICAL_FAILURE]:
            emotional_impact = "frustration" if result.outcome == OutcomeType.FAILURE else "humiliation"
            prompt_parts.append(
                f"[EMOTIONAL_CONSEQUENCE: {result.character_id} feels {emotional_impact} from the failure]"
            )
        
        return "\n".join(prompt_parts)
    
    def get_character_performance_summary(self, character_id: str) -> Dict[str, Any]:
        """Get performance summary for a character."""
        if character_id not in self.character_performance:
            return {}
        
        performance = self.character_performance[character_id]
        
        # Calculate success rates by resolution type
        type_performance = {}
        for res_type, results in performance.get('by_type', {}).items():
            successes = sum(1 for r in results if r['success'])
            total = len(results)
            type_performance[res_type] = {
                'success_rate': successes / total if total > 0 else 0,
                'total_attempts': total,
                'average_margin': sum(r['margin'] for r in results) / total if total > 0 else 0
            }
        
        return {
            'character_id': character_id,
            'total_resolutions': performance.get('total_resolutions', 0),
            'total_successes': performance.get('total_successes', 0),
            'overall_success_rate': performance.get('success_rate', 0),
            'performance_by_type': type_performance,
            'recent_streak': self._calculate_recent_streak(character_id),
            'best_resolution_type': self._get_best_resolution_type(character_id),
            'worst_resolution_type': self._get_worst_resolution_type(character_id)
        }
    
    def simulate_resolution(self, resolution_type: ResolutionType, difficulty: int,
                          character_stats: Dict[str, int], iterations: int = 1000) -> Dict[str, Any]:
        """Simulate many resolutions to analyze probability distributions."""
        outcomes = {outcome: 0 for outcome in OutcomeType}
        margins = []
        
        for _ in range(iterations):
            # Simulate dice roll and modifiers
            dice_rolled = self._roll_dice()
            total_roll = sum(dice_rolled)
            modifiers = self._calculate_modifiers("simulation", resolution_type, character_stats)
            final_result = total_roll + sum(modifiers.values())
            margin = final_result - difficulty
            
            outcome = self._determine_outcome(dice_rolled, final_result, difficulty)
            outcomes[outcome] += 1
            margins.append(margin)
        
        # Calculate statistics
        success_count = outcomes[OutcomeType.SUCCESS] + outcomes[OutcomeType.CRITICAL_SUCCESS] + outcomes[OutcomeType.PARTIAL_SUCCESS]
        
        return {
            'resolution_type': resolution_type.value,
            'difficulty': difficulty,
            'character_stats': character_stats,
            'iterations': iterations,
            'success_probability': success_count / iterations,
            'outcome_distribution': {k.value: v / iterations for k, v in outcomes.items()},
            'average_margin': sum(margins) / len(margins),
            'margin_range': (min(margins), max(margins)),
            'modifiers_applied': modifiers
        }
    
    def export_engine_data(self) -> Dict[str, Any]:
        """Export all engine data for persistence."""
        return {
            'config': self.config.to_dict(),
            'resolution_history': [result.to_dict() for result in self.resolution_history],
            'narrative_branches': {
                key: [branch.to_dict() for branch in branches]
                for key, branches in self.narrative_branches.items()
            },
            'character_performance': self.character_performance
        }
    
    def import_engine_data(self, data: Dict[str, Any]) -> None:
        """Import engine data from external source."""
        if 'config' in data:
            self.config = ResolutionConfig.from_dict(data['config'])
        
        if 'resolution_history' in data:
            self.resolution_history = [
                ResolutionResult.from_dict(result_data)
                for result_data in data['resolution_history']
            ]
        
        if 'narrative_branches' in data:
            self.narrative_branches = {}
            for key, branches_data in data['narrative_branches'].items():
                self.narrative_branches[key] = [
                    NarrativeBranch(
                        branch_id=b['branch_id'],
                        outcome_type=OutcomeType(b['outcome_type']),
                        narrative_text=b['narrative_text'],
                        emotional_impact=b.get('emotional_impact', ''),
                        stat_changes=b.get('stat_changes', {}),
                        scene_transitions=b.get('scene_transitions', []),
                        character_consequences=b.get('character_consequences', [])
                    )
                    for b in branches_data
                ]
        
        if 'character_performance' in data:
            self.character_performance = data['character_performance']
        
        logger.info("Imported narrative dice engine data")
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics."""
        total_resolutions = len(self.resolution_history)
        if total_resolutions == 0:
            return {'total_resolutions': 0}
        
        successes = sum(1 for r in self.resolution_history if r.success)
        
        # Count outcomes
        outcome_counts = {}
        for outcome in OutcomeType:
            outcome_counts[outcome.value] = sum(1 for r in self.resolution_history if r.outcome == outcome)
        
        # Count by resolution type
        type_counts = {}
        for res_type in ResolutionType:
            type_counts[res_type.value] = sum(1 for r in self.resolution_history if r.resolution_type == res_type)
        
        return {
            'total_resolutions': total_resolutions,
            'total_successes': successes,
            'overall_success_rate': successes / total_resolutions,
            'outcome_distribution': outcome_counts,
            'resolution_type_distribution': type_counts,
            'total_characters_tracked': len(self.character_performance),
            'total_narrative_branches': sum(len(branches) for branches in self.narrative_branches.values()),
            'engine_enabled': self.config.enabled,
            'dice_type': self.config.dice_type.value
        }
    
    # Private helper methods
    
    def _roll_dice(self, advantage: bool = False, disadvantage: bool = False) -> List[int]:
        """Roll dice based on current configuration."""
        roll_func = self.dice_functions[self.config.dice_type]
        
        if advantage and self.config.advantage_enabled:
            # Roll twice, take higher
            roll1 = roll_func()
            roll2 = roll_func()
            if len(roll1) == 1 and len(roll2) == 1:
                return [max(roll1[0], roll2[0])]
            else:
                return roll1 if sum(roll1) > sum(roll2) else roll2
        elif disadvantage and self.config.disadvantage_enabled:
            # Roll twice, take lower
            roll1 = roll_func()
            roll2 = roll_func()
            if len(roll1) == 1 and len(roll2) == 1:
                return [min(roll1[0], roll2[0])]
            else:
                return roll1 if sum(roll1) < sum(roll2) else roll2
        else:
            return roll_func()
    
    def _roll_d6(self) -> List[int]:
        """Roll a single d6."""
        return [random.randint(1, 6)]
    
    def _roll_d10(self) -> List[int]:
        """Roll a single d10."""
        return [random.randint(1, 10)]
    
    def _roll_d12(self) -> List[int]:
        """Roll a single d12."""
        return [random.randint(1, 12)]
    
    def _roll_d20(self) -> List[int]:
        """Roll a single d20."""
        return [random.randint(1, 20)]
    
    def _roll_d100(self) -> List[int]:
        """Roll a single d100."""
        return [random.randint(1, 100)]
    
    def _roll_2d10(self) -> List[int]:
        """Roll two d10s."""
        return [random.randint(1, 10), random.randint(1, 10)]
    
    def _roll_3d6(self) -> List[int]:
        """Roll three d6s."""
        return [random.randint(1, 6) for _ in range(3)]
    
    def _roll_4d6_drop_lowest(self) -> List[int]:
        """Roll four d6s and drop the lowest."""
        rolls = [random.randint(1, 6) for _ in range(4)]
        rolls.remove(min(rolls))
        return rolls
    
    def _calculate_modifiers(self, character_id: str, resolution_type: ResolutionType,
                           character_stats: Optional[Dict[str, int]] = None) -> Dict[str, int]:
        """Calculate modifiers based on character stats and resolution type."""
        modifiers = {}
        
        if not self.config.skill_dependency or not character_stats:
            return modifiers
        
        # Get relevant stat for this resolution type
        relevant_stat = self.stat_mappings.get(resolution_type)
        if relevant_stat and relevant_stat in character_stats:
            stat_value = character_stats[relevant_stat]
            
            # Convert stat (1-10) to modifier (-4 to +5, clamped by tolerance)
            modifier = stat_value - 5  # 5 is average, so modifier ranges from -4 to +5
            modifier = max(-self.config.modifier_tolerance, min(self.config.modifier_tolerance, modifier))
            
            # Always include the modifier, even if it's 0
            modifiers[relevant_stat] = modifier
        
        return modifiers
    
    def _determine_outcome(self, dice_rolled: List[int], final_result: int, difficulty: int) -> OutcomeType:
        """Determine the outcome type based on dice and result."""
        # Check for critical results (natural 1s and 20s for d20 system)
        if self.config.dice_type == DiceType.D20 and len(dice_rolled) == 1:
            natural_roll = dice_rolled[0]
            if natural_roll <= self.config.critical_range:
                return OutcomeType.CRITICAL_FAILURE
            elif natural_roll >= (20 - self.config.critical_range + 1):
                return OutcomeType.CRITICAL_SUCCESS
        
        # Determine success/failure
        margin = final_result - difficulty
        
        if margin >= 10:
            return OutcomeType.CRITICAL_SUCCESS
        elif margin >= 0:
            return OutcomeType.SUCCESS
        elif margin >= -5:
            return OutcomeType.PARTIAL_SUCCESS
        elif margin >= -10:
            return OutcomeType.FAILURE
        else:
            return OutcomeType.CRITICAL_FAILURE
    
    def _generate_narrative_impact(self, character_id: str, resolution_type: ResolutionType,
                                 outcome: OutcomeType, margin: int, scene_context: str) -> str:
        """Generate narrative impact description for the resolution."""
        impact_templates = {
            OutcomeType.CRITICAL_SUCCESS: [
                f"{character_id} exceeds all expectations in {resolution_type.value}",
                f"Spectacular success opens new opportunities for {character_id}",
                f"{character_id} demonstrates mastery in {resolution_type.value}"
            ],
            OutcomeType.SUCCESS: [
                f"{character_id} successfully handles the {resolution_type.value} challenge",
                f"Competent performance leads to positive outcome",
                f"{character_id} achieves their goal through {resolution_type.value}"
            ],
            OutcomeType.PARTIAL_SUCCESS: [
                f"{character_id} partially succeeds but with complications",
                f"Mixed results create both opportunity and challenge",
                f"Success comes with unexpected consequences"
            ],
            OutcomeType.FAILURE: [
                f"{character_id} fails at {resolution_type.value} with notable consequences",
                f"Failure creates new obstacles and story complications",
                f"Setback requires {character_id} to find alternative approaches"
            ],
            OutcomeType.CRITICAL_FAILURE: [
                f"{character_id} fails spectacularly with serious ramifications",
                f"Catastrophic failure dramatically alters the situation",
                f"Major setback forces significant story direction change"
            ]
        }
        
        templates = impact_templates.get(outcome, ["Standard resolution outcome"])
        return random.choice(templates)
    
    def _generate_branch_narrative(self, resolution_type: ResolutionType, 
                                 outcome: OutcomeType, scene_context: str) -> str:
        """Generate narrative text for a story branch."""
        branch_templates = {
            OutcomeType.CRITICAL_SUCCESS: f"The {resolution_type.value} succeeds beyond all expectations, opening new possibilities and impressing all witnesses.",
            OutcomeType.SUCCESS: f"The {resolution_type.value} attempt succeeds, achieving the desired outcome and moving the story forward positively.",
            OutcomeType.PARTIAL_SUCCESS: f"The {resolution_type.value} partially succeeds, creating a mixed outcome with both benefits and complications.",
            OutcomeType.FAILURE: f"The {resolution_type.value} fails, creating setbacks and forcing characters to find alternative solutions.",
            OutcomeType.CRITICAL_FAILURE: f"The {resolution_type.value} fails catastrophically, with serious negative consequences that reshape the entire situation."
        }
        
        return branch_templates.get(outcome, "The attempt concludes with uncertain results.")
    
    def _get_emotional_impact(self, outcome: OutcomeType) -> str:
        """Get emotional impact for different outcomes."""
        emotional_impacts = {
            OutcomeType.CRITICAL_SUCCESS: "pride, confidence, elation",
            OutcomeType.SUCCESS: "satisfaction, confidence",
            OutcomeType.PARTIAL_SUCCESS: "mixed feelings, cautious optimism",
            OutcomeType.FAILURE: "disappointment, frustration",
            OutcomeType.CRITICAL_FAILURE: "humiliation, despair, anger"
        }
        return emotional_impacts.get(outcome, "neutral")
    
    def _get_stat_changes(self, outcome: OutcomeType) -> Dict[str, int]:
        """Get potential stat changes based on outcome."""
        stat_changes = {
            OutcomeType.CRITICAL_SUCCESS: {"confidence": 2, "courage": 1},
            OutcomeType.SUCCESS: {"confidence": 1},
            OutcomeType.PARTIAL_SUCCESS: {},
            OutcomeType.FAILURE: {"confidence": -1},
            OutcomeType.CRITICAL_FAILURE: {"confidence": -2, "humility": 1}
        }
        return stat_changes.get(outcome, {})
    
    def _get_character_consequences(self, outcome: OutcomeType) -> List[str]:
        """Get character consequences for different outcomes."""
        consequences = {
            OutcomeType.CRITICAL_SUCCESS: ["Gains reputation", "Unlocks new opportunities", "Increases social standing"],
            OutcomeType.SUCCESS: ["Achieves immediate goal", "Maintains current standing"],
            OutcomeType.PARTIAL_SUCCESS: ["Achieves partial goal", "Creates new complications"],
            OutcomeType.FAILURE: ["Must find alternative approach", "Faces immediate setback"],
            OutcomeType.CRITICAL_FAILURE: ["Suffers major setback", "Loses reputation", "Creates new enemies"]
        }
        return consequences.get(outcome, [])
    
    def _create_auto_success(self, character_id: str, resolution_type: ResolutionType,
                           difficulty: Union[int, DifficultyLevel], scene_context: str) -> ResolutionResult:
        """Create an automatic success result when engine is disabled."""
        difficulty_value = difficulty.value if isinstance(difficulty, DifficultyLevel) else difficulty
        
        return ResolutionResult(
            resolution_id=f"auto_{int(datetime.now().timestamp())}",
            character_id=character_id,
            resolution_type=resolution_type,
            dice_rolled=[20],  # Fake natural 20
            total_roll=20,
            modifiers={},
            final_result=25,  # Always beats difficulty
            difficulty=difficulty_value,
            outcome=OutcomeType.SUCCESS,
            success=True,
            margin=25 - difficulty_value,
            narrative_impact=f"Automatic success in {resolution_type.value}",
            timestamp=datetime.now(),
            scene_context=scene_context
        )
    
    def _update_character_performance(self, result: ResolutionResult) -> None:
        """Update character performance tracking."""
        char_id = result.character_id
        
        if char_id not in self.character_performance:
            self.character_performance[char_id] = {
                'total_resolutions': 0,
                'total_successes': 0,
                'success_rate': 0.0,
                'by_type': {},
                'recent_results': []
            }
        
        performance = self.character_performance[char_id]
        
        # Update totals
        performance['total_resolutions'] += 1
        if result.success:
            performance['total_successes'] += 1
        performance['success_rate'] = performance['total_successes'] / performance['total_resolutions']
        
        # Update by type
        res_type = result.resolution_type.value
        if res_type not in performance['by_type']:
            performance['by_type'][res_type] = []
        
        performance['by_type'][res_type].append({
            'success': result.success,
            'margin': result.margin,
            'outcome': result.outcome.value,
            'timestamp': result.timestamp.isoformat()
        })
        
        # Keep recent results (last 10)
        performance['recent_results'].append({
            'resolution_type': res_type,
            'success': result.success,
            'outcome': result.outcome.value,
            'margin': result.margin
        })
        
        if len(performance['recent_results']) > 10:
            performance['recent_results'] = performance['recent_results'][-10:]
    
    def _calculate_recent_streak(self, character_id: str) -> Dict[str, int]:
        """Calculate recent success/failure streak for character."""
        if character_id not in self.character_performance:
            return {'current_streak': 0, 'streak_type': 'none'}
        
        recent = self.character_performance[character_id].get('recent_results', [])
        if not recent:
            return {'current_streak': 0, 'streak_type': 'none'}
        
        # Find current streak
        current_streak = 0
        streak_type = 'success' if recent[-1]['success'] else 'failure'
        
        for result in reversed(recent):
            if (streak_type == 'success' and result['success']) or (streak_type == 'failure' and not result['success']):
                current_streak += 1
            else:
                break
        
        return {'current_streak': current_streak, 'streak_type': streak_type}
    
    def _get_best_resolution_type(self, character_id: str) -> Optional[str]:
        """Get character's best resolution type by success rate."""
        if character_id not in self.character_performance:
            return None
        
        by_type = self.character_performance[character_id].get('by_type', {})
        best_type = None
        best_rate = 0
        
        for res_type, results in by_type.items():
            if len(results) >= 3:  # Need at least 3 attempts
                successes = sum(1 for r in results if r['success'])
                rate = successes / len(results)
                if rate > best_rate:
                    best_rate = rate
                    best_type = res_type
        
        return best_type
    
    def _get_worst_resolution_type(self, character_id: str) -> Optional[str]:
        """Get character's worst resolution type by success rate."""
        if character_id not in self.character_performance:
            return None
        
        by_type = self.character_performance[character_id].get('by_type', {})
        worst_type = None
        worst_rate = 1.0
        
        for res_type, results in by_type.items():
            if len(results) >= 3:  # Need at least 3 attempts
                successes = sum(1 for r in results if r['success'])
                rate = successes / len(results)
                if rate < worst_rate:
                    worst_rate = rate
                    worst_type = res_type
        
        return worst_type
