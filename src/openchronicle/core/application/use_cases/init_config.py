"""Initialize configuration directory with model and core JSON configs."""

from __future__ import annotations

import json
from pathlib import Path

# Core config template with sensible defaults.
# Matches the schema documented in docs/configuration/config_files.md.
_CORE_TEMPLATE: dict = {
    "provider": "stub",
    "default_mode": "fast",
    "model_fast": "gpt-4o-mini",
    "model_quality": "gpt-4o",
    "context_max_tokens": 8192,
    "pools": {
        "fast": "",
        "quality": "",
        "nsfw": "",
    },
    "weights": {
        "ollama": 100,
        "openai": 20,
    },
    "fallback": {
        "max_fallbacks": 1,
        "on_transient": True,
        "on_constraint": True,
        "on_refusal": False,
    },
    "budget": {
        "max_total_tokens": 0,
        "max_llm_calls": 0,
    },
    "retry": {
        "max_retries": 2,
        "max_retry_sleep_ms": 2000,
        "rate_limit_max_wait_ms": 5000,
    },
    "privacy": {
        "mode": "off",
        "external_only": True,
        "categories": ["email", "phone", "ip", "ssn", "cc", "api_key"],
        "redact_style": "mask",
        "log_events": True,
    },
    "telemetry": {
        "enabled": True,
    },
    "router": {
        "rules": {
            "enabled": True,
            "log_reasons": False,
            "nsfw_route_gte": 0.70,
            "nsfw_uncertain_gte": 0.45,
            "persona_uncertain_to_nsfw": True,
        },
        "assist": {
            "enabled": False,
            "backend": "linear",
            "model_path": "",
            "timeout_ms": 50,
        },
    },
}


def execute(config_dir: str) -> dict[str, str | int | list[str]]:
    """
    Initialize configuration directory with example model configs and
    the core JSON config template.

    Creates <config_dir>/models if missing and populates it with minimal
    example v1-style model configs.  Also creates core.json if it doesn't
    exist.

    API keys are resolved at runtime from standard environment variables
    (e.g. OPENAI_API_KEY), so configs don't need embedded keys.

    Args:
        config_dir: Base configuration directory

    Returns:
        Dict with initialization result info
    """
    config_path = Path(config_dir)
    models_dir = config_path / "models"

    # Ensure directories exist
    models_dir.mkdir(parents=True, exist_ok=True)

    # Define minimal example model configs — no embedded API keys.
    # Keys are resolved at runtime: inline -> api_key_env -> standard env var.
    model_examples = {
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
            "limits": {
                "max_tokens": 16384,
                "context_window": 128000,
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
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
            "limits": {
                "max_tokens": 8192,
                "context_window": 200000,
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
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
            "limits": {
                "max_tokens": 4096,
                "context_window": 32000,
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
            },
        },
    }

    created: list[str] = []
    skipped: list[str] = []

    # Write model configs
    for filename, config_content in model_examples.items():
        config_file = models_dir / filename
        if config_file.exists():
            skipped.append(f"models/{filename}")
        else:
            config_file.write_text(json.dumps(config_content, indent=2) + "\n", encoding="utf-8")
            created.append(f"models/{filename}")

    # Write core config template
    core_file = config_path / "core.json"
    if core_file.exists():
        skipped.append("core.json")
    else:
        core_file.write_text(json.dumps(_CORE_TEMPLATE, indent=2) + "\n", encoding="utf-8")
        created.append("core.json")

    return {
        "config_dir": str(config_path),
        "models_dir": str(models_dir),
        "created_count": len(created),
        "created": created,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }
