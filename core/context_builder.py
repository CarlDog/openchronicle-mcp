import os
import json
import random
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning, log_error

from .memory_manager import load_current_memory
from .content_analyzer import ContentAnalyzer
from .character_style_manager import CharacterStyleManager
from .character_consistency_engine import CharacterConsistencyEngine
from .emotional_stability_engine import EmotionalStabilityEngine
from .character_interaction_engine import CharacterInteractionEngine
from .token_manager import TokenManager

def load_canon_snippets(storypack_path, refs=None, limit=5):
    canon_dir = os.path.join(storypack_path, "canon")
    snippets = []

    if not os.path.exists(canon_dir):
        return snippets

    if refs:
        for ref in refs:
            # Try JSON first, then fallback to TXT for backward compatibility
            json_path = os.path.join(canon_dir, f"{ref}.json")
            txt_path = os.path.join(canon_dir, f"{ref}.txt")
            
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert JSON to readable text format
                    snippets.append(json_to_readable_text(data))
            elif os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as f:
                    snippets.append(f.read().strip())
    else:
        # Load random canon snippets if no refs provided
        canon_files = [f for f in os.listdir(canon_dir) if f.endswith((".json", ".txt"))]
        if canon_files:
            random.shuffle(canon_files)
            for filename in canon_files[:limit]:
                file_path = os.path.join(canon_dir, filename)
                if filename.endswith(".json"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        snippets.append(json_to_readable_text(data))
                else:
                    with open(file_path, "r", encoding="utf-8") as f:
                        snippets.append(f.read().strip())

    return snippets

def json_to_readable_text(data, indent=0):
    """Convert JSON data to readable text format for context injection."""
    lines = []
    prefix = "  " * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key.replace('_', ' ').title()}:")
                lines.append(json_to_readable_text(value, indent + 1))
            else:
                lines.append(f"{prefix}{key.replace('_', ' ').title()}: {value}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- {json_to_readable_text(item, indent + 1)}")
            else:
                lines.append(f"{prefix}- {item}")
    else:
        return str(data)
    
    return "\n".join(lines)

def build_context(user_input, story_data):
    """
    Build context with basic analysis (synchronous version).
    For advanced analysis, use build_context_with_analysis.
    """
    story_id = story_data["id"]
    story_path = story_data["path"]

    memory = load_current_memory(story_id)
    canon_chunks = load_canon_snippets(story_path)

    # Build memory summary for context
    memory_summary = []
    if memory.get("characters"):
        memory_summary.append("=== CHARACTERS ===")
        for char_name, char_data in memory["characters"].items():
            memory_summary.append(f"{char_name}: {char_data.get('current_state', {})}")
    
    if memory.get("world_state"):
        memory_summary.append("=== WORLD STATE ===")
        for key, value in memory["world_state"].items():
            memory_summary.append(f"{key}: {value}")
    
    if memory.get("flags"):
        memory_summary.append("=== ACTIVE FLAGS ===")
        for flag in memory["flags"]:
            memory_summary.append(f"- {flag['name']}")
    
    if memory.get("recent_events"):
        memory_summary.append("=== RECENT EVENTS ===")
        for event in memory["recent_events"][-5:]:  # Last 5 events
            memory_summary.append(f"- {event['description']}")

    prompt_parts = [
        "You are continuing a fictional interactive narrative.",
        f"Story Title: {story_data['meta'].get('title', 'Untitled')}",
        "",
        "=== CANON ===",
        *canon_chunks,
        "",
        *memory_summary,
        "",
        "=== USER INPUT ===",
        user_input,
        "",
        "Continue the story with rich detail and continuity."
    ]

    prompt = "\n".join(prompt_parts)
    return {
        "prompt": prompt,
        "full_context": prompt,  # For compatibility
        "memory": memory,
        "canon_used": canon_chunks,
        "analysis": None  # No analysis in basic version
    }

async def build_context_with_analysis(user_input, story_data):
    """
    Build optimized context using content analysis.
    This is the new intelligent version that reduces tokens.
    """
    from .content_analyzer import ContentAnalyzer
    from .model_adapter import ModelManager
    
    # Initialize content analyzer
    model_manager = ModelManager()
    content_analyzer = ContentAnalyzer(model_manager)
    
    story_id = story_data["id"]
    story_path = story_data["path"]

    # Step 1: Analyze user input
    story_context = {
        "story_id": story_id,
        "meta": story_data.get("meta", {}),
        "characters": {}
    }
    
    # Load current memory for character context
    memory = load_current_memory(story_id)
    if memory.get("characters"):
        story_context["characters"] = memory["characters"]

    analysis = await content_analyzer.analyze_user_input(user_input, story_context)
    
    # Step 2: Select optimized canon based on analysis
    optimized_canon_refs = await content_analyzer.optimize_canon_selection(analysis, story_data)
    canon_chunks = load_canon_snippets(story_path, refs=optimized_canon_refs)
    
    # Step 3: Optimize memory context
    optimized_memory = await content_analyzer.optimize_memory_context(analysis, memory)
    
    # Step 4: Build optimized memory summary
    memory_summary = []
    if optimized_memory.get("characters"):
        memory_summary.append("=== CHARACTERS ===")
        for char_name, char_data in optimized_memory["characters"].items():
            memory_summary.append(f"{char_name}: {char_data.get('current_state', {})}")
    
    if optimized_memory.get("world_state"):
        memory_summary.append("=== WORLD STATE ===")
        for key, value in optimized_memory["world_state"].items():
            memory_summary.append(f"{key}: {value}")
    
    if optimized_memory.get("flags"):
        memory_summary.append("=== ACTIVE FLAGS ===")
        for flag in optimized_memory["flags"]:
            memory_summary.append(f"- {flag['name']}")
    
    if optimized_memory.get("recent_events"):
        memory_summary.append("=== RECENT EVENTS ===")
        for event in optimized_memory["recent_events"]:
            memory_summary.append(f"- {event['description']}")

    # Step 5: Build optimized prompt
    response_style = analysis.get("response_style", "narrative")
    content_type = analysis.get("content_type", "action")
    
    # Customize prompt based on analysis
    style_instruction = {
        "narrative": "Continue the story with rich detail and continuity.",
        "descriptive": "Provide vivid descriptions of the scene and atmosphere.",
        "action": "Focus on action and movement in your response.",
        "dialogue": "Emphasize character dialogue and interaction."
    }.get(response_style, "Continue the story with rich detail and continuity.")
    
    prompt_parts = [
        "You are continuing a fictional interactive narrative.",
        f"Story Title: {story_data['meta'].get('title', 'Untitled')}",
        f"Content Type: {content_type}",
        "",
        "=== CANON ===",
        *canon_chunks,
        "",
        *memory_summary,
        "",
        "=== USER INPUT ===",
        user_input,
        "",
        style_instruction
    ]

    prompt = "\n".join(prompt_parts)
    
    return {
        "prompt": prompt,
        "full_context": prompt,
        "memory": memory,  # Return full memory for logging
        "optimized_memory": optimized_memory,
        "canon_used": canon_chunks,
        "analysis": analysis,
        "routing": content_analyzer.get_routing_recommendation(analysis)
    }

async def build_context_with_dynamic_models(user_input: str, story_data: Dict[str, Any], 
                                          model_manager) -> Dict[str, Any]:
    """
    Build context with dynamic model selection, optimization, and character consistency.
    """
    story_id = story_data["id"]
    story_path = story_data["path"]
    
    # Initialize managers
    content_analyzer = ContentAnalyzer(model_manager)
    character_manager = CharacterStyleManager(model_manager)
    consistency_engine = CharacterConsistencyEngine(character_manager)
    emotional_engine = EmotionalStabilityEngine()
    interaction_engine = CharacterInteractionEngine()
    token_manager = TokenManager(model_manager)
    
    # Load character styles and consistency data
    character_manager.load_character_styles(story_path)
    consistency_engine.load_character_consistency_data(story_path)
    
    # Analyze user input for optimal model selection
    try:
        analysis = await content_analyzer.analyze_user_input(user_input, {
            "story_id": story_id,
            "meta": story_data.get("meta", {}),
            "characters": story_data.get("characters", {})
        })
        
        recommended_model = analysis.get("routing_recommendation", "mock")
        content_type = analysis.get("content_type", "general")
        
        log_system_event("context_building", 
                        f"Recommended model: {recommended_model} for {content_type}")
        
    except Exception as e:
        log_error(f"Content analysis failed, using fallback: {e}")
        analysis = {"routing_recommendation": "mock", "content_type": "general"}
        recommended_model = "mock"
        content_type = "general"
    
    # Load memory and canon
    memory = load_current_memory(story_id)
    canon_chunks = load_canon_snippets(story_path)
    
    # Determine active character if any
    active_character = None
    if analysis.get("entities", {}).get("characters"):
        active_character = analysis["entities"]["characters"][0]
    
    # Select model based on character and content
    if active_character:
        selected_model = character_manager.select_character_model(
            active_character, content_type)
        if selected_model != recommended_model:
            log_info(f"Character-specific model override: {selected_model} for {active_character}")
            recommended_model = selected_model
    
    # Build context parts
    context_parts = {
        "system": _build_system_context(story_data),
        "memory": _build_memory_context(memory),
        "canon": _build_canon_context(canon_chunks),
        "user_input": user_input
    }
    
    # Add character consistency context if applicable
    if active_character:
        # Add character style context
        character_context = character_manager.build_character_context(
            active_character, recommended_model)
        if character_context:
            context_parts["character_style"] = character_context
        
        # Add motivation anchoring for consistency
        motivation_prompt = consistency_engine.get_motivation_prompt(
            active_character, content_type)
        if motivation_prompt:
            context_parts["character_consistency"] = motivation_prompt
        
        # Add emotional stability context and anti-loop prompts
        emotional_context = emotional_engine.get_emotional_context(active_character)
        if emotional_context['active_cooldowns']:
            cooldown_warnings = []
            for cooldown in emotional_context['active_cooldowns']:
                remaining = cooldown['remaining_minutes']
                behavior = cooldown['behavior']
                cooldown_warnings.append(
                    f"{behavior} behavior should be avoided for {remaining} more minutes"
                )
            
            if cooldown_warnings:
                context_parts["emotional_stability"] = (
                    f"[EMOTIONAL_STABILITY_GUIDANCE: {active_character} has recent "
                    f"emotional patterns to avoid: {'; '.join(cooldown_warnings)}. "
                    f"Consider introducing variety, internal conflict, or external "
                    f"distractions to maintain authentic character development.]"
                )
        
        # Check for potential loops in user input and add prevention prompts
        if user_input:
            input_loops = emotional_engine.detect_emotional_loops(active_character, user_input)
            if input_loops:
                anti_loop_prompt = emotional_engine.generate_anti_loop_prompt(active_character, input_loops)
                if anti_loop_prompt and "emotional_stability" in context_parts:
                    context_parts["emotional_stability"] += f"\n{anti_loop_prompt}"
                elif anti_loop_prompt:
                    context_parts["emotional_stability"] = anti_loop_prompt
    
    # Add character interaction dynamics context for multi-character scenes
    if active_character:
        # Detect if this might be a multi-character scene (basic heuristic)
        scene_characters = _detect_scene_characters(user_input, story_data.get("characters", {}))
        
        if len(scene_characters) > 1 and active_character in scene_characters:
            # Create or get existing scene
            scene_id = f"scene_{story_id}_{hash(frozenset(scene_characters)) % 10000}"
            
            # Check if scene exists, if not create it
            if scene_id not in interaction_engine.scene_states:
                interaction_engine.create_scene(
                    scene_id=scene_id,
                    characters=scene_characters,
                    scene_focus="character interaction",
                    environment_context="current scene"
                )
            
            # Generate relationship context
            relationship_prompt = interaction_engine.generate_relationship_prompt(scene_id, active_character)
            if relationship_prompt:
                context_parts["character_interactions"] = relationship_prompt
    
    # Estimate token usage and trim if necessary
    estimated_tokens = sum(
        token_manager.estimate_tokens(part, recommended_model)
        for part in context_parts.values()
    )
    
    # Check if we need to trim for token limits
    model_config = model_manager.get_adapter_info(recommended_model)
    max_tokens = model_config.get("max_tokens", 4096)
    target_tokens = int(max_tokens * 0.6)  # Leave room for response
    
    if estimated_tokens > target_tokens:
        log_warning(f"Context too long ({estimated_tokens} tokens), trimming to {target_tokens}")
        
        # Use fallback motivation prompt if we need to trim
        if active_character and "character_consistency" in context_parts:
            fallback_prompt = consistency_engine.get_fallback_prompt(
                active_character, max_tokens=150)
            context_parts["character_consistency"] = fallback_prompt
        
        context_parts = token_manager.trim_context_intelligently(
            context_parts, target_tokens, recommended_model)
    
    # Build final context
    final_context = _assemble_context(context_parts)
    
    return {
        "context": final_context,
        "recommended_model": recommended_model,
        "content_analysis": analysis,
        "active_character": active_character,
        "consistency_engine": consistency_engine,
        "token_estimate": token_manager.estimate_tokens(final_context, recommended_model)
    }

def _build_system_context(story_data: Dict[str, Any]) -> str:
    """Build system context section."""
    return f"""You are continuing a fictional interactive narrative.
Story Title: {story_data['meta'].get('title', 'Untitled')}
Description: {story_data['meta'].get('description', 'No description')}"""

def _build_memory_context(memory: Dict[str, Any]) -> str:
    """Build memory context section."""
    parts = []
    
    if memory.get("characters"):
        parts.append("=== CHARACTERS ===")
        for char_name, char_data in memory["characters"].items():
            parts.append(f"{char_name}: {char_data.get('current_state', {})}")
    
    if memory.get("world_state"):
        parts.append("=== WORLD STATE ===")
        for key, value in memory["world_state"].items():
            parts.append(f"{key}: {value}")
    
    if memory.get("flags"):
        parts.append("=== ACTIVE FLAGS ===")
        for flag in memory["flags"]:
            parts.append(f"- {flag['name']}")
    
    if memory.get("recent_events"):
        parts.append("=== RECENT EVENTS ===")
        for event in memory["recent_events"][-5:]:
            parts.append(f"- {event['description']}")
    
    return "\n".join(parts)

def _build_canon_context(canon_chunks: List[str]) -> str:
    """Build canon context section."""
    if not canon_chunks:
        return ""
    
    parts = ["=== CANON ==="]
    parts.extend(canon_chunks)
    return "\n".join(parts)

def _assemble_context(context_parts: Dict[str, str]) -> str:
    """Assemble final context from parts."""
    sections = []
    
    # Order matters for context flow
    section_order = ["system", "memory", "canon", "character_style", "character_consistency", "user_input"]
    
    for section in section_order:
        if section in context_parts and context_parts[section]:
            if section == "user_input":
                sections.append(f"=== USER INPUT ===\n{context_parts[section]}")
            else:
                sections.append(context_parts[section])
    
    sections.append("\nContinue the story naturally based on the user's input, maintaining consistency with the established world and characters.")
    
    return "\n\n".join(sections)

async def validate_character_consistency(generated_output: str, character_name: str, 
                                       scene_id: str, consistency_engine: CharacterConsistencyEngine,
                                       context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Validate generated output for character consistency violations.
    """
    if not character_name or not consistency_engine:
        return {"violations": [], "consistency_score": 1.0}
    
    try:
        # Analyze the output for consistency violations
        violations = consistency_engine.analyze_behavioral_consistency(
            character_name, generated_output, scene_id, context
        )
        
        # Get current consistency score
        consistency_score = consistency_engine.get_consistency_score(character_name)
        
        # Log results
        if violations:
            log_warning(f"Character consistency violations detected for {character_name} in {scene_id}")
            for violation in violations:
                log_warning(f"  - {violation.violation_type.value}: {violation.description}")
        else:
            log_info(f"Character consistency maintained for {character_name} in {scene_id}")
        
        return {
            "violations": [v.to_dict() for v in violations],
            "consistency_score": consistency_score,
            "character_name": character_name,
            "scene_id": scene_id
        }
        
    except Exception as e:
        log_error(f"Character consistency validation failed: {e}")
        return {
            "violations": [],
            "consistency_score": 1.0,
            "error": str(e)
        }

async def validate_emotional_stability(generated_output: str, character_name: str,
                                     scene_id: str, emotional_engine: EmotionalStabilityEngine,
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Validate generated output for emotional stability and detect loops.
    """
    if not character_name or not emotional_engine:
        return {"loops": [], "stability_score": 1.0, "anti_loop_prompt": ""}
    
    try:
        # Detect emotional loops in the output
        detected_loops = emotional_engine.detect_emotional_loops(character_name, generated_output)
        
        # Get current emotional context
        emotional_context = emotional_engine.get_emotional_context(character_name)
        stability_score = emotional_context['emotional_stability_score']
        
        # Generate anti-loop prompt if needed
        anti_loop_prompt = ""
        if detected_loops:
            anti_loop_prompt = emotional_engine.generate_anti_loop_prompt(character_name, detected_loops)
            
            # Trigger cooldowns for detected loop behaviors
            for loop in detected_loops:
                if loop.loop_type in ['excessive_flirtation', 'praise_seeking', 'neediness']:
                    emotional_engine.trigger_behavior_cooldown(character_name, loop.loop_type.replace('_', ''))
        
        # Track emotional state based on content analysis
        if context and 'content_analysis' in context:
            content_flags = context['content_analysis'].get('flags', [])
            emotional_intensity = 0.5  # Default
            
            # Determine emotion and intensity from content flags
            if 'flirty' in content_flags or 'romantic' in content_flags:
                emotional_engine.track_emotional_state(character_name, 'flirty', 0.7, scene_id)
            elif 'emotional' in content_flags:
                emotional_engine.track_emotional_state(character_name, 'vulnerable', 0.6, scene_id)
            elif 'praise_seeking' in generated_output.lower():
                emotional_engine.track_emotional_state(character_name, 'insecure', 0.5, scene_id)
        
        # Log results
        if detected_loops:
            log_warning(f"Emotional loops detected for {character_name} in {scene_id}")
            for loop in detected_loops:
                log_warning(f"  - {loop.loop_type}: {loop.pattern} (confidence: {loop.confidence:.2f})")
        else:
            log_info(f"Emotional stability maintained for {character_name} in {scene_id}")
        
        return {
            "loops": [
                {
                    "type": loop.loop_type,
                    "pattern": loop.pattern,
                    "confidence": loop.confidence,
                    "severity": loop.severity,
                    "suggested_disruption": loop.suggested_disruption
                }
                for loop in detected_loops
            ],
            "stability_score": stability_score,
            "anti_loop_prompt": anti_loop_prompt,
            "character_name": character_name,
            "scene_id": scene_id,
            "active_cooldowns": emotional_context['active_cooldowns']
        }
        
    except Exception as e:
        log_error(f"Emotional stability validation failed: {e}")
        return {
            "loops": [],
            "stability_score": 1.0,
            "anti_loop_prompt": "",
            "error": str(e)
        }

def get_character_consistency_report(consistency_engine: CharacterConsistencyEngine, 
                                   character_name: str = None) -> Dict[str, Any]:
    """
    Get character consistency report(s).
    """
    if not consistency_engine:
        return {"error": "No consistency engine available"}
    
    try:
        if character_name:
            return consistency_engine.get_consistency_report(character_name)
        else:
            # Get stats for all characters
            stats = consistency_engine.get_stats()
            character_reports = {}
            
            for char_name in consistency_engine.motivation_anchors.keys():
                character_reports[char_name] = consistency_engine.get_consistency_report(char_name)
            
            return {
                "overall_stats": stats,
                "character_reports": character_reports
            }
            
    except Exception as e:
        log_error(f"Failed to generate consistency report: {e}")
        return {"error": str(e)}

def get_emotional_stability_report(emotional_engine: EmotionalStabilityEngine,
                                 character_name: str = None) -> Dict[str, Any]:
    """
    Get emotional stability report(s).
    """
    if not emotional_engine:
        return {"error": "No emotional stability engine available"}
    
    try:
        if character_name:
            context = emotional_engine.get_emotional_context(character_name)
            cooldown_status = emotional_engine.get_cooldown_status(character_name)
            
            return {
                "character_name": character_name,
                "current_emotional_state": context.get('current_state'),
                "recent_emotions": context.get('recent_emotions', []),
                "stability_score": context.get('emotional_stability_score', 1.0),
                "active_cooldowns": context.get('active_cooldowns', []),
                "cooldown_details": cooldown_status
            }
        else:
            # Get overall engine statistics
            engine_stats = emotional_engine.get_engine_stats()
            character_reports = {}
            
            # Get reports for all tracked characters
            for char_id in emotional_engine.emotional_histories.keys():
                character_reports[char_id] = {
                    "emotional_context": emotional_engine.get_emotional_context(char_id),
                    "cooldown_status": emotional_engine.get_cooldown_status(char_id)
                }
            
            return {
                "overall_stats": engine_stats,
                "character_reports": character_reports
            }
            
    except Exception as e:
        log_error(f"Failed to generate emotional stability report: {e}")
        return {"error": str(e)}

def _detect_scene_characters(user_input: str, characters: Dict[str, Any]) -> List[str]:
    """
    Detect which characters are likely present in the current scene based on user input.
    
    This is a simple heuristic that looks for character names in the input.
    In a more sophisticated implementation, this could use NLP or scene analysis.
    """
    if not user_input or not characters:
        return []
    
    input_lower = user_input.lower()
    detected_characters = []
    
    for char_name, char_data in characters.items():
        # Check if character name appears in input
        if char_name.lower() in input_lower:
            detected_characters.append(char_name)
        
        # Check aliases if they exist
        if isinstance(char_data, dict):
            aliases = char_data.get('aliases', [])
            for alias in aliases:
                if alias.lower() in input_lower:
                    detected_characters.append(char_name)
                    break
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(detected_characters))