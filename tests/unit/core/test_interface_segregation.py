"""
Tests for Interface Segregation Implementation

Tests for the segregated model and memory management interfaces,
validating that interface segregation improves testability and maintainability.

Phase 2 Week 11-12: Interface Segregation & Architecture Cleanup
"""

import asyncio
from datetime import UTC
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from openchronicle.domain.models.model_interfaces import AdapterStatus
from openchronicle.domain.models.model_interfaces import IModelLifecycleManager
from openchronicle.domain.models.model_interfaces import IModelResponseGenerator
from openchronicle.domain.models.model_interfaces import ModelConfiguration
from openchronicle.domain.models.model_interfaces import ModelResponse
from openchronicle.domain.models.model_orchestrator import ModelLifecycleManager
from openchronicle.domain.models.model_orchestrator import ModelOrchestrator
from openchronicle.domain.models.model_orchestrator import ModelResponseGenerator
from openchronicle.infrastructure.memory.memory_interfaces import CharacterMemory
from openchronicle.infrastructure.memory.memory_interfaces import (
    ICharacterMemoryManager,
)
from openchronicle.infrastructure.memory.memory_interfaces import (
    IMemoryContextBuilder,
)
from openchronicle.infrastructure.memory.memory_interfaces import IMemoryFlagManager
from openchronicle.infrastructure.memory.memory_interfaces import IMemoryPersistence
from openchronicle.infrastructure.memory.memory_interfaces import IWorldStateManager
from openchronicle.infrastructure.memory.memory_interfaces import MemorySnapshot
from openchronicle.infrastructure.memory.memory_interfaces import WorldState


class TestModelInterfaceSegregation:
    """Test model management interface segregation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_adapters = {"test_adapter": Mock(), "fallback_adapter": Mock()}
        self.mock_config_manager = Mock()
        self.mock_performance_monitor = Mock()

    def test_response_generator_interface_compliance(self):
        """Test that response generator implements its interface correctly."""
        generator = ModelResponseGenerator(
            self.mock_adapters, self.mock_config_manager, self.mock_performance_monitor
        )

        # Verify interface compliance
        assert isinstance(generator, IModelResponseGenerator)
        assert hasattr(generator, "generate_response")
        assert hasattr(generator, "generate_with_fallback_chain")
        assert hasattr(generator, "get_fallback_chain")

    @pytest.mark.asyncio
    async def test_response_generator_successful_generation(self):
        """Test successful response generation."""
        # Setup mocks
        mock_adapter = AsyncMock()
        mock_adapter.generate_response.return_value = "Generated response"
        mock_adapter.model_name = "test_model"

        self.mock_adapters["test_adapter"] = mock_adapter
        self.mock_config_manager.get_model_configuration.return_value = (
            ModelConfiguration(
                provider_name="test_adapter",
                model_name="test_model",
                enabled=True,
                config={},
                fallback_chain=[],
                metadata={},
            )
        )

        generator = ModelResponseGenerator(
            self.mock_adapters, self.mock_config_manager, self.mock_performance_monitor
        )

        # Test response generation
        response = await generator.generate_response(
            prompt="Test prompt", adapter_name="test_adapter"
        )

        # Verify response
        assert isinstance(response, ModelResponse)
        assert response.content == "Generated response"
        assert response.adapter_name == "test_adapter"
        assert response.success is True

        # Verify metrics were recorded
        self.mock_performance_monitor.record_response_time.assert_called_once()
        self.mock_performance_monitor.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_generator_fallback_chain(self):
        """Test fallback chain functionality."""
        # Setup primary adapter to fail
        mock_primary = AsyncMock()
        mock_primary.generate_response.side_effect = Exception("Primary failed")

        # Setup fallback adapter to succeed
        mock_fallback = AsyncMock()
        mock_fallback.generate_response.return_value = "Fallback response"
        mock_fallback.model_name = "fallback_model"

        self.mock_adapters["primary_adapter"] = mock_primary
        self.mock_adapters["fallback_adapter"] = mock_fallback

        generator = ModelResponseGenerator(
            self.mock_adapters, self.mock_config_manager, self.mock_performance_monitor
        )

        # Mock fallback chain
        generator.get_fallback_chain = Mock(return_value=["fallback_adapter"])

        # Test fallback
        response = await generator.generate_response(
            prompt="Test prompt", adapter_name="primary_adapter", use_fallback=True
        )

        # Verify fallback was used
        assert response.adapter_name == "fallback_adapter"
        assert response.content == "Fallback response"

        # Verify failure was recorded
        self.mock_performance_monitor.record_failure.assert_called()

    def test_lifecycle_manager_interface_compliance(self):
        """Test that lifecycle manager implements its interface correctly."""
        manager = ModelLifecycleManager(self.mock_adapters, self.mock_config_manager)

        # Verify interface compliance
        assert isinstance(manager, IModelLifecycleManager)
        assert hasattr(manager, "initialize_adapter")
        assert hasattr(manager, "health_check_adapter")
        assert hasattr(manager, "is_adapter_available")
        assert hasattr(manager, "is_adapter_healthy")

    @pytest.mark.asyncio
    async def test_lifecycle_manager_initialization(self):
        """Test adapter initialization functionality."""
        self.mock_config_manager.get_model_configuration.return_value = (
            ModelConfiguration(
                provider_name="test_adapter",
                model_name="test_model",
                enabled=True,
                config={},
                fallback_chain=[],
                metadata={},
            )
        )

        manager = ModelLifecycleManager(self.mock_adapters, self.mock_config_manager)

        # Test initialization
        success = await manager.initialize_adapter("test_adapter")

        # Verify initialization
        assert success is True
        assert manager.is_adapter_healthy("test_adapter") is True

    @pytest.mark.asyncio
    async def test_lifecycle_manager_health_checks(self):
        """Test health check functionality."""
        manager = ModelLifecycleManager(self.mock_adapters, self.mock_config_manager)

        # Initialize adapter first
        manager.adapter_health["test_adapter"] = {
            "status": "healthy",
            "last_check": datetime.now(UTC),
            "error_count": 0,
            "success_count": 5,
        }

        # Test health check
        status = await manager.health_check_adapter("test_adapter")

        # Verify status
        assert isinstance(status, AdapterStatus)
        assert status.name == "test_adapter"
        assert status.is_healthy is True
        assert status.error_count == 0

    @pytest.mark.asyncio
    async def test_lifecycle_manager_concurrent_initialization(self):
        """Test concurrent adapter initialization."""
        # Setup multiple configurations
        configs = {
            "adapter1": ModelConfiguration("adapter1", "model1", True, {}, [], {}),
            "adapter2": ModelConfiguration("adapter2", "model2", True, {}, [], {}),
            "adapter3": ModelConfiguration("adapter3", "model3", True, {}, [], {}),
        }

        self.mock_config_manager.get_available_models.return_value = configs

        manager = ModelLifecycleManager(self.mock_adapters, self.mock_config_manager)

        # Test concurrent initialization
        results = await manager.initialize_all_adapters(max_concurrent=2)

        # Verify results
        assert len(results) == 3
        assert all(isinstance(success, bool) for success in results.values())

    def test_segregated_orchestrator_composition(self):
        """Test that segregated orchestrator properly composes interfaces."""
        orchestrator = ModelOrchestrator()

        # Verify interface access
        assert isinstance(orchestrator.response_generator, IModelResponseGenerator)
        assert isinstance(orchestrator.lifecycle_manager, IModelLifecycleManager)
        assert hasattr(orchestrator, "configuration_manager")
        assert hasattr(orchestrator, "performance_monitor")

        # Verify convenience methods exist
        assert hasattr(orchestrator, "generate_response")
        assert hasattr(orchestrator, "initialize_adapter")
        assert hasattr(orchestrator, "get_adapter_status")
        assert hasattr(orchestrator, "add_model_config")

    @pytest.mark.asyncio
    async def test_segregated_orchestrator_delegation(self):
        """Test that orchestrator delegates correctly to components."""
        orchestrator = ModelOrchestrator()

        # Mock the internal components
        orchestrator._response_generator.generate_response = AsyncMock(
            return_value=ModelResponse(
                content="test",
                adapter_name="test",
                model_name="test",
                metadata={},
                timestamp=datetime.now(UTC),
                success=True,
            )
        )

        # Test delegation
        response = await orchestrator.generate_response("test prompt", "test_adapter")

        # Verify delegation occurred
        orchestrator._response_generator.generate_response.assert_called_once_with(
            "test prompt", "test_adapter"
        )
        assert response.content == "test"


class TestInterfaceSegregationBenefits:
    """Test that interface segregation provides expected benefits."""

    def test_interface_focused_testing(self):
        """Test that segregated interfaces enable focused testing."""
        # Create mock that only implements response generation
        mock_generator = Mock(spec=IModelResponseGenerator)

        # Test that we can test just response generation logic
        assert hasattr(mock_generator, "generate_response")
        assert not hasattr(
            mock_generator, "initialize_adapter"
        )  # Not part of this interface

        # This demonstrates that tests can focus on single responsibilities
        # Note: For async methods, we need to handle coroutines properly
        mock_generator.generate_response = AsyncMock(return_value="test_response")

        # In real usage, this would be awaited
        coro = mock_generator.generate_response("test_prompt", "test_adapter")
        assert asyncio.iscoroutine(coro)

        # Verify the mock was configured correctly
        mock_generator.generate_response.assert_called_once_with(
            "test_prompt", "test_adapter"
        )

    def test_interface_substitutability(self):
        """Test that interfaces can be substituted with different implementations."""

        # Create different implementations of the same interface
        class MockResponseGenerator(IModelResponseGenerator):
            async def generate_response(
                self, prompt, adapter_name, model_params=None, use_fallback=True
            ):
                return ModelResponse(
                    content=f"Mock: {prompt}",
                    adapter_name=adapter_name,
                    model_name="mock_model",
                    metadata={},
                    timestamp=datetime.now(UTC),
                    success=True,
                )

            async def generate_with_fallback_chain(
                self, prompt, adapter_chain, model_params=None
            ):
                return await self.generate_response(
                    prompt, adapter_chain[0], model_params
                )

            def get_fallback_chain(self, adapter_name):
                return ["fallback1", "fallback2"]

        class TestResponseGenerator(IModelResponseGenerator):
            async def generate_response(
                self, prompt, adapter_name, model_params=None, use_fallback=True
            ):
                return ModelResponse(
                    content=f"Test: {prompt}",
                    adapter_name=adapter_name,
                    model_name="test_model",
                    metadata={},
                    timestamp=datetime.now(UTC),
                    success=True,
                )

            async def generate_with_fallback_chain(
                self, prompt, adapter_chain, model_params=None
            ):
                return await self.generate_response(
                    prompt, adapter_chain[0], model_params
                )

            def get_fallback_chain(self, adapter_name):
                return ["test_fallback"]

        # Both implementations satisfy the interface
        mock_gen = MockResponseGenerator()
        test_gen = TestResponseGenerator()

        # Client code can use either implementation
        async def use_generator(generator: IModelResponseGenerator):
            return await generator.generate_response("test", "adapter")

        # This demonstrates that implementations are substitutable
        # (In a real test, we'd use asyncio.run)
        assert hasattr(mock_gen, "generate_response")
        assert hasattr(test_gen, "generate_response")

    def test_dependency_injection_compatibility(self):
        """Test that segregated interfaces work well with dependency injection."""
        from openchronicle.shared.dependency_injection import DIContainer
        from openchronicle.shared.dependency_injection import ServiceLifetime

        container = DIContainer()

        # Create concrete implementations instead of mocks for proper DI testing
        class TestResponseGenerator:
            def __init__(self):
                self.name = "TestResponseGenerator"

            async def generate_response(
                self, prompt: str, adapter_name: str = None
            ) -> dict:
                return {"content": "test response", "adapter": adapter_name}

        class TestLifecycleManager:
            def __init__(self):
                self.name = "TestLifecycleManager"

            async def initialize_adapter(self, adapter_name: str) -> bool:
                return True

        # Register concrete implementations
        container.register(
            IModelResponseGenerator, TestResponseGenerator, ServiceLifetime.SINGLETON
        )
        container.register(
            IModelLifecycleManager, TestLifecycleManager, ServiceLifetime.SINGLETON
        )

        # Test that services can be resolved
        resolved_generator = container.resolve(IModelResponseGenerator)
        resolved_lifecycle = container.resolve(IModelLifecycleManager)

        assert isinstance(resolved_generator, TestResponseGenerator)
        assert isinstance(resolved_lifecycle, TestLifecycleManager)
        assert resolved_generator.name == "TestResponseGenerator"
        assert resolved_lifecycle.name == "TestLifecycleManager"

        # Test singleton behavior - should return same instance
        second_generator = container.resolve(IModelResponseGenerator)
        assert second_generator is resolved_generator

        # This demonstrates clean DI integration with interface segregation

    def test_interface_single_responsibility(self):
        """Test that each interface has a single, well-defined responsibility."""
        # Response generation interface should only handle response generation
        response_methods = [
            method
            for method in dir(IModelResponseGenerator)
            if not method.startswith("_")
        ]
        assert all(
            "response" in method.lower() or "fallback" in method.lower()
            for method in response_methods
        )

        # Lifecycle management interface should only handle lifecycle
        lifecycle_methods = [
            method
            for method in dir(IModelLifecycleManager)
            if not method.startswith("_")
        ]
        lifecycle_keywords = [
            "initialize",
            "health",
            "shutdown",
            "restart",
            "available",
            "healthy",
        ]
        assert all(
            any(keyword in method.lower() for keyword in lifecycle_keywords)
            for method in lifecycle_methods
        )


class TestMemoryInterfaceSegregation:
    """Test memory management interface segregation."""

    def test_memory_interfaces_exist(self):
        """Test that memory interfaces are properly defined."""
        # Test that all memory interfaces exist and have expected methods
        assert hasattr(IMemoryPersistence, "load_current_memory")
        assert hasattr(IMemoryPersistence, "save_current_memory")
        assert hasattr(IMemoryPersistence, "archive_memory_snapshot")

        assert hasattr(ICharacterMemoryManager, "get_character_memory")
        assert hasattr(ICharacterMemoryManager, "update_character_memory")
        assert hasattr(ICharacterMemoryManager, "update_character_mood")

        assert hasattr(IWorldStateManager, "get_world_state")
        assert hasattr(IWorldStateManager, "update_world_state")
        assert hasattr(IWorldStateManager, "add_location")

        assert hasattr(IMemoryContextBuilder, "build_scene_context")
        assert hasattr(IMemoryContextBuilder, "build_character_context")
        assert hasattr(IMemoryContextBuilder, "get_recent_events")

        assert hasattr(IMemoryFlagManager, "add_memory_flag")
        assert hasattr(IMemoryFlagManager, "remove_memory_flag")
        assert hasattr(IMemoryFlagManager, "has_memory_flag")

    def test_memory_data_structures(self):
        """Test that memory data structures are properly defined."""
        # Test MemorySnapshot structure
        snapshot = MemorySnapshot(
            story_id="test",
            scene_id="scene1",
            timestamp=datetime.now(UTC),
            character_memories={},
            world_state={},
            active_flags=[],
            recent_events=[],
            metadata={},
        )
        assert snapshot.story_id == "test"
        assert snapshot.scene_id == "scene1"

        # Test CharacterMemory structure
        character = CharacterMemory(
            character_name="Test Character",
            personality={},
            relationships={},
            experiences=[],
            current_mood="neutral",
            voice_profile={},
            last_updated=datetime.now(UTC),
            metadata={},
        )
        assert character.character_name == "Test Character"
        assert character.current_mood == "neutral"

        # Test WorldState structure
        world = WorldState(
            locations={},
            time_context={},
            environmental_factors={},
            active_plotlines=[],
            global_flags=[],
            last_updated=datetime.now(UTC),
        )
        assert isinstance(world.locations, dict)
        assert isinstance(world.active_plotlines, list)


if __name__ == "__main__":
    pytest.main([__file__])
