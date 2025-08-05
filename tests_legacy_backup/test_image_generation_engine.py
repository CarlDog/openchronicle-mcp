"""
Tests for Image Generation Engine

Tests the image generation system including:
- Image adapter functionality
- Engine integration with story system
- Metadata management
- Auto-generation features
- Error handling and fallbacks
"""

import asyncio
import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest

from core.image_systems import (
    ImageGenerationEngine, ImageMetadata, create_image_engine,
    auto_generate_character_portrait, auto_generate_scene_image
)
from core.image_systems import (
    ImageAdapterRegistry, ImageGenerationRequest, ImageGenerationResult,
    ImageProvider, ImageSize, ImageType, OpenAIImageAdapter, MockImageAdapter,
    create_image_registry
)


class TestImageAdapter:
    """Test image adapter functionality"""
    
    def test_image_generation_request_creation(self):
        """Test creation and validation of image generation requests"""
        request = ImageGenerationRequest(
            prompt="A fantasy wizard",
            image_type=ImageType.CHARACTER,
            character_name="Gandalf"
        )
        
        assert request.prompt == "A fantasy wizard"
        assert request.image_type == ImageType.CHARACTER
        assert request.character_name == "Gandalf"
        assert request.size == ImageSize.SQUARE_512  # Default
        assert "detailed character portrait" in request.style_modifiers
        assert "high quality" in request.style_modifiers
        
    def test_image_generation_request_scene_modifiers(self):
        """Test scene-specific style modifiers"""
        request = ImageGenerationRequest(
            prompt="A grand castle",
            image_type=ImageType.SCENE
        )
        
        assert "detailed environment" in request.style_modifiers
        assert "atmospheric" in request.style_modifiers
        assert "cinematic composition" in request.style_modifiers
        
    def test_mock_adapter_availability(self):
        """Test mock adapter availability"""
        config = {"enabled": True, "provider": "mock"}
        adapter = MockImageAdapter(config)
        
        assert adapter.is_available()
        assert adapter.supports_size(ImageSize.SQUARE_512)
        assert adapter.supports_size(ImageSize.SQUARE_1024)
        
    @pytest.mark.asyncio
    async def test_mock_adapter_generation(self):
        """Test mock adapter image generation"""
        config = {"enabled": True, "provider": "mock"}
        adapter = MockImageAdapter(config)
        
        request = ImageGenerationRequest(
            prompt="Test wizard",
            image_type=ImageType.CHARACTER
        )
        
        result = await adapter.generate_image(request)
        
        assert result.success
        assert result.image_url is not None
        assert result.image_url.startswith("data:image/png;base64,")
        assert result.generation_time > 0
        assert result.cost == 0.0
        assert result.metadata["model"] == "mock_generator"
        
    def test_openai_adapter_availability(self):
        """Test OpenAI adapter availability checks"""
        # Without API key
        config = {"enabled": True, "provider": "openai_dalle"}
        adapter = OpenAIImageAdapter(config)
        assert not adapter.is_available()
        
        # With API key
        config["api_key"] = "test-key"
        adapter = OpenAIImageAdapter(config)
        assert adapter.is_available()
        
    def test_openai_adapter_size_support(self):
        """Test OpenAI adapter size support"""
        config = {"enabled": True, "provider": "openai_dalle", "model": "dall-e-3"}
        adapter = OpenAIImageAdapter(config)
        
        assert adapter.supports_size(ImageSize.SQUARE_1024)
        assert adapter.supports_size(ImageSize.PORTRAIT_512)
        assert not adapter.supports_size(ImageSize.SQUARE_512)  # Not supported by DALL-E 3
        
    def test_registry_creation(self):
        """Test image adapter registry creation"""
        config = {
            "image_adapters": {
                "mock": {"enabled": True},
                "openai": {"enabled": True, "model": "dall-e-3"}
            }
        }
        
        registry = create_image_registry(config)
        
        assert registry.get_adapter(ImageProvider.MOCK) is not None
        assert registry.get_adapter(ImageProvider.OPENAI_DALLE) is not None
        
        available = registry.get_available_adapters()
        assert len(available) >= 1  # At least mock should be available
        
    @pytest.mark.asyncio
    async def test_registry_fallback(self):
        """Test registry fallback mechanism"""
        config = {
            "image_adapters": {
                "mock": {"enabled": True}
            }
        }
        
        registry = create_image_registry(config)
        
        request = ImageGenerationRequest(
            prompt="Test image",
            image_type=ImageType.CHARACTER
        )
        
        # Should fallback to mock adapter
        result = await registry.generate_image(request, ImageProvider.OPENAI_DALLE)
        assert result.success
        assert "mock" in result.metadata["model"]


class TestImageGenerationEngine:
    """Test the main image generation engine"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.story_path = Path(self.temp_dir) / "test_story"
        self.story_path.mkdir()
        
        self.config = {
            "image_adapters": {
                "mock": {"enabled": True}
            },
            "auto_generate": {
                "character_portraits": True,
                "scene_images": True,
                "scene_triggers": ["major_event", "new_location"]
            },
            "naming": {
                "character_prefix": "char",
                "scene_prefix": "scene"
            }
        }
        
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_engine_initialization(self):
        """Test engine initialization"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        assert engine.story_path == self.story_path
        assert engine.images_path.exists()
        assert engine.metadata_file.name == "images.json"
        assert len(engine.metadata) == 0
        
    @pytest.mark.asyncio
    async def test_basic_image_generation(self):
        """Test basic image generation"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        image_id = await engine.generate_image(
            prompt="A brave knight",
            image_type=ImageType.CHARACTER,
            character_name="Sir Lancelot"
        )
        
        assert image_id is not None
        assert image_id in engine.metadata
        
        metadata = engine.metadata[image_id]
        assert metadata.character_name == "Sir Lancelot"
        assert metadata.image_type == ImageType.CHARACTER
        assert metadata.prompt == "A brave knight"
        
        # Check file was created
        image_path = engine.get_image_path(image_id)
        assert image_path.exists()
        
    @pytest.mark.asyncio
    async def test_character_portrait_generation(self):
        """Test character portrait generation with character data"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        character_data = {
            "description": "A wise old wizard",
            "appearance": {
                "hair": "long white beard",
                "eyes": "twinkling blue"
            },
            "personality": {
                "demeanor": "kind and thoughtful"
            }
        }
        
        image_id = await engine.generate_character_portrait("Gandalf", character_data)
        
        assert image_id is not None
        metadata = engine.metadata[image_id]
        
        assert metadata.character_name == "Gandalf"
        assert metadata.image_type == ImageType.CHARACTER
        assert "wise old wizard" in metadata.prompt
        assert "hair: long white beard" in metadata.prompt
        
    @pytest.mark.asyncio
    async def test_scene_image_generation(self):
        """Test scene image generation"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        scene_data = {
            "description": "A grand throne room",
            "location": "Royal Palace",
            "atmosphere": "majestic and imposing"
        }
        
        context = {
            "recent_events": "The king has called for a royal audience"
        }
        
        image_id = await engine.generate_scene_image("scene_001", scene_data, context)
        
        assert image_id is not None
        metadata = engine.metadata[image_id]
        
        assert metadata.scene_id == "scene_001"
        assert metadata.image_type == ImageType.SCENE
        assert "grand throne room" in metadata.prompt
        assert "Royal Palace" in metadata.prompt
        
    def test_filename_generation(self):
        """Test filename generation patterns"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        # Character filename
        filename = engine._generate_filename(ImageType.CHARACTER, "Gandalf")
        assert filename.startswith("char-gandalf-")
        assert filename.endswith(".png")
        
        # Scene filename
        filename = engine._generate_filename(ImageType.SCENE, scene_id="scene_001")
        assert filename.startswith("scene-scene_001-")
        assert filename.endswith(".png")
        
    def test_metadata_persistence(self):
        """Test metadata saving and loading"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        # Create test metadata
        metadata = ImageMetadata(
            image_id="test_001",
            filename="test.png",
            image_type=ImageType.CHARACTER,
            prompt="Test prompt",
            character_name="TestChar",
            scene_id=None,
            provider="mock",
            model="test_model",
            size="512x512",
            generation_time=1.0,
            cost=0.0,
            timestamp="2025-01-01T00:00:00",
            tags=["test"]
        )
        
        engine.metadata["test_001"] = metadata
        engine._save_metadata()
        
        # Create new engine and check if metadata was loaded
        engine2 = ImageGenerationEngine(str(self.story_path), self.config)
        
        assert "test_001" in engine2.metadata
        loaded_meta = engine2.metadata["test_001"]
        assert loaded_meta.character_name == "TestChar"
        assert loaded_meta.image_type == ImageType.CHARACTER
        
    def test_image_querying(self):
        """Test querying images by character, scene, and tags"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        # Add test metadata
        metadata1 = ImageMetadata(
            image_id="char_001", filename="char1.png", image_type=ImageType.CHARACTER,
            prompt="Character 1", character_name="Gandalf", scene_id=None,
            provider="mock", model="test", size="512x512", generation_time=1.0,
            cost=0.0, timestamp="2025-01-01T00:00:00", tags=["wizard", "main"]
        )
        
        metadata2 = ImageMetadata(
            image_id="scene_001", filename="scene1.png", image_type=ImageType.SCENE,
            prompt="Scene 1", character_name=None, scene_id="scene_001",
            provider="mock", model="test", size="512x512", generation_time=1.0,
            cost=0.0, timestamp="2025-01-01T00:00:00", tags=["indoor", "palace"]
        )
        
        engine.metadata["char_001"] = metadata1
        engine.metadata["scene_001"] = metadata2
        
        # Test queries
        gandalf_images = engine.get_images_by_character("Gandalf")
        assert len(gandalf_images) == 1
        assert gandalf_images[0].image_id == "char_001"
        
        scene_images = engine.get_images_by_scene("scene_001")
        assert len(scene_images) == 1
        assert scene_images[0].image_id == "scene_001"
        
        wizard_images = engine.get_images_by_tag("wizard")
        assert len(wizard_images) == 1
        assert wizard_images[0].image_id == "char_001"
        
    def test_image_deletion(self):
        """Test image deletion"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        # Create a test file
        test_file = engine.images_path / "test.png"
        test_file.write_text("test content")
        
        # Add metadata
        metadata = ImageMetadata(
            image_id="test_001", filename="test.png", image_type=ImageType.CHARACTER,
            prompt="Test", character_name="Test", scene_id=None,
            provider="mock", model="test", size="512x512", generation_time=1.0,
            cost=0.0, timestamp="2025-01-01T00:00:00", tags=[]
        )
        engine.metadata["test_001"] = metadata
        
        # Delete image
        success = engine.delete_image("test_001")
        
        assert success
        assert "test_001" not in engine.metadata
        assert not test_file.exists()
        
    def test_engine_statistics(self):
        """Test engine statistics collection"""
        engine = ImageGenerationEngine(str(self.story_path), self.config)
        
        # Simulate some generated images
        engine.stats["images_generated"] = 5
        engine.stats["total_cost"] = 0.20
        engine.stats["generation_time"] = 12.5
        engine.stats["providers_used"] = {"openai", "mock"}
        
        stats = engine.get_engine_stats()
        
        assert stats["images_generated"] == 5
        assert stats["total_cost"] == 0.20
        assert stats["generation_time"] == 12.5
        assert "openai" in stats["providers_used"]
        assert "mock" in stats["providers_used"]
        assert "available_adapters" in stats


class TestAutoGeneration:
    """Test automatic image generation features"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.story_path = Path(self.temp_dir) / "test_story"
        self.story_path.mkdir()
        
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @pytest.mark.asyncio
    async def test_auto_character_portrait_enabled(self):
        """Test automatic character portrait generation when enabled"""
        config = {
            "image_adapters": {"mock": {"enabled": True}},
            "auto_generate": {"character_portraits": True}
        }
        
        engine = ImageGenerationEngine(str(self.story_path), config)
        character_data = {"description": "A brave knight"}
        
        image_id = await auto_generate_character_portrait(engine, "Lancelot", character_data)
        
        assert image_id is not None
        assert "Lancelot" in [meta.character_name for meta in engine.metadata.values()]
        
    @pytest.mark.asyncio
    async def test_auto_character_portrait_disabled(self):
        """Test no generation when auto portraits disabled"""
        config = {
            "image_adapters": {"mock": {"enabled": True}},
            "auto_generate": {"character_portraits": False}
        }
        
        engine = ImageGenerationEngine(str(self.story_path), config)
        character_data = {"description": "A brave knight"}
        
        image_id = await auto_generate_character_portrait(engine, "Lancelot", character_data)
        
        assert image_id is None
        assert len(engine.metadata) == 0
        
    @pytest.mark.asyncio
    async def test_auto_character_portrait_existing(self):
        """Test no duplicate generation for existing character portraits"""
        config = {
            "image_adapters": {"mock": {"enabled": True}},
            "auto_generate": {"character_portraits": True}
        }
        
        engine = ImageGenerationEngine(str(self.story_path), config)
        
        # Generate first portrait
        await engine.generate_character_portrait("Lancelot", {"description": "A knight"})
        
        # Try auto-generation - should skip
        character_data = {"description": "A brave knight"}
        image_id = await auto_generate_character_portrait(engine, "Lancelot", character_data)
        
        assert image_id is None
        # Should still only have one image
        lancelot_images = engine.get_images_by_character("Lancelot")
        assert len(lancelot_images) == 1
        
    @pytest.mark.asyncio
    async def test_auto_scene_generation_triggers(self):
        """Test automatic scene generation triggers"""
        config = {
            "image_adapters": {"mock": {"enabled": True}},
            "auto_generate": {
                "scene_images": True,
                "scene_triggers": ["major_event", "new_location"]
            }
        }
        
        engine = ImageGenerationEngine(str(self.story_path), config)
        
        # Test major event trigger
        scene_data = {
            "description": "Epic battle scene",
            "importance": "high"
        }
        
        image_id = await auto_generate_scene_image(engine, "scene_001", scene_data)
        assert image_id is not None
        
        # Test new location trigger
        scene_data = {
            "description": "Ancient ruins",
            "new_location": True
        }
        
        image_id = await auto_generate_scene_image(engine, "scene_002", scene_data)
        assert image_id is not None
        
        # Test no trigger
        scene_data = {
            "description": "Normal conversation",
            "importance": "normal"
        }
        
        image_id = await auto_generate_scene_image(engine, "scene_003", scene_data)
        assert image_id is None


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.story_path = Path(self.temp_dir) / "test_story"
        self.story_path.mkdir()
        
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @pytest.mark.asyncio
    async def test_no_available_adapters(self):
        """Test behavior when no adapters are available"""
        config = {
            "image_adapters": {
                "mock": {"enabled": False}
            }
        }
        
        engine = ImageGenerationEngine(str(self.story_path), config)
        
        image_id = await engine.generate_image(
            prompt="Test",
            image_type=ImageType.CHARACTER
        )
        
        assert image_id is None
        assert len(engine.metadata) == 0
        
    def test_corrupted_metadata_handling(self):
        """Test handling of corrupted metadata files"""
        engine = ImageGenerationEngine(str(self.story_path), {"image_adapters": {}})
        
        # Create corrupted metadata file
        with open(engine.metadata_file, 'w') as f:
            f.write("invalid json content")
            
        # Should handle gracefully and start with empty metadata
        engine2 = ImageGenerationEngine(str(self.story_path), {"image_adapters": {}})
        assert len(engine2.metadata) == 0
        
    def test_missing_image_file_handling(self):
        """Test handling when image file is missing"""
        engine = ImageGenerationEngine(str(self.story_path), {"image_adapters": {}})
        
        # Create metadata for non-existent file
        metadata = ImageMetadata(
            image_id="missing_001", filename="missing.png", image_type=ImageType.CHARACTER,
            prompt="Missing", character_name="Ghost", scene_id=None,
            provider="mock", model="test", size="512x512", generation_time=1.0,
            cost=0.0, timestamp="2025-01-01T00:00:00", tags=[]
        )
        engine.metadata["missing_001"] = metadata
        
        # Getting path should work
        path = engine.get_image_path("missing_001")
        assert path is not None
        assert not path.exists()
        
        # Deletion should handle missing file gracefully
        success = engine.delete_image("missing_001")
        assert success  # Should succeed even if file doesn't exist


if __name__ == "__main__":
    # Run tests manually if pytest not available
    import asyncio
    
    async def run_basic_tests():
        """Run basic functionality tests"""
        print("Testing Image Generation Engine...")
        
        # Test basic adapter
        adapter_test = TestImageAdapter()
        await adapter_test.test_mock_adapter_generation()
        print("✅ Mock adapter generation works")
        
        # Test engine
        engine_test = TestImageGenerationEngine()
        engine_test.setup_method()
        
        try:
            await engine_test.test_basic_image_generation()
            print("✅ Basic image generation works")
            
            await engine_test.test_character_portrait_generation()
            print("✅ Character portrait generation works")
            
            await engine_test.test_scene_image_generation()
            print("✅ Scene image generation works")
            
        finally:
            engine_test.teardown_method()
            
        print("All basic tests passed! 🎉")
        
    asyncio.run(run_basic_tests())
