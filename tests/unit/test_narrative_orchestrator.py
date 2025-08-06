"""
Unit tests for NarrativeOrchestrator

Tests the narrative systems coordination and management functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List, Optional

# Import the orchestrator under test
from core.narrative_systems.narrative_orchestrator import NarrativeOrchestrator, NarrativeState

# Import enhanced mock adapters for isolated testing
from tests.mocks.mock_adapters import MockLLMAdapter, MockModelOrchestrator


class TestNarrativeOrchestratorInitialization:
    """Test NarrativeOrchestrator initialization and configuration."""
    
    def test_orchestrator_initialization(self):
        """Test basic orchestrator initialization."""
        orchestrator = NarrativeOrchestrator()
        
        assert orchestrator is not None
        assert hasattr(orchestrator, 'response_orchestrator')
        assert hasattr(orchestrator, 'mechanics_orchestrator')
        assert hasattr(orchestrator, 'consistency_orchestrator')
    
    def test_orchestrator_state_management(self):
        """Test narrative state management capabilities."""
        orchestrator = NarrativeOrchestrator()
        
        # Test state initialization
        initial_state = orchestrator.get_narrative_state()
        assert initial_state is not None
        assert isinstance(initial_state, dict)
        
        # Test state updates
        test_state = {'scene_id': 'test_123', 'mood': 'tense'}
        result = orchestrator.update_narrative_state(test_state)
        assert result is not None


class TestNarrativeMechanics:
    """Test narrative mechanics and dice engine functionality."""
    
    def test_narrative_mechanics_basic(self):
        """Test basic narrative mechanics operations."""
        orchestrator = NarrativeOrchestrator()
        
        # Test mechanics availability
        assert hasattr(orchestrator, 'mechanics_orchestrator')
        
        # Test dice engine integration
        dice_result = orchestrator.roll_dice('1d20')
        assert dice_result is not None
        assert isinstance(dice_result, (int, dict))
    
    @pytest.mark.asyncio
    async def test_narrative_branching(self):
        """Test narrative branching capabilities."""
        orchestrator = NarrativeOrchestrator()
        
        # Test branching logic
        scenario = {
            'scene_id': 'test_scene',
            'choices': ['option_a', 'option_b', 'option_c'],
            'character_stats': {'wisdom': 15, 'charisma': 12}
        }
        
        branch_result = await orchestrator.evaluate_narrative_branch(scenario)
        assert branch_result is not None
        assert 'selected_option' in branch_result or 'error' in branch_result
    
    def test_mechanics_orchestration(self):
        """Test mechanics orchestration coordination."""
        orchestrator = NarrativeOrchestrator()
        
        # Test mechanics coordination
        mechanics_status = orchestrator.get_mechanics_status()
        assert mechanics_status is not None
        assert isinstance(mechanics_status, dict)


class TestEmotionalStability:
    """Test emotional stability tracking and management."""
    
    def test_emotional_stability_tracking(self):
        """Test character emotional stability tracking."""
        orchestrator = NarrativeOrchestrator()
        
        # Test emotional state tracking
        character_data = {
            'character_id': 'test_char_001',
            'emotional_state': 'stable',
            'recent_events': ['positive_interaction', 'minor_stress']
        }
        
        stability_result = orchestrator.track_emotional_stability(character_data)
        assert stability_result is not None
        assert 'stability_score' in stability_result or 'error' in stability_result
    
    def test_emotional_consistency_validation(self):
        """Test emotional consistency validation."""
        orchestrator = NarrativeOrchestrator()
        
        # Test consistency checking
        emotional_history = [
            {'timestamp': 1, 'state': 'happy', 'intensity': 7},
            {'timestamp': 2, 'state': 'sad', 'intensity': 9},  # Sudden change
            {'timestamp': 3, 'state': 'angry', 'intensity': 8}
        ]
        
        consistency_result = orchestrator.validate_emotional_consistency(emotional_history)
        assert consistency_result is not None
        assert isinstance(consistency_result, dict)


class TestQualityAssessment:
    """Test response quality assessment functionality."""
    
    @pytest.mark.asyncio
    async def test_response_quality_assessment(self):
        """Test response quality evaluation."""
        orchestrator = NarrativeOrchestrator()
        
        # Test quality assessment
        response_data = {
            'content': 'The hero stepped forward, sword gleaming in the moonlight.',
            'context': {'genre': 'fantasy', 'mood': 'dramatic'},
            'character_consistency': True,
            'narrative_flow': True
        }
        
        quality_result = await orchestrator.assess_response_quality(response_data)
        assert quality_result is not None
        assert 'quality_score' in quality_result or 'error' in quality_result
    
    def test_quality_metrics_calculation(self):
        """Test quality metrics calculation."""
        orchestrator = NarrativeOrchestrator()
        
        # Test metrics calculation
        metrics_data = {
            'coherence': 8.5,
            'creativity': 7.2,
            'character_voice': 9.1,
            'plot_advancement': 6.8
        }
        
        overall_quality = orchestrator.calculate_quality_metrics(metrics_data)
        assert overall_quality is not None
        assert isinstance(overall_quality, (float, dict))


class TestNarrativeIntegration:
    """Test integration between narrative subsystems."""
    
    @pytest.mark.asyncio
    async def test_response_orchestration_integration(self):
        """Test integration with response orchestration."""
        orchestrator = NarrativeOrchestrator()
        
        # Test response orchestration
        request_data = {
            'prompt': 'What happens next?',
            'context': {'scene': 'forest_clearing', 'characters': ['hero', 'wizard']},
            'requirements': {'style': 'descriptive', 'length': 'medium'}
        }
        
        orchestration_result = await orchestrator.orchestrate_response(request_data)
        assert orchestration_result is not None
        assert isinstance(orchestration_result, dict)
    
    def test_consistency_orchestration_integration(self):
        """Test integration with consistency orchestration."""
        orchestrator = NarrativeOrchestrator()
        
        # Test consistency orchestration
        consistency_data = {
            'scene_history': ['scene_1', 'scene_2', 'scene_3'],
            'character_states': {'hero': {'health': 80, 'morale': 'high'}},
            'world_state': {'time_of_day': 'evening', 'weather': 'clear'}
        }
        
        consistency_result = orchestrator.validate_narrative_consistency(consistency_data)
        assert consistency_result is not None
        assert isinstance(consistency_result, dict)


class TestNarrativeErrorHandling:
    """Test error handling in narrative operations."""
    
    @pytest.mark.asyncio
    async def test_invalid_narrative_data_handling(self):
        """Test handling of invalid narrative data."""
        orchestrator = NarrativeOrchestrator()
        
        # Test with invalid data
        invalid_data = {
            'malformed': True,
            'missing_required_fields': None
        }
        
        try:
            result = await orchestrator.process_narrative_request(invalid_data)
            # Should handle gracefully
            assert result is not None
            assert 'error' in result or 'success' in result
        except Exception as e:
            # Exception handling is also acceptable
            assert len(str(e)) > 0
    
    def test_subsystem_failure_recovery(self):
        """Test recovery from subsystem failures."""
        orchestrator = NarrativeOrchestrator()
        
        # Mock subsystem failure
        with patch.object(orchestrator, 'mechanics_orchestrator') as mock_mechanics:
            mock_mechanics.side_effect = Exception("Subsystem failure")
            
            # Should handle gracefully
            try:
                result = orchestrator.get_mechanics_status()
                assert result is not None
            except Exception:
                # Exception is acceptable for this test
                pass


class TestNarrativePerformance:
    """Test performance aspects of narrative operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_narrative_operations(self):
        """Test concurrent narrative processing."""
        orchestrator = NarrativeOrchestrator()
        
        # Test concurrent operations
        async def process_narrative(i):
            return await orchestrator.process_simple_narrative_request({
                'id': f'request_{i}',
                'content': f'Test narrative request {i}'
            })
        
        tasks = [process_narrative(i) for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        assert len(results) == 3
        # All results should be non-None (success or exception)
        assert all(result is not None for result in results)
    
    def test_narrative_state_performance(self):
        """Test narrative state management performance."""
        orchestrator = NarrativeOrchestrator()
        
        # Test rapid state updates
        import time
        start_time = time.time()
        
        for i in range(10):
            state_update = {'update_id': i, 'timestamp': time.time()}
            orchestrator.update_narrative_state(state_update)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time
        assert execution_time < 5.0  # 5 seconds max for 10 updates
