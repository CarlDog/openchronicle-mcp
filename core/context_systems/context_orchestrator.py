"""
Context Orchestrator - Unified Context Management

This orchestrator coordinates between all context subsystems:
- Memory-based context (memory_management/context/)
- Content analysis context (content_analysis/context_orchestrator.py)  
- Narrative response context (narrative_systems/response/context_analyzer.py)

Replaces the legacy monolithic context_builder.py with a clean orchestration pattern.
"""

import os
import json
import sys
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error

# Import modular context systems
from ..memory_management.context import ContextBuilder as MemoryContextBuilder
from ..memory_management.context import ContextConfiguration as MemoryContextConfiguration
from ..memory_management.context import ContextMetrics as MemoryContextMetrics
from ..content_analysis.context_orchestrator import ContentAnalysisOrchestrator as ContentContextOrchestrator
from ..narrative_systems.response.context_analyzer import ContextAnalyzer as NarrativeContextAnalyzer

# Import supporting systems
from ..memory_management import MemoryOrchestrator
from ..content_analysis import ContentAnalysisOrchestrator
from ..narrative_systems import NarrativeOrchestrator


@dataclass
class ContextConfiguration:
    """Configuration for unified context generation."""
    include_memory_context: bool = True
    include_content_analysis: bool = True
    include_narrative_context: bool = True
    max_context_length: int = 2000
    prioritize_recent_content: bool = True
    
    # Memory context settings
    memory_detail_level: str = "full"  # "full", "summary", "minimal"
    max_recent_events: int = 5
    
    # Content analysis settings
    enable_content_enhancement: bool = True
    content_analysis_depth: str = "standard"  # "minimal", "standard", "deep"
    
    # Narrative context settings
    include_story_context: bool = True
    narrative_focus: str = "balanced"  # "character", "plot", "world", "balanced"


@dataclass 
class ContextMetrics:
    """Comprehensive metrics about generated context."""
    total_length: int
    memory_context_length: int
    content_analysis_length: int
    narrative_context_length: int
    context_completeness: float  # 0.0 to 1.0
    processing_time_ms: int
    components_used: List[str]


class ContextOrchestrator:
    """
    Unified Context Orchestrator
    
    Coordinates between all context subsystems to provide comprehensive context
    for narrative AI operations. Replaces the legacy monolithic context builder.
    """
    
    def __init__(self):
        """Initialize the context orchestrator with all subsystems."""
        # Initialize core components with delayed loading to avoid circular imports
        self.memory_context = None
        self.content_context = None
        self.narrative_context = None
        
        # Initialize orchestrators with delayed loading
        self.memory_orchestrator = None
        self.content_orchestrator = None
        self.narrative_orchestrator = None
        
        self.default_config = ContextConfiguration()
        self._initialized = False
        
        log_info("ContextOrchestrator initialized (delayed loading)")
    
    async def build_context(self, user_input: str, story_data: Optional[Dict[str, Any]] = None, 
                          config: Optional[ContextConfiguration] = None) -> str:
        """
        Build comprehensive context for narrative generation.
        
        This is the main entry point method expected by integration tests.
        
        Args:
            user_input: User's input or prompt for context building
            story_data: Optional story data for context enhancement
            config: Optional configuration for context building
            
        Returns:
            Formatted context string ready for narrative generation
        """
        try:
            # Use default story data if none provided
            if story_data is None:
                story_data = {"content": user_input, "scenes": [], "characters": []}
            
            # Use build_context_with_analysis for comprehensive context
            return await self.build_context_with_analysis(
                user_input=user_input,
                story_data=story_data,
                config=config or self.default_config
            )
            
        except Exception as e:
            log_error(f"Failed to build context: {e}")
            # Return simple fallback context
            return self._create_fallback_context(user_input, story_data or {})
    
    def _ensure_initialized(self):
        """Ensure all subsystems are initialized (lazy loading)."""
        if self._initialized:
            return
        
        try:
            # Initialize memory context builder
            self.memory_context = MemoryContextBuilder()
            
            # Initialize memory orchestrator
            self.memory_orchestrator = MemoryOrchestrator()
            
            # Content and narrative systems are optional for now
            try:
                self.content_context = ContentContextOrchestrator(None)  # Pass None for model_manager for now
                self.content_orchestrator = ContentAnalysisOrchestrator(None)
            except Exception as e:
                log_warning(f"Content analysis systems not available: {str(e)}")
                self.content_context = None
                self.content_orchestrator = None
            
            try:
                self.narrative_context = NarrativeContextAnalyzer()
                self.narrative_orchestrator = NarrativeOrchestrator()
            except Exception as e:
                log_warning(f"Narrative systems not available: {str(e)}")
                self.narrative_context = None
                self.narrative_orchestrator = None
            
            self._initialized = True
            log_info("ContextOrchestrator fully initialized")
            
        except Exception as e:
            log_error(f"Failed to initialize context orchestrator: {str(e)}")
            # Continue with minimal functionality
    
    async def build_context_with_analysis(self, user_input: str, story_data: Dict[str, Any], 
                                         config: Optional[ContextConfiguration] = None) -> str:
        """
        Build comprehensive context with analysis - main interface function.
        
        This replaces the legacy build_context_with_analysis function from context_builder.py
        """
        self._ensure_initialized()
        
        if config is None:
            config = self.default_config
            
        start_time = self._get_current_time_ms()
        context_parts = []
        components_used = []
        
        try:
            # 1. Memory-based context (primary system)
            if config.include_memory_context and self.memory_orchestrator:
                memory_context = await self._build_memory_context(story_data, config)
                if memory_context:
                    context_parts.append(memory_context)
                    components_used.append("memory_context")
                    log_info("Memory context generated successfully")
            
            # 2. Content analysis context (optional)
            if config.include_content_analysis and self.content_orchestrator:
                content_context = await self._build_content_context(user_input, story_data, config)
                if content_context:
                    context_parts.append(content_context)
                    components_used.append("content_analysis")
                    log_info("Content analysis context generated successfully")
            
            # 3. Narrative context (optional)
            if config.include_narrative_context and self.narrative_orchestrator:
                narrative_context = await self._build_narrative_context(user_input, story_data, config)
                if narrative_context:
                    context_parts.append(narrative_context)
                    components_used.append("narrative_context")
                    log_info("Narrative context generated successfully")
            
            # 4. Assemble final context
            final_context = self._assemble_context(context_parts, config)
            
            # 5. Generate metrics
            processing_time = self._get_current_time_ms() - start_time
            metrics = self._calculate_metrics(final_context, context_parts, components_used, processing_time)
            
            log_system_event("context_generation", f"Generated context: {len(final_context)} chars, {len(components_used)} components")
            
            return final_context
            
        except Exception as e:
            log_error(f"Context generation failed: {str(e)}")
            # Return minimal fallback context
            return self._create_fallback_context(user_input, story_data)
    
    async def build_simple_context(self, story_data: Dict[str, Any], 
                                  config: Optional[ContextConfiguration] = None) -> str:
        """Build basic context without complex analysis."""
        if config is None:
            config = ContextConfiguration(
                include_content_analysis=False,
                include_narrative_context=False,
                memory_detail_level="summary"
            )
        
        return await self._build_memory_context(story_data, config)
    
    async def build_character_focused_context(self, character_name: str, story_data: Dict[str, Any],
                                            config: Optional[ContextConfiguration] = None) -> str:
        """Build context focused on a specific character."""
        if config is None:
            config = ContextConfiguration(narrative_focus="character")
        
        # Use memory context builder for character-focused context
        memory = await self.memory_orchestrator.load_current_memory(story_data.get('story_id'))
        if memory:
            return self.memory_context.build_character_focused_context(memory, character_name)
        return ""
    
    def analyze_context_metrics(self, context: str) -> ContextMetrics:
        """Analyze comprehensive context metrics."""
        return ContextMetrics(
            total_length=len(context),
            memory_context_length=0,  # Would need to track during generation
            content_analysis_length=0,
            narrative_context_length=0,
            context_completeness=1.0,
            processing_time_ms=0,
            components_used=["analysis"]
        )
    
    # Private helper methods
    
    async def _build_memory_context(self, story_data: Dict[str, Any], 
                                   config: ContextConfiguration) -> str:
        """Build memory-based context using memory_management/context/ system."""
        try:
            story_id = story_data.get('story_id')
            if not story_id:
                return ""
            
            memory = await self.memory_orchestrator.load_current_memory(story_id)
            if not memory:
                return ""
            
            # Use modular memory context builder
            memory_config = MemoryContextConfiguration(
                max_context_length=config.max_context_length // 3,  # Reserve space for other components
                character_detail_level=config.memory_detail_level,
                max_recent_events=config.max_recent_events
            )
            
            return self.memory_context.build_memory_context(memory, memory_config)
            
        except Exception as e:
            log_warning(f"Memory context generation failed: {str(e)}")
            return ""
    
    async def _build_content_context(self, user_input: str, story_data: Dict[str, Any],
                                    config: ContextConfiguration) -> str:
        """Build content analysis context using content_analysis/ system."""
        try:
            if not config.enable_content_enhancement:
                return ""
            
            # Use content analysis orchestrator for context enhancement
            analysis_result = await self.content_orchestrator.analyze_content(
                user_input, 
                {
                    'story_data': story_data,
                    'analysis_depth': config.content_analysis_depth
                }
            )
            
            # Format analysis for context
            if analysis_result and 'content_analysis' in analysis_result:
                return self._format_content_analysis_context(analysis_result['content_analysis'])
            
            return ""
            
        except Exception as e:
            log_warning(f"Content analysis context generation failed: {str(e)}")
            return ""
    
    async def _build_narrative_context(self, user_input: str, story_data: Dict[str, Any],
                                      config: ContextConfiguration) -> str:
        """Build narrative context using narrative_systems/response/ system."""
        try:
            if not config.include_story_context:
                return ""
            
            # Use narrative orchestrator for story context
            narrative_result = await self.narrative_orchestrator.analyze_context(
                user_input,
                story_data,
                {'focus': config.narrative_focus}
            )
            
            if narrative_result and 'narrative_context' in narrative_result:
                return self._format_narrative_context(narrative_result['narrative_context'])
            
            return ""
            
        except Exception as e:
            log_warning(f"Narrative context generation failed: {str(e)}")
            return ""
    
    def _assemble_context(self, context_parts: List[str], config: ContextConfiguration) -> str:
        """Assemble final context from all parts."""
        if not context_parts:
            return ""
        
        # Join with clear separators
        context = "\n\n".join(filter(None, context_parts))
        
        # Truncate if necessary
        if len(context) > config.max_context_length:
            context = context[:config.max_context_length - 50] + "\n\n[Context truncated]"
        
        return context
    
    def _format_content_analysis_context(self, analysis: Dict[str, Any]) -> str:
        """Format content analysis results for context."""
        context_parts = []
        
        if 'themes' in analysis:
            context_parts.append(f"Content Themes: {', '.join(analysis['themes'])}")
        
        if 'sentiment' in analysis:
            context_parts.append(f"Content Sentiment: {analysis['sentiment']}")
        
        if 'key_entities' in analysis:
            context_parts.append(f"Key Entities: {', '.join(analysis['key_entities'])}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _format_narrative_context(self, narrative: Dict[str, Any]) -> str:
        """Format narrative analysis results for context."""
        context_parts = []
        
        if 'story_progression' in narrative:
            context_parts.append(f"Story Progression: {narrative['story_progression']}")
        
        if 'character_dynamics' in narrative:
            context_parts.append(f"Character Dynamics: {narrative['character_dynamics']}")
        
        if 'plot_elements' in narrative:
            context_parts.append(f"Plot Elements: {narrative['plot_elements']}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _create_fallback_context(self, user_input: str, story_data: Dict[str, Any]) -> str:
        """Create minimal fallback context when full generation fails."""
        fallback_parts = []
        
        if story_data.get('story_id'):
            fallback_parts.append(f"Story: {story_data['story_id']}")
        
        if user_input:
            fallback_parts.append(f"User Input: {user_input}")
        
        fallback_parts.append("Context: Basic fallback context")
        
        return "\n".join(fallback_parts)
    
    def _calculate_metrics(self, final_context: str, context_parts: List[str], 
                          components_used: List[str], processing_time: int) -> ContextMetrics:
        """Calculate comprehensive context metrics."""
        return ContextMetrics(
            total_length=len(final_context),
            memory_context_length=len(context_parts[0]) if len(context_parts) > 0 else 0,
            content_analysis_length=len(context_parts[1]) if len(context_parts) > 1 else 0,
            narrative_context_length=len(context_parts[2]) if len(context_parts) > 2 else 0,
            context_completeness=min(1.0, len(components_used) / 3.0),
            processing_time_ms=processing_time,
            components_used=components_used
        )
    
    def _get_current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        import time
        return int(time.time() * 1000)


# Direct exports for clean modular access
# No compatibility layer needed - clean breaking changes enabled by pre-public status
