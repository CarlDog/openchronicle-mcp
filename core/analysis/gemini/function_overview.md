# Core Module Function and Method Overview

This document provides a comprehensive overview of all functions and methods within each module of the `core` directory. It is intended to help identify shared functionalities and potential opportunities for creating centralized external helpers.

## `bookmark_manager.py`

-   **BookmarkManager**:
    -   `__init__(self, story_id)`
    -   `create_bookmark(self, scene_id, label, description, bookmark_type, metadata)`
    -   `get_bookmark(self, bookmark_id)`
    -   `list_bookmarks(self, bookmark_type, scene_id, limit)`
    -   `update_bookmark(self, bookmark_id, label, description, bookmark_type, metadata)`
    -   `delete_bookmark(self, bookmark_id)`
    -   `delete_bookmarks_for_scene(self, scene_id)`
    -   `search_bookmarks(self, query, bookmark_type)`
    -   `get_bookmarks_with_scenes(self, bookmark_type)`
    -   `auto_create_chapter_bookmark(self, scene_id, chapter_title, chapter_level)`
    -   `get_chapter_bookmarks(self)`
    -   `get_timeline_bookmarks(self)`
    -   `get_chapter_structure(self)`
    -   `get_stats(self)`
    -   `_format_bookmark(self, row)`

## `character_consistency_engine.py`

-   **CharacterConsistencyEngine**:
    -   `__init__(self, story_id, model_manager)`
    -   `analyze_character_consistency(self, character_name, scene_text)`
    -   `_get_character_profile(self, character_name)`
    -   `_get_recent_character_scenes(self, character_name, limit)`
    -   `_build_consistency_prompt(self, character_profile, recent_scenes, new_scene_text)`
    -   `_parse_consistency_report(self, report_text)`
    -   `suggest_character_modifications(self, character_name, scene_text)`
    -   `_build_modification_prompt(self, character_profile, scene_text)`
    -   `_parse_suggested_modifications(self, modification_text)`
    -   `validate_character_arc(self, character_name)`
    -   `_get_character_arc_scenes(self, character_name)`
    -   `_build_arc_validation_prompt(self, character_profile, arc_scenes)`
    -   `_parse_arc_validation_report(self, report_text)`
    -   `get_character_relationship_summary(self, character_name)`
    -   `_build_relationship_summary_prompt(self, character_profile, all_characters)`
    -   `_parse_relationship_summary(self, summary_text)`

## `character_interaction_engine.py`

-   **CharacterInteractionEngine**:
    -   `__init__(self, story_id, model_manager)`
    -   `generate_interaction(self, characters, context, style_modifiers)`
    -   `_get_character_profiles(self, character_names)`
    -   `_build_interaction_prompt(self, character_profiles, context, style_modifiers)`
    -   `_parse_interaction_result(self, result_text)`
    -   `analyze_interaction_quality(self, interaction_text)`
    -   `_build_quality_analysis_prompt(self, interaction_text)`
    -   `_parse_quality_analysis(self, analysis_text)`
    -   `suggest_interaction_improvements(self, interaction_text)`
    -   `_build_improvement_suggestion_prompt(self, interaction_text)`
    -   `_parse_improvement_suggestions(self, suggestion_text)`
    -   `get_character_dialogue_style(self, character_name)`
    -   `_build_dialogue_style_prompt(self, character_profile)`
    -   `_parse_dialogue_style(self, style_text)`

## `character_stat_engine.py`

-   **CharacterStatEngine**:
    -   `__init__(self, story_id)`
    -   `get_character_stats(self, character_name)`
    -   `update_character_stats(self, character_name, updates)`
    -   `calculate_derived_stats(self, character_name)`
    -   `get_stat_modifier(self, stat_value)`
    -   `perform_stat_check(self, character_name, stat_name, difficulty)`
    -   `apply_stat_effects(self, character_name, effects)`
    -   `get_all_character_stats(self)`
    -   `get_stat_leaderboard(self, stat_name)`
    -   `get_character_progression(self, character_name)`
    -   `_get_stat_history(self, character_name, stat_name)`

## `character_style_manager.py`

-   **CharacterStyleManager**:
    -   `__init__(self, story_id, model_manager)`
    -   `get_character_style(self, character_name)`
    -   `update_character_style(self, character_name, updates)`
    -   `generate_style_prompt(self, character_name)`
    -   `analyze_style_consistency(self, character_name, text)`
    -   `_build_style_analysis_prompt(self, character_style, text)`
    -   `_parse_style_analysis(self, analysis_text)`
    -   `suggest_style_improvements(self, character_name, text)`
    -   `_build_style_improvement_prompt(self, character_style, text)`
    -   `_parse_style_improvements(self, improvement_text)`

## `content_analyzer.py`

-   **ContentAnalyzer**:
    -   `__init__(self, model_manager)`
    -   `analyze_text(self, text, analysis_types)`
    -   `_analyze_sentiment(self, text)`
    -   `_analyze_emotion(self, text)`
    -   `_analyze_themes(self, text)`
    -   `_analyze_writing_style(self, text)`
    -   `_analyze_readability(self, text)`
    -   `_analyze_entities(self, text)`
    -   `_analyze_plot_points(self, text)`
    -   `_analyze_character_mentions(self, text)`
    -   `_build_analysis_prompt(self, text, analysis_types)`
    -   `_parse_analysis_report(self, report_text)`

## `context_builder.py`

-   **ContextBuilder**:
    -   `__init__(self, story_id, memory_manager)`
    -   `build_context(self, scene_id, context_type, options)`
    -   `_get_scene_data(self, scene_id)`
    -   `_get_character_data(self, character_names)`
    -   `_get_world_data(self, world_keys)`
    -   `_get_recent_scenes(self, current_scene_id, num_scenes)`
    -   `_format_context_for_prompt(self, context_data)`
    -   `build_character_context(self, character_name, options)`
    -   `build_scene_context(self, scene_id, options)`
    -   `build_world_context(self, world_keys, options)`

## `database.py`

-   `init_database(story_id)`
-   `get_connection(story_id)`
-   `execute_query(story_id, query, params)`
-   `execute_update(story_id, query, params)`
-   `execute_insert(story_id, query, params)`
-   `close_connection(story_id)`

## `emotional_stability_engine.py`

-   **EmotionalStabilityEngine**:
    -   `__init__(self, story_id, memory_manager)`
    -   `get_emotional_state(self, character_name)`
    -   `update_emotional_state(self, character_name, new_mood, scene_context, emotional_triggers)`
    -   `calculate_mood_stability(self, character_name)`
    -   `get_mood_history(self, character_name, limit)`
    -   `get_emotional_triggers(self, character_name)`
    -   `suggest_emotional_arc(self, character_name)`
    -   `_build_emotional_arc_prompt(self, character_profile)`
    -   `_parse_emotional_arc(self, arc_text)`
    -   `get_emotional_report(self, character_name)`

## `image_adapter.py`

-   **ImageAdapter** (ABC):
    -   `__init__(self, config)`
    -   `generate_image(self, request)`
    -   `is_available(self)`
    -   `get_provider_name(self)`
    -   `supports_size(self, size)`
-   **OpenAIImageAdapter**:
    -   `__init__(self, config)`
    -   `is_available(self)`
    -   `supports_size(self, size)`
    -   `generate_image(self, request)`
-   **MockImageAdapter**:
    -   `__init__(self, config)`
    -   `is_available(self)`
    -   `generate_image(self, request)`
-   **ImageAdapterRegistry**:
    -   `__init__(self)`
    -   `register_adapter(self, adapter)`
    -   `get_adapter(self, provider)`
    -   `get_available_adapters(self)`
    -   `get_best_adapter(self, request)`
    -   `generate_image(self, request, preferred_provider)`
-   `create_image_registry(config)`

## `image_generation_engine.py`

-   **ImageGenerationEngine**:
    -   `__init__(self, story_path, config)`
    -   `generate_image(self, prompt, image_type, **kwargs)`
    -   `generate_character_portrait(self, character_name, character_data)`
    -   `generate_scene_image(self, scene_id, scene_data)`
    -   `_build_character_prompt(self, character_data)`
    -   `_build_scene_prompt(self, scene_data)`
    -   `_save_image(self, image_data, filename)`
    -   `_save_metadata(self, metadata)`
    -   `_load_metadata(self)`
    -   `_generate_filename(self, image_type, entity_name)`

## `intelligent_response_engine.py`

-   **IntelligentResponseEngine**:
    -   `__init__(self, model_manager, memory_manager)`
    -   `generate_response(self, story_id, prompt, options)`
    -   `_build_full_prompt(self, story_id, prompt, options)`
    -   `_select_model(self, prompt_length, response_length)`
    -   `_handle_fallback(self, story_id, prompt, options, error)`
    -   `_post_process_response(self, response_text)`
    -   `generate_character_dialogue(self, story_id, character_name, context)`
    -   `generate_narrative_summary(self, story_id, text)`

## `memory_consistency_engine.py`

-   **MemoryConsistencyEngine**:
    -   `__init__(self, story_id, memory_manager, model_manager)`
    -   `check_consistency(self, scene_text)`
    -   `_get_relevant_memory(self, scene_text)`
    -   `_build_consistency_prompt(self, relevant_memory, scene_text)`
    -   `_parse_consistency_report(self, report_text)`
    -   `suggest_memory_updates(self, scene_text)`
    -   `_build_update_suggestion_prompt(self, scene_text)`
    -   `_parse_suggested_updates(self, update_text)`
    -   `get_memory_report(self, character_name)`

## `memory_manager.py`

-   `load_current_memory(story_id)`
-   `save_current_memory(story_id, memory_data)`
-   `archive_memory_snapshot(story_id, scene_id, memory_data)`
-   `update_character_memory(story_id, character_name, updates)`
-   `get_character_memory_snapshot(story_id, character_name, format_for_prompt)`
-   `format_character_snapshot_for_prompt(snapshot)`
-   `refresh_memory_after_rollback(story_id, target_scene_id)`
-   `get_character_voice_prompt(story_id, character_name)`
-   `update_character_mood(story_id, character_name, new_mood, scene_context, emotional_triggers)`
-   `update_world_state(story_id, updates)`
-   `add_memory_flag(story_id, flag_name, flag_data)`
-   `remove_memory_flag(story_id, flag_name)`
-   `has_memory_flag(story_id, flag_name)`
-   `add_recent_event(story_id, event_description, event_data)`
-   `get_recent_events(story_id, limit)`

## `model_adapter.py`

-   **ModelAdapter** (ABC):
    -   `__init__(self, config)`
    -   `generate_response(self, prompt, options)`
    -   `is_available(self)`
-   **OpenAIAdapter**:
    -   `__init__(self, config)`
    -   `generate_response(self, prompt, options)`
    -   `is_available(self)`
-   **AnthropicAdapter**:
    -   `__init__(self, config)`
    -   `generate_response(self, prompt, options)`
    -   `is_available(self)`
-   **OllamaAdapter**:
    -   `__init__(self, config)`
    -   `generate_response(self, prompt, options)`
    -   `is_available(self)`
-   **MockAdapter**:
    -   `__init__(self, config)`
    -   `generate_response(self, prompt, options)`
    -   `is_available(self)`
-   **ModelManager**:
    -   `__init__(self, config_path)`
    -   `load_config(self)`
    -   `save_config(self)`
    -   `register_adapter(self, adapter_name, adapter_class)`
    -   `get_adapter(self, adapter_name)`
    -   `get_fallback_chain(self, preferred_adapter)`
    -   `generate_response(self, prompt, adapter_name, options)`
    -   `list_models(self)`
    -   `get_model_info(self, model_name)`

## `narrative_dice_engine.py`

-   **NarrativeDiceEngine**:
    -   `__init__(self, story_id, model_manager)`
    -   `roll_dice(self, num_dice, num_sides, modifier, description)`
    -   `interpret_roll(self, roll_result, context)`
    -   `_build_interpretation_prompt(self, roll_result, context)`
    -   `_parse_interpretation(self, interpretation_text)`
    -   `perform_skill_check(self, character_name, skill_name, difficulty)`
    -   `perform_contest(self, character1_name, skill1_name, character2_name, skill2_name)`
    -   `get_dice_log(self)`

## `rollback_engine.py`

-   `create_rollback_point(story_id, scene_id, description)`
-   `list_rollback_points(story_id)`
-   `get_scenes_after(story_id, target_scene_id)`
-   `backup_scenes_for_rollback(story_id, scenes_to_backup)`
-   `rollback_to_scene(story_id, target_scene_id, create_backup)`
-   `rollback_to_timestamp(story_id, target_timestamp, create_backup)`
-   `get_rollback_candidates(story_id, limit)`
-   `validate_rollback_integrity(story_id)`
-   `cleanup_old_rollback_data(story_id, days_to_keep)`

## `scene_logger.py`

-   `save_scene(story_id, scene_data)`
-   `load_scene(story_id, scene_id)`
-   `list_scenes(story_id, limit, offset)`
-   `get_last_scene(story_id)`
-   `search_scenes(story_id, query)`
-   `get_scene_count(story_id)`
-   `delete_scene(story_id, scene_id)`
-   `update_scene(story_id, scene_id, updates)`
-   `get_scene_history(story_id, scene_id)`

## `search_engine.py`

-   **SearchEngine**:
    -   `__init__(self, story_id)`
    -   `search(self, query, search_type, options)`
    -   `_search_scenes(self, query, options)`
    -   `_search_characters(self, query, options)`
    -   `_search_world_data(self, query, options)`
    -   `_search_bookmarks(self, query, options)`
    -   `_build_search_query(self, query, options)`
    -   `_format_search_results(self, results, search_type)`

## `story_loader.py`

-   `load_story(story_id)`
-   `create_new_story(story_name, template)`
-   `list_stories()`
-   `get_story_metadata(story_id)`
-   `save_story_metadata(story_id, metadata)`

## `timeline_builder.py`

-   **TimelineBuilder**:
    -   `__init__(self, story_id)`
    -   `build_timeline(self, start_date, end_date)`
    -   `_get_scenes_in_range(self, start_date, end_date)`
    -   `_get_bookmarks_in_range(self, start_date, end_date)`
    -   `_create_timeline_event(self, item, event_type)`
    -   `_sort_timeline(self, timeline)`
    -   `get_events_by_character(self, character_name)`
    -   `get_events_by_location(self, location_name)`
    -   `get_full_timeline(self)`

## `token_manager.py`

-   **TokenManager**:
    -   `__init__(self, model_manager)`
    -   `get_tokenizer(self, model_name)`
    -   `estimate_tokens(self, text, model_name)`
    -   `select_optimal_model_for_length(self, prompt_length, response_length)`
    -   `check_truncation_risk(self, prompt, model_name, max_response_tokens)`
    -   `trim_context_intelligently(self, context_parts, target_tokens, model_name)`
    -   `detect_truncation(self, response)`
    -   `continue_scene(self, original_prompt, partial_response, story_id, model_name)`
    -   `track_token_usage(self, model_name, prompt_tokens, response_tokens, cost)`
    -   `get_usage_stats(self)`
    -   `recommend_model_switch(self, current_model, usage_pattern)`
