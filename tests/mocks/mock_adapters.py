"""
Enhanced Mock Adapters for OpenChronicle Testing

Comprehensive mock LLM providers and adapters for reliable testing without
requiring actual API calls to external services. Includes advanced features
for testing edge cases, performance scenarios, and error conditions.

This file replaces the old mock_adapters.py with enhanced functionality
while maintaining backward compatibility for existing tests.
"""

import asyncio
import time
import random
import json
from typing import Dict, Any, List, Optional, Union
from unittest.mock import Mock, MagicMock, AsyncMock
from dataclasses import dataclass, asdict


@dataclass
class MockResponse:
    """Structured mock response for consistent testing."""
    content: str
    model: str
    provider: str
    tokens_used: int
    finish_reason: str
    timestamp: float
    metadata: Dict[str, Any]
    call_number: int


class MockLLMAdapter:
    """Enhanced mock LLM adapter with advanced testing features."""
    
    def __init__(self, name: str = "mock_adapter", **kwargs):
        self.name = name
        self.api_key = "mock_api_key"
        self.model_name = kwargs.get('model_name', 'mock-model-v1')
        self.max_tokens = kwargs.get('max_tokens', 2000)
        self.temperature = kwargs.get('temperature', 0.7)
        self.call_count = 0
        self.last_prompt = None
        self.response_history = []
        
        # Performance simulation
        self.simulate_delay = kwargs.get('simulate_delay', 0.1)
        self.delay_variance = kwargs.get('delay_variance', 0.05)
        
        # Failure simulation
        self.simulate_failures = kwargs.get('simulate_failures', False)
        self.failure_rate = kwargs.get('failure_rate', 0.1)
        self.failure_pattern = kwargs.get('failure_pattern', 'random')  # 'random', 'every_n', 'after_m_calls'
        self.failure_after_calls = kwargs.get('failure_after_calls', 5)
        
        # Response quality simulation
        self.response_quality = kwargs.get('response_quality', 'high')  # 'high', 'medium', 'low'
        self.coherence_level = kwargs.get('coherence_level', 0.9)  # 0.0 to 1.0
        
        # Token usage simulation
        self.token_multiplier = kwargs.get('token_multiplier', 1.3)
        self.min_tokens = kwargs.get('min_tokens', 50)
        
        # Backward compatibility
        self.config = {}
        
    async def generate_response(self, prompt: str, **kwargs) -> MockResponse:
        """Generate enhanced mock response with realistic behavior."""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Simulate processing delay with variance
        if self.simulate_delay > 0:
            delay = self.simulate_delay + random.uniform(-self.delay_variance, self.delay_variance)
            delay = max(0.01, delay)  # Ensure minimum delay
            await asyncio.sleep(delay)
        
        # Check for simulated failures
        if self._should_fail():
            raise self._generate_failure_exception()
        
        # Generate contextual response
        response_content = self._generate_enhanced_response(prompt, kwargs)
        
        # Calculate token usage
        tokens_used = self._calculate_token_usage(response_content, prompt)
        
        # Create structured response
        response = MockResponse(
            content=response_content,
            model=self.model_name,
            provider=self.name,
            tokens_used=tokens_used,
            finish_reason='stop',
            timestamp=time.time(),
            metadata=self._generate_metadata(prompt, kwargs),
            call_number=self.call_count
        )
        
        # Store in history
        self.response_history.append(response)
        
        return response
    
    def _should_fail(self) -> bool:
        """Determine if this call should simulate a failure."""
        if not self.simulate_failures:
            return False
        
        if self.failure_pattern == 'random':
            return random.random() < self.failure_rate
        elif self.failure_pattern == 'every_n':
            return self.call_count % int(1/self.failure_rate) == 0
        elif self.failure_pattern == 'after_m_calls':
            return self.call_count > self.failure_after_calls
        else:
            return False
    
    def _generate_failure_exception(self) -> Exception:
        """Generate realistic failure exception."""
        failure_types = [
            Exception(f"Mock API error from {self.name}: Rate limit exceeded"),
            Exception(f"Mock API error from {self.name}: Service unavailable"),
            Exception(f"Mock API error from {self.name}: Invalid request"),
            Exception(f"Mock API error from {self.name}: Timeout")
        ]
        return random.choice(failure_types)
    
    def _generate_enhanced_response(self, prompt: str, kwargs: Dict[str, Any]) -> str:
        """Generate enhanced contextual response."""
        prompt_lower = prompt.lower()
        
        # Get base response
        response = self._get_base_response(prompt_lower)
        
        # Adjust quality based on configuration
        quality_level = self.coherence_level
        if self.response_quality == 'low':
            quality_level = 0.3
        elif self.response_quality == 'medium':
            quality_level = 0.6
        
        response = self._adjust_response_quality(response, quality_level)
        
        # Add creativity for high-quality responses
        if self.response_quality == 'high':
            response = self._add_creativity(response)
        
        # Truncate if needed
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        response = self._truncate_to_tokens(response, max_tokens)
        
        return response
    
    def _get_base_response(self, prompt_lower: str) -> str:
        """Get base response based on prompt content."""
        # Character creation responses
        if 'character' in prompt_lower and 'create' in prompt_lower:
            return "A mysterious figure emerged from the shadows, their intentions unclear but their presence commanding attention. Their eyes held ancient wisdom, and their movements spoke of experience beyond mortal years."
        
        # Scene continuation responses  
        elif 'continue' in prompt_lower or 'what happens next' in prompt_lower:
            return "The tension in the air grew palpable as events began to unfold in unexpected ways. Each moment seemed to carry the weight of destiny, and the characters found themselves at the crossroads of fate."
        
        # Dialogue responses
        elif 'dialogue' in prompt_lower or 'conversation' in prompt_lower:
            return '"I understand your concern," the character replied thoughtfully, "but we must consider all possibilities before acting. Sometimes the greatest wisdom lies in patience and observation."'
        
        # Action sequences
        elif 'action' in prompt_lower or 'fight' in prompt_lower or 'battle' in prompt_lower:
            return "Swift movements and calculated decisions marked the intense sequence that followed. Every strike and parry was a dance of death, each moment a test of skill and determination."
        
        # Forest/outdoor scenes
        elif 'forest' in prompt_lower or 'woods' in prompt_lower:
            return "The ancient trees loomed overhead, their branches creating a natural cathedral of shadows and light. The forest floor was alive with the sounds of nature, and the air carried the scent of earth and growth."
        
        # Castle/palace scenes
        elif 'castle' in prompt_lower or 'palace' in prompt_lower:
            return "The imposing stone walls rose before them, a testament to centuries of power and tradition. The castle stood as a symbol of authority, its towers reaching toward the heavens like fingers of stone."
        
        # Default response
        else:
            return f"This is an enhanced mock response generated for testing purposes. The original prompt contained {len(prompt_lower.split())} words and touched upon themes of narrative development and character interaction."
    
    def _degrade_response_quality(self, response: str) -> str:
        """Degrade response quality for testing error conditions."""
        words = response.split()
        if len(words) > 10:
            # Remove random words
            remove_count = max(1, len(words) // 4)
            for _ in range(remove_count):
                if len(words) > 5:
                    words.pop(random.randint(0, len(words) - 1))
        return ' '.join(words)
    
    def _adjust_response_quality(self, response: str, quality_level: float) -> str:
        """Adjust response quality based on coherence level."""
        if quality_level < 0.5:
            return self._degrade_response_quality(response)
        elif quality_level < 0.8:
            return self._make_more_focused(response)
        else:
            return response
    
    def _add_creativity(self, response: str) -> str:
        """Add creative elements to high-quality responses."""
        creative_elements = [
            " The moment seemed to hold infinite possibilities.",
            " Time itself seemed to pause in reverence.",
            " The very air crackled with anticipation.",
            " Destiny's hand guided their path forward."
        ]
        return response + random.choice(creative_elements)
    
    def _make_more_focused(self, response: str) -> str:
        """Make response more focused and direct."""
        sentences = response.split('. ')
        if len(sentences) > 1:
            return '. '.join(sentences[:2]) + '.'
        return response
    
    def _truncate_to_tokens(self, response: str, max_tokens: int) -> str:
        """Truncate response to fit within token limit."""
        estimated_tokens = len(response.split()) * self.token_multiplier
        if estimated_tokens > max_tokens:
            words = response.split()
            max_words = int(max_tokens / self.token_multiplier)
            return ' '.join(words[:max_words]) + '...'
        return response
    
    def _calculate_token_usage(self, response: str, prompt: str) -> int:
        """Calculate realistic token usage."""
        response_tokens = len(response.split()) * self.token_multiplier
        prompt_tokens = len(prompt.split()) * self.token_multiplier
        return max(self.min_tokens, int(response_tokens + prompt_tokens))
    
    def _generate_metadata(self, prompt: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate realistic metadata."""
        return {
            'prompt_tokens': len(prompt.split()),
            'response_tokens': len(self.last_prompt.split()) if self.last_prompt else 0,
            'model_version': self.model_name,
            'temperature': kwargs.get('temperature', self.temperature),
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
            'quality_level': self.response_quality,
            'coherence_score': self.coherence_level
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive adapter statistics."""
        return {
            'name': self.name,
            'total_calls': self.call_count,
            'last_prompt_length': len(self.last_prompt) if self.last_prompt else 0,
            'status': 'healthy' if not self.simulate_failures else 'degraded',
            'simulated_failures': self.simulate_failures,
            'failure_rate': self.failure_rate,
            'response_quality': self.response_quality,
            'average_delay_ms': int(self.simulate_delay * 1000),
            'response_history_count': len(self.response_history),
            'model_name': self.model_name,
            'max_tokens': self.max_tokens
        }


class MockImageAdapter:
    """Enhanced mock image generation adapter for testing."""
    
    def __init__(self, name: str = "mock_image_adapter", **kwargs):
        self.name = name
        self.call_count = 0
        self.last_prompt = None
        self.simulate_delay = kwargs.get('simulate_delay', 0.2)
        self.simulate_failures = kwargs.get('simulate_failures', False)
        self.failure_rate = kwargs.get('failure_rate', 0.1)
        
    async def generate_image(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate enhanced mock image response."""
        self.call_count += 1
        self.last_prompt = prompt
        
        # Simulate processing delay
        if self.simulate_delay > 0:
            await asyncio.sleep(self.simulate_delay)
        
        # Simulate failures
        if self.simulate_failures and random.random() < self.failure_rate:
            raise Exception(f"Mock image generation failed: {prompt[:50]}...")
        
        return {
            'image_url': f"https://mock-image-service.com/generated/{self.call_count}.png",
            'prompt': prompt,
            'provider': self.name,
            'timestamp': time.time(),
            'call_number': self.call_count,
            'metadata': {
                'width': kwargs.get('width', 1024),
                'height': kwargs.get('height', 1024),
                'style': kwargs.get('style', 'default'),
                'quality': 'high',
                'generation_time_ms': int(self.simulate_delay * 1000)
            }
        }


class MockModelOrchestrator:
    """Enhanced mock model orchestrator with advanced testing features."""
    
    def __init__(self, **kwargs):
        self.adapters = {}
        self.fallback_chain = ['enhanced_mock_1', 'enhanced_mock_2', 'enhanced_mock_3']
        self.call_count = 0
        self.failure_count = 0
        self.response_history = []
        
        # Initialize mock adapters
        self._initialize_adapters()
        
        # Configuration
        self.simulate_failures = kwargs.get('simulate_failures', False)
        self.failure_rate = kwargs.get('failure_rate', 0.1)
        self.enable_fallback = kwargs.get('enable_fallback', True)
        self.max_retries = kwargs.get('max_retries', 3)
        
        # Backward compatibility
        self.active_adapter = 'enhanced_mock_1'
    
    def _initialize_adapters(self):
        """Initialize mock adapters with different characteristics."""
        self.adapters['enhanced_mock_1'] = MockLLMAdapter(
            name='enhanced_mock_1',
            model_name='mock-fast-model',
            simulate_delay=0.05,
            response_quality='high'
        )
        
        self.adapters['enhanced_mock_2'] = MockLLMAdapter(
            name='enhanced_mock_2',
            model_name='mock-reliable-model',
            simulate_delay=0.1,
            response_quality='high',
            simulate_failures=False
        )
        
        self.adapters['enhanced_mock_3'] = MockLLMAdapter(
            name='enhanced_mock_3',
            model_name='mock-fallback-model',
            simulate_delay=0.15,
            response_quality='medium',
            simulate_failures=True,
            failure_rate=0.2
        )
    
    async def generate_with_fallback(self, prompt: str, **kwargs) -> MockResponse:
        """Generate response with fallback chain support."""
        self.call_count += 1
        
        # Try each adapter in the fallback chain
        for adapter_name in self.fallback_chain:
            try:
                adapter = self.adapters.get(adapter_name)
                if adapter:
                    response = await adapter.generate_response(prompt, **kwargs)
                    self.response_history.append({
                        'adapter': adapter_name,
                        'response': response,
                        'call_number': self.call_count
                    })
                    return response
            except Exception as e:
                self.failure_count += 1
                continue
        
        # If all adapters fail
        raise Exception(f"All adapters in fallback chain failed for prompt: {prompt[:50]}...")
        
    def get_adapter(self, name: str) -> Optional[MockLLMAdapter]:
        """Get specific adapter by name."""
        return self.adapters.get(name)
    
    def get_fallback_chain(self, provider: Optional[str] = None) -> List[str]:
        """Get current fallback chain."""
        return self.fallback_chain.copy()
    
    def add_model_config(self, provider_name: str, config: Dict[str, Any]):
        """Add new model configuration."""
        if provider_name not in self.adapters:
            self.adapters[provider_name] = MockLLMAdapter(
                name=provider_name,
                **config
            )
            self.fallback_chain.append(provider_name)
                
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator statistics."""
        return {
            'active_adapter': self.active_adapter,
            'total_adapters': len(self.adapters),
            'adapter_stats': {name: adapter.get_stats() for name, adapter in self.adapters.items()},
            'fallback_chain': self.fallback_chain,
            'total_calls': self.call_count,
            'failure_count': self.failure_count,
            'success_rate': (self.call_count - self.failure_count) / max(self.call_count, 1),
            'response_history_count': len(self.response_history)
        }


class MockDatabaseManager:
    """Enhanced mock database manager with realistic behavior."""
    
    def __init__(self, **kwargs):
        self.data = {}
        self.call_count = 0
        self.failure_count = 0
        
        # Performance simulation
        self.simulate_delay = kwargs.get('simulate_delay', 0.01)
        self.simulate_failures = kwargs.get('simulate_failures', False)
        self.failure_rate = kwargs.get('failure_rate', 0.05)
        
        # Initialize with test data
        self._initialize_test_data()
    
    def _initialize_test_data(self):
        """Initialize with realistic test data."""
        self.data['scenes'] = [
            {'id': 'scene_1', 'content': 'The hero enters the forest', 'timestamp': time.time()},
            {'id': 'scene_2', 'content': 'A mysterious figure appears', 'timestamp': time.time()},
            {'id': 'scene_3', 'content': 'The journey continues', 'timestamp': time.time()}
        ]
        
        self.data['characters'] = [
            {'name': 'Gandalf', 'memory': 'Wise wizard with ancient knowledge'},
            {'name': 'Aragorn', 'memory': 'Ranger with royal heritage'},
            {'name': 'Frodo', 'memory': 'Hobbit carrying the ring'}
        ]
        
        self.data['timeline'] = [
            {'scene_id': 'scene_1', 'order': 1, 'timestamp': time.time()},
            {'scene_id': 'scene_2', 'order': 2, 'timestamp': time.time()},
            {'scene_id': 'scene_3', 'order': 3, 'timestamp': time.time()}
        ]
    
    async def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute mock database query with realistic behavior."""
        self.call_count += 1
        
        # Simulate processing delay
        if self.simulate_delay > 0:
            await asyncio.sleep(self.simulate_delay)
        
        # Check for simulated failures
        if self.simulate_failures and random.random() < self.failure_rate:
            self.failure_count += 1
            raise Exception(f"Mock database error: {query[:50]}...")
        
        # Parse and execute query
        query_lower = query.lower()
        
        if 'select' in query_lower:
            return self._mock_select_response(query, params)
        elif 'insert' in query_lower:
            return self._mock_insert_response(query, params)
        elif 'update' in query_lower:
            return self._mock_update_response(query, params)
        elif 'delete' in query_lower:
            return self._mock_delete_response(query, params)
        else:
            return []
    
    def _mock_select_response(self, query: str, params: Optional[tuple]) -> List[Dict[str, Any]]:
        """Generate mock SELECT response."""
        query_lower = query.lower()
        
        if 'scene' in query_lower:
            return self.data['scenes']
        elif 'character' in query_lower:
            return self.data['characters']
        elif 'timeline' in query_lower:
            return self.data['timeline']
        else:
            return [{'result': 'mock_data', 'query': query}]
    
    def _mock_insert_response(self, query: str, params: Optional[tuple]) -> List[Dict[str, Any]]:
        """Generate mock INSERT response."""
        return [{'inserted_id': f'mock_id_{self.call_count}', 'affected_rows': 1}]
    
    def _mock_update_response(self, query: str, params: Optional[tuple]) -> List[Dict[str, Any]]:
        """Generate mock UPDATE response."""
        return [{'affected_rows': 1, 'updated': True}]
    
    def _mock_delete_response(self, query: str, params: Optional[tuple]) -> List[Dict[str, Any]]:
        """Generate mock DELETE response."""
        return [{'affected_rows': 1, 'deleted': True}]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database manager statistics."""
        return {
            'total_queries': self.call_count,
            'successful_queries': self.call_count - self.failure_count,
            'failed_queries': self.failure_count,
            'success_rate': (self.call_count - self.failure_count) / max(self.call_count, 1),
            'average_delay_ms': int(self.simulate_delay * 1000),
            'failure_rate': self.failure_rate if self.simulate_failures else 0.0,
            'data_tables': list(self.data.keys())
        }


# Factory functions for easy test setup
def create_mock_adapters(count: int = 3) -> Dict[str, MockLLMAdapter]:
    """Create multiple enhanced mock adapters with different characteristics."""
    adapters = {}
    
    for i in range(count):
        name = f'mock_adapter_{i+1}'
        adapters[name] = MockLLMAdapter(
            name=name,
            model_name=f'mock-model-v{i+1}',
            simulate_delay=0.05 + (i * 0.02),
            response_quality=['high', 'medium', 'low'][i % 3],
            simulate_failures=(i == count - 1),  # Last adapter simulates failures
            failure_rate=0.1 + (i * 0.05)
        )
    
    return adapters


def create_test_model_orchestrator() -> MockModelOrchestrator:
    """Create enhanced test orchestrator with comprehensive features."""
    return MockModelOrchestrator(
        simulate_failures=False,
        enable_fallback=True,
        max_retries=3
    )


def create_mock_database() -> MockDatabaseManager:
    """Create enhanced mock database with realistic behavior."""
    return MockDatabaseManager(
        simulate_delay=0.01,
        simulate_failures=False,
        failure_rate=0.05
    )


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
