import os
import json
import random

def load_memory(story_id):
    memory_path = os.path.join("storage", story_id, "memory", "current_memory.json")
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_canon_snippets(storypack_path, refs=None, limit=5):
    canon_dir = os.path.join(storypack_path, "canon")
    snippets = []

    if refs:
        for ref in refs:
            file_path = os.path.join(canon_dir, f"{ref}.txt")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    snippets.append(f.read().strip())
    else:
        # Load random canon snippets if no refs provided
        canon_files = [f for f in os.listdir(canon_dir) if f.endswith(".txt")]
        random.shuffle(canon_files)
        for filename in canon_files[:limit]:
            with open(os.path.join(canon_dir, filename), "r", encoding="utf-8") as f:
                snippets.append(f.read().strip())

    return snippets

def build_context(user_input, story_data):
    story_id = story_data["id"]
    story_path = story_data["path"]

    memory = load_memory(story_id)
    canon_chunks = load_canon_snippets(story_path)

    prompt_parts = [
        "You are continuing a fictional interactive narrative.",
        f"Story Title: {story_data['meta'].get('title', 'Untitled')}",
        "",
        "=== CANON ===",
        *canon_chunks,
        "",
        "=== MEMORY STATE ===",
        json.dumps(memory, indent=2),
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