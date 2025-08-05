"""
Mock Adapters for OpenChronicle Testing

Provides mock LLM providers and adapters for isolated testing without
requiring actual API calls to external services.
"""

from typing import Dict, Any, List, Optional
import json
import time
from unittest.mock import Mock, MagicMock


class MockLLMAdapter:
    """Mock LLM adapter for testing without external API calls."""
    
    def __init__(self, name: str = "mock_adapter", **kwargs):
        self.name = name
        self.api_key = "mock_api_key"
        self.model_name = "mock_model"
        self.max_tokens = 2000
        self.temperature = 0.7
        self.call_count = 0
        self.last_prompt = None
        self.simulate_delay = kwargs.get('simulate_delay', 0.1)
        self.simulate_failures = kwargs.get('simulate_failures', False)
        self.failure_rate = kwargs.get('failure_rate', 0.1)
        
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate mock response."""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Simulate processing delay
        if self.simulate_delay > 0:
            time.sleep(self.simulate_delay)
        
        # Simulate occasional failures
        if self.simulate_failures and self.call_count % int(1/self.failure_rate) == 0:
            raise Exception(f"Mock failure from {self.name}")
        
        # Generate contextual mock response based on prompt content
        response_content = self._generate_contextual_response(prompt)
        
        return {
            'content': response_content,
            'model': self.model_name,
            'provider': self.name,
            'tokens_used': len(response_content.split()) * 1.3,  # Rough token estimate
            'finish_reason': 'stop',
            'timestamp': time.time(),
            'call_number': self.call_count
        }
    
    def _generate_contextual_response(self, prompt: str) -> str:
        """Generate contextual mock response based on prompt content."""
        prompt_lower = prompt.lower()
        
        # Character creation responses
        if 'character' in prompt_lower and 'create' in prompt_lower:
            return "A mysterious figure emerged from the shadows, their intentions unclear but their presence commanding attention."
        
        # Scene continuation responses  
        elif 'continue' in prompt_lower or 'what happens next' in prompt_lower:
            return "The tension in the air grew palpable as events began to unfold in unexpected ways."
        
        # Dialogue responses
        elif 'dialogue' in prompt_lower or 'conversation' in prompt_lower:
            return '"I understand your concern," the character replied thoughtfully, "but we must consider all possibilities before acting."'
        
        # Action sequences
        elif 'action' in prompt_lower or 'fight' in prompt_lower or 'battle' in prompt_lower:
            return "Swift movements and calculated decisions marked the intense sequence that followed."
        
        # Default response
        else:
            return f"This is a mock response generated for testing purposes. Original prompt contained {len(prompt.split())} words."
    
    def get_stats(self) -> Dict[str, Any]:
        """Get mock adapter statistics."""
        return {
            'name': self.name,
            'total_calls': self.call_count,
            'last_prompt_length': len(self.last_prompt) if self.last_prompt else 0,
            'status': 'healthy',
            'simulated_failures': self.simulate_failures
        }


class MockImageAdapter:
    """Mock image generation adapter for testing."""
    
    def __init__(self, name: str = "mock_image_adapter", **kwargs):
        self.name = name
        self.call_count = 0
        self.last_prompt = None
        
    def generate_image(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate mock image response."""
        self.call_count += 1
        self.last_prompt = prompt
        
        return {
            'image_url': f"https://mock-image-service.com/generated/{self.call_count}.png",
            'prompt': prompt,
            'provider': self.name,
            'timestamp': time.time(),
            'call_number': self.call_count,
            'metadata': {
                'width': kwargs.get('width', 1024),
                'height': kwargs.get('height', 1024),
                'style': kwargs.get('style', 'default')
            }
        }


class MockModelOrchestrator:
    """Mock model orchestrator for testing model management."""
    
    def __init__(self):
        self.adapters = {
            'primary_mock': MockLLMAdapter('primary_mock'),
            'fallback_mock': MockLLMAdapter('fallback_mock', simulate_failures=True),
            'reliable_mock': MockLLMAdapter('reliable_mock', simulate_delay=0.05)
        }
        self.active_adapter = 'primary_mock'
        self.fallback_chain = ['primary_mock', 'fallback_mock', 'reliable_mock']
        
    def get_adapter(self, name: str) -> MockLLMAdapter:
        """Get adapter by name."""
        return self.adapters.get(name)
    
    def generate_with_fallback(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response with fallback logic."""
        for adapter_name in self.fallback_chain:
            try:
                adapter = self.adapters[adapter_name]
                response = adapter.generate_response(prompt, **kwargs)
                response['adapter_used'] = adapter_name
                return response
            except Exception as e:
                if adapter_name == self.fallback_chain[-1]:  # Last adapter
                    raise Exception(f"All adapters failed. Last error: {e}")
                continue
                
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            'active_adapter': self.active_adapter,
            'total_adapters': len(self.adapters),
            'adapter_stats': {name: adapter.get_stats() for name, adapter in self.adapters.items()},
            'fallback_chain': self.fallback_chain
        }


class MockDatabaseManager:
    """Mock database manager for testing persistence without actual database."""
    
    def __init__(self):
        self.data = {}  # In-memory storage
        self.operation_count = 0
        
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Mock query execution."""
        self.operation_count += 1
        
        # Simple mock responses based on query type
        if 'SELECT' in query.upper():
            return self._mock_select_response(query)
        elif 'INSERT' in query.upper():
            return self._mock_insert_response(query, params)
        elif 'UPDATE' in query.upper():
            return self._mock_update_response(query, params)
        else:
            return []
    
    def _mock_select_response(self, query: str) -> List[Dict[str, Any]]:
        """Generate mock SELECT response."""
        if 'scenes' in query.lower():
            return [
                {
                    'scene_id': 'mock_scene_001',
                    'user_input': 'Mock user input',
                    'model_output': 'Mock model output',
                    'timestamp': '2025-08-05T12:00:00Z',
                    'structured_tags': '{"mood": "neutral", "scene_type": "dialogue"}'
                }
            ]
        return []
    
    def _mock_insert_response(self, query: str, params: Optional[tuple]) -> List[Dict[str, Any]]:
        """Generate mock INSERT response."""
        return [{'rowid': self.operation_count, 'success': True}]
    
    def _mock_update_response(self, query: str, params: Optional[tuple]) -> List[Dict[str, Any]]:
        """Generate mock UPDATE response."""
        return [{'rows_affected': 1, 'success': True}]


# Factory functions for easy test setup
def create_mock_adapters(count: int = 3) -> Dict[str, MockLLMAdapter]:
    """Create multiple mock adapters for testing."""
    return {
        f'mock_adapter_{i}': MockLLMAdapter(f'mock_adapter_{i}')
        for i in range(count)
    }

def create_test_model_orchestrator() -> MockModelOrchestrator:
    """Create mock model orchestrator for testing."""
    return MockModelOrchestrator()

def create_mock_database() -> MockDatabaseManager:
    """Create mock database manager for testing."""
    return MockDatabaseManager()


# Test data generators
class MockDataGenerator:
    """Generate realistic test data for various scenarios."""
    
    @staticmethod
    def generate_scene_data(count: int = 5) -> List[Dict[str, Any]]:
        """Generate multiple mock scene data entries."""
        scenes = []
        for i in range(count):
            scenes.append({
                'scene_id': f'test_scene_{i+1:03d}',
                'user_input': f'Test user input for scene {i+1}',
                'model_output': f'Generated content for scene {i+1} with narrative elements.',
                'memory_snapshot': {
                    'scene_number': i+1,
                    'character_state': 'active',
                    'location': f'test_location_{i+1}'
                },
                'timestamp': f'2025-08-05T12:{i:02d}:00Z',
                'flags': ['test_flag'],
                'context_refs': [f'context_{i+1}']
            })
        return scenes
    
    @staticmethod  
    def generate_character_data() -> Dict[str, Any]:
        """Generate mock character data."""
        return {
            'name': 'Test Character',
            'personality': 'Analytical and thoughtful',
            'background': 'Experienced problem solver',
            'current_state': {
                'emotional_state': 'curious',
                'physical_state': 'healthy',
                'location': 'starting_area'
            },
            'relationships': {},
            'goals': ['discover_truth', 'help_others']
        }


# Export all mock components
__all__ = [
    'MockLLMAdapter',
    'MockImageAdapter', 
    'MockModelOrchestrator',
    'MockDatabaseManager',
    'MockDataGenerator',
    'create_mock_adapters',
    'create_test_model_orchestrator',
    'create_mock_database'
]
