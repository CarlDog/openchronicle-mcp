"""
Character Base Classes

Provides base classes and interfaces for the character management system.
These classes establish common patterns used across all character components.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from datetime import datetime
from enum import Enum

# Setup logging
logger = logging.getLogger(__name__)

class CharacterEngineBase(ABC):
    """
    Abstract base class for all character management components.
    
    Provides common patterns for configuration, character data management,
    and component lifecycle that all character engines should follow.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize character engine component."""
        self.config = config or {}
        self.character_data: Dict[str, Any] = {}
        self._setup_logging()
        self._validate_config()
    
    def _setup_logging(self) -> None:
        """Setup component-specific logging."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def _validate_config(self) -> None:
        """Validate component configuration. Override in subclasses."""
        pass
    
    @abstractmethod
    def initialize_character(self, character_id: str, **kwargs) -> Any:
        """Initialize character data for this component."""
        pass
    
    @abstractmethod
    def get_character_data(self, character_id: str) -> Optional[Any]:
        """Retrieve character data for this component."""
        pass
    
    @abstractmethod
    def export_character_data(self, character_id: str) -> Dict[str, Any]:
        """Export character data for serialization."""
        pass
    
    @abstractmethod
    def import_character_data(self, character_data: Dict[str, Any]) -> None:
        """Import character data from serialization."""
        pass
    
    def get_component_stats(self) -> Dict[str, Any]:
        """Get component statistics and status."""
        return {
            'component_name': self.__class__.__name__,
            'character_count': len(self.character_data),
            'characters': list(self.character_data.keys()),
            'config': self.config
        }
    
    def cleanup_character(self, character_id: str) -> bool:
        """Remove character data from this component."""
        if character_id in self.character_data:
            del self.character_data[character_id]
            self.logger.info(f"Cleaned up character data for {character_id}")
            return True
        return False

class CharacterDataMixin:
    """
    Mixin class providing common serialization methods for character data.
    
    Any dataclass representing character data should include this mixin
    to ensure consistent serialization behavior.
    """
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        
        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
            elif isinstance(value, list) and value and hasattr(value[0], 'to_dict'):
                data[key] = [item.to_dict() if hasattr(item, 'to_dict') else item for item in value]
                
        return data
    
    @classmethod 
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterDataMixin':
        """Create instance from dictionary."""
        # This is a base implementation - subclasses should override
        # to handle their specific field types properly
        return cls(**data)

class CharacterEventHandler:
    """
    Base class for handling character-related events.
    
    Provides event subscription and notification patterns for character
    state changes, interactions, and system events.
    """
    
    def __init__(self):
        self.event_handlers: Dict[str, List[callable]] = {}
        self.event_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
    
    def subscribe_to_event(self, event_type: str, handler: callable) -> None:
        """Subscribe to character events."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def unsubscribe_from_event(self, event_type: str, handler: callable) -> bool:
        """Unsubscribe from character events."""
        if event_type in self.event_handlers and handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
            return True
        return False
    
    def emit_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Emit character event to all subscribers."""
        # Add to history
        event_record = {
            'type': event_type,
            'data': event_data,
            'timestamp': datetime.now().isoformat(),
            'source': self.__class__.__name__
        }
        
        self.event_history.append(event_record)
        
        # Trim history if needed
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
        
        # Notify subscribers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
    
    def get_event_history(self, event_type: Optional[str] = None, 
                         character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get filtered event history."""
        history = self.event_history
        
        if event_type:
            history = [e for e in history if e['type'] == event_type]
        
        if character_id:
            history = [e for e in history if e['data'].get('character_id') == character_id]
        
        return history

# Common interfaces that components can implement

class CharacterStateProvider(ABC):
    """Interface for components that provide character state information."""
    
    @abstractmethod
    def get_character_state(self, character_id: str) -> Dict[str, Any]:
        """Get current character state."""
        pass
    
    @abstractmethod
    def update_character_state(self, character_id: str, state_updates: Dict[str, Any]) -> bool:
        """Update character state."""
        pass

class CharacterBehaviorProvider(ABC):
    """Interface for components that influence character behavior."""
    
    @abstractmethod
    def get_behavior_context(self, character_id: str, situation_type: str) -> Dict[str, Any]:
        """Get behavior context for character in given situation."""
        pass
    
    @abstractmethod
    def generate_response_modifiers(self, character_id: str, content_type: str) -> Dict[str, Any]:
        """Get response modifiers for character content generation."""
        pass

class CharacterValidationProvider(ABC):
    """Interface for components that validate character consistency."""
    
    @abstractmethod
    def validate_character_action(self, character_id: str, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate if action is consistent with character."""
        pass
    
    @abstractmethod
    def get_consistency_score(self, character_id: str) -> float:
        """Get character consistency score (0.0 to 1.0)."""
        pass
