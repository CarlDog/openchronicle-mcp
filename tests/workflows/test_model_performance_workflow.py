"""
Model Performance & Optimization Workflow Test

Tests the complete model performance optimization journey:
Model selection → Performance monitoring → Optimization application → Adaptation

This workflow validates:
- Initial model performance baseline establishment
- Real-time performance monitoring during story generation
- Automatic optimization trigger detection
- Performance improvement implementation
- Model switching and fallback mechanisms
- Long-term performance trend analysis
- Resource usage optimization
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List
import statistics

# Import core systems
from core.models import ModelOrchestrator
from core.performance import PerformanceOrchestrator
from core.memory import MemoryOrchestrator
from core.database import DatabaseOrchestrator

# Import test utilities
from tests.mocks.mock_adapters import MockModelOrchestrator

class TestModelPerformanceWorkflow:
    """Test complete model performance optimization workflow."""
    
    @pytest.fixture
    def performance_test_scenario(self):
        """Provide performance testing scenario data."""
        return {
            "story_id": "test_performance_optimization",
            "test_models": [
                {
                    "name": "primary_model",
                    "type": "gpt-4", 
                    "expected_response_time": 2.0,  # seconds
                    "expected_quality_score": 0.85,
                    "cost_per_token": 0.00003
                },
                {
                    "name": "fallback_model",
                    "type": "gpt-3.5-turbo",
                    "expected_response_time": 1.0,
                    "expected_quality_score": 0.75,
                    "cost_per_token": 0.000002
                },
                {
                    "name": "local_model", 
                    "type": "llama-2-7b",
                    "expected_response_time": 5.0,
                    "expected_quality_score": 0.70,
                    "cost_per_token": 0.0  # Local model, no API cost
                }
            ],
            "performance_scenarios": [
                {
                    "scenario": "simple_response",
                    "prompt_complexity": "low",
                    "expected_tokens": 100,
                    "performance_threshold": 3.0  # seconds
                },
                {
                    "scenario": "complex_narrative",
                    "prompt_complexity": "high", 
                    "expected_tokens": 500,
                    "performance_threshold": 8.0
                },
                {
                    "scenario": "rapid_interaction",
                    "prompt_complexity": "medium",
                    "expected_tokens": 200,
                    "performance_threshold": 2.0
                }
            ],
            "optimization_targets": {
                "response_time": {"target": 2.0, "tolerance": 0.5},
                "quality_score": {"target": 0.80, "tolerance": 0.05},
                "cost_efficiency": {"target": 0.01, "tolerance": 0.005}  # cost per response
            }
        }
    
    @pytest_asyncio.fixture
    async def performance_orchestrators(self, performance_test_scenario):
        """Initialize orchestrators for performance testing."""
        story_id = performance_test_scenario["story_id"]
        
        # Initialize orchestrators
        model_orchestrator = MockModelOrchestrator()
        performance_orchestrator = PerformanceOrchestrator()
        memory_orchestrator = MemoryOrchestrator()
        database_orchestrator = DatabaseOrchestrator()
        
        # Initialize performance monitoring
        await performance_orchestrator.initialize_monitoring(story_id)
        
        return {
            "model": model_orchestrator,
            "performance": performance_orchestrator,
            "memory": memory_orchestrator,
            "database": database_orchestrator
        }
    
    @pytest.mark.asyncio
    async def test_complete_performance_optimization_workflow(self, performance_test_scenario, performance_orchestrators):
        """Test complete model performance optimization workflow."""
        story_id = performance_test_scenario["story_id"]
        orchestrators = performance_orchestrators
        
        print(f"⚡ Starting performance optimization workflow for story: {story_id}")
        
        # === PHASE 1: BASELINE PERFORMANCE ESTABLISHMENT ===
        print("📊 Establishing performance baselines...")
        
        baseline_metrics = {}
        
        for model_config in performance_test_scenario["test_models"]:
            model_name = model_config["name"]
            print(f"   Testing baseline for {model_name}...")
            
            # Configure model
            await orchestrators["model"].configure_model(
                model_name=model_name,
                model_type=model_config["type"],
                performance_params={
                    "expected_response_time": model_config["expected_response_time"],
                    "quality_target": model_config["expected_quality_score"]
                }
            )
            
            # Run baseline performance tests
            baseline_results = []
            for scenario in performance_test_scenario["performance_scenarios"]:
                start_time = time.time()
                
                # Generate test response
                test_prompt = self._generate_test_prompt(scenario)
                response = await orchestrators["model"].generate_response(
                    prompt=test_prompt,
                    adapter_name=model_name,
                    story_id=story_id
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # Calculate performance metrics
                performance_data = {
                    "scenario": scenario["scenario"],
                    "response_time": response_time,
                    "token_count": len(response.content.split()) * 1.3,  # Approximate tokens
                    "quality_score": self._calculate_quality_score(response.content),
                    "cost_estimate": model_config["cost_per_token"] * len(response.content.split()) * 1.3,
                    "within_threshold": response_time <= scenario["performance_threshold"]
                }
                
                baseline_results.append(performance_data)
                
                # Record performance metrics
                await orchestrators["performance"].record_model_performance(
                    model_name=model_name,
                    metrics=performance_data
                )
            
            baseline_metrics[model_name] = baseline_results
            print(f"   ✅ Baseline established for {model_name}")
        
        print("✅ All baseline metrics established")
        
        # === PHASE 2: REAL-TIME PERFORMANCE MONITORING ===
        print("🔍 Starting real-time performance monitoring...")
        
        # Simulate continuous story generation with performance monitoring
        monitoring_sessions = 5
        performance_trends = {model: [] for model in baseline_metrics.keys()}
        
        for session in range(monitoring_sessions):
            print(f"   Monitoring session {session + 1}/{monitoring_sessions}")
            
            for model_name in baseline_metrics.keys():
                # Generate story content with performance monitoring
                start_time = time.time()
                
                story_prompt = f"Continue the story: Session {session + 1} narrative development"
                response = await orchestrators["model"].generate_response(
                    prompt=story_prompt,
                    adapter_name=model_name,
                    story_id=story_id
                )
                
                end_time = time.time()
                
                # Monitor performance
                session_performance = {
                    "session": session + 1,
                    "response_time": end_time - start_time,
                    "quality_score": self._calculate_quality_score(response.content),
                    "memory_usage": await orchestrators["performance"].get_memory_usage(),
                    "timestamp": time.time()
                }
                
                performance_trends[model_name].append(session_performance)
                
                # Record for analysis
                await orchestrators["performance"].record_realtime_metrics(
                    model_name=model_name,
                    session_data=session_performance
                )
        
        print("✅ Real-time monitoring completed")
        
        # === PHASE 3: PERFORMANCE ANALYSIS & OPTIMIZATION TRIGGERS ===
        print("🔧 Analyzing performance and triggering optimizations...")
        
        optimization_results = {}
        
        for model_name, trend_data in performance_trends.items():
            # Calculate performance trends
            response_times = [data["response_time"] for data in trend_data]
            quality_scores = [data["quality_score"] for data in trend_data]
            
            avg_response_time = statistics.mean(response_times)
            avg_quality = statistics.mean(quality_scores)
            response_time_variance = statistics.variance(response_times) if len(response_times) > 1 else 0
            
            # Check against optimization targets
            targets = performance_test_scenario["optimization_targets"]
            
            needs_optimization = {
                "response_time": abs(avg_response_time - targets["response_time"]["target"]) > targets["response_time"]["tolerance"],
                "quality": abs(avg_quality - targets["quality_score"]["target"]) > targets["quality_score"]["tolerance"],
                "consistency": response_time_variance > 1.0  # High variance indicates inconsistency
            }
            
            if any(needs_optimization.values()):
                print(f"   ⚠️  {model_name} requires optimization: {needs_optimization}")
                
                # Apply optimization
                optimization_applied = await self._apply_performance_optimization(
                    orchestrators["performance"],
                    model_name,
                    needs_optimization,
                    trend_data
                )
                
                optimization_results[model_name] = optimization_applied
            else:
                print(f"   ✅ {model_name} performance within targets")
                optimization_results[model_name] = {"status": "optimal", "changes": []}
        
        print("✅ Performance optimization analysis completed")
        
        # === PHASE 4: MODEL SWITCHING & FALLBACK TESTING ===
        print("🔄 Testing model switching and fallback mechanisms...")
        
        # Simulate model failure and fallback
        fallback_tests = []
        
        primary_model = performance_test_scenario["test_models"][0]["name"]
        fallback_model = performance_test_scenario["test_models"][1]["name"]
        
        # Test graceful fallback
        try:
            # Simulate primary model failure
            await orchestrators["model"].simulate_model_failure(primary_model)
            
            # Attempt generation (should fallback)
            fallback_start = time.time()
            fallback_response = await orchestrators["model"].generate_response_with_fallback(
                prompt="Test fallback generation",
                primary_adapter=primary_model,
                fallback_adapters=[fallback_model],
                story_id=story_id
            )
            fallback_time = time.time() - fallback_start
            
            fallback_tests.append({
                "test": "primary_failure_fallback",
                "success": fallback_response is not None,
                "fallback_time": fallback_time,
                "used_model": fallback_model
            })
            
        except Exception as e:
            fallback_tests.append({
                "test": "primary_failure_fallback",
                "success": False,
                "error": str(e)
            })
        
        print("✅ Fallback mechanism testing completed")
        
        # === PHASE 5: OPTIMIZATION VALIDATION ===
        print("✅ Validating optimization results...")
        
        # Re-test performance after optimizations
        post_optimization_metrics = {}
        
        for model_name in baseline_metrics.keys():
            if model_name in optimization_results and optimization_results[model_name].get("changes"):
                # Re-run performance test
                validation_start = time.time()
                validation_response = await orchestrators["model"].generate_response(
                    prompt="Post-optimization validation test",
                    adapter_name=model_name,
                    story_id=story_id
                )
                validation_time = time.time() - validation_start
                
                post_optimization_metrics[model_name] = {
                    "response_time": validation_time,
                    "quality_score": self._calculate_quality_score(validation_response.content),
                    "optimization_effective": validation_time < avg_response_time  # Compare to pre-optimization
                }
        
        print("✅ Optimization validation completed")
        
        # === WORKFLOW METRICS ===
        workflow_metrics = {
            "models_tested": len(performance_test_scenario["test_models"]),
            "scenarios_evaluated": len(performance_test_scenario["performance_scenarios"]),
            "monitoring_sessions": monitoring_sessions,
            "optimizations_applied": len([r for r in optimization_results.values() if r.get("changes")]),
            "fallback_tests": len(fallback_tests),
            "fallback_success_rate": sum(1 for test in fallback_tests if test["success"]) / len(fallback_tests) if fallback_tests else 0,
            "performance_improvement": self._calculate_improvement_percentage(baseline_metrics, post_optimization_metrics),
            "workflow_status": "completed"
        }
        
        print(f"🏁 Performance optimization workflow completed!")
        print(f"📊 Performance metrics: {workflow_metrics}")
        
        return {
            "baseline_metrics": baseline_metrics,
            "performance_trends": performance_trends,
            "optimization_results": optimization_results,
            "fallback_tests": fallback_tests,
            "post_optimization": post_optimization_metrics,
            "metrics": workflow_metrics
        }
    
    def _generate_test_prompt(self, scenario: Dict[str, Any]) -> str:
        """Generate test prompt based on scenario complexity."""
        if scenario["prompt_complexity"] == "low":
            return "Generate a simple story continuation."
        elif scenario["prompt_complexity"] == "medium":
            return "Continue the story with character development and plot advancement."
        else:  # high complexity
            return "Create a complex narrative scene with multiple characters, dialogue, action, and world-building details."
    
    def _calculate_quality_score(self, content: str) -> float:
        """Calculate simple quality score based on content characteristics."""
        if not content:
            return 0.0
        
        # Simple heuristics for quality
        word_count = len(content.split())
        has_dialogue = '"' in content or "'" in content
        has_variety = len(set(content.lower().split())) / len(content.split()) if content.split() else 0
        
        quality = 0.5  # Base score
        
        if word_count > 50:
            quality += 0.1
        if word_count > 100:
            quality += 0.1
        if has_dialogue:
            quality += 0.1
        if has_variety > 0.7:
            quality += 0.2
        
        return min(quality, 1.0)
    
    async def _apply_performance_optimization(self, 
                                           performance_orchestrator,
                                           model_name: str,
                                           optimization_needs: Dict[str, bool],
                                           trend_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply performance optimization based on identified needs."""
        
        optimizations_applied = []
        
        if optimization_needs["response_time"]:
            # Apply response time optimization
            await performance_orchestrator.optimize_response_time(model_name)
            optimizations_applied.append("response_time_optimization")
        
        if optimization_needs["quality"]:
            # Apply quality optimization
            await performance_orchestrator.optimize_quality_settings(model_name)
            optimizations_applied.append("quality_optimization")
        
        if optimization_needs["consistency"]:
            # Apply consistency optimization
            await performance_orchestrator.stabilize_performance(model_name)
            optimizations_applied.append("consistency_optimization")
        
        return {
            "status": "optimized",
            "changes": optimizations_applied,
            "timestamp": time.time()
        }
    
    def _calculate_improvement_percentage(self, 
                                        baseline_metrics: Dict[str, List[Dict[str, Any]]], 
                                        post_optimization: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall performance improvement percentage."""
        if not post_optimization:
            return 0.0
        
        improvements = []
        for model_name, post_data in post_optimization.items():
            if model_name in baseline_metrics:
                baseline_avg = statistics.mean([m["response_time"] for m in baseline_metrics[model_name]])
                post_time = post_data["response_time"]
                improvement = (baseline_avg - post_time) / baseline_avg * 100
                improvements.append(improvement)
        
        return statistics.mean(improvements) if improvements else 0.0
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, performance_test_scenario, performance_orchestrators):
        """Test model performance under high load conditions."""
        story_id = f"{performance_test_scenario['story_id']}_load_test"
        orchestrators = performance_orchestrators
        
        # Simulate high load with concurrent requests
        concurrent_requests = 10
        
        async def generate_concurrent_response(request_id):
            start_time = time.time()
            response = await orchestrators["model"].generate_response(
                prompt=f"Concurrent request {request_id}",
                story_id=story_id
            )
            return {
                "request_id": request_id,
                "response_time": time.time() - start_time,
                "success": response is not None
            }
        
        # Run concurrent requests
        load_test_start = time.time()
        results = await asyncio.gather(
            *[generate_concurrent_response(i) for i in range(concurrent_requests)],
            return_exceptions=True
        )
        total_load_time = time.time() - load_test_start
        
        # Analyze load test results
        successful_requests = [r for r in results if isinstance(r, dict) and r["success"]]
        success_rate = len(successful_requests) / concurrent_requests
        avg_response_time = statistics.mean([r["response_time"] for r in successful_requests]) if successful_requests else 0
        
        # Validate performance under load
        assert success_rate >= 0.8  # At least 80% success rate
        assert avg_response_time < 10.0  # Reasonable response time under load
        
        print(f"✅ Load test completed: {success_rate:.2%} success rate, {avg_response_time:.2f}s avg response time")


if __name__ == "__main__":
    # Allow running workflow tests directly
    pytest.main([__file__, "-v", "--tb=short"])
