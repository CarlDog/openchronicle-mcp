```prompt
---
mode: ask
---
ROLE: You are optimizing OpenChronicle's async memory subsystem for narrative coherence and performance under heavy scene generation loads.

SCOPE: Memory performance optimization, caching strategies, and async operation efficiency.

OPENCHRONICLE MEMORY ARCHITECTURE:
- **MemoryOrchestrator**: Sync memory operations with async compatibility wrappers
- **AsyncMemoryOrchestrator**: Native async operations with caching and lazy loading
- **Memory Components**: Character memory, world state, scene context, snapshot management
- **Synchronization**: Memory-scene coordination for narrative consistency
- **Persistence**: Multiple backends (filesystem, database) with async repository patterns

CRITICAL PERFORMANCE PATTERNS:

✅ **Memory-Scene Synchronization**: Always update memory before logging scenes
✅ **Async Operation Chains**: Use await throughout async memory operations
✅ **Caching Strategy**: LRU cache with configurable TTL for frequently accessed memories
✅ **Lazy Loading**: Load memory components on-demand for large stories
✅ **Batch Operations**: Group memory updates for efficiency

PERFORMANCE BOTTLENECKS TO IDENTIFY:

🔍 **Latency Issues**:
- Synchronous I/O in async contexts
- Missing cache hits on repeated memory access
- Inefficient memory serialization/deserialization
- Blocking operations in async memory chains

🔍 **Memory Usage Issues**:
- Memory leaks in long-running narrative sessions
- Unbounded cache growth
- Duplicate memory objects in cache
- Inefficient character memory storage

🔍 **Consistency Issues**:
- Race conditions in concurrent memory updates
- Memory-scene synchronization violations
- Stale cache entries after memory updates
- Inconsistent async/sync operation results

OPTIMIZATION FOCUS AREAS:

1. **Async Operation Performance**
   - Validate proper async/await usage throughout memory operations
   - Identify blocking I/O operations in async contexts
   - Assess async operation chaining and error propagation
   - Review AsyncMemoryOrchestrator vs MemoryOrchestrator usage patterns

2. **Caching Effectiveness**
   - Analyze cache hit rates and TTL effectiveness
   - Evaluate cache size and eviction policies
   - Review cache invalidation on memory updates
   - Assess cache memory usage and garbage collection

3. **Memory Operation Latency**
   - Profile memory load/save operation performance
   - Identify serialization/deserialization bottlenecks
   - Analyze database/filesystem I/O patterns
   - Review memory snapshot creation and restoration

4. **Narrative Coherence Under Load**
   - Validate memory consistency during concurrent scene generation
   - Assess memory-scene synchronization performance
   - Review rollback operation efficiency
   - Analyze memory state consistency across character interactions

5. **Scalability Analysis**
   - Evaluate performance with large story datasets
   - Assess memory usage growth patterns
   - Review concurrent memory operation handling
   - Analyze performance degradation curves

SPECIFIC OPTIMIZATION TARGETS:

**AsyncMemoryOrchestrator Optimizations**:
- Cache effectiveness monitoring and tuning
- Async repository operation performance
- Memory serialization optimization
- Concurrent operation coordination

**Memory Synchronization Optimizations**:
- Memory-scene update batching
- Snapshot creation performance
- Character memory consolidation
- World state update efficiency

**Infrastructure Optimizations**:
- Database connection pooling and async drivers
- Filesystem I/O optimization
- Memory repository caching strategies
- Error handling performance impact

DELIVERABLES:

1. **Performance Bottleneck Analysis**
   - Profile async memory operations under load
   - Identify synchronous I/O blocking async contexts
   - Measure cache effectiveness and memory usage patterns
   - Document performance degradation points

2. **Caching Strategy Optimization**
   - Analyze current cache hit rates and effectiveness
   - Recommend cache size and TTL tuning
   - Propose cache invalidation strategy improvements
   - Design cache warming strategies for common access patterns

3. **Async Operation Validation**
   - Audit async/await usage throughout memory subsystem
   - Identify and fix blocking operations in async contexts
   - Validate async operation error handling and propagation
   - Review async operation chaining and composition

4. **Memory Coherence Verification**
   - Test memory consistency under concurrent operations
   - Validate memory-scene synchronization performance
   - Assess rollback operation efficiency and correctness
   - Review character memory isolation and consistency

5. **Scalability Recommendations**
   - Provide performance benchmarks for different story sizes
   - Recommend infrastructure scaling strategies
   - Propose memory usage optimization techniques
   - Design performance monitoring and alerting

OPENCHRONICLE-SPECIFIC VALIDATION:

Focus on these critical files and patterns:
- `src/openchronicle/infrastructure/memory/core/async_memory_orchestrator.py`
- `src/openchronicle/infrastructure/memory/core/memory_orchestrator.py`
- Memory-scene synchronization in workflow implementations
- Cache implementation in `src/openchronicle/infrastructure/memory/engines/caching/`
- Repository patterns in `src/openchronicle/infrastructure/memory/engines/persistence/`

PERFORMANCE TESTING SCENARIOS:

1. **High-Frequency Scene Generation**: Rapid scene creation with memory updates
2. **Large Story Loading**: Memory performance with extensive character/world state
3. **Concurrent User Sessions**: Multiple stories accessing memory simultaneously
4. **Memory-Intensive Operations**: Character relationship updates, world state changes
5. **Cache Stress Testing**: Memory access patterns that challenge cache effectiveness

OUTPUT FORMAT:
- Provide specific performance metrics and bottleneck locations
- Include code examples of optimized async patterns
- Reference OpenChronicle memory architecture patterns
- Recommend specific caching and async optimizations
- Focus on narrative coherence preservation during optimization

SUCCESS CRITERIA:
- Async memory operations show measurable latency improvement
- Cache hit rates optimized for common narrative access patterns
- Memory usage stable under extended narrative sessions
- Memory-scene synchronization maintains consistency under load
- Performance scales linearly with story complexity
```
