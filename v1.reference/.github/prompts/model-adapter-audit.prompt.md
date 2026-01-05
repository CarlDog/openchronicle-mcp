```prompt
---
mode: ask
---
ROLE: You are auditing OpenChronicle's model adapter ecosystem for integration consistency, fallback reliability, and provider management across 15+ LLM providers.

SCOPE: Model adapter integration patterns, orchestration compliance, and fallback chain reliability.

OPENCHRONICLE MODEL ARCHITECTURE:
- **ModelOrchestrator**: Central orchestration with component-based architecture
- **Provider Coverage**: 15+ LLM providers (OpenAI, Ollama, Anthropic, etc.)
- **Fallback Chains**: Dynamic fallback configuration for resilience
- **Dynamic Configuration**: Runtime model addition via model_registry.json
- **Health Monitoring**: Continuous provider status tracking
- **Mock Integration**: Segregated mock adapters for development/testing

CRITICAL PATTERNS TO VALIDATE:
✅ **Always Route Through ModelManager**: No direct adapter instantiation
✅ **Fallback Chain Usage**: Use `model_manager.get_fallback_chain(adapter_name)`
✅ **Health Checks**: Validate adapter availability before usage
✅ **Configuration Management**: Load from `config/model_registry.json` as single source
✅ **Error Handling**: Preserve narrative context during provider failures

ANTI-PATTERNS TO DETECT:
❌ Direct adapter imports and instantiation
❌ Hardcoded provider configurations
❌ Missing fallback chain implementations
❌ Provider failures breaking narrative flow
❌ Mixed mock/production adapter usage
❌ Configuration scattered across multiple files

AUDIT FOCUS AREAS:

1. **Orchestration Compliance**
   - Are all model operations routed through ModelOrchestrator?
   - Is dynamic adapter initialization used properly?
   - Are adapters registered with the DI container correctly?

2. **Fallback Chain Analysis**
   - Do fallback chains cover all realistic failure scenarios?
   - Is fallback logic implemented consistently across providers?
   - Are fallback chains configured in model_registry.json?

3. **Provider Health Management**
   - Is health monitoring implemented for all providers?
   - Do health checks trigger appropriate fallback behavior?
   - Are provider status changes logged and tracked?

4. **Configuration Validation**
   - Is model_registry.json the single source of truth for provider configs?
   - Are runtime configuration additions properly validated?
   - Is configuration loading centralized through ConfigurationManager?

5. **Mock Adapter Segregation**
   - Are test mocks properly isolated from production code?
   - Is production mock adapter used correctly for demos/development?
   - Are mock responses deterministic and controllable?

6. **Error Context Preservation**
   - Do provider failures maintain narrative coherence?
   - Is error context passed through fallback chains?
   - Are model adapter errors properly categorized and handled?

DELIVERABLES:

1. **Integration Compliance Report**
   - List all direct adapter instantiations bypassing ModelOrchestrator
   - Identify configuration loading violations
   - Document missing fallback chain implementations

2. **Fallback Chain Validation**
   - Test fallback behavior under simulated provider failures
   - Verify fallback chain coverage for all configured providers
   - Assess fallback performance and latency impact

3. **Health Monitoring Assessment**
   - Evaluate provider health check implementations
   - Review health status tracking and logging
   - Validate automatic failover mechanisms

4. **Configuration Audit**
   - Verify model_registry.json as single configuration source
   - Check dynamic configuration addition patterns
   - Validate configuration schema compliance

5. **Mock Integration Review**
   - Assess mock adapter usage patterns
   - Verify separation between test and production mocks
   - Review mock response configuration and control

OPENCHRONICLE-SPECIFIC VALIDATION:

Check these specific integration points:
- `core/model_management/model_orchestrator.py` - Orchestration patterns
- `config/model_registry.json` - Configuration centralization
- Provider adapter implementations in `src/openchronicle/infrastructure/adapters/`
- Mock adapter separation in `core/adapters/providers/mock_adapter.py` vs `tests/mocks/`
- Fallback chain configuration and execution logic

OUTPUT FORMAT:
- Reference specific OpenChronicle modules and files
- Provide concrete examples of violations with file:line references
- Recommend specific improvements aligned with ModelOrchestrator patterns
- Focus on narrative AI reliability and provider resilience
- Include test scenarios for validating fixes

SUCCESS CRITERIA:
- All model operations route through ModelOrchestrator
- Fallback chains handle all provider failure scenarios
- Configuration loading centralized and validated
- Mock adapters properly segregated and controlled
- Provider health monitoring active and effective
- Error handling preserves narrative context throughout fallback chains
```
