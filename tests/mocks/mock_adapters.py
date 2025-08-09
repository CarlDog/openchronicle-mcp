"""
Test Mock Adapter for OpenChronicle Test Suite

A controllable, predictable mock adapter specifically designed for testing.
Provides deterministic responses, state manipulation, and assertion helpers
to ensure reliable and repeatable test execution.

This adapter is NOT intended for user configuration - it's purely for testing
internal OpenChronicle components.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from unittest.mock import AsyncMock


@dataclass
class TestResponse:
    """Predictable response structure for testing."""
    content: str
    model: str = "test-mock"
    provider: str = "test_mock"
    tokens_used: int = 0
    finish_reason: str = "completed"
    metadata: Optional[Dict[str, Any]] = None
    generation_time: float = 0.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TestMockState:
    """State tracking for test mock adapter."""
    call_count: int = 0
    last_prompt: str = ""
    response_queue: List[str] = field(default_factory=list)
    error_queue: List[Exception] = field(default_factory=list) 
    response_delay: float = 0.0
    should_fail: bool = False
    custom_validators: List[Callable] = field(default_factory=list)
    conversation_log: List[Dict[str, Any]] = field(default_factory=list)


class TestMockAdapter:
    """
    Test-focused mock adapter with controllable, predictable behavior.
    
    Features:
    - Deterministic responses for consistent testing
    - Queue-based response system for multi-step scenarios
    - Error injection for failure testing
    - Call tracking and assertion helpers
    - State inspection and manipulation
    """
    
    def __init__(self, model_name: str = "test-mock", **config):
        self.model_name = model_name
        self.provider_name = "test_mock"
        
        # Test-specific state
        self.state = TestMockState()
        
        # Default responses for different scenarios
        self.default_responses = {
            'story_continuation': "The story continued with dramatic flair.",
            'character_dialogue': '"I see," the character replied thoughtfully.',
            'scene_description': "The scene unfolded with vivid detail.",
            'general': "This is a test response for the given prompt.",
            'error_test': "This response should not appear if error testing works.",
            'performance_test': "Performance test response generated quickly."
        }
        
        # Configuration
        self.config = {
            'deterministic': config.get('deterministic', True),
            'track_calls': config.get('track_calls', True),
            'validate_prompts': config.get('validate_prompts', True),
            'max_response_length': config.get('max_response_length', 1000)
        }
        
        self.reset_state()
    
    def reset_state(self):
        """Reset adapter state for fresh test runs."""
        self.state = TestMockState()
    
    # =================
    # RESPONSE CONTROL
    # =================
    
    def queue_response(self, response: str):
        """Queue a specific response for the next call."""
        self.state.response_queue.append(response)
    
    def queue_responses(self, responses: List[str]):
        """Queue multiple responses in order."""
        self.state.response_queue.extend(responses)
    
    def queue_error(self, error: Exception):
        """Queue an error to be raised on next call."""
        self.state.error_queue.append(error)
    
    def set_response_delay(self, delay_seconds: float):
        """Set artificial delay for response simulation."""
        self.state.response_delay = delay_seconds
    
    def set_failure_mode(self, should_fail: bool = True):
        """Enable/disable automatic failure mode."""
        self.state.should_fail = should_fail
    
    def add_validator(self, validator: Callable[[str], bool]):
        """Add custom prompt validator."""
        self.state.custom_validators.append(validator)
    
    # =================
    # MAIN API METHODS
    # =================
    
    async def generate_response(self, prompt: str, **kwargs) -> TestResponse:
        """
        Generate a controllable test response.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional test parameters
            
        Returns:
            TestResponse with predictable content
        """
        start_time = time.time()
        
        # Track the call
        self.state.call_count += 1
        self.state.last_prompt = prompt
        
        if self.config['track_calls']:
            self.state.conversation_log.append({
                'call_number': self.state.call_count,
                'prompt': prompt,
                'kwargs': kwargs,
                'timestamp': start_time
            })
        
        # Validate prompt if enabled
        if self.config['validate_prompts']:
            self._validate_prompt(prompt)
        
        # Apply artificial delay
        if self.state.response_delay > 0:
            await asyncio.sleep(self.state.response_delay)
        
        # Check for queued errors
        if self.state.error_queue:
            error = self.state.error_queue.pop(0)
            raise error
        
        # Check failure mode
        if self.state.should_fail:
            raise Exception("Test mock adapter in failure mode")
        
        # Generate response content
        response_content = self._get_response_content(prompt, **kwargs)
        
        # Create response
        response = TestResponse(
            content=response_content,
            model=self.model_name,
            provider=self.provider_name,
            tokens_used=self._calculate_test_tokens(response_content),
            finish_reason="completed",
            metadata={
                'test_call_number': self.state.call_count,
                'test_deterministic': self.config['deterministic'],
                'test_prompt_length': len(prompt),
                **kwargs
            },
            generation_time=time.time() - start_time
        )
        
        # Update conversation log
        if self.config['track_calls']:
            self.state.conversation_log[-1]['response'] = response_content
            self.state.conversation_log[-1]['generation_time'] = response.generation_time
        
        return response
    
    def _get_response_content(self, prompt: str, **kwargs) -> str:
        """Get response content based on queue or defaults."""
        # Use queued response if available
        if self.state.response_queue:
            return self.state.response_queue.pop(0)
        
        # Determine response type from prompt or kwargs
        response_type = kwargs.get('test_response_type', self._classify_prompt(prompt))
        
        # Generate deterministic response
        if self.config['deterministic']:
            return self._generate_deterministic_response(response_type, prompt)
        else:
            return self.default_responses.get(response_type, self.default_responses['general'])
    
    def _classify_prompt(self, prompt: str) -> str:
        """Classify prompt type for appropriate response."""
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ['continue', 'story', 'narrative']):
            return 'story_continuation'
        elif any(word in prompt_lower for word in ['character', 'dialogue', 'said']):
            return 'character_dialogue'
        elif any(word in prompt_lower for word in ['describe', 'scene', 'setting']):
            return 'scene_description'
        elif 'error' in prompt_lower or 'fail' in prompt_lower:
            return 'error_test'
        elif 'performance' in prompt_lower or 'speed' in prompt_lower:
            return 'performance_test'
        else:
            return 'general'
    
    def _generate_deterministic_response(self, response_type: str, prompt: str) -> str:
        """Generate deterministic response based on prompt hash."""
        # Create consistent response based on prompt content
        prompt_hash = hash(prompt) % 1000
        
        base_response = self.default_responses.get(response_type, self.default_responses['general'])
        
        # Add deterministic variation
        variations = [
            f"{base_response} (Variation A{prompt_hash})",
            f"{base_response} (Variation B{prompt_hash})",
            f"{base_response} (Variation C{prompt_hash})"
        ]
        
        return variations[prompt_hash % len(variations)]
    
    def _validate_prompt(self, prompt: str):
        """Validate prompt using custom validators."""
        if not prompt or not prompt.strip():
            raise ValueError("Test mock received empty prompt")
        
        if len(prompt) > self.config['max_response_length']:
            raise ValueError(f"Test prompt exceeds max length: {len(prompt)}")
        
        # Run custom validators
        for validator in self.state.custom_validators:
            if not validator(prompt):
                raise ValueError("Custom prompt validation failed")
    
    def _calculate_test_tokens(self, content: str) -> int:
        """Calculate predictable token count for testing."""
        # Deterministic token calculation for testing
        return len(content.split()) * 2  # Consistent 2 tokens per word
    
    # =================
    # ASSERTION HELPERS
    # =================
    
    def assert_called(self):
        """Assert that the adapter was called."""
        assert self.state.call_count > 0, "Mock adapter was not called"
    
    def assert_called_times(self, expected_count: int):
        """Assert specific number of calls."""
        assert self.state.call_count == expected_count, \
            f"Expected {expected_count} calls, got {self.state.call_count}"
    
    def assert_last_prompt_contains(self, text: str):
        """Assert last prompt contains specific text."""
        assert text in self.state.last_prompt, \
            f"Last prompt '{self.state.last_prompt}' does not contain '{text}'"
    
    def assert_no_queued_responses(self):
        """Assert all queued responses were consumed."""
        assert len(self.state.response_queue) == 0, \
            f"Unused queued responses: {self.state.response_queue}"
    
    def assert_conversation_flow(self, expected_prompts: List[str]):
        """Assert conversation followed expected prompt sequence."""
        actual_prompts = [log['prompt'] for log in self.state.conversation_log]
        assert actual_prompts == expected_prompts, \
            f"Expected prompts {expected_prompts}, got {actual_prompts}"
    
    # =================
    # STATE INSPECTION
    # =================
    
    def get_call_count(self) -> int:
        """Get number of times adapter was called."""
        return self.state.call_count
    
    def get_last_prompt(self) -> str:
        """Get the last prompt received."""
        return self.state.last_prompt
    
    def get_conversation_log(self) -> List[Dict[str, Any]]:
        """Get complete conversation log."""
        return self.state.conversation_log.copy()
    
    def get_prompt_history(self) -> List[str]:
        """Get list of all prompts received."""
        return [log['prompt'] for log in self.state.conversation_log]
    
    def has_pending_responses(self) -> bool:
        """Check if there are queued responses remaining."""
        return len(self.state.response_queue) > 0
    
    def has_pending_errors(self) -> bool:
        """Check if there are queued errors remaining."""
        return len(self.state.error_queue) > 0
    
    # =================
    # STANDARD ADAPTER INTERFACE
    # =================
    
    async def validate_connection(self) -> bool:
        """Always returns True for test mock."""
        return True
    
    def get_supported_features(self) -> List[str]:
        """Return test-specific features."""
        return [
            "test_deterministic_responses",
            "test_queue_management",
            "test_error_injection",
            "test_call_tracking",
            "test_assertion_helpers",
            "test_state_inspection"
        ]
    
    def get_model_info(self) -> Dict[str, Any]:
        """Return test mock information."""
        return {
            "name": self.model_name,
            "provider": self.provider_name,
            "type": "test_mock",
            "deterministic": self.config['deterministic'],
            "features": self.get_supported_features(),
            "state": {
                "call_count": self.state.call_count,
                "queued_responses": len(self.state.response_queue),
                "queued_errors": len(self.state.error_queue),
                "failure_mode": self.state.should_fail
            }
        }
    
    # =================
    # TEST SCENARIOS
    # =================
    
    def setup_multi_turn_scenario(self, responses: List[str]):
        """Setup for multi-turn conversation testing."""
        self.reset_state()
        self.queue_responses(responses)
    
    def setup_error_scenario(self, error_on_call: int, error: Exception):
        """Setup error to occur on specific call number."""
        self.reset_state()
        
        # Queue normal responses until error call
        for i in range(error_on_call - 1):
            self.queue_response(f"Response {i + 1}")
        
        # Queue the error
        self.queue_error(error)
    
    def setup_performance_scenario(self, response_delay: float = 0.1):
        """Setup for performance testing with delays."""
        self.reset_state()
        self.set_response_delay(response_delay)
        self.queue_response("Performance test response")
    
    def setup_validation_scenario(self, validator: Callable[[str], bool]):
        """Setup custom prompt validation testing."""
        self.reset_state()
        self.add_validator(validator)


# =================
# TEST HELPER FUNCTIONS
# =================

def create_test_mock(**config) -> TestMockAdapter:
    """Factory function for creating test mock adapters."""
    return TestMockAdapter(**config)


def create_deterministic_mock() -> TestMockAdapter:
    """Create a deterministic mock for consistent testing."""
    return TestMockAdapter(deterministic=True, track_calls=True)


def create_error_mock(error: Exception) -> TestMockAdapter:
    """Create a mock that will raise an error on first call."""
    mock = TestMockAdapter()
    mock.queue_error(error)
    return mock


def create_multi_response_mock(responses: List[str]) -> TestMockAdapter:
    """Create a mock with predefined response sequence."""
    mock = TestMockAdapter()
    mock.queue_responses(responses)
    return mock


# =================
# ASYNC TEST HELPERS
# =================

class AsyncTestMockAdapter(TestMockAdapter):
    """Extended test mock with additional async testing capabilities."""
    
    async def async_assert_called_within(self, timeout: float = 1.0):
        """Assert adapter called within timeout period."""
        start_time = time.time()
        initial_count = self.state.call_count
        
        while time.time() - start_time < timeout:
            if self.state.call_count > initial_count:
                return
            await asyncio.sleep(0.01)
        
        raise AssertionError(f"Adapter not called within {timeout} seconds")
    
    async def wait_for_calls(self, expected_count: int, timeout: float = 5.0):
        """Wait for specific number of calls with timeout."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.state.call_count >= expected_count:
                return
            await asyncio.sleep(0.01)
        
        raise AssertionError(
            f"Expected {expected_count} calls, got {self.state.call_count} within {timeout}s"
        )
