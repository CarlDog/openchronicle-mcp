# Mock Adapter Architecture

OpenChronicle uses two distinct mock adapter implementations that serve different purposes in the development and testing workflow.

## 🏗️ Architecture Overview

```
openchronicle-core/
├── core/adapters/providers/mock_adapter.py     # Production Mock
└── tests/mocks/mock_adapters.py                # Test Mock
```

## 📦 Production Mock Adapter

**Location**: `core/adapters/providers/mock_adapter.py`

### Purpose

User-configurable mock adapter for development, prototyping, and demonstration environments where realistic behavior is important.

### Key Features

- **Realistic Response Generation**: Multiple personality types (creative, analytical, balanced, concise)
- **Configurable Behavior**: Quality levels, response length, creativity settings
- **Realistic Timing**: Simulates actual API response times with variance
- **Content Libraries**: Pre-built vocabularies for realistic story generation
- **User Configuration**: Easy setup in `config/models/` registry files
- **Production Ready**: Proper error handling, logging, and state management

### Configuration Example

```json
{
  "mock_creative_writer": {
    "provider": "mock",
    "model_name": "creative-writer-v1",
    "personality": "creative",
    "response_quality": "high",
    "response_length": "medium",
    "creativity_level": 0.8,
    "response_time_ms": 600
  }
}
```

### Use Cases

- **Development Environment**: No API costs while developing features
- **Demonstrations**: Reliable responses for showcasing OpenChronicle
- **Prototyping**: Quick testing of narrative flows without external dependencies
- **Offline Testing**: Full functionality without internet connection

## 🧪 Test Mock Adapter

**Location**: `tests/mocks/mock_adapters.py`

### Purpose

Specialized testing framework with predictable, controllable behavior for reliable component testing.

### Key Features

- **Deterministic Responses**: Consistent, predictable outputs for test reliability
- **Response Queuing**: Pre-define specific responses for test scenarios
- **Error Injection**: Controlled error simulation for edge case testing
- **Assertion Helpers**: Built-in test validation methods
- **State Control**: Reset, track, and validate test state
- **Performance Optimization**: Instant responses for fast test execution

### Usage Example

```python
# Setup test adapter
test_adapter = TestMockAdapter('test-model', response_pattern='story')

# Queue specific responses
test_adapter.queue_responses([
    "Expected response 1",
    "Expected response 2"
])

# Generate response
response = await test_adapter.generate_response("test prompt")

# Validate with built-in assertions
assert test_adapter.assert_call_count(1)
assert test_adapter.assert_last_prompt_contains("test")
assert response.assert_contains("Expected")
```

### Use Cases

- **Unit Testing**: Predictable responses for component validation
- **Integration Testing**: Controlled behavior for system interactions
- **Performance Testing**: Fast execution without realistic delays
- **Edge Case Testing**: Controlled error injection and failure scenarios

## 🎯 Key Differences

| Aspect | Production Mock | Test Mock |
|--------|----------------|-----------|
| **Purpose** | User experience & realism | Test reliability & control |
| **Response Quality** | Realistic, varied content | Predictable, simple content |
| **Timing** | Simulates real API delays | Instant response (optimized) |
| **Configuration** | JSON config files | Code-based test setup |
| **State Management** | Conversation history | Test state tracking |
| **Error Handling** | Production-ready | Controlled error injection |
| **Assertions** | None (production use) | Built-in test helpers |

## 🔄 Integration Points

### Production Mock Integration

```python
# Configured through model registry
model_manager.load_model_config("mock_creative_writer")
response = await model_manager.generate_response(prompt)
```

### Test Mock Integration

```python
# Direct instantiation in tests
mock_orchestrator = MockModelOrchestrator()
mock_orchestrator.adapters['test_model'] = TestMockAdapter()
response = await mock_orchestrator.generate_response(prompt)
```

## 📈 Benefits

### Production Mock Benefits

- **No API Costs**: Develop without external API charges
- **Offline Capability**: Full functionality without internet
- **Consistent Demos**: Reliable behavior for presentations
- **Rapid Prototyping**: Quick iteration without API limits

### Test Mock Benefits

- **Fast Test Execution**: No artificial delays
- **Reliable Test Results**: Deterministic behavior
- **Easy Debugging**: Controllable responses and state
- **Comprehensive Validation**: Built-in assertion helpers

## 🛠️ Implementation Notes

Both mock adapters are designed to be:

- **Drop-in Replacements**: Compatible with existing adapter interfaces
- **Independently Maintained**: Separate codebases for different concerns
- **Fully Featured**: Complete implementations of their respective use cases
- **Well Documented**: Clear APIs and configuration options

This separation ensures that production mocks remain user-friendly and realistic, while test mocks stay focused on reliability and control for effective testing workflows.
