"""
OpenChronicle Application Layer.

This layer contains the application's use cases and coordinates between
the domain layer and infrastructure layer. It implements the CQRS pattern
with commands for write operations and queries for read operations.

The application layer:
- Defines commands and queries that represent business use cases
- Orchestrates complex workflows involving multiple domain services
- Maintains transaction boundaries and ensures data consistency
- Provides a clean interface between domain logic and external systems

Key Components:
- Commands: Write operations that change system state
- Queries: Read operations that retrieve information
- Orchestrators: Coordinate complex workflows and use cases
- Interfaces: Abstract repository and service contracts

Architecture Principles:
- CQRS: Separate read and write operations
- Clean Architecture: Dependencies point inward toward domain
- SOLID: Single responsibility, dependency inversion
- DDD: Application services coordinate domain objects
"""

from .commands import (
    Command,
    CommandResult,
    CreateStoryCommand,
    UpdateStoryCommand,
    CreateCharacterCommand,
    UpdateCharacterCommand,
    GenerateSceneCommand,
    SaveSceneCommand,
    UpdateMemoryCommand,
    RollbackStoryCommand,
    DeleteStoryCommand,
    DeleteCharacterCommand,
)

from .queries import (
    Query,
    QueryResult,
    PaginationInfo,
    GetStoryQuery,
    ListStoriesQuery,
    GetCharacterQuery,
    ListCharactersQuery,
    GetSceneQuery,
    ListScenesQuery,
    GetMemoryStateQuery,
    SearchMemoryQuery,
    GetCharacterRelationshipsQuery,
    GetStoryTimelineQuery,
    GetStoryStatisticsQuery,
    SearchContentQuery,
    GetModelUsageQuery,
    ValidateStoryConsistencyQuery,
)

from .orchestrators import (
    BaseOrchestrator,
    StoryOrchestrator,
    CharacterOrchestrator,
    NarrativeOrchestrator,
    StoryRepository,
    CharacterRepository,
    SceneRepository,
    MemoryManager,
    ModelManager,
)


# Application layer facade for easy access
class ApplicationFacade:
    """
    Facade providing easy access to application layer components.

    This class acts as a single entry point for the application layer,
    reducing coupling and providing a stable interface for external systems.
    """

    def __init__(
        self,
        story_orchestrator: StoryOrchestrator,
        character_orchestrator: CharacterOrchestrator,
        narrative_orchestrator: NarrativeOrchestrator,
    ):
        self.story = story_orchestrator
        self.character = character_orchestrator
        self.narrative = narrative_orchestrator

    async def execute_command(self, command: Command) -> CommandResult:
        """Execute a command through the appropriate orchestrator."""

        # Story commands
        if isinstance(
            command, (CreateStoryCommand, UpdateStoryCommand, DeleteStoryCommand)
        ):
            return await self.story.handle_command(command)

        # Character commands
        elif isinstance(
            command,
            (CreateCharacterCommand, UpdateCharacterCommand, DeleteCharacterCommand),
        ):
            return await self.character.handle_command(command)

        # Narrative commands
        elif isinstance(
            command,
            (
                GenerateSceneCommand,
                SaveSceneCommand,
                UpdateMemoryCommand,
                RollbackStoryCommand,
            ),
        ):
            return await self.narrative.handle_command(command)

        else:
            return CommandResult.failure(f"Unknown command type: {type(command)}")

    async def execute_query(self, query: Query) -> QueryResult:
        """Execute a query through the appropriate handler."""

        # Story queries
        if isinstance(
            query,
            (
                GetStoryQuery,
                ListStoriesQuery,
                GetStoryStatisticsQuery,
                ValidateStoryConsistencyQuery,
            ),
        ):
            return await self.story.handle_query(query)

        # Character queries
        elif isinstance(
            query,
            (GetCharacterQuery, ListCharactersQuery, GetCharacterRelationshipsQuery),
        ):
            return await self.character.handle_query(query)

        # Scene and narrative queries
        elif isinstance(
            query,
            (
                GetSceneQuery,
                ListScenesQuery,
                GetMemoryStateQuery,
                SearchMemoryQuery,
                GetStoryTimelineQuery,
            ),
        ):
            return await self.narrative.handle_query(query)

        # Cross-cutting queries
        elif isinstance(query, (SearchContentQuery, GetModelUsageQuery)):
            return await self._handle_cross_cutting_query(query)

        else:
            return QueryResult.failure(f"Unknown query type: {type(query)}")

    async def _handle_cross_cutting_query(self, query: Query) -> QueryResult:
        """Handle queries that span multiple orchestrators."""
        # These would be implemented based on specific requirements
        # and might involve coordinating between multiple orchestrators
        return QueryResult.failure("Cross-cutting queries not yet implemented")


# Version information
__version__ = "1.0.0"
__author__ = "OpenChronicle Team"


# Export main components
__all__ = [
    # Commands
    "Command",
    "CommandResult",
    "CreateStoryCommand",
    "UpdateStoryCommand",
    "CreateCharacterCommand",
    "UpdateCharacterCommand",
    "GenerateSceneCommand",
    "SaveSceneCommand",
    "UpdateMemoryCommand",
    "RollbackStoryCommand",
    "DeleteStoryCommand",
    "DeleteCharacterCommand",
    # Queries
    "Query",
    "QueryResult",
    "PaginationInfo",
    "GetStoryQuery",
    "ListStoriesQuery",
    "GetCharacterQuery",
    "ListCharactersQuery",
    "GetSceneQuery",
    "ListScenesQuery",
    "GetMemoryStateQuery",
    "SearchMemoryQuery",
    "GetCharacterRelationshipsQuery",
    "GetStoryTimelineQuery",
    "GetStoryStatisticsQuery",
    "SearchContentQuery",
    "GetModelUsageQuery",
    "ValidateStoryConsistencyQuery",
    # Orchestrators
    "BaseOrchestrator",
    "StoryOrchestrator",
    "CharacterOrchestrator",
    "NarrativeOrchestrator",
    # Interfaces
    "StoryRepository",
    "CharacterRepository",
    "SceneRepository",
    "MemoryManager",
    "ModelManager",
    # Facade
    "ApplicationFacade",
    # Metadata
    "__version__",
    "__author__",
]
