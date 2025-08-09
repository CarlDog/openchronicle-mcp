"""
API interfaces for OpenChronicle.

This module provides REST API endpoints for all OpenChronicle functionality.
It serves as the HTTP interface layer in the hexagonal architecture.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from contextlib import asynccontextmanager

from ...application import ApplicationFacade
from ...infrastructure import InfrastructureContainer, InfrastructureConfig


# ================================
# Request/Response Models
# ================================

class StoryCreateRequest(BaseModel):
    """Request model for creating a new story."""
    title: str = Field(..., min_length=1, max_length=200, description="Story title")
    description: Optional[str] = Field(None, max_length=2000, description="Story description")
    world_state: Dict[str, Any] = Field(default_factory=dict, description="Initial world state")
    genre: Optional[str] = Field(None, description="Story genre")
    target_audience: Optional[str] = Field(None, description="Target audience")


class StoryUpdateRequest(BaseModel):
    """Request model for updating an existing story."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    world_state: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class CharacterCreateRequest(BaseModel):
    """Request model for creating a new character."""
    name: str = Field(..., min_length=1, max_length=100, description="Character name")
    personality_traits: Dict[str, float] = Field(default_factory=dict, description="Personality traits with 0-10 values")
    background: Optional[str] = Field(None, max_length=1000, description="Character background")
    appearance: Optional[str] = Field(None, max_length=500, description="Physical appearance")
    goals: List[str] = Field(default_factory=list, description="Character goals")
    relationships: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Character relationships")


class SceneGenerateRequest(BaseModel):
    """Request model for generating a new scene."""
    story_id: str = Field(..., description="Story ID")
    setting: str = Field(..., description="Scene setting")
    participant_ids: List[str] = Field(..., description="Character IDs participating in scene")
    user_input: str = Field(..., description="User direction for scene")
    model_preference: Optional[str] = Field(None, description="Preferred AI model")


class StoryResponse(BaseModel):
    """Response model for story data."""
    id: str
    title: str
    description: Optional[str]
    world_state: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class CharacterResponse(BaseModel):
    """Response model for character data."""
    id: str
    name: str
    personality_traits: Dict[str, float]
    background: Optional[str]
    appearance: Optional[str]
    goals: List[str]
    relationships: Dict[str, Dict[str, Any]]
    emotional_state: Dict[str, float]
    character_arc: List[Dict[str, Any]]
    memory_profile: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SceneResponse(BaseModel):
    """Response model for scene data."""
    id: str
    story_id: str
    setting: str
    participants: List[str]
    ai_response: str
    user_input: str
    character_updates: Dict[str, Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    timestamp: datetime
    components: Dict[str, str]


# ================================
# Dependencies
# ================================

class APIContainer:
    """Container for API dependencies."""
    
    def __init__(self):
        # Create default infrastructure configuration
        config = InfrastructureConfig(
            storage_backend="filesystem",
            storage_path="storage",
            cache_type="memory"
        )
        self.infrastructure = InfrastructureContainer(config)
        self.app_facade = None
    
    async def initialize(self):
        """Initialize the application facade."""
        await self.infrastructure.initialize()
        self.app_facade = ApplicationFacade(
            story_orchestrator=self.infrastructure.get_story_orchestrator(),
            character_orchestrator=self.infrastructure.get_character_orchestrator(), 
            scene_orchestrator=self.infrastructure.get_scene_orchestrator(),
            memory_manager=self.infrastructure.get_memory_manager()
        )


# Global container instance
_container = APIContainer()


async def get_app_facade() -> ApplicationFacade:
    """Dependency injection for application facade."""
    if _container.app_facade is None:
        await _container.initialize()
    return _container.app_facade


# ================================
# Application Lifecycle
# ================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    print("🚀 Starting OpenChronicle API...")
    await _container.initialize()
    print("✅ API ready!")
    
    yield
    
    # Shutdown
    print("🔄 Shutting down OpenChronicle API...")
    await _container.infrastructure.shutdown()
    print("✅ Shutdown complete!")


# ================================
# FastAPI Application
# ================================

app = FastAPI(
    title="OpenChronicle API",
    description="Narrative AI engine with advanced character management and story generation",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware for web client support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================
# Story Endpoints
# ================================

@app.post("/api/v1/stories", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    request: StoryCreateRequest,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> StoryResponse:
    """Create a new story."""
    try:
        result = await app_facade.create_story(
            title=request.title,
            description=request.description,
            world_state=request.world_state,
            genre=request.genre,
            target_audience=request.target_audience
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        story = result.data
        return StoryResponse(
            id=story.id,
            title=story.title,
            description=story.description,
            world_state=story.world_state,
            status=story.status.value,
            created_at=story.created_at,
            updated_at=story.updated_at,
            metadata=story.metadata
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create story: {str(e)}"
        )


@app.get("/api/v1/stories/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: str,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> StoryResponse:
    """Get a story by ID."""
    try:
        result = await app_facade.get_story(story_id)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Story not found: {story_id}"
            )
        
        story = result.data
        return StoryResponse(
            id=story.id,
            title=story.title,
            description=story.description,
            world_state=story.world_state,
            status=story.status.value,
            created_at=story.created_at,
            updated_at=story.updated_at,
            metadata=story.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get story: {str(e)}"
        )


@app.put("/api/v1/stories/{story_id}", response_model=StoryResponse)
async def update_story(
    story_id: str,
    request: StoryUpdateRequest,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> StoryResponse:
    """Update an existing story."""
    try:
        # Build update data from non-None fields
        update_data = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.world_state is not None:
            update_data["world_state"] = request.world_state
        if request.status is not None:
            update_data["status"] = request.status
        
        result = await app_facade.update_story(story_id, update_data)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        story = result.data
        return StoryResponse(
            id=story.id,
            title=story.title,
            description=story.description,
            world_state=story.world_state,
            status=story.status.value,
            created_at=story.created_at,
            updated_at=story.updated_at,
            metadata=story.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update story: {str(e)}"
        )


@app.get("/api/v1/stories", response_model=List[StoryResponse])
async def list_stories(
    skip: int = 0,
    limit: int = 50,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> List[StoryResponse]:
    """List all stories with pagination."""
    try:
        result = await app_facade.list_stories(skip=skip, limit=limit)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        stories = result.data
        return [
            StoryResponse(
                id=story.id,
                title=story.title,
                description=story.description,
                world_state=story.world_state,
                status=story.status.value,
                created_at=story.created_at,
                updated_at=story.updated_at,
                metadata=story.metadata
            )
            for story in stories
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list stories: {str(e)}"
        )


# ================================
# Character Endpoints  
# ================================

@app.post("/api/v1/stories/{story_id}/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    story_id: str,
    request: CharacterCreateRequest,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> CharacterResponse:
    """Create a new character in a story."""
    try:
        result = await app_facade.create_character(
            story_id=story_id,
            name=request.name,
            personality_traits=request.personality_traits,
            background=request.background,
            appearance=request.appearance,
            goals=request.goals,
            relationships=request.relationships
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        character = result.data
        return CharacterResponse(
            id=character.id,
            name=character.name,
            personality_traits=character.personality_traits,
            background=character.background,
            appearance=character.appearance,
            goals=character.goals,
            relationships=character.relationships,
            emotional_state=character.emotional_state,
            character_arc=character.character_arc,
            memory_profile=character.memory_profile,
            created_at=character.created_at,
            updated_at=character.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create character: {str(e)}"
        )


@app.get("/api/v1/characters/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> CharacterResponse:
    """Get a character by ID."""
    try:
        result = await app_facade.get_character(character_id)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character not found: {character_id}"
            )
        
        character = result.data
        return CharacterResponse(
            id=character.id,
            name=character.name,
            personality_traits=character.personality_traits,
            background=character.background,
            appearance=character.appearance,
            goals=character.goals,
            relationships=character.relationships,
            emotional_state=character.emotional_state,
            character_arc=character.character_arc,
            memory_profile=character.memory_profile,
            created_at=character.created_at,
            updated_at=character.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get character: {str(e)}"
        )


@app.get("/api/v1/stories/{story_id}/characters", response_model=List[CharacterResponse])
async def list_story_characters(
    story_id: str,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> List[CharacterResponse]:
    """List all characters in a story."""
    try:
        result = await app_facade.get_story_characters(story_id)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        characters = result.data
        return [
            CharacterResponse(
                id=character.id,
                name=character.name,
                personality_traits=character.personality_traits,
                background=character.background,
                appearance=character.appearance,
                goals=character.goals,
                relationships=character.relationships,
                emotional_state=character.emotional_state,
                character_arc=character.character_arc,
                memory_profile=character.memory_profile,
                created_at=character.created_at,
                updated_at=character.updated_at
            )
            for character in characters
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list characters: {str(e)}"
        )


# ================================
# Scene Endpoints
# ================================

@app.post("/api/v1/scenes", response_model=SceneResponse, status_code=status.HTTP_201_CREATED)
async def generate_scene(
    request: SceneGenerateRequest,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> SceneResponse:
    """Generate a new scene."""
    try:
        result = await app_facade.generate_scene(
            story_id=request.story_id,
            setting=request.setting,
            participant_ids=request.participant_ids,
            user_input=request.user_input,
            model_preference=request.model_preference
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        scene_data = result.data
        return SceneResponse(
            id=scene_data["scene_id"],
            story_id=request.story_id,
            setting=request.setting,
            participants=request.participant_ids,
            ai_response=scene_data["content"],
            user_input=request.user_input,
            character_updates=scene_data.get("character_updates", {}),
            metadata=scene_data.get("metadata", {}),
            created_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate scene: {str(e)}"
        )


@app.get("/api/v1/stories/{story_id}/scenes", response_model=List[SceneResponse])
async def list_story_scenes(
    story_id: str,
    skip: int = 0,
    limit: int = 50,
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> List[SceneResponse]:
    """List scenes for a story with pagination."""
    try:
        result = await app_facade.get_story_scenes(story_id, skip=skip, limit=limit)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": result.errors}
            )
        
        scenes = result.data
        return [
            SceneResponse(
                id=scene.id,
                story_id=scene.story_id,
                setting=scene.setting,
                participants=scene.participants,
                ai_response=scene.ai_response,
                user_input=scene.user_input,
                character_updates=scene.character_updates,
                metadata=scene.metadata,
                created_at=scene.created_at
            )
            for scene in scenes
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scenes: {str(e)}"
        )


# ================================
# Health & System Endpoints
# ================================

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check(
    app_facade: ApplicationFacade = Depends(get_app_facade)
) -> HealthResponse:
    """Health check endpoint."""
    try:
        # Get infrastructure health status
        health_status = await _container.infrastructure.health_check()
        
        return HealthResponse(
            status=health_status["status"],
            timestamp=datetime.now(),
            components=health_status["components"]
        )
        
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            components={"error": str(e)}
        )


@app.get("/api/v1/status")
async def system_status():
    """System status and information."""
    return {
        "service": "OpenChronicle API",
        "version": "0.1.0",
        "architecture": "Hexagonal/Clean Architecture",
        "timestamp": datetime.now(),
        "endpoints": {
            "stories": "/api/v1/stories",
            "characters": "/api/v1/characters",
            "scenes": "/api/v1/scenes",
            "health": "/api/v1/health"
        }
    }


# ================================
# Development Server
# ================================

def run_dev_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """Run the development server."""
    print(f"🚀 Starting OpenChronicle API on {host}:{port}")
    uvicorn.run(
        "src.openchronicle.interfaces.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    run_dev_server()
