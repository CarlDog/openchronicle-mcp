import os
import json
import random
from .memory_manager import load_current_memory

def load_canon_snippets(storypack_path, refs=None, limit=5):
    canon_dir = os.path.join(storypack_path, "canon")
    snippets = []

    if not os.path.exists(canon_dir):
        return snippets

    if refs:
        for ref in refs:
            file_path = os.path.join(canon_dir, f"{ref}.txt")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    snippets.append(f.read().strip())
    else:
        # Load random canon snippets if no refs provided
        canon_files = [f for f in os.listdir(canon_dir) if f.endswith(".txt")]
        if canon_files:
            random.shuffle(canon_files)
            for filename in canon_files[:limit]:
                with open(os.path.join(canon_dir, filename), "r", encoding="utf-8") as f:
                    snippets.append(f.read().strip())

    return snippets

def build_context(user_input, story_data):
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
        "memory": memory,
        "canon_used": canon_chunks
    }