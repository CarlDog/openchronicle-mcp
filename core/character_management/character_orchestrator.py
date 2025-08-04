"""
Character Orchestrator

Central coordinator for all character management components.
Provides unified interface replacing the previous separate character engines.
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime

from .character_base import (
    CharacterEngineBase, 
    CharacterEventHandler,
    CharacterStateProvider,
    CharacterBehaviorProvider,
    CharacterValidationProvider
)
from .character_data import (
    CharacterData, 
    CharacterStats,
    CharacterStatType,
    CharacterBehaviorType,
    CharacterRelationType,
    CharacterInteractionType,
    CharacterConsistencyLevel
)
from .character_storage import CharacterStorage

logger = logging.getLogger(__name__)

class CharacterOrchestrator(CharacterEventHandler):
    """
    Central orchestrator for all character management functionality.
    
    Replaces the previous separate character engines with a unified system
    that coordinates stats, interactions, consistency, and presentation.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize character orchestrator."""
        super().__init__()
        self.config = config or {}
        
        # Initialize storage
        storage_config = self.config.get('storage', {})
        self.storage = CharacterStorage(storage_config)
        
        # Component registry - will be populated as components are loaded
        self.components: Dict[str, CharacterEngineBase] = {}
        self.state_providers: List[CharacterStateProvider] = []
        self.behavior_providers: List[CharacterBehaviorProvider] = []
        self.validation_providers: List[CharacterValidationProvider] = []
        
        # Configuration
        self.auto_save = self.config.get('auto_save', True)
        self.validation_enabled = self.config.get('validation_enabled', True)
        self.event_logging_enabled = self.config.get('event_logging_enabled', True)
        
        # Subscribe to storage events
        self.storage.subscribe_to_event('character_updated', self._on_character_updated)
        self.storage.subscribe_to_event('character_created', self._on_character_created)
        
        logger.info("Character orchestrator initialized")
    
    def register_component(self, component_name: str, component: CharacterEngineBase) -> None:
        """Register a character management component."""
        self.components[component_name] = component
        
        # Register with appropriate provider lists
        if isinstance(component, CharacterStateProvider):
            self.state_providers.append(component)
        if isinstance(component, CharacterBehaviorProvider):
            self.behavior_providers.append(component)
        if isinstance(component, CharacterValidationProvider):
            self.validation_providers.append(component)
        
        logger.info(f"Registered component: {component_name}")
    
    def unregister_component(self, component_name: str) -> bool:
        """Unregister a character management component."""
        if component_name not in self.components:
            return False
        
        component = self.components[component_name]
        
        # Remove from provider lists
        if component in self.state_providers:
            self.state_providers.remove(component)
        if component in self.behavior_providers:
            self.behavior_providers.remove(component)
        if component in self.validation_providers:
            self.validation_providers.remove(component)
        
        del self.components[component_name]
        logger.info(f"Unregistered component: {component_name}")
        return True
    
    # =============================================================================
    # Character Lifecycle Management
    # =============================================================================
    
    def create_character(self, character_id: str, character_data: Optional[Dict] = None) -> CharacterData:
        """Create a new character with all components initialized."""
        # Create character through storage
        character = self.storage.initialize_character(character_id, character_data)
        
        # Initialize in all components
        for component_name, component in self.components.items():
            try:
                component.initialize_character(character_id, **(character_data or {}))
            except Exception as e:
                logger.error(f"Failed to initialize character {character_id} in {component_name}: {e}")
        
        self.emit_event('character_orchestrated', {
            'character_id': character_id,
            'action': 'created',
            'components': list(self.components.keys())
        })
        
        return character
    
    def get_character(self, character_id: str) -> Optional[CharacterData]:
        """Get complete character data."""
        return self.storage.get_character_data(character_id)
    
    def delete_character(self, character_id: str) -> bool:
        """Delete character from all components and storage."""
        success = True
        
        # Delete from all components
        for component_name, component in self.components.items():
            try:
                component.cleanup_character(character_id)
            except Exception as e:
                logger.error(f"Failed to cleanup character {character_id} from {component_name}: {e}")
                success = False
        
        # Delete from storage
        if not self.storage.delete_character(character_id):
            success = False
        
        if success:
            self.emit_event('character_orchestrated', {
                'character_id': character_id,
                'action': 'deleted'
            })
        
        return success
    
    def list_characters(self) -> List[str]:
        """List all available characters."""
        return self.storage.list_characters()
    
    # =============================================================================
    # Character Statistics Interface
    # =============================================================================
    
    def get_character_stats(self, character_id: str) -> Optional[CharacterStats]:
        """Get character statistics."""
        character = self.get_character(character_id)
        return character.stats if character else None
    
    def update_character_stat(self, character_id: str, stat_type: CharacterStatType, 
                            new_value: int, reason: str, scene_context: str = "") -> bool:
        """Update a character statistic."""
        character = self.get_character(character_id)
        if not character or not character.stats:
            return False
        
        # Validate if enabled
        if self.validation_enabled:
            for provider in self.validation_providers:
                valid, error = provider.validate_character_action(character_id, {
                    'type': 'stat_update',
                    'stat_type': stat_type.value,
                    'new_value': new_value,
                    'reason': reason
                })
                if not valid:
                    logger.warning(f"Stat update validation failed for {character_id}: {error}")
                    return False
        
        # Update stat
        character.stats.update_stat(stat_type, new_value, reason, scene_context)
        
        # Save changes
        self.storage.update_character_component(character_id, 'stats', character.stats)
        
        self.emit_event('character_stat_updated', {
            'character_id': character_id,
            'stat_type': stat_type.value,
            'new_value': new_value,
            'reason': reason
        })
        
        return True
    
    def get_effective_stat(self, character_id: str, stat_type: CharacterStatType) -> Optional[int]:
        """Get effective character stat value including modifiers."""
        stats = self.get_character_stats(character_id)
        return stats.get_effective_stat(stat_type) if stats else None
    
    # =============================================================================
    # Character Behavior Interface  
    # =============================================================================
    
    def generate_behavior_context(self, character_id: str, situation_type: str = "general") -> Dict[str, Any]:
        """Generate comprehensive behavior context for character."""
        context = {
            'character_id': character_id,
            'situation_type': situation_type,
            'timestamp': datetime.now().isoformat()
        }
        
        # Gather context from all behavior providers
        for provider in self.behavior_providers:
            try:
                provider_context = provider.get_behavior_context(character_id, situation_type)
                context.update(provider_context)
            except Exception as e:
                logger.error(f"Error getting behavior context from {provider.__class__.__name__}: {e}")
        
        return context
    
    def generate_response_modifiers(self, character_id: str, content_type: str = "dialogue") -> Dict[str, Any]:
        """Generate response modifiers for character content generation."""
        modifiers = {
            'character_id': character_id,
            'content_type': content_type,
            'timestamp': datetime.now().isoformat()
        }
        
        # Gather modifiers from all behavior providers
        for provider in self.behavior_providers:
            try:
                provider_modifiers = provider.generate_response_modifiers(character_id, content_type)
                modifiers.update(provider_modifiers)
            except Exception as e:
                logger.error(f"Error getting response modifiers from {provider.__class__.__name__}: {e}")
        
        return modifiers
    
    # =============================================================================
    # Character State Interface
    # =============================================================================
    
    def get_character_state(self, character_id: str) -> Dict[str, Any]:
        """Get comprehensive character state from all providers."""
        state = {
            'character_id': character_id,
            'timestamp': datetime.now().isoformat()
        }
        
        # Gather state from all state providers
        for provider in self.state_providers:
            try:
                provider_state = provider.get_character_state(character_id)
                state.update(provider_state)
            except Exception as e:
                logger.error(f"Error getting character state from {provider.__class__.__name__}: {e}")
        
        return state
    
    def update_character_state(self, character_id: str, state_updates: Dict[str, Any]) -> bool:
        """Update character state across all providers."""
        success = True
        
        # Update state in all state providers
        for provider in self.state_providers:
            try:
                if not provider.update_character_state(character_id, state_updates):
                    success = False
            except Exception as e:
                logger.error(f"Error updating character state in {provider.__class__.__name__}: {e}")
                success = False
        
        if success:
            self.emit_event('character_state_updated', {
                'character_id': character_id,
                'updates': state_updates
            })
        
        return success
    
    # =============================================================================
    # Character Validation Interface
    # =============================================================================
    
    def validate_character_action(self, character_id: str, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate character action across all validation providers."""
        if not self.validation_enabled:
            return True, None
        
        for provider in self.validation_providers:
            try:
                valid, error = provider.validate_character_action(character_id, action)
                if not valid:
                    return False, error
            except Exception as e:
                logger.error(f"Error in validation provider {provider.__class__.__name__}: {e}")
                return False, f"Validation error: {e}"
        
        return True, None
    
    def get_consistency_score(self, character_id: str) -> float:
        """Get overall character consistency score."""
        scores = []
        
        for provider in self.validation_providers:
            try:
                score = provider.get_consistency_score(character_id)
                scores.append(score)
            except Exception as e:
                logger.error(f"Error getting consistency score from {provider.__class__.__name__}: {e}")
        
        return sum(scores) / len(scores) if scores else 1.0
    
    # =============================================================================
    # Data Management Interface
    # =============================================================================
    
    def export_character_data(self, character_id: str) -> Dict[str, Any]:
        """Export complete character data from all components."""
        base_data = self.storage.export_character_data(character_id)
        
        # Add component data
        component_data = {}
        for component_name, component in self.components.items():
            try:
                component_data[component_name] = component.export_character_data(character_id)
            except Exception as e:
                logger.error(f"Error exporting data from {component_name}: {e}")
        
        base_data['component_data'] = component_data
        return base_data
    
    def import_character_data(self, character_data: Dict[str, Any]) -> bool:
        """Import complete character data to all components."""
        # Import base data
        if not self.storage.import_character_data(character_data):
            return False
        
        # Import component data
        component_data = character_data.get('component_data', {})
        for component_name, data in component_data.items():
            if component_name in self.components:
                try:
                    self.components[component_name].import_character_data(data)
                except Exception as e:
                    logger.error(f"Error importing data to {component_name}: {e}")
        
        return True
    
    def save_all_characters(self) -> Dict[str, bool]:
        """Save all character data."""
        return self.storage.save_all_pending()
    
    # =============================================================================
    # System Interface
    # =============================================================================
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        component_stats = {}
        for component_name, component in self.components.items():
            try:
                component_stats[component_name] = component.get_component_stats()
            except Exception as e:
                logger.error(f"Error getting stats from {component_name}: {e}")
                component_stats[component_name] = {'error': str(e)}
        
        return {
            'orchestrator_version': '1.0.0',
            'registered_components': list(self.components.keys()),
            'character_count': len(self.list_characters()),
            'storage_stats': self.storage.get_cache_stats(),
            'component_stats': component_stats,
            'providers': {
                'state_providers': len(self.state_providers),
                'behavior_providers': len(self.behavior_providers),
                'validation_providers': len(self.validation_providers)
            }
        }
    
    def cleanup_cache(self, max_age_hours: int = 24) -> Dict[str, int]:
        """Clean up cached data across all components."""
        results = {}
        
        # Cleanup storage cache
        results['storage'] = self.storage.cleanup_cache(max_age_hours)
        
        # Cleanup component caches
        for component_name, component in self.components.items():
            if hasattr(component, 'cleanup_cache'):
                try:
                    results[component_name] = component.cleanup_cache(max_age_hours)
                except Exception as e:
                    logger.error(f"Error cleaning up {component_name} cache: {e}")
                    results[component_name] = 0
        
        return results
    
    # =============================================================================
    # Event Handlers
    # =============================================================================
    
    def _on_character_updated(self, event_data: Dict[str, Any]) -> None:
        """Handle character update events from storage."""
        if self.event_logging_enabled:
            logger.info(f"Character updated: {event_data}")
    
    def _on_character_created(self, event_data: Dict[str, Any]) -> None:
        """Handle character creation events from storage."""
        if self.event_logging_enabled:
            logger.info(f"Character created: {event_data}")
