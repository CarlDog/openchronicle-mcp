"""Initialize model configuration directory with examples."""

from __future__ import annotations

import json
from pathlib import Path


def execute(config_dir: str) -> dict[str, str | int | list[str]]:
    """
    Initialize configuration directory with example model configs.

    Creates <config_dir>/models if missing and populates it with minimal
    example v1-style model configs.  API keys are resolved at runtime from
    standard environment variables (e.g. OPENAI_API_KEY), so configs don't
    need embedded keys.

    Args:
        config_dir: Base configuration directory

    Returns:
        Dict with initialization result info
    """
    config_path = Path(config_dir)
    models_dir = config_path / "models"

    # Ensure directories exist
    models_dir.mkdir(parents=True, exist_ok=True)

    # Define minimal example configs — no embedded API keys.
    # Keys are resolved at runtime: inline → api_key_env → standard env var.
    examples = {
        "openai_gpt4o_mini.json": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "display_name": "OpenAI GPT-4o Mini",
            "description": "OpenAI's GPT-4o-mini model (cost-effective)",
            "api_config": {
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "default_base_url": "https://api.openai.com/v1",
                "timeout": 30,
                "auth_header": "Authorization",
                "auth_format": "Bearer {api_key}",
            },
        },
        "anthropic_claude_sonnet4.json": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "display_name": "Anthropic Claude Sonnet 4",
            "description": "Claude Sonnet 4 - excellent reasoning and writing",
            "api_config": {
                "endpoint": "https://api.anthropic.com/v1/messages",
                "default_base_url": "https://api.anthropic.com",
                "timeout": 60,
                "auth_header": "x-api-key",
                "auth_format": "{api_key}",
            },
        },
        "ollama_mistral_7b.json": {
            "provider": "ollama",
            "model": "mistral:7b",
            "display_name": "Ollama - Mistral 7B",
            "description": "Local Mistral 7B model via Ollama",
            "api_config": {
                "endpoint": "http://localhost:11434/api/chat",
                "default_base_url": "http://localhost:11434",
                "timeout": 120,
            },
        },
    }

    created = []
    skipped = []

    for filename, config_content in examples.items():
        config_file = models_dir / filename
        if config_file.exists():
            skipped.append(filename)
        else:
            config_file.write_text(json.dumps(config_content, indent=2) + "\n", encoding="utf-8")
            created.append(filename)

    return {
        "config_dir": str(config_path),
        "models_dir": str(models_dir),
        "created_count": len(created),
        "created": created,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }
