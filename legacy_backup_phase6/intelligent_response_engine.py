"""
Intelligent Response Engine for OpenChronicle

This engine provides adaptive story generation by intelligently analyzing context,
selecting optimal response strategies, coordinating between models, and ensuring
high-quality narrative output based on all available character and story data.

The engine serves as the final coordination layer that brings together insights
from all other engines to generate contextually appropriate and engaging responses.
"""

import json
import time
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
from pathlib import Path
import sys

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error


class ResponseStrategy(Enum):
    """Response generation strategies based on context analysis."""
    NARRATIVE_FOCUS = "narrative_focus"        # Rich storytelling with atmosphere
    CHARACTER_FOCUS = "character_focus"        # Character development and interaction
    ACTION_FOCUS = "action_focus"              # Fast-paced action and events
    DIALOGUE_FOCUS = "dialogue_focus"          # Conversation and character voice
    EXPLORATION_FOCUS = "exploration_focus"    # World-building and discovery
    EMOTIONAL_FOCUS = "emotional_focus"        # Emotional depth and character feelings
    TACTICAL_FOCUS = "tactical_focus"          # Strategic thinking and planning
    MYSTERY_FOCUS = "mystery_focus"            # Suspense and revelation
    ADAPTIVE_MIXED = "adaptive_mixed"          # Dynamic mix based on context


class ContextQuality(Enum):
    """Context quality levels for response adaptation."""
    RICH = "rich"              # Comprehensive context available
    MODERATE = "moderate"      # Some context available
    LIMITED = "limited"        # Minimal context available
    SPARSE = "sparse"         # Very little context available


class ResponseComplexity(Enum):
    """Response complexity levels."""
    SIMPLE = "simple"          # Short, direct responses
    MODERATE = "moderate"      # Balanced responses
    COMPLEX = "complex"        # Rich, detailed responses
    DYNAMIC = "dynamic"        # Adaptive complexity


@dataclass
class ContextAnalysis:
    """Analysis of available context for response generation."""
    quality: ContextQuality
    character_depth: float      # 0.0-1.0 how much character info is available
    world_richness: float       # 0.0-1.0 how much world context is available
    emotional_context: float    # 0.0-1.0 emotional context availability
    action_context: float       # 0.0-1.0 action/event context
    dialogue_context: float     # 0.0-1.0 conversation context
    memory_continuity: float    # 0.0-1.0 memory consistency
    total_tokens: int          # Estimated total context tokens
    key_elements: List[str]    # Important context elements identified
    missing_elements: List[str] # Important elements that are missing


@dataclass
class ResponsePlan:
    """Plan for generating an optimal response."""
    strategy: ResponseStrategy
    complexity: ResponseComplexity
    model_preference: str
    focus_areas: List[str]
    tone_guidance: str
    length_target: str         # "short", "medium", "long"
    special_instructions: List[str]
    confidence: float          # 0.0-1.0 confidence in this plan


@dataclass
class ResponseEvaluation:
    """Evaluation of a generated response."""
    quality_score: float       # 0.0-1.0 overall quality
    coherence_score: float     # 0.0-1.0 narrative coherence
    character_consistency: float # 0.0-1.0 character consistency
    engagement_level: float    # 0.0-1.0 estimated engagement
    technical_quality: float   # 0.0-1.0 grammar, style, etc.
    context_utilization: float # 0.0-1.0 how well context was used
    areas_for_improvement: List[str]
    strengths: List[str]


@dataclass
class ResponseMetrics:
    """Metrics for response performance tracking."""
    timestamp: datetime
    strategy_used: ResponseStrategy
    model_used: str
    context_quality: ContextQuality
    response_time: float       # Time taken to generate
    user_satisfaction: Optional[float]  # If available
    technical_metrics: Dict[str, float]


class IntelligentResponseEngine:
    """
    Advanced response generation engine that adapts to context and learns from patterns.
    
    This engine coordinates all other engines to generate optimal responses by:
    1. Analyzing available context quality and completeness
    2. Selecting appropriate response strategies 
    3. Coordinating model selection and prompt engineering
    4. Evaluating response quality and learning from patterns
    5. Adapting future responses based on performance history
    """
    
    def __init__(self, data_dir: str = "storage/temp/test_data/response_engine"):
        """Initialize the Intelligent Response Engine."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance tracking
        self.response_history: List[ResponseMetrics] = []
        self.strategy_performance: Dict[ResponseStrategy, List[float]] = {}
        self.model_performance: Dict[str, List[float]] = {}
        self.context_patterns: Dict[str, Any] = {}
        
        # Adaptive thresholds
        self.quality_thresholds = {
            ContextQuality.RICH: 0.8,
            ContextQuality.MODERATE: 0.6,
            ContextQuality.LIMITED: 0.4,
            ContextQuality.SPARSE: 0.2
        }
        
        # Strategy weights (learned over time)
        self.strategy_weights = {strategy: 1.0 for strategy in ResponseStrategy}
        
        # Load persisted data
        self._load_engine_data()
        
        log_info("Intelligent Response Engine initialized")
    
    def analyze_context(self, context_data: Dict[str, Any]) -> ContextAnalysis:
        """
        Analyze the quality and completeness of available context.
        
        Args:
            context_data: Complete context from build_context_with_dynamic_models
            
        Returns:
            ContextAnalysis with detailed assessment
        """
        try:
            # Extract context components
            full_context = context_data.get("context", "")
            analysis = context_data.get("content_analysis", {})
            active_character = context_data.get("active_character")
            token_estimate = context_data.get("token_estimate", 0)
            
            # Analyze character depth
            character_depth = 0.0
            if active_character:
                character_depth += 0.3  # Base for having active character
                
                # Check for character style context
                if "[CHARACTER_STYLE:" in full_context:
                    character_depth += 0.25
                
                # Check for character consistency context
                if "[CHARACTER_CONSISTENCY:" in full_context:
                    character_depth += 0.25
                
                # Check for emotional context
                if "[EMOTIONAL_STABILITY:" in full_context:
                    character_depth += 0.15
                
                # Check for character stats
                if "[CHARACTER_STATS:" in full_context:
                    character_depth += 0.15
                
                # Check for character memories
                if "character_memories" in full_context:
                    character_depth += 0.1
                
                # Check for character mentions in content
                if analysis.get("entities", {}).get("characters"):
                    character_depth += 0.1
            
            # Analyze world richness
            world_richness = 0.0
            if "=== CANON ===" in full_context:
                canon_length = len(full_context.split("=== CANON ===")[1].split("===")[0])
                world_richness += min(0.4, canon_length / 1000)  # Up to 0.4 based on canon length
            
            if "=== WORLD STATE ===" in full_context:
                world_richness += 0.3
            
            if "=== RECENT EVENTS ===" in full_context:
                world_richness += 0.2
            
            if analysis.get("entities", {}).get("locations"):
                world_richness += 0.1
            
            # Analyze emotional context
            emotional_context = 0.0
            if analysis.get("emotional_tone"):
                emotional_context += 0.3
            
            if "emotional_stability" in full_context:
                emotional_context += 0.4
            
            if analysis.get("flags") and any(flag in ["emotional", "romantic", "sad", "angry", "happy"] for flag in analysis["flags"]):
                emotional_context += 0.3
            
            # Analyze action context
            action_context = 0.0
            content_type = analysis.get("content_type", "")
            if content_type in ["action", "combat", "physical"]:
                action_context += 0.4
            
            if "dice_resolution" in full_context:
                action_context += 0.3
            
            if analysis.get("entities", {}).get("objects"):
                action_context += 0.2
            
            if any(word in full_context.lower() for word in ["fight", "run", "jump", "climb", "attack"]):
                action_context += 0.1
            
            # Analyze dialogue context
            dialogue_context = 0.0
            if content_type == "dialogue":
                dialogue_context += 0.4
            
            if "character_interactions" in full_context:
                dialogue_context += 0.3
            
            if analysis.get("entities", {}).get("characters") and len(analysis["entities"]["characters"]) > 1:
                dialogue_context += 0.2
            
            if any(word in full_context.lower() for word in ["say", "tell", "ask", "speak", "talk"]):
                dialogue_context += 0.1
            
            # Analyze memory continuity
            memory_continuity = 0.0
            if "character_memories" in full_context:
                memory_continuity += 0.4
            
            if "=== CHARACTERS ===" in full_context:
                memory_continuity += 0.3
            
            if "=== RECENT EVENTS ===" in full_context:
                memory_continuity += 0.2
            
            if token_estimate > 1000:  # Rich context suggests good continuity
                memory_continuity += 0.1
            
            # Determine overall quality
            context_scores = [character_depth, world_richness, emotional_context, 
                            action_context, dialogue_context, memory_continuity]
            average_score = statistics.mean(context_scores)
            
            if average_score >= 0.6:
                quality = ContextQuality.RICH
            elif average_score >= 0.4:
                quality = ContextQuality.MODERATE
            elif average_score >= 0.25:
                quality = ContextQuality.LIMITED
            else:
                quality = ContextQuality.SPARSE
            
            # Identify key elements present
            key_elements = []
            if character_depth > 0.5:
                key_elements.append("rich_character_context")
            if world_richness > 0.5:
                key_elements.append("detailed_world_state")
            if emotional_context > 0.5:
                key_elements.append("emotional_depth")
            if action_context > 0.5:
                key_elements.append("action_dynamics")
            if dialogue_context > 0.5:
                key_elements.append("dialogue_context")
            if memory_continuity > 0.5:
                key_elements.append("strong_continuity")
            
            # Identify missing elements
            missing_elements = []
            if character_depth < 0.3:
                missing_elements.append("character_depth")
            if world_richness < 0.3:
                missing_elements.append("world_context")
            if emotional_context < 0.3:
                missing_elements.append("emotional_context")
            if memory_continuity < 0.3:
                missing_elements.append("memory_continuity")
            
            context_analysis = ContextAnalysis(
                quality=quality,
                character_depth=character_depth,
                world_richness=world_richness,
                emotional_context=emotional_context,
                action_context=action_context,
                dialogue_context=dialogue_context,
                memory_continuity=memory_continuity,
                total_tokens=token_estimate,
                key_elements=key_elements,
                missing_elements=missing_elements
            )
            
            log_info(f"Context analysis complete: {quality.value} quality with {len(key_elements)} key elements")
            return context_analysis
            
        except Exception as e:
            log_error(f"Context analysis failed: {e}")
            # Return minimal analysis on failure
            return ContextAnalysis(
                quality=ContextQuality.SPARSE,
                character_depth=0.0,
                world_richness=0.0,
                emotional_context=0.0,
                action_context=0.0,
                dialogue_context=0.0,
                memory_continuity=0.0,
                total_tokens=0,
                key_elements=[],
                missing_elements=["context_analysis_failed"]
            )
    
    def plan_response(self, context_analysis: ContextAnalysis, 
                     user_input: str, content_analysis: Dict[str, Any]) -> ResponsePlan:
        """
        Create an optimal response plan based on context analysis.
        
        Args:
            context_analysis: Result from analyze_context
            user_input: Original user input
            content_analysis: Content analysis from ContentAnalyzer
            
        Returns:
            ResponsePlan with strategy and parameters
        """
        try:
            # Determine primary strategy based on strongest context signals
            context_scores = {
                ResponseStrategy.CHARACTER_FOCUS: context_analysis.character_depth,
                ResponseStrategy.NARRATIVE_FOCUS: context_analysis.world_richness,
                ResponseStrategy.EMOTIONAL_FOCUS: context_analysis.emotional_context,
                ResponseStrategy.ACTION_FOCUS: context_analysis.action_context,
                ResponseStrategy.DIALOGUE_FOCUS: context_analysis.dialogue_context
            }
            
            # Apply strategy performance weights
            weighted_scores = {}
            for strategy, score in context_scores.items():
                weight = self.strategy_weights.get(strategy, 1.0)
                weighted_scores[strategy] = score * weight
            
            # Select primary strategy
            primary_strategy = max(weighted_scores, key=weighted_scores.get)
            
            # Check for mixed strategy if scores are close (but not if primary score is very low)
            sorted_scores = sorted(weighted_scores.values(), reverse=True)
            max_score = sorted_scores[0]
            
            # Only use adaptive mixed if we have decent scores and they're close
            if len(sorted_scores) > 1 and max_score > 0.3 and sorted_scores[0] - sorted_scores[1] < 0.1:
                primary_strategy = ResponseStrategy.ADAPTIVE_MIXED
            
            # Special strategy overrides based on content
            content_type = content_analysis.get("content_type", "")
            flags = content_analysis.get("flags", [])
            
            if content_type == "exploration" or "exploration" in flags:
                primary_strategy = ResponseStrategy.EXPLORATION_FOCUS
            elif content_type == "mystery" or "mystery" in flags:
                primary_strategy = ResponseStrategy.MYSTERY_FOCUS
            elif content_type == "investigation" and "mystery" in flags:
                primary_strategy = ResponseStrategy.MYSTERY_FOCUS
            elif "tactical" in flags or "planning" in user_input.lower():
                primary_strategy = ResponseStrategy.TACTICAL_FOCUS
            
            # Determine complexity based on context quality and token budget
            if context_analysis.quality == ContextQuality.RICH:
                complexity = ResponseComplexity.COMPLEX
            elif context_analysis.quality == ContextQuality.MODERATE:
                complexity = ResponseComplexity.MODERATE
            elif context_analysis.quality == ContextQuality.LIMITED:
                complexity = ResponseComplexity.SIMPLE
            else:
                complexity = ResponseComplexity.DYNAMIC  # Adapt based on what's available
            
            # Model preference based on strategy and content
            model_preference = content_analysis.get("routing_recommendation", "mock")
            
            # Override model for specific strategies if needed
            if primary_strategy == ResponseStrategy.DIALOGUE_FOCUS:
                # Prefer models good at dialogue
                model_preference = content_analysis.get("routing_recommendation", "mock")
            elif primary_strategy == ResponseStrategy.ACTION_FOCUS:
                # Prefer models good at action scenes
                model_preference = content_analysis.get("routing_recommendation", "mock")
            
            # Determine focus areas
            focus_areas = []
            if context_analysis.character_depth > 0.5:
                focus_areas.append("character_development")
            if context_analysis.emotional_context > 0.5:
                focus_areas.append("emotional_depth")
            if context_analysis.action_context > 0.5:
                focus_areas.append("action_dynamics")
            if context_analysis.world_richness > 0.5:
                focus_areas.append("world_building")
            if context_analysis.dialogue_context > 0.5:
                focus_areas.append("dialogue_quality")
            
            # Generate tone guidance
            emotional_tone = content_analysis.get("emotional_tone", "neutral")
            tone_guidance = f"Maintain {emotional_tone} tone"
            
            if primary_strategy == ResponseStrategy.EMOTIONAL_FOCUS:
                tone_guidance += ", emphasize emotional authenticity and depth"
            elif primary_strategy == ResponseStrategy.ACTION_FOCUS:
                tone_guidance += ", keep pacing energetic and engaging"
            elif primary_strategy == ResponseStrategy.DIALOGUE_FOCUS:
                tone_guidance += ", prioritize natural conversation flow"
            
            # Determine length target
            if complexity == ResponseComplexity.SIMPLE:
                length_target = "short"
            elif complexity == ResponseComplexity.COMPLEX:
                length_target = "long"
            else:
                length_target = "medium"
            
            # Generate special instructions
            special_instructions = []
            
            if context_analysis.missing_elements:
                if "character_depth" in context_analysis.missing_elements:
                    special_instructions.append("Focus on establishing character presence and personality")
                if "world_context" in context_analysis.missing_elements:
                    special_instructions.append("Include environmental and setting details")
                if "emotional_context" in context_analysis.missing_elements:
                    special_instructions.append("Add emotional nuance and character feelings")
            
            if primary_strategy == ResponseStrategy.ADAPTIVE_MIXED:
                special_instructions.append("Balance multiple narrative elements dynamically")
            
            if context_analysis.memory_continuity < 0.3:
                special_instructions.append("Establish continuity with previous events")
            
            # Calculate confidence based on context quality and strategy match
            base_confidence = {
                ContextQuality.RICH: 0.9,
                ContextQuality.MODERATE: 0.7,
                ContextQuality.LIMITED: 0.5,
                ContextQuality.SPARSE: 0.3
            }[context_analysis.quality]
            
            # Adjust confidence based on strategy performance history
            strategy_history = self.strategy_performance.get(primary_strategy, [])
            if strategy_history:
                strategy_avg = statistics.mean(strategy_history[-10:])  # Last 10 uses
                confidence_adjustment = (strategy_avg - 0.5) * 0.2  # ±0.1 adjustment
                base_confidence = max(0.1, min(0.95, base_confidence + confidence_adjustment))
            
            response_plan = ResponsePlan(
                strategy=primary_strategy,
                complexity=complexity,
                model_preference=model_preference,
                focus_areas=focus_areas,
                tone_guidance=tone_guidance,
                length_target=length_target,
                special_instructions=special_instructions,
                confidence=base_confidence
            )
            
            log_info(f"Response plan created: {primary_strategy.value} strategy with {complexity.value} complexity (confidence: {base_confidence:.2f})")
            return response_plan
            
        except Exception as e:
            log_error(f"Response planning failed: {e}")
            # Return fallback plan
            return ResponsePlan(
                strategy=ResponseStrategy.NARRATIVE_FOCUS,
                complexity=ResponseComplexity.MODERATE,
                model_preference="mock",
                focus_areas=["general_storytelling"],
                tone_guidance="Continue the story naturally",
                length_target="medium",
                special_instructions=["Use fallback response strategy"],
                confidence=0.3
            )
    
    def enhance_prompt_with_plan(self, original_prompt: str, 
                                response_plan: ResponsePlan) -> str:
        """
        Enhance the original prompt with intelligent response guidance.
        
        Args:
            original_prompt: Original context prompt
            response_plan: Response plan from plan_response
            
        Returns:
            Enhanced prompt with response guidance
        """
        try:
            # Create strategy-specific guidance
            strategy_guidance = {
                ResponseStrategy.NARRATIVE_FOCUS: "Focus on rich storytelling, vivid descriptions, and atmospheric details. Create immersive narrative experiences.",
                ResponseStrategy.CHARACTER_FOCUS: "Prioritize character development, personality expression, and authentic character voice. Show character growth and depth.",
                ResponseStrategy.ACTION_FOCUS: "Emphasize dynamic action, movement, and exciting events. Keep pacing energetic and consequences meaningful.",
                ResponseStrategy.DIALOGUE_FOCUS: "Center on natural conversation, character voice, and meaningful exchanges. Make dialogue feel authentic and purposeful.",
                ResponseStrategy.EXPLORATION_FOCUS: "Highlight discovery, world-building, and environmental storytelling. Reveal new aspects of the world organically.",
                ResponseStrategy.EMOTIONAL_FOCUS: "Delve into emotional depth, character feelings, and psychological nuance. Create emotional resonance and authenticity.",
                ResponseStrategy.TACTICAL_FOCUS: "Emphasize strategic thinking, planning, and logical problem-solving. Show intelligent decision-making processes.",
                ResponseStrategy.MYSTERY_FOCUS: "Build suspense, reveal information gradually, and maintain intrigue. Balance revelation with continued mystery.",
                ResponseStrategy.ADAPTIVE_MIXED: "Dynamically balance multiple narrative elements based on context. Adapt style to what the moment needs most."
            }
            
            # Create complexity guidance
            complexity_guidance = {
                ResponseComplexity.SIMPLE: "Keep the response concise and focused. Be direct and clear.",
                ResponseComplexity.MODERATE: "Provide balanced detail and depth. Include key narrative elements without overwhelming.",
                ResponseComplexity.COMPLEX: "Create rich, detailed responses with multiple layers. Explore nuance and depth across several elements.",
                ResponseComplexity.DYNAMIC: "Adapt response length and complexity to what the context supports most effectively."
            }
            
            # Build enhancement sections
            enhancement_parts = []
            
            # Add strategy guidance
            enhancement_parts.append(f"[RESPONSE_STRATEGY: {strategy_guidance[response_plan.strategy]}]")
            
            # Add complexity guidance
            enhancement_parts.append(f"[RESPONSE_COMPLEXITY: {complexity_guidance[response_plan.complexity]}]")
            
            # Add tone guidance
            enhancement_parts.append(f"[TONE_GUIDANCE: {response_plan.tone_guidance}]")
            
            # Add length target
            enhancement_parts.append(f"[LENGTH_TARGET: Aim for {response_plan.length_target} response length]")
            
            # Add focus areas if any
            if response_plan.focus_areas:
                focus_list = ", ".join(response_plan.focus_areas)
                enhancement_parts.append(f"[FOCUS_AREAS: Emphasize {focus_list}]")
            
            # Add special instructions if any
            if response_plan.special_instructions:
                for instruction in response_plan.special_instructions:
                    enhancement_parts.append(f"[SPECIAL_INSTRUCTION: {instruction}]")
            
            # Combine original prompt with enhancements
            enhanced_prompt = original_prompt + "\n\n=== INTELLIGENT RESPONSE GUIDANCE ===\n" + "\n".join(enhancement_parts)
            
            # Add final adaptive instruction
            enhanced_prompt += f"\n\n[INTELLIGENT_RESPONSE_ENGINE: Generate response using {response_plan.strategy.value} strategy with {response_plan.complexity.value} complexity. Confidence level: {response_plan.confidence:.2f}]"
            
            log_info(f"Prompt enhanced with {response_plan.strategy.value} strategy guidance")
            return enhanced_prompt
            
        except Exception as e:
            log_error(f"Prompt enhancement failed: {e}")
            return original_prompt  # Return original on failure
    
    def evaluate_response(self, response: str, original_context: Dict[str, Any],
                         response_plan: ResponsePlan, user_input: str) -> ResponseEvaluation:
        """
        Evaluate the quality of a generated response.
        
        Args:
            response: Generated response text
            original_context: Original context data
            response_plan: Plan used for generation
            user_input: Original user input
            
        Returns:
            ResponseEvaluation with quality metrics
        """
        try:
            # Basic quality metrics
            response_length = len(response)
            word_count = len(response.split())
            
            # Quality score based on length appropriateness
            target_lengths = {
                "short": (50, 200),
                "medium": (150, 500), 
                "long": (400, 1000)
            }
            
            target_range = target_lengths.get(response_plan.length_target, (150, 500))
            length_score = 1.0
            if response_length < target_range[0]:
                length_score = response_length / target_range[0]
            elif response_length > target_range[1]:
                length_score = max(0.5, target_range[1] / response_length)
            
            # Coherence score (basic heuristics)
            sentences = response.split('.')
            coherence_score = 0.8  # Base score
            
            # Penalize very short or very long sentences
            sentence_lengths = [len(s.strip()) for s in sentences if s.strip()]
            if sentence_lengths:
                avg_sentence_length = statistics.mean(sentence_lengths)
                if avg_sentence_length < 20 or avg_sentence_length > 200:
                    coherence_score -= 0.1
            
            # Check for repetitive patterns
            words = response.lower().split()
            if len(words) > 10:
                unique_words = len(set(words))
                repetition_ratio = unique_words / len(words)
                if repetition_ratio < 0.7:
                    coherence_score -= 0.2
            
            # Character consistency (check if character name appears and is consistent)
            character_consistency = 0.8  # Base score
            active_character = original_context.get("active_character")
            if active_character:
                # Simple check for character name consistency
                if active_character.lower() in response.lower():
                    character_consistency = 0.9
                # Additional checks could be added here
            
            # Engagement level (heuristic based on content variety)
            engagement_level = 0.6  # Base score
            
            # Check for dialogue
            if '"' in response or "'" in response:
                engagement_level += 0.1
            
            # Check for action words
            action_words = ["moved", "walked", "ran", "looked", "turned", "opened", "closed", "grabbed"]
            if any(word in response.lower() for word in action_words):
                engagement_level += 0.1
            
            # Check for emotional words
            emotion_words = ["felt", "thought", "worried", "excited", "happy", "sad", "angry", "surprised"]
            if any(word in response.lower() for word in emotion_words):
                engagement_level += 0.1
            
            # Check for descriptive content
            descriptive_words = ["beautiful", "dark", "bright", "cold", "warm", "soft", "loud", "quiet"]
            if any(word in response.lower() for word in descriptive_words):
                engagement_level += 0.1
            
            engagement_level = min(1.0, engagement_level)
            
            # Technical quality (basic grammar and style checks)
            technical_quality = 0.8  # Base score
            
            # Check for basic grammar issues
            if response.count('(') != response.count(')'):
                technical_quality -= 0.1
            if response.count('[') != response.count(']'):
                technical_quality -= 0.1
            
            # Check for proper capitalization
            sentences_for_caps = [s.strip() for s in response.split('.') if s.strip()]
            if sentences_for_caps:
                properly_capitalized = sum(1 for s in sentences_for_caps if s[0].isupper())
                cap_ratio = properly_capitalized / len(sentences_for_caps)
                if cap_ratio < 0.8:
                    technical_quality -= 0.1
            
            # Context utilization (check if key context elements were used)
            context_utilization = 0.5  # Base score
            
            context_text = original_context.get("context", "")
            
            # Check if character context was utilized
            if active_character and active_character.lower() in response.lower():
                context_utilization += 0.2
            
            # Check if world elements were utilized
            if "=== CANON ===" in context_text and any(word in response.lower() for word in ["place", "location", "world", "setting"]):
                context_utilization += 0.15
            
            # Check if recent events were referenced
            if "=== RECENT EVENTS ===" in context_text and any(word in response.lower() for word in ["remember", "recently", "earlier", "before"]):
                context_utilization += 0.15
            
            context_utilization = min(1.0, context_utilization)
            
            # Overall quality score (weighted average)
            quality_score = (
                length_score * 0.15 +
                coherence_score * 0.25 +
                character_consistency * 0.20 +
                engagement_level * 0.20 +
                technical_quality * 0.10 +
                context_utilization * 0.10
            )
            
            # Identify areas for improvement
            areas_for_improvement = []
            if length_score < 0.7:
                areas_for_improvement.append("response_length")
            if coherence_score < 0.7:
                areas_for_improvement.append("narrative_coherence")
            if character_consistency < 0.7:
                areas_for_improvement.append("character_consistency")
            if engagement_level < 0.7:
                areas_for_improvement.append("engagement_level")
            if technical_quality < 0.7:
                areas_for_improvement.append("technical_quality")
            if context_utilization < 0.7:
                areas_for_improvement.append("context_utilization")
            
            # Identify strengths
            strengths = []
            if length_score >= 0.8:
                strengths.append("appropriate_length")
            if coherence_score >= 0.8:
                strengths.append("narrative_coherence")
            if character_consistency >= 0.8:
                strengths.append("character_consistency")
            if engagement_level >= 0.8:
                strengths.append("high_engagement")
            if technical_quality >= 0.8:
                strengths.append("technical_quality")
            if context_utilization >= 0.8:
                strengths.append("excellent_context_use")
            
            evaluation = ResponseEvaluation(
                quality_score=quality_score,
                coherence_score=coherence_score,
                character_consistency=character_consistency,
                engagement_level=engagement_level,
                technical_quality=technical_quality,
                context_utilization=context_utilization,
                areas_for_improvement=areas_for_improvement,
                strengths=strengths
            )
            
            log_info(f"Response evaluation complete: {quality_score:.2f} overall quality")
            return evaluation
            
        except Exception as e:
            log_error(f"Response evaluation failed: {e}")
            # Return neutral evaluation on failure
            return ResponseEvaluation(
                quality_score=0.5,
                coherence_score=0.5,
                character_consistency=0.5,
                engagement_level=0.5,
                technical_quality=0.5,
                context_utilization=0.5,
                areas_for_improvement=["evaluation_failed"],
                strengths=[]
            )
    
    def record_response_metrics(self, response_plan: ResponsePlan, 
                               evaluation: ResponseEvaluation,
                               model_used: str, response_time: float,
                               context_analysis: ContextAnalysis) -> None:
        """
        Record response metrics for learning and adaptation.
        
        Args:
            response_plan: Plan used for generation
            evaluation: Response evaluation results
            model_used: Model that generated the response
            response_time: Time taken to generate response
            context_analysis: Context analysis results
        """
        try:
            # Create metrics record
            metrics = ResponseMetrics(
                timestamp=datetime.now(),
                strategy_used=response_plan.strategy,
                model_used=model_used,
                context_quality=context_analysis.quality,
                response_time=response_time,
                user_satisfaction=None,  # Could be added later with user feedback
                technical_metrics={
                    "quality_score": evaluation.quality_score,
                    "coherence_score": evaluation.coherence_score,
                    "character_consistency": evaluation.character_consistency,
                    "engagement_level": evaluation.engagement_level,
                    "technical_quality": evaluation.technical_quality,
                    "context_utilization": evaluation.context_utilization
                }
            )
            
            # Add to history
            self.response_history.append(metrics)
            
            # Update strategy performance tracking
            if response_plan.strategy not in self.strategy_performance:
                self.strategy_performance[response_plan.strategy] = []
            self.strategy_performance[response_plan.strategy].append(evaluation.quality_score)
            
            # Keep only recent performance data (last 100 responses per strategy)
            if len(self.strategy_performance[response_plan.strategy]) > 100:
                self.strategy_performance[response_plan.strategy] = self.strategy_performance[response_plan.strategy][-100:]
            
            # Update model performance tracking
            if model_used not in self.model_performance:
                self.model_performance[model_used] = []
            self.model_performance[model_used].append(evaluation.quality_score)
            
            # Keep only recent model performance data
            if len(self.model_performance[model_used]) > 100:
                self.model_performance[model_used] = self.model_performance[model_used][-100:]
            
            # Update strategy weights based on performance
            self._update_strategy_weights()
            
            # Persist data periodically
            if len(self.response_history) % 10 == 0:  # Every 10 responses
                self._save_engine_data()
            
            log_info(f"Response metrics recorded: {evaluation.quality_score:.2f} quality using {response_plan.strategy.value}")
            
        except Exception as e:
            log_error(f"Failed to record response metrics: {e}")
    
    def _update_strategy_weights(self) -> None:
        """Update strategy weights based on performance history."""
        try:
            for strategy, scores in self.strategy_performance.items():
                if len(scores) >= 5:  # Minimum data for meaningful adjustment
                    avg_score = statistics.mean(scores[-20:])  # Last 20 uses
                    
                    # Adjust weight based on performance vs baseline (0.6)
                    baseline = 0.6
                    performance_delta = avg_score - baseline
                    
                    # Gradual weight adjustment
                    new_weight = self.strategy_weights[strategy] + (performance_delta * 0.1)
                    self.strategy_weights[strategy] = max(0.5, min(2.0, new_weight))
            
        except Exception as e:
            log_error(f"Failed to update strategy weights: {e}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of engine performance and learning.
        
        Returns:
            Dictionary with performance statistics
        """
        try:
            if not self.response_history:
                return {"status": "no_data", "message": "No response history available"}
            
            # Overall statistics
            recent_responses = self.response_history[-50:]  # Last 50 responses
            overall_quality = statistics.mean([r.technical_metrics["quality_score"] for r in recent_responses])
            
            # Strategy performance
            strategy_stats = {}
            for strategy, scores in self.strategy_performance.items():
                if scores:
                    strategy_stats[strategy.value] = {
                        "average_quality": statistics.mean(scores[-20:]) if len(scores) >= 20 else statistics.mean(scores),
                        "total_uses": len(scores),
                        "current_weight": self.strategy_weights[strategy],
                        "recent_trend": "improving" if len(scores) >= 10 and statistics.mean(scores[-5:]) > statistics.mean(scores[-10:-5]) else "stable"
                    }
            
            # Model performance
            model_stats = {}
            for model, scores in self.model_performance.items():
                if scores:
                    model_stats[model] = {
                        "average_quality": statistics.mean(scores[-20:]) if len(scores) >= 20 else statistics.mean(scores),
                        "total_uses": len(scores)
                    }
            
            # Context quality impact
            quality_impact = {}
            for quality_level in ContextQuality:
                matching_responses = [r for r in recent_responses if r.context_quality == quality_level]
                if matching_responses:
                    avg_quality = statistics.mean([r.technical_metrics["quality_score"] for r in matching_responses])
                    quality_impact[quality_level.value] = {
                        "average_quality": avg_quality,
                        "response_count": len(matching_responses)
                    }
            
            return {
                "status": "active",
                "total_responses": len(self.response_history),
                "recent_overall_quality": overall_quality,
                "strategy_performance": strategy_stats,
                "model_performance": model_stats,
                "context_quality_impact": quality_impact,
                "learning_status": "active" if len(self.response_history) >= 10 else "initial_learning"
            }
            
        except Exception as e:
            log_error(f"Failed to generate performance summary: {e}")
            return {"status": "error", "message": str(e)}
    
    def _save_engine_data(self) -> None:
        """Save engine data to persistence."""
        try:
            data = {
                "strategy_weights": {s.value: w for s, w in self.strategy_weights.items()},
                "strategy_performance": {s.value: scores for s, scores in self.strategy_performance.items()},
                "model_performance": self.model_performance,
                "quality_thresholds": {q.value: t for q, t in self.quality_thresholds.items()},
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.data_dir / "engine_data.json", "w") as f:
                json.dump(data, f, indent=2)
            
            log_info("Intelligent Response Engine data saved")
            
        except Exception as e:
            log_error(f"Failed to save engine data: {e}")
    
    def _load_engine_data(self) -> None:
        """Load engine data from persistence."""
        try:
            data_file = self.data_dir / "engine_data.json"
            if data_file.exists():
                with open(data_file, "r") as f:
                    data = json.load(f)
                
                # Load strategy weights
                if "strategy_weights" in data:
                    for strategy_name, weight in data["strategy_weights"].items():
                        try:
                            strategy = ResponseStrategy(strategy_name)
                            self.strategy_weights[strategy] = weight
                        except ValueError:
                            continue
                
                # Load strategy performance
                if "strategy_performance" in data:
                    for strategy_name, scores in data["strategy_performance"].items():
                        try:
                            strategy = ResponseStrategy(strategy_name)
                            self.strategy_performance[strategy] = scores
                        except ValueError:
                            continue
                
                # Load model performance
                if "model_performance" in data:
                    self.model_performance = data["model_performance"]
                
                # Load quality thresholds
                if "quality_thresholds" in data:
                    for quality_name, threshold in data["quality_thresholds"].items():
                        try:
                            quality = ContextQuality(quality_name)
                            self.quality_thresholds[quality] = threshold
                        except ValueError:
                            continue
                
                log_info("Intelligent Response Engine data loaded")
            
        except Exception as e:
            log_error(f"Failed to load engine data: {e}")


# Integration function for use with context builder
def enhance_context_with_intelligent_response(context_data: Dict[str, Any], 
                                             user_input: str,
                                             engine: IntelligentResponseEngine = None) -> Dict[str, Any]:
    """
    Enhance context with intelligent response planning.
    
    Args:
        context_data: Context from build_context_with_dynamic_models
        user_input: Original user input
        engine: IntelligentResponseEngine instance (created if None)
        
    Returns:
        Enhanced context data with response planning
    """
    try:
        if engine is None:
            engine = IntelligentResponseEngine()
        
        # Analyze context
        context_analysis = engine.analyze_context(context_data)
        
        # Plan response
        content_analysis = context_data.get("content_analysis", {})
        response_plan = engine.plan_response(context_analysis, user_input, content_analysis)
        
        # Enhance prompt
        original_prompt = context_data.get("context", "")
        enhanced_prompt = engine.enhance_prompt_with_plan(original_prompt, response_plan)
        
        # Add intelligent response data to context
        enhanced_context_data = context_data.copy()  # Don't modify original
        enhanced_context_data["intelligent_response"] = {
            "context_analysis": asdict(context_analysis),
            "response_plan": asdict(response_plan),
            "enhanced_prompt": enhanced_prompt,
            "engine_instance": engine  # For post-generation evaluation
        }
        
        # Update the main context with enhanced prompt
        enhanced_context_data["context"] = enhanced_prompt
        
        log_info(f"Context enhanced with intelligent response planning: {response_plan.strategy.value}")
        return enhanced_context_data
        
    except Exception as e:
        log_error(f"Intelligent response enhancement failed: {e}")
        return context_data  # Return original on failure
