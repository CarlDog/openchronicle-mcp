# OpenChronicle Four-Tier Testing Strategy

## ✅ Implementation Complete

Our professional four-tier testing strategy is now fully implemented and operational:

## Quick Start

Use the provided `run_tests.py` script for easy test execution:

```bash
# Run production tests with mock adapters (most common)
python run_tests.py --tier production-mock

# Run quick smoke tests
python run_tests.py --tier smoke

# Run all production tiers (excludes stress tests)
python run_tests.py --all-tiers

# Run stress tests (standalone, never mixed)
python run_tests.py --tier stress
```

## Manual pytest Commands

### Tier 1: Production Tests with Real Adapters
```bash
python -m pytest -m "production_real" -v tests/
```
- Uses real model APIs and external services
- Requires API keys and configuration
- Longer execution time
- For final validation before deployment

### Tier 2: Production Tests with Mock Adapters
```bash
python -m pytest -m "(production_mock or mock_only)" -v tests/
```
- Uses mock adapters and test data
- No external dependencies
- Fast execution
- Primary development testing

### Tier 3: Smoke Tests
```bash
python -m pytest -m "(smoke or core)" -v tests/
```
- Essential functionality validation
- Quick sanity checks
- Perfect for CI/CD pipelines
- Basic integration verification

### Tier 4: Stress Tests (Standalone)
```bash
python -m pytest -m "(stress or chaos)" -v --timeout=600 tests/
```
- High-load and chaos engineering tests
- **NEVER** mixed with other test tiers
- Resource intensive
- Separate execution environment recommended

## Standard Test Run (Most Common)
```bash
python -m pytest -m "(not stress and not chaos)" -v tests/
```
- Runs all tests except stress tests
- Good for regular development
- Balanced coverage and speed

## Configuration

### Professional pytest.ini Configuration
Located in `tests/pytest.ini` with all custom markers properly defined:

```ini
[pytest]
# Professional pytest configuration for OpenChronicle's four-tier testing strategy
markers =
    production_real: Production code tests using real model adapters and content
    production_mock: Production code tests using mock adapters and test content
    smoke: Quick smoke tests for major functionality validation
    core: Essential core functionality tests
    stress: High-load stress testing (isolated execution only)
    chaos: Chaos engineering and fault injection tests
    # ... additional markers
```

### Test Tier Detection
The `TestConfigurationManager` in `tests/conftest.py` automatically detects the current tier and provides appropriate:
- Model adapter settings (real vs mock)
- Database configuration (memory vs persistent)
- Performance limits and timeouts
- Resource allocation

## Test Marking Examples

### Production Mock Test
```python
@pytest.mark.production_mock
@pytest.mark.asyncio
async def test_model_with_mock_adapter(self, model_adapter):
    response = await model_adapter.generate_response("Test")
    assert response['content'] == 'Mock response content'
```

### Smoke Test
```python
@pytest.mark.smoke
def test_basic_functionality(self):
    orchestrator = ModelOrchestrator()
    assert orchestrator is not None
```

### Stress Test
```python
@pytest.mark.stress
@pytest.mark.asyncio
async def test_high_load_scenario(self):
    # This test runs ONLY in stress tier
    tasks = [run_operation() for _ in range(1000)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 1000
```

## CI/CD Integration

### Development Pipeline
```bash
python run_tests.py --tier production-mock
```

### Pre-deployment Pipeline
```bash
python run_tests.py --all-tiers
```

### Performance Monitoring
```bash
python run_tests.py --tier stress
```

## Implementation Status

✅ **Complete**: Four-tier testing strategy fully operational
✅ **Configuration**: Professional pytest.ini with all markers defined
✅ **Scripts**: User-friendly run_tests.py script with clear outputs
✅ **Documentation**: Comprehensive testing strategy documentation
✅ **Examples**: Working test examples demonstrating each tier
✅ **Integration**: TestConfigurationManager with automatic tier detection
✅ **Clean Output**: No warnings or configuration errors

## Benefits

1. **Clear Separation**: Each tier has a specific purpose
2. **Resource Efficiency**: Stress tests don't slow down development
3. **Flexible Execution**: Run what you need, when you need it
4. **Professional Standards**: Industry-standard testing practices
5. **CI/CD Ready**: Easy integration with automated pipelines
6. **No Configuration Warnings**: Clean, professional test execution
