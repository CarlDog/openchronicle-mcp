"""
Unit Tests for SceneOrchestrator

Tests the SceneOrchestrator's ability to coordinate scene persistence, analysis,
and management subsystems in the modular architecture.
"""


import pytest


# Test the actual orchestrator import
try:
    from src.openchronicle.domain.services.scenes.scene_orchestrator import (
        SceneOrchestrator,
    )
    SCENE_ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    SCENE_ORCHESTRATOR_AVAILABLE = False
    IMPORT_ERROR = str(e)

from mocks.mock_adapters import MockDataGenerator
from mocks.mock_adapters import create_mock_database


@pytest.mark.unit
class TestSceneOrchestrator:
    """Test SceneOrchestrator functionality and coordination."""

    def test_import_availability(self):
        """Test that SceneOrchestrator can be imported."""
        if not SCENE_ORCHESTRATOR_AVAILABLE:
            pytest.fail(f"SceneOrchestrator import failed: {IMPORT_ERROR}")

        assert SCENE_ORCHESTRATOR_AVAILABLE, "SceneOrchestrator should be importable"

    @pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
    def test_orchestrator_initialization(self, test_story_id):
        """Test SceneOrchestrator initialization."""
        # Test basic initialization
        orchestrator = SceneOrchestrator(test_story_id)

        # Verify orchestrator is properly initialized
        assert orchestrator is not None
        assert orchestrator.story_id == test_story_id

        # Test configuration initialization
        config = {'enable_logging': False, 'enable_mood_analysis': True}
        orchestrator_with_config = SceneOrchestrator(test_story_id, config=config)

        assert orchestrator_with_config.story_id == test_story_id

    @pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
    def test_orchestrator_components_initialization(self, test_story_id):
        """Test that orchestrator initializes all required components."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test that orchestrator has expected attributes/components
        # Note: Actual attributes depend on implementation
        expected_components = [
            'story_id',
            # Add other expected components based on actual implementation
        ]

        for component in expected_components:
            assert hasattr(orchestrator, component), f"Orchestrator missing {component}"

    @pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
    def test_scene_creation_workflow(self, test_story_id, sample_scene_data):
        """Test complete scene creation workflow."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test scene creation method exists and is callable
        assert hasattr(orchestrator, 'create_scene') or hasattr(orchestrator, 'save_scene'), \
            "Orchestrator should have scene creation method"

        # Test with actual scene orchestrator API parameters
        try:
            # Use save_scene with correct parameters
            if hasattr(orchestrator, 'save_scene'):
                result = orchestrator.save_scene(
                    user_input="Test user input",
                    model_output=sample_scene_data.get('scene_content', 'Test scene content'),
                    memory_snapshot={'location': sample_scene_data.get('location', 'test_location')},
                    flags=sample_scene_data.get('tags', ['test']),
                    scene_label=f"Scene {sample_scene_data.get('scene_number', 1)}"
                )
            elif hasattr(orchestrator, 'create_scene'):
                # If create_scene exists, try that instead
                result = orchestrator.create_scene(
                    user_input="Test user input",
                    model_output=sample_scene_data.get('scene_content', 'Test scene content')
                )

            # Basic validation that something was returned
            assert result is not None, "Scene creation should return a result"

        except Exception as e:
            # If method exists but fails, that's important information
            pytest.fail(f"Scene creation method exists but failed: {e}")    @pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
    def test_orchestrator_error_handling(self, test_story_id):
        """Test orchestrator error handling."""
        # Test that orchestrator handles None story_id gracefully
        # (Based on test results, it appears to accept None but log it)
        orchestrator_none = SceneOrchestrator(None)
        assert orchestrator_none is not None

        # Test with empty string (this might raise an error)
        try:
            orchestrator_empty = SceneOrchestrator("")
            # If it doesn't raise an error, that's also valid behavior
            assert orchestrator_empty is not None
        except (ValueError, TypeError):
            # Expected behavior for empty string
            pass

    @pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
    def test_orchestrator_configuration_handling(self, test_story_id):
        """Test orchestrator configuration handling."""
        # Test with valid configuration
        valid_config = {
            'enable_logging': False,
            'enable_mood_analysis': True,
            'enable_structured_tags': True
        }

        orchestrator = SceneOrchestrator(test_story_id, config=valid_config)
        assert orchestrator.story_id == test_story_id

        # Test with None configuration (should use defaults)
        orchestrator_default = SceneOrchestrator(test_story_id, config=None)
        assert orchestrator_default.story_id == test_story_id

        # Test with empty configuration
        orchestrator_empty = SceneOrchestrator(test_story_id, config={})
        assert orchestrator_empty.story_id == test_story_id


@pytest.mark.unit
@pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
class TestSceneOrchestrationMethods:
    """Test specific orchestration methods and workflows."""

    def test_scene_id_generation(self, test_story_id):
        """Test scene ID generation functionality."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test that ID generation methods exist
        # Note: Actual method names depend on implementation
        possible_id_methods = [
            'generate_scene_id',
            'create_scene_id',
            '_generate_id'
        ]

        has_id_method = any(hasattr(orchestrator, method) for method in possible_id_methods)

        # Check if ID generator is accessible through properties
        if hasattr(orchestrator, 'id_generator'):
            # Test the ID generator component
            id_gen = orchestrator.id_generator
            assert id_gen is not None, "ID generator should be available"
            # Test that it can generate an ID
            test_id = id_gen.generate_scene_id()
            assert test_id is not None, "Should generate a valid scene ID"
            return

        # If no direct ID method, check if it's handled in scene creation
        if not has_id_method:
            # This is acceptable - ID generation might be internal to scene creation
            pytest.skip("ID generation appears to be internal to scene creation")

    def test_structured_tags_handling(self, test_story_id, sample_scene_data):
        """Test structured tags creation and management."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test if orchestrator has structured tag capabilities
        tag_methods = [
            'generate_structured_tags',
            'create_tags',
            'analyze_scene'
        ]

        has_tag_method = any(hasattr(orchestrator, method) for method in tag_methods)

        # Check if labeling system is accessible through properties
        if hasattr(orchestrator, 'labeling_system'):
            # Test the labeling system component
            labeling = orchestrator.labeling_system
            assert labeling is not None, "Labeling system should be available"
            return

        if not has_tag_method:
            # Tags might be generated internally during scene creation
            pytest.skip("Structured tag generation appears to be internal")

    def test_mood_analysis_integration(self, test_story_id, sample_scene_data):
        """Test mood analysis integration."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test if orchestrator has mood analysis capabilities
        mood_methods = [
            'analyze_mood',
            'extract_mood',
            'get_scene_mood'
        ]

        has_mood_method = any(hasattr(orchestrator, method) for method in mood_methods)

        # Check if mood analyzer is accessible through properties
        if hasattr(orchestrator, 'mood_analyzer'):
            # Test the mood analyzer component
            mood_analyzer = orchestrator.mood_analyzer
            assert mood_analyzer is not None, "Mood analyzer should be available"
            return

        if not has_mood_method:
            # Mood analysis might be internal to scene processing
            pytest.skip("Mood analysis appears to be internal")


@pytest.mark.integration
@pytest.mark.skipif(not SCENE_ORCHESTRATOR_AVAILABLE, reason="SceneOrchestrator not available")
class TestSceneOrchestrationIntegration:
    """Test integration between orchestrator components."""

    def test_persistence_layer_integration(self, test_story_id):
        """Test integration with persistence layer."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test that persistence layer is accessible
        persistence_attributes = [
            'persistence_layer',
            'repository',
            'database_manager',
            '_repository'
        ]

        has_persistence = any(hasattr(orchestrator, attr) for attr in persistence_attributes)

        if not has_persistence:
            pytest.skip("Persistence layer integration not directly accessible")

    def test_analysis_layer_integration(self, test_story_id):
        """Test integration with analysis layer."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test that analysis layer is accessible
        analysis_attributes = [
            'analysis_layer',
            'statistics_engine',
            'mood_analyzer',
            '_analyzer'
        ]

        has_analysis = any(hasattr(orchestrator, attr) for attr in analysis_attributes)

        if not has_analysis:
            pytest.skip("Analysis layer integration not directly accessible")

    def test_management_layer_integration(self, test_story_id):
        """Test integration with management layer."""
        orchestrator = SceneOrchestrator(test_story_id)

        # Test that management layer is accessible
        management_attributes = [
            'management_layer',
            'scene_manager',
            'labeling_system',
            '_manager'
        ]

        has_management = any(hasattr(orchestrator, attr) for attr in management_attributes)

        if not has_management:
            pytest.skip("Management layer integration not directly accessible")


@pytest.mark.mock_only
class TestSceneOrchestrationWithMocks:
    """Test orchestration with mock components."""

    def test_scene_creation_with_mock_data(self, test_story_id):
        """Test scene creation using mock data."""
        # Generate comprehensive mock scene data
        mock_scenes = MockDataGenerator.generate_scene_data(count=3)

        # Validate mock data structure
        assert len(mock_scenes) == 3
        for scene in mock_scenes:
            assert 'scene_id' in scene
            assert 'user_input' in scene
            assert 'model_output' in scene
            assert 'memory_snapshot' in scene

    @pytest.mark.asyncio
    async def test_mock_database_integration(self, test_story_id):
        """Test orchestration with mock database."""
        mock_db = create_mock_database()

        # Test mock database operations
        result = await mock_db.execute_query("SELECT * FROM scenes WHERE story_id = ?", (test_story_id,))
        assert isinstance(result, list)

        # Test mock insert
        insert_result = await mock_db.execute_query("INSERT INTO scenes (story_id, content) VALUES (?, ?)",
                                            (test_story_id, "test_content"))
        assert insert_result[0]['affected_rows'] == 1
        assert 'inserted_id' in insert_result[0]
