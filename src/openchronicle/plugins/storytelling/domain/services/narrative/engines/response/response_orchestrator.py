"""
OpenChronicle Core - Response Intelligence Orchestrator

Coordinates intelligent response analysis, planning, and evaluation.
Replaces IntelligentResponseEngine with modular component architecture.

Author: OpenChronicle Development Team
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openchronicle.domain.models.model_orchestrator import ModelOrchestrator
from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_error_with_context

from ...shared import NarrativeComponent
from ...shared import StateManager
from ...shared import ValidationResult
from .context_analyzer import ContextAnalyzer
from .response_models import ContextAnalysis
from .response_models import ResponseContext
from .response_models import ResponseEvaluation
from .response_models import ResponseMetrics
from .response_models import ResponsePlan
from .response_models import ResponseRequest
from .response_models import ResponseResult
from .response_planner import ResponsePlanner


class ResponseOrchestrator(NarrativeComponent):
    """
    Orchestrates intelligent response generation process.

    Coordinates:
    - Context analysis (ContextAnalyzer)
    - Response planning (ResponsePlanner)
    - Response evaluation (ResponseEvaluator)
    - Performance metrics tracking
    """

    def __init__(
        self,
        data_dir: str = "storage/response_intelligence",
        config: dict[str, Any] = None,
    ):
        super().__init__("ResponseOrchestrator", config)

        # Centralized logger
        self.logger = get_logger()

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Component instances
        self.context_analyzer = ContextAnalyzer(
            config.get("context_analyzer", {}) if config else {}
        )
        self.response_planner = ResponsePlanner(
            config.get("response_planner", {}) if config else {}
        )
        # Add model orchestrator for proper response generation
        self.model_orchestrator = ModelOrchestrator()

        # Note: ResponseEvaluator will be added when we create it

        # State management
        self.state_manager = StateManager()
        self.response_history: list[ResponseResult] = []
        self.performance_metrics = ResponseMetrics(
            generation_time=0.0,
            analysis_time=0.0,
            planning_time=0.0,
            evaluation_time=0.0,
        )

        # Load existing data
        self._load_orchestrator_data()

    async def process(self, data: dict[str, Any]) -> ResponseResult:
        """Process a complete response request."""

        def _raise_validation_error(issues):
            raise ValueError(f"Invalid request: {issues}")

        start_time = time.time()

        try:
            self.logger.info(
                "ResponseOrchestrator: processing request",
                context_tags=["response","start"],
            )
            # Extract request data
            request = self._create_request_from_data(data)

            # Validate request
            validation = self.validate({"request": request})
            if not validation.is_valid:
                _raise_validation_error(validation.issues)

            # Step 1: Analyze context
            analysis_start = time.time()
            context_analysis = self._analyze_context(request.context)
            analysis_time = time.time() - analysis_start
            self.logger.debug(
                "ResponseOrchestrator: context analyzed",
                context_tags=["response","analyze"],
                request_id=getattr(request, "request_id", None),
                analysis_time=analysis_time,
            )

            # Step 2: Plan response
            planning_start = time.time()
            response_plan = self._plan_response(context_analysis, request)
            planning_time = time.time() - planning_start
            self.logger.debug(
                "ResponseOrchestrator: response planned",
                context_tags=["response","plan"],
                request_id=getattr(request, "request_id", None),
                planning_time=planning_time,
                strategy=getattr(response_plan, "strategy", None),
                complexity=getattr(response_plan, "complexity", None),
            )

            # Step 3: Generate response (integrated with model orchestrator)
            generation_start = time.time()
            generated_response = await self._generate_response(
                context_analysis, response_plan
            )
            generation_time = time.time() - generation_start
            self.logger.debug(
                "ResponseOrchestrator: response generated",
                context_tags=["response","generate"],
                request_id=getattr(request, "request_id", None),
                generation_time=generation_time,
                generated_len=len(generated_response) if isinstance(generated_response, str) else None,
            )

            # Step 4: Evaluate response (placeholder for now)
            evaluation_start = time.time()
            evaluation = self._evaluate_response(
                generated_response, context_analysis, response_plan
            )
            evaluation_time = time.time() - evaluation_start
            self.logger.debug(
                "ResponseOrchestrator: response evaluated",
                context_tags=["response","evaluate"],
                request_id=getattr(request, "request_id", None),
                evaluation_time=evaluation_time,
                overall_score=getattr(evaluation, "overall_score", None),
            )

            # Update metrics
            self._update_metrics(
                analysis_time, planning_time, generation_time, evaluation_time
            )

            # Create result
            result = ResponseResult(
                request=request,
                analysis=context_analysis,
                plan=response_plan,
                generated_response=generated_response,
                evaluation=evaluation,
                metrics=self.performance_metrics,
                success=True,
            )

            # Store result
            self.response_history.append(result)
            self._save_orchestrator_data()

            self.logger.info(
                "ResponseOrchestrator: request complete",
                context_tags=["response","success"],
                request_id=getattr(request, "request_id", None),
                total_time=time.time() - start_time,
            )

        except Exception as e:
            # Log with context, but preserve current return behavior
            try:
                req_id = getattr(locals().get("request", None), "request_id", None)
            except Exception:
                req_id = None
            log_error_with_context(
                e,
                context={
                    "component": "ResponseOrchestrator",
                    "request_id": req_id,
                    "phase": "process",
                },
            )
            return ResponseResult(
                request=(
                    request
                    if "request" in locals()
                    else ResponseRequest(context=ResponseContext(user_input=""))
                ),
                analysis=ContextAnalysis(
                    quality="poor", complexity_needs="simple", content_type="error"
                ),
                plan=ResponsePlan(
                    strategy="conservative", complexity="simple", content_focus="error"
                ),
                generated_response="",
                evaluation=ResponseEvaluation(
                    overall_score=0.0,
                    coherence_score=0.0,
                    creativity_score=0.0,
                    context_integration_score=0.0,
                ),
                metrics=self.performance_metrics,
                success=False,
                error_message=str(e),
            )
        else:
            return result

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate response orchestrator data."""
        if "request" not in data:
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                validation_type="request_validation",
                issues=["Request object required"],
            )

        return ValidationResult(
            is_valid=True, confidence=1.0, validation_type="request_validation"
        )

    def _create_request_from_data(self, data: dict[str, Any]) -> ResponseRequest:
        """Create ResponseRequest from input data."""
        # Extract context
        context_data = data.get("context", {})
        context = ResponseContext(
            user_input=context_data.get("user_input", ""),
            story_state=context_data.get("story_state", {}),
            character_states=context_data.get("character_states", {}),
            narrative_history=context_data.get("narrative_history", []),
            scene_context=context_data.get("scene_context", {}),
        )

        # Create request
        request = ResponseRequest(
            context=context,
            preferred_strategy=data.get("preferred_strategy"),
            preferred_complexity=data.get("preferred_complexity"),
            quality_requirements=data.get("quality_requirements", {}),
            custom_instructions=data.get("custom_instructions", []),
            request_id=data.get("request_id", f"req_{int(time.time())}"),
            timestamp=datetime.now().isoformat(),
            priority=data.get("priority", "normal"),
        )

        return request

    def _analyze_context(self, context: ResponseContext) -> ContextAnalysis:
        """Analyze request context."""
        context_data = {
            "context": {
                "user_input": context.user_input,
                "story_state": context.story_state,
                "character_states": context.character_states,
                "narrative_history": context.narrative_history,
                "scene_context": context.scene_context,
            }
        }

        return self.context_analyzer.process(context_data)

    def _plan_response(
        self, context_analysis: ContextAnalysis, request: ResponseRequest
    ) -> ResponsePlan:
        """Plan response based on analysis."""
        planning_data = {
            "context_analysis": context_analysis,
            "preferences": {
                "strategy": request.preferred_strategy,
                "complexity": request.preferred_complexity,
            },
        }

        return self.response_planner.process(planning_data)

    async def _generate_response(
        self, context_analysis: ContextAnalysis, response_plan: ResponsePlan
    ) -> str:
        """Generate response based on plan using model orchestrator."""
        try:
            # Build enhanced prompt based on plan
            strategy = response_plan.strategy.value
            complexity = response_plan.complexity.value
            content_focus = response_plan.content_focus

            # Create comprehensive prompt
            prompt_parts = [
                f"Generate a {complexity} response with {strategy} strategy.",
                f"Focus on: {content_focus}",
                f"Context: {context_analysis.content_summary}",
            ]

            # Add key points if available
            if response_plan.key_points:
                prompt_parts.append(f"Key points to address: {', '.join(response_plan.key_points)}")

            # Add quality targets
            if response_plan.quality_targets:
                quality_desc = ", ".join([f"{k}: {v}" for k, v in response_plan.quality_targets.items()])
                prompt_parts.append(f"Quality targets: {quality_desc}")

            # Set target length
            if response_plan.estimated_length > 0:
                prompt_parts.append(f"Target length: approximately {response_plan.estimated_length} characters")

            enhanced_prompt = "\n".join(prompt_parts)

            # Use model orchestrator for generation
            model_response = await self.model_orchestrator.generate_response(
                prompt=enhanced_prompt,
                adapter_name=None,  # Use default adapter
                context={"strategy": strategy, "complexity": complexity},
                max_tokens=min(response_plan.estimated_length // 4, 1000),  # Rough token estimation
                temperature=0.7 if complexity in ["complex", "elaborate"] else 0.5
            )
        except (AttributeError, KeyError) as e:
            self.logger.exception("Error accessing response generation data")
            # Fallback to basic response
            strategy = getattr(response_plan.strategy, 'value', 'balanced')
            complexity = getattr(response_plan.complexity, 'value', 'moderate')
            return (f"[FALLBACK RESPONSE - Strategy: {strategy}, Complexity: {complexity}, "
                    f"Focus: {response_plan.content_focus}]")
        except (ValueError, TypeError) as e:
            self.logger.exception("Error with response generation parameters")
            return "[ERROR RESPONSE - Parameter error in generation]"
        except Exception as e:
            self.logger.exception("Error generating response")
            return f"[ERROR RESPONSE - Generation failed: {e}]"
        else:
            return (model_response.content if model_response else
                    f"[FALLBACK RESPONSE - Strategy: {strategy}, Complexity: {complexity}, Focus: {content_focus}]")

    def _evaluate_response(
        self,
        response: str,
        context_analysis: ContextAnalysis,
        response_plan: ResponsePlan,
    ) -> ResponseEvaluation:
        """Evaluate generated response with comprehensive metrics."""
        try:
            # Calculate length-based score
            response_length = len(response)
            expected_length = response_plan.estimated_length
            length_score = min(1.0, response_length / max(expected_length, 1)) if expected_length > 0 else 0.8

            # Calculate coherence score based on structure and content
            coherence_score = self._calculate_coherence_score(response, context_analysis)

            # Calculate creativity score based on uniqueness and engagement
            creativity_score = self._calculate_creativity_score(response, response_plan)

            # Calculate context integration score
            context_integration_score = self._calculate_context_integration_score(response, context_analysis)

            # Calculate overall score as weighted average
            overall_score = (
                length_score * 0.2 +
                coherence_score * 0.3 +
                creativity_score * 0.25 +
                context_integration_score * 0.25
            )

            # Analyze strengths and weaknesses
            strengths = []
            weaknesses = []
            suggestions = []

            if length_score > 0.8:
                strengths.append("Appropriate length")
            elif length_score < 0.5:
                weaknesses.append("Length mismatch")
                suggestions.append("Adjust response length to better match requirements")

            if coherence_score > 0.8:
                strengths.append("Good coherence and structure")
            elif coherence_score < 0.6:
                weaknesses.append("Poor coherence")
                suggestions.append("Improve logical flow and structure")

            if creativity_score > 0.7:
                strengths.append("Creative and engaging")
            elif creativity_score < 0.5:
                weaknesses.append("Lacks creativity")
                suggestions.append("Add more creative elements or unique perspectives")

            if context_integration_score > 0.8:
                strengths.append("Excellent context integration")
            elif context_integration_score < 0.6:
                weaknesses.append("Poor context integration")
                suggestions.append("Better incorporate contextual information")

            # Check if response meets plan requirements
            meets_plan = overall_score >= 0.7 and len(weaknesses) <= 1

            return ResponseEvaluation(
                overall_score=overall_score,
                coherence_score=coherence_score,
                creativity_score=creativity_score,
                context_integration_score=context_integration_score,
                strengths=strengths,
                weaknesses=weaknesses,
                suggestions=suggestions,
                meets_plan=meets_plan,
            )

        except (AttributeError, KeyError) as e:
            self.logger.exception("Error accessing evaluation data")
            return self._fallback_evaluation()
        except (ValueError, TypeError) as e:
            self.logger.exception("Error with evaluation parameters")
            return self._fallback_evaluation()
        except Exception as e:
            self.logger.exception("Error evaluating response")
            return self._fallback_evaluation()

    def _calculate_coherence_score(self, response: str, context_analysis: ContextAnalysis) -> float:
        """Calculate coherence score based on response structure."""
        try:
            # Simple coherence metrics
            sentences = response.split('.')
            avg_sentence_length = (sum(len(s.split()) for s in sentences if s.strip()) /
                                  max(len([s for s in sentences if s.strip()]), 1))

            # Penalize very short or very long sentences
            sentence_score = 1.0 - abs(avg_sentence_length - 15) / 30.0  # Target ~15 words per sentence
            sentence_score = max(0.0, min(1.0, sentence_score))

            # Check for repetition
            words = response.lower().split()
            unique_words = len(set(words))
            repetition_score = unique_words / max(len(words), 1)

            return (sentence_score * 0.4 + repetition_score * 0.6)

        except (AttributeError, KeyError) as e:
            self.logger.warning(f"Error accessing coherence calculation data: {e}")
            return 0.7  # Default coherence score
        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.warning(f"Error with coherence calculation parameters: {e}")
            return 0.7  # Default coherence score
        except Exception as e:
            self.logger.warning(f"Unexpected error in coherence calculation: {e}")
            return 0.7  # Default coherence score

    def _calculate_creativity_score(self, response: str, response_plan: ResponsePlan) -> float:
        """Calculate creativity score based on uniqueness and engagement."""
        try:
            # Simple creativity metrics
            words = response.split()

            # Vocabulary diversity
            unique_words = len(set(word.lower() for word in words))
            diversity_score = min(1.0, unique_words / max(len(words), 1) * 2)

            # Response complexity alignment
            complexity_value = getattr(response_plan.complexity, 'value', 'moderate')
            if complexity_value in ['complex', 'elaborate']:
                target_creativity = 0.8
            elif complexity_value == 'moderate':
                target_creativity = 0.7
            else:
                target_creativity = 0.6

            # Combine metrics
            return min(1.0, (diversity_score + target_creativity) / 2)

        except (AttributeError, KeyError) as e:
            self.logger.warning(f"Error accessing creativity calculation data: {e}")
            return 0.6  # Default creativity score
        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.warning(f"Error with creativity calculation parameters: {e}")
            return 0.6  # Default creativity score
        except Exception as e:
            self.logger.warning(f"Unexpected error in creativity calculation: {e}")
            return 0.6  # Default creativity score

    def _calculate_context_integration_score(self, response: str, context_analysis: ContextAnalysis) -> float:
        """Calculate how well the response integrates context."""
        try:
            if not context_analysis.content_summary:
                overlap_score = 0.5  # No context to integrate
            else:
                # Check for context keywords in response
                context_words = set(context_analysis.content_summary.lower().split())
                response_words = set(response.lower().split())

                # Calculate overlap
                overlap = len(context_words.intersection(response_words))
                overlap_score = min(1.0, overlap / max(len(context_words), 1) * 3)
        except (AttributeError, KeyError) as e:
            self.logger.warning(f"Error accessing context integration data: {e}")
            return 0.5  # Default context integration score
        except (ValueError, TypeError, ZeroDivisionError) as e:
            self.logger.warning(f"Error with context integration parameters: {e}")
            return 0.5  # Default context integration score
        except Exception as e:
            self.logger.warning(f"Unexpected error in context integration calculation: {e}")
            return 0.5  # Default context integration score
        else:
            return overlap_score

    def _fallback_evaluation(self) -> ResponseEvaluation:
        """Provide fallback evaluation when normal evaluation fails."""
        return ResponseEvaluation(
            overall_score=0.5,
            coherence_score=0.5,
            creativity_score=0.5,
            context_integration_score=0.5,
            strengths=["Response generated"],
            weaknesses=["Evaluation system error"],
            suggestions=["Check evaluation system"],
            meets_plan=False,
        )

    def _update_metrics(
        self,
        analysis_time: float,
        planning_time: float,
        generation_time: float,
        evaluation_time: float,
    ) -> None:
        """Update performance metrics."""
        self.performance_metrics.analysis_time = analysis_time
        self.performance_metrics.planning_time = planning_time
        self.performance_metrics.generation_time = generation_time
        self.performance_metrics.evaluation_time = evaluation_time
        self.performance_metrics.responses_generated += 1

        # Update averages if we have history
        if self.response_history:
            total_quality = sum(
                result.evaluation.overall_score for result in self.response_history
            )
            self.performance_metrics.average_quality = total_quality / len(
                self.response_history
            )

    def get_response_history(self, limit: int = 10) -> list[ResponseResult]:
        """Get recent response history."""
        return self.response_history[-limit:] if self.response_history else []

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        return {
            "total_responses": self.performance_metrics.responses_generated,
            "average_quality": self.performance_metrics.average_quality,
            "average_times": {
                "analysis": self.performance_metrics.analysis_time,
                "planning": self.performance_metrics.planning_time,
                "generation": self.performance_metrics.generation_time,
                "evaluation": self.performance_metrics.evaluation_time,
            },
            "component_status": {
                "context_analyzer": self.context_analyzer.get_component_status(),
                "response_planner": self.response_planner.get_component_status(),
            },
        }

    def _save_orchestrator_data(self) -> None:
        """Save orchestrator state and history."""
        try:
            # Save metrics
            metrics_file = self.data_dir / "performance_metrics.json"
            with open(metrics_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "generation_time": self.performance_metrics.generation_time,
                        "analysis_time": self.performance_metrics.analysis_time,
                        "planning_time": self.performance_metrics.planning_time,
                        "evaluation_time": self.performance_metrics.evaluation_time,
                        "average_quality": self.performance_metrics.average_quality,
                        "responses_generated": self.performance_metrics.responses_generated,
                    },
                    f,
                    indent=2,
                )

            # Save recent history (keep last 100 entries)
            recent_history = (
                self.response_history[-100:]
                if len(self.response_history) > 100
                else self.response_history
            )
            history_file = self.data_dir / "response_history.json"
            with open(history_file, "w", encoding="utf-8") as f:
                # Convert to serializable format
                history_data = []
                for result in recent_history:
                    history_data.append(
                        {
                            "request_id": result.request.request_id,
                            "timestamp": result.request.timestamp,
                            "success": result.success,
                            "quality_score": result.evaluation.overall_score,
                            "strategy": result.plan.strategy.value,
                            "complexity": result.plan.complexity.value,
                        }
                    )
                json.dump(history_data, f, indent=2)

        except Exception as e:
            # Don't fail the main operation if saving fails, but log it
            log_error_with_context(
                e,
                context={
                    "component": "ResponseOrchestrator",
                    "phase": "save",
                    "data_dir": str(self.data_dir),
                },
            )

    def _load_orchestrator_data(self) -> None:
        """Load existing orchestrator data."""
        try:
            # Load metrics
            metrics_file = self.data_dir / "performance_metrics.json"
            if metrics_file.exists():
                with open(metrics_file, encoding="utf-8") as f:
                    metrics_data = json.load(f)
                    self.performance_metrics.generation_time = metrics_data.get(
                        "generation_time", 0.0
                    )
                    self.performance_metrics.analysis_time = metrics_data.get(
                        "analysis_time", 0.0
                    )
                    self.performance_metrics.planning_time = metrics_data.get(
                        "planning_time", 0.0
                    )
                    self.performance_metrics.evaluation_time = metrics_data.get(
                        "evaluation_time", 0.0
                    )
                    self.performance_metrics.average_quality = metrics_data.get(
                        "average_quality", 0.0
                    )
                    self.performance_metrics.responses_generated = metrics_data.get(
                        "responses_generated", 0
                    )

        except Exception as e:
            # Start fresh if loading fails, but log it
            log_error_with_context(
                e,
                context={
                    "component": "ResponseOrchestrator",
                    "phase": "load",
                    "data_dir": str(self.data_dir),
                },
            )
